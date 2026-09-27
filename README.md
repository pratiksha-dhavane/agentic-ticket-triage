# Agentic Ticket Triage

An event-driven support ticket triage pipeline: Kafka + a LangGraph agent (RAG + LLM
decisioning) + Kubernetes. Built as a hands-on learning project to get real experience
with Kafka, agentic AI orchestration, Docker, and Kubernetes end to end.

## What it does

1. A **producer** service publishes simulated support tickets to a Kafka topic (`tickets`),
   keyed by `customer_id` so all of one customer's tickets land on the same partition (ordering).
2. An **agent** service consumes tickets, runs them through a LangGraph pipeline:
   - Retrieves relevant policy context via **real embedding-based RAG** (Gemini embeddings +
     cosine similarity over a small in-memory knowledge base)
   - Classifies the ticket and decides **resolve** vs **escalate** via an LLM call
   - Branches (a real conditional edge, not just sequential steps): resolved tickets get a
     drafted customer-facing response; escalated tickets are flagged for a human, no draft
3. The agent publishes the result to a second Kafka topic (`resolutions`).

## Why Kafka (not just a direct API call)

Decouples ticket ingestion from processing — the agent can crash, restart, or be scaled to
multiple replicas without losing tickets, since they sit in Kafka until consumed. Also
absorbs bursty ticket volume without back-pressuring whatever produces the tickets upstream.

## Architecture

```
producer --(tickets topic, keyed by customer_id)--> agent --(resolutions topic)--> [downstream]
                                                       |
                                                       +--> RAG lookup (Gemini embeddings)
                                                       +--> LLM call (3-tier fallback chain)
```

**LLM fallback chain:** `gemini-flash-latest` → `gemini-flash-lite-latest` → `gemma-4-26b-a4b-it`
(all via the Gemini API). Any failure (quota, rate limit, outage) falls through to the next
tier automatically — verified under real quota exhaustion during development, not just
simulated.

**Delivery guarantee:** the agent disables Kafka auto-commit and only commits its consumer
offset after confirming the `resolutions` message was actually delivered — avoids silently
losing a ticket's result if the process crashes mid-processing.

## Project structure

```
producer/       # Kafka producer - generates and sends tickets
agent/
  agent.py      # Kafka consumer/producer plumbing only
  graph.py      # LangGraph agent: nodes + conditional routing
  llm.py        # 3-tier LLM fallback chain
  kb.py         # RAG knowledge base + embedding-based retrieval
docker-compose.yml
k8s/            # Kubernetes manifests (Deployments, Service, Job)
```

## Running locally (Docker Compose)

```bash
export GEMINI_API_KEY="your-key"
docker compose up --build
```

## Running on Kubernetes

Images are prebuilt and pushed to Docker Hub (multi-arch: amd64 + arm64) rather than built
in-cluster.

```bash
kubectl create secret generic gemini-secret --from-literal=api-key=YOUR_KEY
kubectl apply -f k8s/kafka.yaml
# wait for the kafka pod to be Running
kubectl apply -f k8s/agent.yaml
kubectl apply -f k8s/producer-job.yaml
```

Note: `producer` is a Kubernetes **Job** (runs once to completion), not a Deployment —
a Deployment would restart and re-send tickets in a loop once the container exits.

## Known limitations / possible next steps

- RAG knowledge base is a small in-memory list (4 entries) — fine at this scale; would move
  to a proper vector DB (e.g. Chroma) once the KB grows past what fits in memory.
- No stateful context across tickets — a customer's second related ticket is processed
  independently, with no memory of the first.
- LLM fallback chain treats all failures identically; a more refined version would
  distinguish per-minute rate limits (retry shortly) from daily quota exhaustion (stay on
  fallback for longer) instead of downgrading uniformly.