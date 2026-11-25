SELECT table_schema, table_name
FROM information_schema.tables
WHERE table_schema IN ('raw', 'staging', 'gold')
ORDER BY table_schema, table_name;


SELECT * FROM gold.dim_customer LIMIT 5;

SELECT * FROM gold.dim_campaign LIMIT 5;

SELECT * FROM gold.fact_leads LIMIT 5;

SELECT * FROM gold.fact_orders LIMIT 5;

SELECT * FROM gold.fact_order_items LIMIT 5;

SELECT * FROM gold.fact_ad_spend_daily LIMIT 5;


SELECT 'dim_customer' AS table_name, COUNT(*) AS total_rows
FROM gold.dim_customer

UNION ALL

SELECT 'dim_campaign', COUNT(*)
FROM gold.dim_campaign

UNION ALL

SELECT 'fact_leads', COUNT(*)
FROM gold.fact_leads

UNION ALL

SELECT 'fact_orders', COUNT(*)
FROM gold.fact_orders

UNION ALL

SELECT 'fact_order_items', COUNT(*)
FROM gold.fact_order_items

UNION ALL

SELECT 'fact_ad_spend_daily', COUNT(*)
FROM gold.fact_ad_spend_daily;



SELECT
    source_table,
    COUNT(*) AS rejected_records
FROM gold.rejected_rows
GROUP BY source_table
ORDER BY source_table;



SELECT
    source_table,
    reason,
    COUNT(*) AS occurrences
FROM gold.rejected_rows
GROUP BY source_table, reason
ORDER BY source_table, occurrences DESC;


SELECT
    run_id,
    start_time,
    end_time,
    rows_read,
    rows_loaded,
    rows_rejected,
    duplicates_removed,
    status
FROM public.pipeline_runs
ORDER BY start_time DESC;