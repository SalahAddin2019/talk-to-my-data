import json
import os
import streamlit as st
from dotenv import load_dotenv
from anthropic import Anthropic
from databricks import sql

load_dotenv()

anthropic_client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

with open("docs/table_metadata.json", "r") as f:
    schema = json.load(f)

SQL_SYSTEM_PROMPT = f"""You are a SQL generator for The Gadget Store (TGS).
You have access to this database schema:

{json.dumps(schema, indent=2)}

Rules:
- Output ONLY a single valid Databricks SQL SELECT statement. No explanation, no markdown formatting, no backticks around the query.
- Only ever generate SELECT statements. Never generate INSERT, UPDATE, DELETE, DROP, ALTER, or any other statement type.
- Always exclude order_status IN ('canceled', 'unavailable') for any revenue or product question, unless the user explicitly asks about cancelled orders.
- If the question is genuinely ambiguous (e.g. "sales" could mean revenue or units), make a reasonable default choice (prefer revenue) rather than asking a question, since this step must always return a runnable query.
"""

def clean_sql(raw_text: str) -> str:
    text = raw_text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text
        if text.endswith("```"):
            text = text[:-3]
    return text.strip()

def generate_sql(user_question: str) -> str:
    response = anthropic_client.messages.create(
        model="claude-sonnet-5",
        max_tokens=500,
        system=SQL_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_question}]
    )
    for block in response.content:
        if block.type == "text":
            return clean_sql(block.text.strip())
    return ""

def is_safe_select(sql_text: str) -> bool:
    normalized = sql_text.strip().lower()
    forbidden = ["insert", "update", "delete", "drop", "alter", "create", "truncate", "merge"]
    return normalized.startswith("select") and not any(word in normalized for word in forbidden)

def run_query(sql_text: str):
    connection = sql.connect(
        server_hostname=os.getenv("DATABRICKS_SERVER_HOSTNAME"),
        http_path=os.getenv("DATABRICKS_HTTP_PATH"),
        access_token=os.getenv("DATABRICKS_TOKEN"),
        schema="tgs_talk_to_data"
    )
    cursor = connection.cursor()
    cursor.execute(sql_text)
    columns = [desc[0] for desc in cursor.description]
    result = cursor.fetchall()
    cursor.close()
    connection.close()
    return columns, result

# ---- UI starts here ----
st.set_page_config(page_title="Talk to my data", page_icon="💬")
st.title("💬 Talk to my data")
st.caption("Ask a question about TGS sales data in plain English.")

user_question = st.text_input("Your question", placeholder="e.g. What are the top 5 products by revenue?")

if st.button("Ask") and user_question:
    with st.spinner("Thinking..."):
        generated_sql = generate_sql(user_question)

    with st.expander("See generated SQL"):
        st.code(generated_sql, language="sql")

    if not is_safe_select(generated_sql):
        st.error("Blocked: the generated statement failed the safety check.")
    else:
        with st.spinner("Running query..."):
            columns, result = run_query(generated_sql)
        st.success(f"Found {len(result)} rows")
        st.dataframe([dict(zip(columns, row)) for row in result])