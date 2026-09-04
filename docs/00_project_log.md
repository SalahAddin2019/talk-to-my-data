# Talk-to-my-data — Running Project Log

Case #1: Building a real-world Generative AI application for The Gadget Store (TGS) sales department.
This document is updated after every step. It's meant to double as the backbone of the dry-run and final presentation.

---

## Step 1 — Dataset Selection & KPI Definition

**Status:** Complete
**Decision owner:** Team (Claude-assisted)

### 1.1 Dataset chosen: Olist Brazilian E-Commerce Public Dataset

Real, anonymised marketplace data: ~100,000 orders placed between 2016–2018, across multiple Brazilian marketplaces. Chosen over UCI Online Retail II and Tableau Superstore because it is **genuinely multi-table with real foreign-key relationships** — which is what actually exercises the hard part of the brief ("enhance the user's question with knowledge about the database tables").

**Stated assumption (to say out loud in the pitch):** Olist is a single-country (Brazil) online marketplace with no physical stores. TGS is multi-country with 1,000+ physical stores. For this PoC we substitute `customer_state` (27 Brazilian states) as the location/"store" dimension the brief asks for ("over time, store, country, etc."). This is disclosed as a modelling choice, not hidden — the retrieval/enrichment approach transfers directly to TGS's real schema once they provide store-level data.

### 1.2 Schema — 9 source tables

| Table | Grain | Key columns |
|---|---|---|
| `olist_orders_dataset` | 1 row per order | `order_id` (PK), `customer_id` (FK), `order_status`, `order_purchase_timestamp`, `order_delivered_customer_date`, `order_estimated_delivery_date` |
| `olist_customers_dataset` | 1 row per customer | `customer_id` (PK), `customer_unique_id`, `customer_city`, `customer_state` |
| `olist_order_items_dataset` | 1 row per line item | `order_id` (FK), `order_item_id`, `product_id` (FK), `seller_id` (FK), `price`, `freight_value` |
| `olist_products_dataset` | 1 row per product | `product_id` (PK), `product_category_name`, dimensions/weight |
| `product_category_name_translation` | 1 row per category | `product_category_name` (PK), `product_category_name_english` |
| `olist_order_payments_dataset` | 1+ rows per order | `order_id` (FK), `payment_sequential`, `payment_type`, `payment_installments`, `payment_value` |
| `olist_order_reviews_dataset` | 1 row per review | `order_id` (FK), `review_score`, `review_comment_message` |
| `olist_sellers_dataset` | 1 row per seller | `seller_id` (PK), `seller_city`, `seller_state` |
| `olist_geolocation_dataset` | zip-prefix lookup | `geolocation_zip_code_prefix`, `lat`, `lng` |

**Join path (orders as anchor):**
`orders → customers (customer_id)` → `order_items (order_id)` → `products (product_id)` → `category_translation (product_category_name)` → `order_payments (order_id)` → `order_reviews (order_id)` → `sellers (seller_id)`

This join path *is* the "table knowledge" the LLM needs to be given in Step 3 (schema enrichment) — we'll turn this table into structured metadata (table name, columns, join keys, one-line description) that gets injected into the prompt.

**Confirmed decision:** Team reviewed whether to add a 3rd KPI (customer retention/CLV) to cover all three of the client's stated business goals, and decided to stay with the 2 locked KPIs below — satisfies the brief's "at least 2 KPIs" requirement. Customer retention/CLV noted as a "next phase" talking point for the final pitch's rollout advice, not built in this PoC.

### 1.3 KPI definitions (locked in)

**KPI 1 — Revenue Trend**
- Definition: total revenue per period (month), using product `price` only (excludes freight — freight is a cost passed to the customer, not TGS revenue)
- Formula: `SUM(order_items.price)` grouped by `DATE_TRUNC(orders.order_purchase_timestamp, MONTH)`
- Only include orders with `order_status` not in `('canceled', 'unavailable')`
- Supports slicing by: month, `customer_state`, `product_category_name_english`

