# Step 2 (Databricks/Azure version) — Setup Guide

## Real paths confirmed for this project (updated after actual setup)
- Catalog: `tgs_talk_to_my_data`
- Schema: `tgs_talk_to_data`
- Volume: `raw`
- Full data path: `/Volumes/tgs_talk_to_my_data/tgs_talk_to_data/raw`

## Why this changed from the earlier BigQuery version
The dataset, join structure, and KPI logic from Step 1/2 don't change at all —
only *where the data physically lives* changes.

## 1. Prerequisites
- Azure Databricks workspace (Premium tier — required for Unity Catalog) — DONE
- Serverless compute — DONE, no cluster management needed

## 2. Getting the CSVs into Databricks — DONE
CSVs downloaded from Kaggle (`olistbr/brazilian-ecommerce`) and uploaded directly
into the Unity Catalog Volume at `/Volumes/tgs_talk_to_my_data/tgs_talk_to_data/raw`.

All 9 files confirmed present:
- olist_customers_dataset.csv (8.62 MB)
- olist_geolocation_dataset.csv (58.44 MB)
- olist_order_items_dataset.csv (14.72 MB)
- olist_order_payments_dataset.csv (5.51 MB)
- olist_order_reviews_dataset.csv (13.78 MB)
- olist_orders_dataset.csv (16.84 MB)
- olist_products_dataset.csv (2.27 MB)
- olist_sellers_dataset.csv (170.61 KB)
- product_category_name_translation.csv (2.55 KB)

## 3. Run `load_data_databricks.py` (or the `.ipynb` version) as a Databricks notebook — DONE
Confirmed row counts on load:
- orders: 99,441
- customers: 99,441
- order_items: 112,650
- products: 32,951
- category_translation: 71
- order_payments: 103,886
- order_reviews: 104,162
- sellers: 3,095
- geolocation: 1,000,163

## 4. Verify — DONE
```sql
SHOW TABLES IN tgs_talk_to_data;
SELECT COUNT(*) FROM tgs_talk_to_data.orders;
```

## 5. KPI validation — DONE
Ran `kpi_queries_databricks.sql` (Revenue Trend query) directly in the notebook.
24 months of data returned (Sept 2016 – Aug/Sept 2018), showing a realistic
growth curve from R$207.86 in the first partial month up to over R$1,000,000/month
by late 2017 — consistent with Olist's known early growth as a real marketplace.
