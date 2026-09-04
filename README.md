# Talk-to-my-data

**Natural language business intelligence for The Gadget Store (TGS)** — ask a plain-English question about sales data and get a real, correct answer, computed live from the database. No SQL, no waiting on an analyst.

Built as Case #1 of the Talk-to-my-data engagement (Artefact).

**Status: Complete and live.** Two working deployments, both linked below.

---

## Business context

TGS has a large amount of sales data but no self-service way for non-technical staff to query it — every question, however simple, currently requires an analyst. This project delivers a working proof of concept for a chatbot that closes that gap: ask "what are our top 5 products by revenue?" in plain English, and get the real answer back in seconds.

## Results snapshot

| | |
|---|---|
| **Dataset** | Olist Brazilian E-Commerce — real, 9 linked tables, ~100,000 orders |
| **KPI 1 — Revenue Trend** | Validated: real growth from R$207.86 (first partial month) to over R$1,000,000/month within ~1 year |
| **KPI 2 — Top-Performing Products** | Validated against an independent manual calculation |
| **Ambiguity handling** | Correctly distinguishes casual chat, ambiguous questions, and clear questions — asking for clarification only when genuinely needed |
| **Safety** | Hard guardrail: only read-only `SELECT` statements ever reach the database |
| **Deployment** | Two independent live environments (see below) |

## Live demos

| Deployment | Audience | Access |
|---|---|---|
| **Databricks Apps** | Team & mentors | Requires a Microsoft Entra ID guest invite |
| **Streamlit Community Cloud** | External sharing (e.g. project owner) | Direct link + username/password |

## How it works

```
User question
     │
     ▼
Claude Sonnet 5 — classifies the message:
  • casual chat            → answered directly, no query run
  • ambiguous data question → asks a clarifying question
  • clear data question     → proceeds
     │
     ▼
Claude Sonnet 5 — generates SQL (schema-aware, using table_metadata.json)
     │
     ▼
Safety guardrail — blocks anything that isn't a plain SELECT
     │
     ▼
Databricks SQL Warehouse — executes the query against real data
     │
     ▼
Streamlit chat UI — shows the answer, the SQL used, and the result table
```

The system remembers the full conversation, so natural follow-ups like "what about the other option?" resolve correctly using earlier context — not treated as a brand-new, unrelated question.

## Tech stack

- **Data platform:** Azure Databricks (Unity Catalog, Delta Lake, SQL Warehouse)
- **Dataset:** [Olist Brazilian E-Commerce](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce)
- **AI:** Anthropic Claude Sonnet 5
- **Interface:** Streamlit
- **Deployment:** Databricks Apps + Streamlit Community Cloud

## Repository structure

```
talk-to-my-data/
├── chat_app.py                 # Main app (Streamlit Community Cloud entrypoint)
├── requirements.txt             # Python dependencies for chat_app.py
├── app_deploy/                   # Minimal deployment package for Databricks Apps
│   ├── app.py
│   ├── app.yaml
│   ├── requirements.txt
│   └── docs/table_metadata.json
├── docs/
│   ├── 00_project_log.md         # Full running build log — every decision, every bug, in order
│   ├── 00_setup_guide.md         # Databricks data-loading setup
│   ├── kpi_queries_databricks.sql
│   ├── load_data_databricks.py
│   └── table_metadata.json       # Schema documentation fed to the AI
└── notebooks/
    └── 01_load_data.ipynb        # Loads the 9 CSVs into Delta tables
```

## KPI definitions

**Revenue Trend** — `SUM(order_items.price)`, monthly, excluding cancelled/unavailable orders.

**Top-Performing Products** — products ranked by revenue, with units sold as a secondary cut.

Both were independently validated against manual calculations before being trusted in any demo — not just "the query ran without errors."

## Local setup

```bash
python -m venv venv
venv\Scripts\activate          # Windows
pip install -r requirements.txt
```

Create a `.env` file in the project root (never committed — see `.gitignore`):
```
ANTHROPIC_API_KEY=sk-ant-...
DATABRICKS_SERVER_HOSTNAME=adb-...azuredatabricks.net
DATABRICKS_HTTP_PATH=/sql/1.0/warehouses/...
DATABRICKS_TOKEN=dapi...
```

Run it:
```bash
streamlit run chat_app.py
```

## Known limitations

- Product names display as raw IDs — the Olist dataset only has categories, not names (TGS's own catalog would resolve this automatically in a real rollout)
- `customer_state` stands in for TGS's store/country dimension, since Olist has no physical stores
- Covers 2 of TGS's 3 stated business goals (sales trends, product performance); customer retention is a recommended next phase, not built in this PoC
- The Streamlit Cloud password gate is basic access control, appropriate for controlled sharing — not enterprise-grade authentication

## Full documentation

For the complete, step-by-step build history — every decision, every real bug encountered during development and deployment, and exactly how each was diagnosed and fixed — see [`docs/00_project_log.md`](docs/00_project_log.md).

---

*Part of the Talk-to-my-data engagement for The Gadget Store (TGS), delivered via Artefact.*
