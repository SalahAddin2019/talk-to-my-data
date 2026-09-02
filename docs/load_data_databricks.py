# Databricks notebook source
# Step 2 (Databricks/Azure): Load the 9 Olist CSVs into managed Delta tables.
#
# Run this as a Databricks notebook (paste into a notebook, or import as .py
# with "Databricks notebook source" format, which this file already has).

from pyspark.sql.types import (
    StructType, StructField, StringType, IntegerType, DoubleType, TimestampType
)

# ---- 1. CONFIG: confirmed real path for this project ----
BASE_PATH = "/Volumes/tgs_talk_to_my_data/tgs_talk_to_data/raw"

SCHEMA_NAME = "tgs_talk_to_data"

spark.sql(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA_NAME}")

# ---- 2. Explicit schemas (matches the types documented in Step 1) ----

orders_schema = StructType([
    StructField("order_id", StringType()),
    StructField("customer_id", StringType()),
    StructField("order_status", StringType()),
    StructField("order_purchase_timestamp", TimestampType()),
    StructField("order_approved_at", TimestampType()),
    StructField("order_delivered_carrier_date", TimestampType()),
    StructField("order_delivered_customer_date", TimestampType()),
    StructField("order_estimated_delivery_date", TimestampType()),
])

customers_schema = StructType([
    StructField("customer_id", StringType()),
    StructField("customer_unique_id", StringType()),
    StructField("customer_zip_code_prefix", StringType()),
    StructField("customer_city", StringType()),
    StructField("customer_state", StringType()),
])

order_items_schema = StructType([
    StructField("order_id", StringType()),
    StructField("order_item_id", IntegerType()),
    StructField("product_id", StringType()),
    StructField("seller_id", StringType()),
    StructField("shipping_limit_date", TimestampType()),
    StructField("price", DoubleType()),
    StructField("freight_value", DoubleType()),
])

products_schema = StructType([
    StructField("product_id", StringType()),
    StructField("product_category_name", StringType()),
    StructField("product_name_lenght", IntegerType()),
    StructField("product_description_lenght", IntegerType()),
    StructField("product_photos_qty", IntegerType()),
    StructField("product_weight_g", IntegerType()),
    StructField("product_length_cm", IntegerType()),
    StructField("product_height_cm", IntegerType()),
    StructField("product_width_cm", IntegerType()),
])

category_translation_schema = StructType([
    StructField("product_category_name", StringType()),
    StructField("product_category_name_english", StringType()),
])

order_payments_schema = StructType([
    StructField("order_id", StringType()),
    StructField("payment_sequential", IntegerType()),
    StructField("payment_type", StringType()),
    StructField("payment_installments", IntegerType()),
    StructField("payment_value", DoubleType()),
])

order_reviews_schema = StructType([
    StructField("review_id", StringType()),
    StructField("order_id", StringType()),
    StructField("review_score", IntegerType()),
    StructField("review_comment_title", StringType()),
    StructField("review_comment_message", StringType()),
    StructField("review_creation_date", TimestampType()),
    StructField("review_answer_timestamp", TimestampType()),
])

sellers_schema = StructType([
    StructField("seller_id", StringType()),
    StructField("seller_zip_code_prefix", StringType()),
    StructField("seller_city", StringType()),
    StructField("seller_state", StringType()),
])

geolocation_schema = StructType([
    StructField("geolocation_zip_code_prefix", StringType()),
    StructField("geolocation_lat", DoubleType()),
    StructField("geolocation_lng", DoubleType()),
    StructField("geolocation_city", StringType()),
    StructField("geolocation_state", StringType()),
])

# ---- 3. File -> table -> schema mapping ----
tables = [
    ("olist_orders_dataset.csv", "orders", orders_schema),
    ("olist_customers_dataset.csv", "customers", customers_schema),
    ("olist_order_items_dataset.csv", "order_items", order_items_schema),
    ("olist_products_dataset.csv", "products", products_schema),
    ("product_category_name_translation.csv", "category_translation", category_translation_schema),
    ("olist_order_payments_dataset.csv", "order_payments", order_payments_schema),
    ("olist_order_reviews_dataset.csv", "order_reviews", order_reviews_schema),
    ("olist_sellers_dataset.csv", "sellers", sellers_schema),
    ("olist_geolocation_dataset.csv", "geolocation", geolocation_schema),
]

# ---- 4. Read each CSV and write as a managed Delta table ----
for filename, table_name, schema in tables:
    df = (
        spark.read
        .option("header", "true")
        .schema(schema)
        .csv(f"{BASE_PATH}/{filename}")
    )
    full_table_name = f"{SCHEMA_NAME}.{table_name}"
    df.write.format("delta").mode("overwrite").saveAsTable(full_table_name)
    print(f"Loaded {full_table_name}: {df.count()} rows")

print("Done. Run: SHOW TABLES IN tgs_talk_to_data;")
