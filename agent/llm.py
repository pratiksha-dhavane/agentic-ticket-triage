"""
LLM client with 3-tier fallback chain: gemini-flash -> gemini-flash-lite -> gemma.
Shared by every node in graph.py that needs a model call.
"""

import os
from dotenv import load_dotenv
from google import genai

MODEL_CHAIN = [
    "gemini-flash-latest",        # primary 
    "gemini-flash-lite-latest",  # 2nd: cheaper, faster
    "gemma-4-26b-a4b-it"         # 3rd: open-weight, most likely to survive a Google-wide outage or quota exhaustion
]

load_dotenv()

client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

def call_llm(prompt: str) -> str: 
    last_error = None
    for i, model_name in enumerate(MODEL_CHAIN):
        try:
            resp = client.models.generate_content(model=model_name, contents=prompt)
            if i > 0:
                print(f" Used fallback model tier {i} : {model_name} ")

            return resp.text
        except Exception as e:
            # TODO: narrow to actual quota/rate-limit exception type once observed
            last_error = e
            print(f" {model_name} failed {e}, trying next in chain... ")

    raise RuntimeError(f"All LLM model tiers failed: {last_error}")