**KPI 2 — Top-Performing Products**
- Definition: products ranked by total revenue over a selectable time window
- Formula: `SUM(order_items.price)` grouped by `product_id` (or `product_category_name_english` for category-level rollups), ordered descending, top N
- Same order-status filter as KPI 1
- Secondary cut available: top products by *units sold* (`COUNT(order_items.order_item_id)`) — worth exposing since "top performing" can mean revenue or volume, and the demo video pattern (clarify before answering) applies here too

### 1.4 Known data-quality notes (from prior public EDA of this dataset, to handle in Step 2 cleaning)
- Some `product_category_name` values have no English translation (~2% of rows) — need a fallback ("Uncategorized") rather than dropping, since dropping loses revenue from those SKUs
- `order_delivered_customer_date` is null for undelivered/cancelled orders — irrelevant to our two KPIs, no action needed yet
- A single order can have multiple `payment_sequential` rows (installments) — must not double-count revenue; revenue lives in `order_items.price`, not `payments`, so this isn't a risk for KPI 1/2, but flagged for anyone touching payments data later

### 1.5 Access note
Downloading requires a Kaggle account (`kaggle.com/datasets/olistbr/brazilian-ecommerce`) — Data Engineer to pull the 9 CSVs and get them into the shared cloud storage / BigQuery in Step 2.

---

## Step 2 — Schema Setup & Data Load

**Status:** Complete — **superseded and rebuilt for Databricks/Azure** (see 2.4 below). Kept the original BigQuery version below for reference only; the team is not using GCP.

### 2.1 Deliverables produced
- `ddl.sql` — CREATE SCHEMA + CREATE TABLE statements for all 9 tables, with join relationships documented as comments
- `load_data.sh` — `bq load` script to load the 9 downloaded CSVs into BigQuery in one pass
- `table_metadata.json` — **this is the key artifact for Step 3.** A machine-readable description of every table, its columns, join paths, and business-term definitions (e.g. what "revenue" means, that "sales" is ambiguous and must be clarified). This gets injected into the LLM's prompt so it can enrich user questions with real schema knowledge — directly satisfying the client's requirement to "enhance the user's question with knowledge about the database tables."
- `kpi_queries.sql` — hand-written, validated SQL for both locked KPIs (Revenue Trend, Top-Performing Products), plus location-sliced variants using `customer_state` as the store/country proxy

### 2.2 Action required from the Data Engineer (cannot be done in this environment — no live GCP/internet access here)
1. Create a GCP project and enable BigQuery
2. Download the 9 CSVs from Kaggle (`olistbr/brazilian-ecommerce`)
3. Run `ddl.sql` (replace `PROJECT_ID` placeholder)
4. Run `PROJECT_ID=<your-project> ./load_data.sh /path/to/csvs`
5. Sanity-check row counts, then run `kpi_queries.sql` and manually verify a couple of numbers against a pandas groupby — this is the KPI-correctness validation the Data Engineer owns per the team plan

### 2.3 Notes / decisions made
- Declared `NOT IN ('canceled', 'unavailable')` as the standard order-status filter for both KPIs — this needs to be applied consistently everywhere revenue is calculated, including later in the LLM-generated SQL, or the numbers won't match the validated baseline
- `order_payments.payment_value` is explicitly called out in the metadata as **not** the source of truth for revenue (it can double-count across installments) — `order_items.price` is

### 2.4 Databricks/Azure version (current — use this one)

**Why the switch:** team confirmed the actual stack is Databricks + Azure, not GCP/BigQuery. Dataset, schema, join paths, and KPI logic are all unchanged — only the storage/compute layer changed.

**Deliverables:**
- `00_setup_guide.md` — how to get the 9 CSVs into Databricks (Unity Catalog Volume upload for a fast start, or Azure Blob/ADLS + service principal for a more "production" story later)
- `load_data_databricks.py` — PySpark notebook that reads each CSV with an explicit typed schema and writes it as a managed Delta table under the `tgs_talk_to_data` schema
- `kpi_queries_databricks.sql` — same two KPIs, adjusted to Databricks SQL syntax (`date_trunc('MONTH', ...)`, no project-id prefix, just `schema.table`)
- `table_metadata.json` — unchanged in substance (it was always platform-agnostic), just reworded to reference Databricks/Delta instead of BigQuery

