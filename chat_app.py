import json
import os
import streamlit as st
from dotenv import load_dotenv
from anthropic import Anthropic
from databricks import sql

load_dotenv()


def get_secret(name: str) -> str:
    """Reads from Streamlit Cloud's secrets manager if available, otherwise
    falls back to a local .env file - so this same file works both locally
    and once deployed."""
    if name in st.secrets:
        return st.secrets[name]
    return os.getenv(name)


anthropic_client = Anthropic(api_key=get_secret("ANTHROPIC_API_KEY"))

with open("docs/table_metadata.json", "r") as f:
    schema = json.load(f)

# ---- Simple username/password gate ----


def check_login():
    if st.session_state.get("authenticated"):
        return True

    st.title("\U0001F4AC Talk to my data")
    st.caption("Please log in to continue.")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    if st.button("Log in"):
        if username == get_secret("APP_USERNAME") and password == get_secret("APP_PASSWORD"):
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("Incorrect username or password.")
    return False


if not check_login():
    st.stop()

# ---- Stage 1: classify the LATEST message into one of three categories ----

CLASSIFY_SYSTEM_PROMPT = f"""You are a data assistant for The Gadget Store (TGS), having an
ongoing conversation with a user. You have access to this database schema:

{json.dumps(schema, indent=2)}

Look at the full conversation so far for context - earlier questions, clarifying
questions you asked, and answers the user gave all matter. For example, if you
previously offered a choice between two options and the user's latest message picks
one (or says "the other one"), that is now CLEAR, not ambiguous.

Classify the user's LATEST message into exactly ONE of these three categories:

1. CHAT - the message is not a data question at all: greetings, thanks, small talk,
   or a meta question about what you can do (e.g. "thank you", "hello", "what can you
   help with?", "nice, thanks!"). Respond with EXACTLY this format:
   CHAT: <a short, natural reply - no SQL, no data>

2. CLARIFY - it IS a data question, but still ambiguous even with the conversation as
   context. Respond with EXACTLY this format:
   CLARIFY: <your specific clarifying question>

3. CLEAR - it IS a data question, and clear enough to query unambiguously using the
   conversation for context. Respond with EXACTLY:
   CLEAR

Respond with only one of the three formats above, nothing else. Do not generate SQL here."""


def classify_message(history: list) -> str:
    response = anthropic_client.messages.create(
        model="claude-sonnet-5",
        max_tokens=200,
        system=CLASSIFY_SYSTEM_PROMPT,
        messages=history,
    )
    for block in response.content:
        if block.type == "text":
            return block.text.strip()
    return "CLEAR"

# ---- Stage 2: generate real SQL, using the full conversation as context ----


SQL_SYSTEM_PROMPT = f"""You are a SQL generator for The Gadget Store (TGS), having an
ongoing conversation with a user. You have access to this database schema:

{json.dumps(schema, indent=2)}

Look at the full conversation so far to understand what the user's latest message
actually means - earlier questions, clarifications, and your own prior answers all
provide context.

Rules:
- Output ONLY a single valid Databricks SQL SELECT statement answering the user's
  latest message, using the conversation for context. No explanation, no markdown
  formatting, no backticks around the query.
- Only ever generate SELECT statements. Never generate INSERT, UPDATE, DELETE, DROP,
  ALTER, or any other statement type.
- Always exclude order_status IN ('canceled', 'unavailable') for any revenue or
  product question, unless the user explicitly asks about cancelled orders.
"""


def clean_sql(raw_text: str) -> str:
    text = raw_text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text
        if text.endswith("```"):
            text = text[:-3]
    return text.strip()


def generate_sql(history: list) -> str:
    response = anthropic_client.messages.create(
        model="claude-sonnet-5",
        max_tokens=500,
        system=SQL_SYSTEM_PROMPT,
        messages=history,
    )
    for block in response.content:
        if block.type == "text":
            return clean_sql(block.text.strip())
    return ""


def is_safe_select(sql_text: str) -> bool:
    normalized = sql_text.strip().lower()
    forbidden = ["insert", "update", "delete", "drop",
                 "alter", "create", "truncate", "merge"]
    return normalized.startswith("select") and not any(word in normalized for word in forbidden)


