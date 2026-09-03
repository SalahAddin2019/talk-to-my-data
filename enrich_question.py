import json
import os
from dotenv import load_dotenv
from anthropic import Anthropic

load_dotenv()
client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

# Load the schema documentation we wrote back in Step 2
with open("docs/table_metadata.json", "r") as f:
    schema = json.load(f)

SYSTEM_PROMPT = f"""You are a data assistant for The Gadget Store (TGS).
You have access to the following database schema:

{json.dumps(schema, indent=2)}

Your job: read the user's question and do ONE of two things:
1. If the question is ambiguous (for example, "sales" could mean revenue
   or units sold), ask a short, specific clarifying question instead of
   guessing.
2. If the question is clear, respond with a short plan describing:
   - which tables are needed
   - which columns/joins are involved
   - any filters that should apply (e.g. excluding cancelled orders)

Do not write SQL yet. Just explain your understanding of the question.
"""

def enrich_question(user_question: str) -> str:
    response = client.messages.create(
        model="claude-sonnet-5",
        max_tokens=300,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_question}]
    )
    # Sonnet 5 can return multiple content blocks (e.g. thinking + text).
    # We want specifically the text block, wherever it appears.
    for block in response.content:
        if block.type == "text":
            return block.text
    return "(No text response received)"

if __name__ == "__main__":
    test_question = "What are the top 5 products by revenue?"
    print(enrich_question(test_question))