"""
Knowledge base with real semantic retrieval via Gemini embeddings.
Embeddings computed once at startup (KB is tiny), cosine similarity via numpy
at query time. No local model, no torch - just API calls + basic math.
"""

import os
import numpy as np
from dotenv import load_dotenv
from google import genai

EMBED_MODEL = "gemini-embedding-001"
SIMILARITY_THRESHOLD = 0.6

load_dotenv()

client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

KB = [
    {
        "topic": "refund",
        "policy": "Refunds are processed within 5-7 business days after return is received. "
                   "If more than 7 business days have passed, escalate to billing team.",
    },
    {
        "topic": "password_reset",
        "policy": "Password reset emails expire after 30 minutes. If customer says the link "
                   "expired or never arrived, auto-resend is allowed without escalation.",
    },
    {
        "topic": "shipping",
        "policy": "Wrong-address shipments cannot be auto-corrected once dispatched. "
                   "Always escalate to logistics team.",
    },
    {
        "topic": "subscription",
        "policy": "Plan changes take effect at the next billing cycle and can be self-served "
                   "via account settings. No escalation needed for standard plan changes.",
    },
]

def embed(text: str) -> np.ndarray:
    result = client.models.embed_content(model=EMBED_MODEL, contents=text)
    return np.array(result.embeddings[0].values)

def cosine_sim(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))

# Pre-compute KB embeddings once at import time - KB is small, cheap , done once.
print("Embedding knowledge base...")
for entry in KB:
    entry["embedding"] = embed(entry["policy"])
print(f"KB ready: {len(KB)} entries embedded.")

def retrieve(ticket_text: str) -> dict|None:
    query_vec = embed(ticket_text)
    best_entry, best_score = None, -1.0

    for entry in KB:
        score = cosine_sim(query_vec, entry["embedding"])
        if score > best_score:
            best_entry, best_score = entry, score

    if best_score >= SIMILARITY_THRESHOLD:
        print(F" RAG match: '{best_entry['topic']}' (similarity: {best_score:.3f}) ")
        return best_entry

    print(f"  RAG match: none (best was '{best_entry['topic']}' at {best_score:.3f}) ")
    return None