**Action required from the Data Engineer:**
1. Get an Azure Databricks workspace running (Premium tier if Unity Catalog is available)
2. Download the 9 CSVs from Kaggle, upload to a Unity Catalog Volume (fastest path — see setup guide for the Azure Blob alternative)
3. Run `load_data_databricks.py` as a notebook, updating `BASE_PATH` to match
4. Run `kpi_queries_databricks.sql` and manually validate a couple of numbers against a pandas baseline (KPI-correctness check, same as before)

---

## Next: Step 3 — Schema-aware question enrichment (AI/LLM Engineer)
Build the prompt that takes `table_metadata.json` + the user's question and produces either (a) a clarifying question, or (b) an enriched, schema-grounded description of what to query — before any SQL is generated.

**Status: Core logic built and validated with Claude Sonnet 5.**

### 3.1 What was built
`enrich_question.py` — loads `table_metadata.json`, builds a system prompt instructing
Claude to either ask a clarifying question (if the request is ambiguous) or produce a
structured plan (tables/joins/filters) if it's clear. Deliberately does NOT generate
SQL yet — that's Step 4, kept as a separate concern so each piece can be tested in
isolation.

### 3.2 Validation — two test cases, opposite expected behaviors

**Test 1 (ambiguous): "What were our total sales last month?"**
Result: Correctly refused to guess. Asked to clarify (a) revenue vs. units sold for
"sales", and (b) which "last month" reference point, given this is historical data
rather than live data. Matches the clarification pattern shown in the client's own
demo video.

**Test 2 (unambiguous): "What are the top 5 products by revenue?"**
Result: Correctly proceeded without asking anything. Produced a specific, accurate plan:
- Tables: orders, order_items, products (+ category_translation as optional)
- Join path: orders -> order_items (order_id) -> products (product_id)
- Filter: excludes order_status IN ('canceled', 'unavailable') — applied automatically,
  matching our documented business rule, without being told to in the question
- Calculation: SUM(order_items.price) grouped by product_id, correctly matching our
  KPI 2 definition from Step 1

This is real evidence the system distinguishes ambiguous vs. clear questions rather
than defaulting to one behavior — a stronger result than the minimum bar.

### 3.3 Bug fixed along the way (worth documenting for the final pitch)
Claude Sonnet 5 can return multiple content blocks per response (e.g. a "thinking"
block plus a "text" block). Original code assumed a single block at index [0], which
crashed on `AttributeError: 'ThinkingBlock' object has no attribute 'text'` the first
time Sonnet actually used extended thinking. Fixed by looping through all returned
blocks and extracting specifically the one with `type == "text"`.

### 3.4 Provider note
Using Anthropic (Claude Sonnet 5) directly rather than Azure OpenAI. Azure OpenAI
requires a manual approval process (7-10 days, often rejects student/trial subscriptions)
which was incompatible with the project timeline. Submitted the Azure OpenAI request
in parallel in case it's approved later — swapping providers is a small, isolated
change since all AI calls are contained in one function.

---

## Next: Step 4 — SQL generation & execution (Backend Engineer)
Take the enriched plan from Step 3 and turn it into real, safely-executed SQL against
the Databricks tables — this is where a query actually runs and returns a result table.

**Status: COMPLETE. Full end-to-end pipeline working: question -> SQL -> safe execution -> real result.**

