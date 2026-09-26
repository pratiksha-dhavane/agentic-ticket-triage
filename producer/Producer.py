"""
Producer service: generates fake support tickets, publishes to Kafka topic `tickets`.
Keyed by customer_id -> guarantees all tickets from one customer land on same partition.
Uses confluent-kafka (librdkafka wrapper) - standard production client.
"""

import json
import time
import uuid
import random
from confluent_kafka import Producer

BOOTSTRAP_SERVERS = "localhost:9092"
TOPIC = "tickets"

sample_tickets = [
    ("cust1", "Refund not received for order #4521, requested 5 days ago"),
    ("cust2", "Cannot reset password, reset email never arrives"),
    ("cust1", "Follow up on refund #4521 - still nothing"),
    ("cust3", "Order shipped to wrong address, need urgent correction"),
    ("cust4", "How do I change my subscription plan?"),
    ("cust2", "Password reset link expired, please resend")
]

def create_ticket(customer_id: str, text: str) -> dict:
    """Creates a fake support ticket."""
    return {
        "ticket_id": str(uuid.uuid4()),
        "customer_id": customer_id,
        "text": text,
        "created_at": time.time()
    }

def delivery_support(err, msg):
    if err is not None:
        print(f"delivery failed: {err}")
    else:
        print(f"Delivered -> Partition: {msg.partition()} offset {msg.offset()}")

def main():
    producer = Producer({"bootstrap.servers": BOOTSTRAP_SERVERS})
    print(f"Producer connected. Sending to topic '{TOPIC}'...")

    for customer_id, text in sample_tickets:
        ticket = create_ticket(customer_id, text)
        producer.produce(
            TOPIC,
            key=customer_id.encode("utf-8"),
            value=json.dumps(ticket).encode("utf-8"),
            callback=delivery_support
        )
        producer.poll(0) # Trigger delivery callbacks
        print(f"Queued ticket for customer {customer_id}: {ticket['ticket_id'][:8]} -> {text}")
        time.sleep(random.uniform(0.3, 1.0))

    producer.flush()
    print("All tickets sent.")

if __name__ == "__main__":
    main()