-- KPI 1: Revenue Trend (monthly)
SELECT
  date_trunc('MONTH', order_purchase_timestamp) AS month,
  SUM(oi.price) AS revenue
FROM tgs_talk_to_data.order_items oi
JOIN tgs_talk_to_data.orders o
  ON oi.order_id = o.order_id
WHERE o.order_status NOT IN ('canceled', 'unavailable')
GROUP BY month
ORDER BY month;

-- KPI 1 variant: Revenue Trend by state (location dimension proxy for "store/country")
SELECT
  date_trunc('MONTH', o.order_purchase_timestamp) AS month,
  c.customer_state,
  SUM(oi.price) AS revenue
FROM tgs_talk_to_data.order_items oi
JOIN tgs_talk_to_data.orders o
  ON oi.order_id = o.order_id
JOIN tgs_talk_to_data.customers c
  ON o.customer_id = c.customer_id
WHERE o.order_status NOT IN ('canceled', 'unavailable')
GROUP BY month, c.customer_state
ORDER BY month, revenue DESC;

-- KPI 2: Top-Performing Products (by revenue, top 10)
SELECT
  p.product_id,
  t.product_category_name_english AS category,
  SUM(oi.price) AS total_revenue,
  COUNT(oi.order_item_id) AS units_sold
FROM tgs_talk_to_data.order_items oi
JOIN tgs_talk_to_data.orders o
  ON oi.order_id = o.order_id
JOIN tgs_talk_to_data.products p
  ON oi.product_id = p.product_id
LEFT JOIN tgs_talk_to_data.category_translation t
  ON p.product_category_name = t.product_category_name
WHERE o.order_status NOT IN ('canceled', 'unavailable')
GROUP BY p.product_id, category
ORDER BY total_revenue DESC
LIMIT 10;

-- KPI 2 variant: Top Product Categories by revenue (rollup, easier to present in the demo)
SELECT
  COALESCE(t.product_category_name_english, 'Uncategorized') AS category,
  SUM(oi.price) AS total_revenue,
  COUNT(oi.order_item_id) AS units_sold
FROM tgs_talk_to_data.order_items oi
JOIN tgs_talk_to_data.orders o
  ON oi.order_id = o.order_id
JOIN tgs_talk_to_data.products p
  ON oi.product_id = p.product_id
LEFT JOIN tgs_talk_to_data.category_translation t
  ON p.product_category_name = t.product_category_name
WHERE o.order_status NOT IN ('canceled', 'unavailable')
GROUP BY category
ORDER BY total_revenue DESC
LIMIT 10;
