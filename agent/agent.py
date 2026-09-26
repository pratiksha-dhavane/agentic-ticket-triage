"""
Agent service: consumes tickets from Kafka, runs them through the LangGraph
agent (retrieve -> classify -> branch to draft/escalate), publishes result
to `resolutions`.
"""

import json
import os
from confluent_kafka import Consumer, Producer
from graph import AGENT_GRAPH

BOOTSTRAP_SERVERS = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
INPUT_TOPIC = "tickets"
OUTPUT_TOPIC = "resolutions"

def process_ticket(ticket: dict) -> dict:
    initial_state = {
        "ticket_id": ticket["ticket_id"],
        "customer_id": ticket["customer_id"],
        "text": ticket["text"],
        "matched_topic": None,
        "policy": "",
        "category": "",
        "decision": "",
        "reasoning": "",
        "draft_response": "",
    }
    final_state = AGENT_GRAPH.invoke(initial_state)
    return {
        "ticket_id": final_state["ticket_id"],
        "customer_id": final_state["customer_id"],
        "original_text": final_state["text"],
        "matched_topic": final_state["matched_topic"],
        "category": final_state["category"],
        "decision": final_state["decision"],
        "reasoning": final_state["reasoning"],
        "draft_response": final_state["draft_response"]
    }

def main():
    consumer = Consumer({
        "bootstrap.servers": BOOTSTRAP_SERVERS,
        "group.id": "agent-service",
        "auto.offset.reset": "earliest",
        "enable.auto.commit": False
    })

    consumer.subscribe([INPUT_TOPIC])

    producer = Producer(
        {
            "bootstrap.servers": BOOTSTRAP_SERVERS
        }
    )

    print(f"Agent listening on '{INPUT_TOPIC}'... ")

    try:
        while True:
            msg = consumer.poll(1.0)
            if msg is None:
                continue
            if msg.error():
                print(f"Consumer error: {msg.error()}")
                continue

            ticket = json.loads(msg.value().decode("utf-8"))
            print(f"\nProcessing ticket {ticket['ticket_id'][:8]} from {ticket['customer_id']}")

            result = process_ticket(ticket)
            print(f" -> decision: {result['decision']} ({result['category']})")

            delivery_status = {"success": False, "error": None}

            def _on_delivery(err, _msg, status=delivery_status):
                status["success"] = err is None
                status["error"] = err

            producer.produce(
                OUTPUT_TOPIC,
                key = ticket["customer_id"].encode("utf-8"),
                value = json.dumps(result).encode("utf-8"),
                callback = _on_delivery
            )
            producer.flush()

            if delivery_status["success"]:
                consumer.commit(message=msg)
            else:
                print(f" DELIVERY FAILED ({delivery_status['error']}) - NOT committing offset, will retry ticket on restart")

    except KeyboardInterrupt:
        print("\nShutting down agent...")
    finally:
        consumer.close()
        producer.flush()

if __name__ == "__main__":
    main()
            