def run_query(sql_text: str):
    with sql.connect(
        server_hostname=get_secret("DATABRICKS_SERVER_HOSTNAME"),
        http_path=get_secret("DATABRICKS_HTTP_PATH"),
        access_token=get_secret("DATABRICKS_TOKEN"),
        schema="tgs_talk_to_data",
    ) as connection:
        with connection.cursor() as cursor:
            cursor.execute(sql_text)
            columns = [desc[0] for desc in cursor.description]
            result = cursor.fetchall()
    return columns, result


def table_preview_text(columns, rows, max_rows=8):
    preview_rows = rows[:max_rows]
    lines = [", ".join(columns)]
    for row in preview_rows:
        lines.append(", ".join(str(v) for v in row))
    if len(rows) > max_rows:
        lines.append(f"... ({len(rows) - max_rows} more rows)")
    return "\n".join(lines)


def answer_question(history: list) -> dict:
    generated_sql = generate_sql(history)

    if not is_safe_select(generated_sql):
        return {
            "role": "assistant",
            "text": "I generated a query for that, but it failed my safety check, so I won't run it. Could you rephrase the question?",
            "sql": generated_sql,
            "history_text": "I generated a query but it failed the safety check and was not run.",
        }

    columns, result = run_query(generated_sql)

    if not result:
        return {
            "role": "assistant",
            "text": "That ran successfully, but returned no rows.",
            "sql": generated_sql,
            "history_text": "The query ran successfully but returned no rows.",
        }

    preview = table_preview_text(columns, result)
    return {
        "role": "assistant",
        "text": f"Found {len(result)} rows.",
        "sql": generated_sql,
        "table": {"columns": columns, "rows": result},
        "history_text": f"Found {len(result)} rows. SQL used: {generated_sql}\nResults:\n{preview}",
    }


# ---- Conversation state ----
if "messages" not in st.session_state:
    st.session_state.messages = []
if "api_history" not in st.session_state:
    st.session_state.api_history = []

# ---- Page setup ----
st.set_page_config(page_title="Talk to my data", page_icon="\U0001F4AC")

with st.sidebar:
    st.header("\U0001F4AC Talk to my data")
    if st.button("+ New chat", use_container_width=True):
        st.session_state.messages = []
        st.session_state.api_history = []
        st.rerun()
    if st.button("Log out", use_container_width=True):
        st.session_state.authenticated = False
        st.rerun()

st.title("\U0001F4AC Talk to my data")
st.caption("Ask a question about TGS sales data in plain English. This remembers the conversation, so follow-ups work.")

# ---- Render full conversation history ----
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["text"])
        if msg.get("sql"):
            with st.expander("See generated SQL"):
                st.code(msg["sql"], language="sql")
        if msg.get("table"):
            rows = [dict(zip(msg["table"]["columns"], row))
                    for row in msg["table"]["rows"]]
            st.dataframe(rows)

# ---- Chat input ----
user_input = st.chat_input("Ask a question...")

if user_input:
    st.session_state.messages.append({"role": "user", "text": user_input})
    st.session_state.api_history.append(
        {"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            classification = classify_message(st.session_state.api_history)

        if classification.startswith("CHAT:"):
            chat_reply = classification.replace("CHAT:", "", 1).strip()
            st.markdown(chat_reply)
            st.session_state.messages.append(
                {"role": "assistant", "text": chat_reply})
            st.session_state.api_history.append(
                {"role": "assistant", "content": chat_reply})

        elif classification.startswith("CLARIFY:"):
            clarifying_question = classification.replace(
                "CLARIFY:", "", 1).strip()
            st.markdown(clarifying_question)
            st.session_state.messages.append(
                {"role": "assistant", "text": clarifying_question})
            st.session_state.api_history.append(
                {"role": "assistant", "content": clarifying_question})

        else:  # CLEAR
            with st.spinner("Generating SQL..."):
                reply = answer_question(st.session_state.api_history)

            st.markdown(reply["text"])
            if reply.get("sql"):
                with st.expander("See generated SQL"):
                    st.code(reply["sql"], language="sql")
            if reply.get("table"):
                rows = [dict(zip(reply["table"]["columns"], row))
                        for row in reply["table"]["rows"]]
                st.dataframe(rows)

            st.session_state.messages.append(reply)
            st.session_state.api_history.append(
                {"role": "assistant", "content": reply["history_text"]})
