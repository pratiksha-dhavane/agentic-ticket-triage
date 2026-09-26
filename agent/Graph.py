
"""
LangGraph agent: turns classify+decide into a real branching flow.
 
retrieve_context -> classify_and_decide -> [conditional] -> draft_response -> END
                                                          -> escalate       -> END
 
The conditional edge is the actual "agentic" part: the next node depends on
the LLM's own decision, not a fixed sequence.
"""

import json
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, START, END

from Kb import retrieve
from Llm import call_llm

class TicketState(TypedDict):
    ticket_id: str
    customer_id: str
    text: str
    matched_topic: str | None
    policy: str
    category: str
    decision: str
    reasoning: str
    draft_response: str

CLASSIFY_PROMPT = """You are a support ticket triage agent.

Ticket: {ticket_text}

Relevant policy (may be "None" if no match found)
{policy}

Response ONLY with JSON, no markdown fences, no extra text:
{{
    "category": "<short category name>",
    "decision": "resolve" or "escalate",
    "reasoning": "<one sentence>"
}}
"""

DRAFT_PROMPT = """Write a short, emphathetic customer-facing response for this ticket.

Ticket: {ticket_text}
Category: {category}
Policy: {policy}

Response with plain text only, no JSON , 2-3 sentences max.
"""

def parse_json_safe(raw: str) -> dict:
    cleaned = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        return {"category": "unknown", "decision": "escalate", "reasoning": "LLM returned invalid JSON"}
    
# --- Nodes ---

def retrieve_context(state: TicketState) -> TicketState:
    kb_entry = retrieve(state["text"])
    return {
        "matched_topic": kb_entry["topic"] if kb_entry else None,
        "policy": kb_entry["policy"] if kb_entry else "None",
    }

def classify_and_decide(state: TicketState) -> TicketState:
    prompt = CLASSIFY_PROMPT.format(ticket_text=state["text"], policy=state.get("policy", "None"))
    raw = call_llm(prompt)
    result = parse_json_safe(raw)
    return {
        "category": result.get("category", "unknown"),
        "decision": result.get("decision", "escalate"),
        "reasoning": result.get("reasoning", "LLM returned invalid JSON")
    }

def draft_response(state: TicketState) -> TicketState:
    prompt = DRAFT_PROMPT.format(
        ticket_text=state["text"],
        category=state.get("category", "unknown"),
        policy=state.get("policy", "None")
    )
    text = call_llm(prompt)
    return {"draft_response": text.strip()}

def escalate(state: TicketState) -> TicketState:
    # No customer-facing draft for escalation - a human handles the reply
    return {"draft_response": ""}

# --- Conditional Routing ---
def route_after_decision(state: TicketState) -> str:
    return "draft_response" if state.get("decision") == "resolve" else "escalate"

# --- Build graph ---

def build_graph():
    builder = StateGraph(TicketState)
    builder.add_node("retrieve_context", retrieve_context)
    builder.add_node("classify_and_decide", classify_and_decide)
    builder.add_node("draft_response", draft_response)
    builder.add_node("escalate", escalate)

    builder.add_edge(START, "retrieve_context")
    builder.add_edge("retrieve_context", "classify_and_decide")
    builder.add_conditional_edges(
        "classify_and_decide",
        route_after_decision,
        ["draft_response", "escalate"]
        )
    builder.add_edge("draft_response", END)
    builder.add_edge("escalate", END)

    return builder.compile()

AGENT_GRAPH = build_graph()