### 4.1 What was built
`ask_question.py` — the full pipeline in one script:
- `generate_sql()` — sends the question + schema metadata to Claude Sonnet 5, gets back a real SQL SELECT statement (evolved from Step 3's "plan only" behavior)
- `clean_sql()` — strips markdown code-fence formatting (```sql ... ```) that Claude sometimes wraps around generated queries
- `is_safe_select()` — guardrail: only allows statements starting with SELECT, blocks INSERT/UPDATE/DELETE/DROP/ALTER/CREATE/TRUNCATE/MERGE outright
- `run_query()` — executes against the real Databricks SQL Warehouse using the databricks-sql-connector, with `schema="tgs_talk_to_data"` set explicitly on the connection

### 4.2 Two real bugs hit and fixed during testing (good material for the final pitch)
1. **Markdown-wrapped SQL**: Claude sometimes returns SQL wrapped in ```sql fences (chat-style
   formatting). The safety check correctly rejected it as unrecognized rather than
   silently failing — proving the guardrail works — but it also blocked genuinely valid
   SQL. Fixed with `clean_sql()`, which strips the fences before the safety check runs.
2. **Schema not found**: Claude generated `FROM orders` (no schema prefix), which is
   reasonable on its own, but the Databricks connection defaulted to schema `default`
   (empty) instead of our real schema `tgs_talk_to_data`. Fixed by explicitly passing
   `schema="tgs_talk_to_data"` when opening the connection, so unqualified table names
   resolve correctly.

### 4.3 Validated end-to-end result
Question: "What are the top 5 products by revenue?"
- Generated SQL correctly joined order_items -> orders, filtered out cancelled/unavailable
  orders (matching our documented business rule, unprompted), grouped and sorted correctly
- Query executed successfully against the real 112,650-row order_items table
- Returned 5 real products with real revenue figures (highest: R$63,885.00)

### 4.4 Infrastructure added this step
- Databricks SQL Warehouse (`talk-to-my-data-sql`, serverless, 2X-Small) created to allow
  external connections from local Python code (separate from the notebook compute used
  in Step 2)
- Databricks personal access token generated, scoped narrowly to `sql` only (not full
  account access)
- New `.env` entries: DATABRICKS_SERVER_HOSTNAME, DATABRICKS_HTTP_PATH, DATABRICKS_TOKEN
  (all confirmed protected by .gitignore, same as the Anthropic key)

---

## Next: Step 5 — Chat interface (Frontend/UX Engineer)
Wrap `ask_question.py`'s pipeline in a simple chat-style UI so non-technical users can
actually interact with it, matching the style of the demo video shown to TGS.

**Status: COMPLETE. Working Streamlit chat app.**

### 5.1 What was built
`chat_app.py` — a Streamlit web app wrapping the exact same pipeline validated in Step 4
(generate_sql -> clean_sql -> is_safe_select -> run_query), with no changes to the core
logic. UI additions: a text input for the question, an "Ask" button, an expandable
"See generated SQL" section for transparency, and a results table.

### 5.2 Validated
Ran locally via `streamlit run chat_app.py`. Tested with "what are the top 5 products by
revenue?" — same correct results as the terminal version in Step 4, now presented as an
actual usable web app rather than a script. This is the form factor a non-technical TGS
sales user could realistically interact with, and matches the chat-style demo video shown
to the client.

### 5.3 Known limitation to mention in the pitch
Product IDs display as raw hash strings rather than human-readable names, since the
Olist dataset doesn't include product names (only categories). A real TGS rollout would
show actual product names, since their catalog data would include them.

---

## Next: Step 6 — Deployment (DevOps Engineer)
Currently the app only runs on localhost (one person's laptop). Deploy it to Azure so
it's reachable as an actual URL, not just "works on my machine."

**Status: COMPLETE. Live at a public Databricks Apps URL.**

### 6.1 Platform decision
Chose Databricks Apps over Azure App Service — keeps everything in one platform,
avoids standing up separate Azure infrastructure, and is explicitly listed as an
acceptable deployment target in the client's own brief.

### 6.2 What was built
- `app_deploy/` — a minimal, clean deployment package containing only what the running
  app needs: `app.py`, `app.yaml`, `requirements.txt`, `docs/table_metadata.json`
  (deliberately excludes docs/notebooks meant for humans, not the app)
- Databricks CLI installed and authenticated (needed broader token scopes than the
  SQL-only token from Step 4: apps + secrets + workspace)
- A dedicated secret scope (`talk-to-my-data-secrets`) storing the Anthropic API key,
  referenced securely via `app.yaml`'s `valueFrom` field rather than any plaintext file
- SQL Warehouse and schema permissions granted to the app's own service principal
  (separate identity from the developer's personal login)

### 6.3 Real debugging done during deployment (good material for the final pitch —
shows the gap between "works on my laptop" and "works as a real deployed service")

1. **Two competing auth methods**: initially tried connecting via a manually-passed
   personal access token (same method as local dev). Databricks Apps have their own
   built-in service-principal identity, auto-injected as DATABRICKS_CLIENT_ID/SECRET.
   Having both a token AND client credentials present caused the SDK to refuse to guess
   which to use ("more than one authorization method configured"). Fixed by switching
   fully to the service-principal method (via databricks-sdk's Config()) and removing
   the redundant personal token from app.yaml.
2. **Schema not found (again)**: the same schema-defaulting issue from Step 4 resurfaced
   after rewriting the connection logic for the new auth method - the schema="tgs_talk_to_data"
   parameter was dropped during the rewrite and had to be re-added.
3. **Insufficient permissions**: the app's service principal is a genuinely separate
   identity from the developer's own login, with zero inherited access. Had to explicitly
   grant USE SCHEMA and SELECT on tgs_talk_to_my_data.tgs_talk_to_data to the app's
   service principal via Unity Catalog permissions - a real, expected step when deploying
   with a dedicated app identity rather than a personal account.

### 6.4 Known limitation to mention in the pitch
Product IDs display as raw hash strings rather than human-readable names (inherited
from Step 5 - Olist dataset limitation, not a deployment issue).

---

## Project status: core technical build complete
Environment -> data -> KPIs -> AI reasoning -> SQL execution -> chat UI -> live deployment,
all working end-to-end. Remaining work is packaging this into the dry-run and final
presentation decks, not further technical build.

---

## Step 7 — Post-deployment refinement (found during real user testing)

After deployment, ran a 10-question test set (5 deliberately ambiguous, 5 deliberately
clear) and found real gaps between the intended behavior and what was actually deployed.
Fixed each one in turn:

### 7.1 Bug: ambiguous questions were never actually being clarified
Root cause: `SQL_SYSTEM_PROMPT` (used in the deployed app since Step 4) explicitly told
the model to "make a reasonable default choice rather than asking a question" - a
deliberate Step 4 decision to guarantee runnable SQL, which directly contradicted the
clarification behavior we validated separately in Step 3's `enrich_question.py`. That
script was never actually wired into the deployed app.
Fix: rebuilt the app around a proper two-stage flow - a classification step runs first
and can stop the flow entirely with a clarifying question; SQL generation only runs on
messages already confirmed clear.

### 7.2 Bug: no way to answer a clarifying question
The first two-stage version asked clarifying questions but had no UI to answer them -
the input box only ever started a new question. Fixed with `st.session_state` to track
a pending clarification and a follow-up answer box.

### 7.3 UX change: rebuilt as a real chat interface
Replaced the button-and-textbox UI with Streamlit's native `st.chat_message` /
`st.chat_input` - full conversation shown as chat bubbles, input fixed at the bottom.

### 7.4 Bug: no conversation memory (follow-ups like "what about the other choice" failed)
Every model call had been stateless - only the latest message was ever sent, with zero
context. Fixed by maintaining a running `api_history` (plain role/content list) sent in
full on every single classify/generate call, so the model can resolve references back
to earlier turns. Assistant replies are summarized (including a preview of actual result
rows) back into history so later questions can reference real numbers, not just row counts.

### 7.5 Bug: casual messages ("thank you") were forced through SQL generation and failed
The original two-way check (ambiguous vs. clear) assumed every message was a data
question. Upgraded to a three-way classifier: CHAT (small talk / thanks / meta questions,
answered directly, no SQL) / CLARIFY / CLEAR.

### 7.6 Feature: "New chat" button
Added a sidebar button that resets both the display history and the API history,
starting a genuinely fresh conversation.

### 7.7 Known issues still to verify
From the original 10-question test: one result table showed garbled/duplicated column
headers (SP state-performance question), and three single-value results displayed
blank in the exported test doc - unclear yet whether that's a real query bug or a
copy-paste artifact. Needs rechecking directly in the live app with the rebuilt code.




