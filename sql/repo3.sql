WITH raw_orders AS (
    SELECT
        payload->>'order_id' AS order_id
    FROM raw.store_order_records
)
SELECT r.order_id
FROM raw_orders r
LEFT JOIN staging.orders s
    ON r.order_id = s.order_id
WHERE s.order_id IS NULL;


WITH raw_items AS (
    SELECT
        r.payload->>'order_id' AS order_id,
        item.ordinality AS item_index,
        item.value->>'sku' AS sku
    FROM raw.store_order_records r
    CROSS JOIN LATERAL
        jsonb_array_elements(
            COALESCE(r.payload->'items', '[]'::jsonb)
        ) WITH ORDINALITY AS item(value, ordinality)
)
SELECT
    r.order_id,
    r.item_index,
    r.sku
FROM raw_items r
LEFT JOIN staging.order_items s
    ON r.order_id = s.order_id
    AND r.item_index = s.item_index
WHERE s.staging_item_id IS NULL;


SELECT
    'orders' AS table_name,
    COUNT(*) AS total,
    COUNT(raw_id) AS populated_raw_ids,
    COUNT(*) FILTER (
        WHERE raw_id IS NULL
    ) AS missing_raw_ids
FROM staging.orders

UNION ALL

SELECT
    'order_items',
    COUNT(*),
    COUNT(raw_id),
    COUNT(*) FILTER (
        WHERE raw_id IS NULL
    )
FROM staging.order_items;

SELECT
    raw_id,
    payload->>'order_id' AS order_id
FROM raw.store_order_records
ORDER BY raw_id
LIMIT 10;

SELECT
    raw_id,
    order_id,
    run_id
FROM staging.orders
LIMIT 10;

SELECT
    payload->>'order_id' AS order_id,
    COUNT(*) AS occurrences
FROM raw.store_order_records
GROUP BY payload->>'order_id'
HAVING COUNT(*) > 1;

SELECT
    COUNT(*) AS total_orders,
    COUNT(raw_id) AS populated_raw_ids,
    COUNT(*) FILTER (
        WHERE raw_id IS NULL
    ) AS missing_raw_ids
FROM staging.orders;


SELECT
    COUNT(*) AS total_items,
    COUNT(raw_id) AS populated_raw_ids,
    COUNT(*) FILTER (
        WHERE raw_id IS NULL
    ) AS missing_raw_ids
FROM staging.order_items;

SELECT
    COUNT(*) AS total_records,
    COUNT(*) FILTER (
        WHERE r.raw_id IS NOT NULL
    ) AS matched_records,
    COUNT(*) FILTER (
        WHERE r.raw_id IS NULL
    ) AS unmatched_records,
    COUNT(*) FILTER (
        WHERE s.order_id = r.payload->>'order_id'
    ) AS correctly_mapped
FROM staging.orders s
LEFT JOIN raw.store_order_records r
    ON s.raw_id = r.raw_id;

SELECT
    COUNT(*) AS total_items,

    COUNT(*) FILTER (
        WHERE r.raw_id IS NOT NULL
    ) AS matched_raw_records,

    COUNT(*) FILTER (
        WHERE s.sku =
            r.payload->'items'->(s.item_index - 1)->>'sku'
    ) AS correctly_mapped_skus

FROM staging.order_items s

LEFT JOIN raw.store_order_records r
    ON s.raw_id = r.raw_id;

SELECT
    COUNT(*) AS total_records,
    COUNT(r.raw_id) AS matched_records,
    COUNT(*) FILTER (
        WHERE r.raw_id IS NULL
    ) AS unmatched_records,
    COUNT(*) FILTER (
        WHERE s.campaign_id = r.payload->>'campaign_id'
    ) AS correctly_mapped
FROM staging.ads s
LEFT JOIN raw.ads_api_records r
    ON s.raw_id = r.raw_id;

SELECT
    COUNT(*) AS total_records,
    COUNT(r.raw_id) AS matched_records,
    COUNT(*) FILTER (
        WHERE r.raw_id IS NULL
    ) AS unmatched_records,
    COUNT(*) FILTER (
        WHERE s.lead_id = r.payload->>'lead_id'
    ) AS correctly_mapped
FROM staging.leads s
LEFT JOIN raw.crm_lead_records r
    ON s.raw_id = r.raw_id;


SELECT
    'ads' AS table_name,
    COUNT(*) AS total_records,
    COUNT(*) FILTER (WHERE is_valid) AS valid_records,
    COUNT(*) FILTER (WHERE NOT is_valid) AS rejected_records
FROM staging.ads

UNION ALL

SELECT
    'leads',
    COUNT(*),
    COUNT(*) FILTER (WHERE is_valid),
    COUNT(*) FILTER (WHERE NOT is_valid)
FROM staging.leads

UNION ALL

SELECT
    'orders',
    COUNT(*),
    COUNT(*) FILTER (WHERE is_valid),
    COUNT(*) FILTER (WHERE NOT is_valid)
FROM staging.orders

UNION ALL

SELECT
    'order_items',
    COUNT(*),
    COUNT(*) FILTER (WHERE is_valid),
    COUNT(*) FILTER (WHERE NOT is_valid)
FROM staging.order_items;

CREATE SCHEMA IF NOT EXISTS gold;

SELECT schema_name
FROM information_schema.schemata
WHERE schema_name = 'gold';


CREATE TABLE IF NOT EXISTS gold.fact_ad_performance (
    ad_id BIGSERIAL PRIMARY KEY,
    raw_id BIGINT,
    campaign_id VARCHAR(100),
    campaign_name VARCHAR(255),
    platform VARCHAR(100),
    ad_date DATE,
    spend NUMERIC(14,2),
    impressions BIGINT,
    clicks BIGINT,
    ctr NUMERIC(10,4),
    cpc NUMERIC(14,2),
    cpm NUMERIC(14,2),
    processed_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);


-- STEP 1: Clear existing data to avoid duplicates on reruns
TRUNCATE TABLE gold.fact_ad_performance RESTART IDENTITY;

-- STEP 2: Insert transformed advertising data
INSERT INTO gold.fact_ad_performance (
    raw_id,
    campaign_id,
    campaign_name,
    platform,
    ad_date,
    spend,
    impressions,
    clicks,
    ctr,
    cpc,
    cpm
)
SELECT
    raw_id,
    campaign_id,
    campaign_name,
    platform,
    ad_date,
    spend,
    impressions,
    clicks,

    -- Click Through Rate (%)
    ROUND(
        (clicks::NUMERIC / NULLIF(impressions, 0)) * 100,
        4
    ),

    -- Cost Per Click
    ROUND(
        spend / NULLIF(clicks, 0),
        2
    ),

    -- Cost Per 1000 Impressions
    ROUND(
        (spend / NULLIF(impressions, 0)) * 1000,
        2
    )

FROM staging.ads
WHERE is_valid = TRUE;

SELECT
    COUNT(*) AS total_records,
    COUNT(DISTINCT raw_id) AS unique_ads,
    ROUND(SUM(spend), 2) AS total_spend,
    SUM(impressions) AS total_impressions,
    SUM(clicks) AS total_clicks,
    ROUND(AVG(ctr), 2) AS average_ctr
FROM gold.fact_ad_performance;


CREATE TABLE IF NOT EXISTS gold.dim_leads (
    lead_key BIGSERIAL PRIMARY KEY,
    raw_id BIGINT,
    lead_id VARCHAR(100),
    first_name VARCHAR(150),
    last_name VARCHAR(150),
    email VARCHAR(255),
    phone VARCHAR(30),
    company VARCHAR(255),
    job_title VARCHAR(255),
    industry VARCHAR(150),
    country VARCHAR(150),
    lead_source VARCHAR(150),
    status VARCHAR(50),
    created_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ,
    processed_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

SELECT
    column_name,
    data_type
FROM information_schema.columns
WHERE table_schema = 'staging'
AND table_name = 'leads'
ORDER BY ordinal_position;


SELECT *
FROM staging.leads
WHERE is_valid = TRUE
LIMIT 5;

ALTER TABLE gold.dim_leads
ADD COLUMN IF NOT EXISTS full_name VARCHAR(255);

ALTER TABLE gold.dim_leads
ADD COLUMN IF NOT EXISTS utm_campaign VARCHAR(255);

TRUNCATE TABLE gold.dim_leads RESTART IDENTITY;

INSERT INTO gold.dim_leads (
    raw_id,
    lead_id,
    full_name,
    email,
    phone,
    utm_campaign,
    created_at
)
SELECT
    raw_id,
    lead_id,
    name,
    email,
    phone,
    utm_campaign,
    created_at
FROM staging.leads
WHERE is_valid = TRUE;
SELECT
    COUNT(*) AS total_leads,
    COUNT(DISTINCT lead_id) AS unique_leads,
    COUNT(DISTINCT email) AS unique_emails
FROM gold.dim_leads;


CREATE TABLE IF NOT EXISTS gold.fact_orders (
    order_key BIGSERIAL PRIMARY KEY,
    raw_id BIGINT,
    order_id VARCHAR(100),
    customer_id VARCHAR(100),
    customer_phone VARCHAR(30),
    order_date TIMESTAMPTZ,
    order_status VARCHAR(50),
    payment_method VARCHAR(100),
    shipping_city VARCHAR(150),
    shipping_country VARCHAR(150),
    total_amount NUMERIC(14,2),
    processed_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- STEP 1: Clear existing records
TRUNCATE TABLE gold.fact_orders RESTART IDENTITY;

-- STEP 2: Load validated orders
INSERT INTO gold.fact_orders (
    raw_id,
    order_id,
    customer_id,
    customer_phone,
    order_date,
    order_status,
    payment_method,
    shipping_city,
    shipping_country,
    total_amount
)
SELECT
    raw_id,
    order_id,
    customer_id,
    customer_phone,
    order_date,
    order_status,
    payment_method,
    shipping_city,
    shipping_country,
    total_amount
FROM staging.orders
WHERE is_valid = TRUE;

SELECT
    COUNT(*) AS total_orders,
    COUNT(DISTINCT order_id) AS unique_orders,
    ROUND(SUM(total_amount), 2) AS total_revenue,
    ROUND(AVG(total_amount), 2) AS average_order_value,
    COUNT(DISTINCT customer_id) AS unique_customers
FROM gold.fact_orders;


CREATE TABLE IF NOT EXISTS gold.fact_order_items (
    item_key BIGSERIAL PRIMARY KEY,
    raw_id BIGINT,
    order_id VARCHAR(100),
    item_index INTEGER,
    sku VARCHAR(100),
    product_name VARCHAR(255),
    quantity INTEGER,
    unit_price NUMERIC(14,2),
    line_total NUMERIC(14,2),
    processed_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);


-- STEP 1: Clear existing records
TRUNCATE TABLE gold.fact_order_items RESTART IDENTITY;

-- STEP 2: Load validated order items
INSERT INTO gold.fact_order_items (
    raw_id,
    order_id,
    item_index,
    sku,
    product_name,
    quantity,
    unit_price,
    line_total
)
SELECT
    raw_id,
    order_id,
    item_index,
    sku,
    product_name,
    qty,
    unit_price,
    (qty * unit_price) AS line_total
FROM staging.order_items
WHERE is_valid = TRUE;


SELECT
    COUNT(*) AS total_items,
    COUNT(DISTINCT order_id) AS unique_orders,
    COUNT(DISTINCT sku) AS unique_products,
    SUM(quantity) AS total_quantity,
    ROUND(SUM(line_total), 2) AS total_item_revenue
FROM gold.fact_order_items;

SELECT
    COUNT(*) AS unmatched_item_records,
    COUNT(DISTINCT i.order_id) AS unmatched_orders
FROM gold.fact_order_items i
LEFT JOIN gold.fact_orders o
    ON i.order_id = o.order_id
WHERE o.order_id IS NULL;


SELECT
    i.order_id,
    COUNT(*) AS item_count,
    SUM(i.line_total) AS item_revenue
FROM gold.fact_order_items i
LEFT JOIN gold.fact_orders o
    ON i.order_id = o.order_id
WHERE o.order_id IS NULL
GROUP BY i.order_id
ORDER BY i.order_id;

CREATE OR REPLACE VIEW gold.vw_marketing_performance AS
SELECT
    campaign_id,
    campaign_name,
    platform,
    SUM(spend) AS total_spend,
    SUM(impressions) AS total_impressions,
    SUM(clicks) AS total_clicks,
    ROUND(
        SUM(clicks)::NUMERIC /
        NULLIF(SUM(impressions), 0) * 100, 2
    ) AS ctr,
    ROUND(
        SUM(spend) /
        NULLIF(SUM(clicks), 0), 2
    ) AS cpc
FROM gold.fact_ad_performance
GROUP BY campaign_id, campaign_name, platform;

CREATE OR REPLACE VIEW gold.vw_sales_performance AS
SELECT
    shipping_country,
    payment_method,
    order_status,

    COUNT(*) AS total_orders,

    COUNT(DISTINCT customer_id) AS unique_customers,

    SUM(total_amount) AS total_revenue,

    ROUND(AVG(total_amount), 2) AS average_order_value

FROM gold.fact_orders

GROUP BY
    shipping_country,
    payment_method,
    order_status;


CREATE OR REPLACE VIEW gold.vw_product_performance AS
SELECT
    sku,
    product_name,

    COUNT(*) AS total_transactions,

    COUNT(DISTINCT order_id) AS total_orders,

    SUM(quantity) AS total_quantity_sold,

    SUM(line_total) AS total_revenue,

    ROUND(AVG(unit_price), 2) AS average_price

FROM gold.fact_order_items

GROUP BY
    sku,
    product_name;

CREATE OR REPLACE VIEW gold.vw_lead_acquisition AS
SELECT
    utm_campaign,

    COUNT(*) AS total_leads,

    COUNT(DISTINCT lead_id) AS unique_leads,

    COUNT(DISTINCT email) AS unique_emails,

    COUNT(DISTINCT phone) AS unique_phones,

    MIN(created_at) AS first_lead_date,

    MAX(created_at) AS latest_lead_date

FROM gold.dim_leads

GROUP BY utm_campaign;

SELECT
    table_schema,
    table_name
FROM information_schema.tables
WHERE table_schema = 'gold'
  AND table_type = 'BASE TABLE'
ORDER BY table_name;

SELECT
    table_name,
    column_name,
    data_type,
    is_nullable
FROM information_schema.columns
WHERE table_schema = 'gold'
  AND table_name IN (
      'dim_leads',
      'fact_ad_performance',
      'fact_orders',
      'fact_order_items'
  )
ORDER BY table_name, ordinal_position;

SELECT column_name, data_type
FROM information_schema.columns
WHERE table_schema = 'gold'
  AND table_name = 'dim_leads'
ORDER BY ordinal_position;

SELECT
    ordinal_position,
    column_name,
    data_type
FROM information_schema.columns
WHERE table_schema = 'gold'
  AND table_name = 'dim_leads'
ORDER BY ordinal_position;

SELECT
    string_agg(
        column_name || ' (' || data_type || ')',
        ', ' ORDER BY ordinal_position
    ) AS all_columns
FROM information_schema.columns
WHERE table_schema = 'gold'
  AND table_name = 'dim_leads';
 CREATE TABLE IF NOT EXISTS gold.dim_customer (
    customer_key BIGSERIAL PRIMARY KEY,
    phone VARCHAR(10) NOT NULL UNIQUE,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);
INSERT INTO gold.dim_customer (phone)
SELECT DISTINCT
    RIGHT(REGEXP_REPLACE(phone, '[^0-9]', '', 'g'), 10)
FROM gold.dim_leads
WHERE phone IS NOT NULL
  AND LENGTH(REGEXP_REPLACE(phone, '[^0-9]', '', 'g')) >= 10
ON CONFLICT (phone) DO NOTHING;
CREATE TABLE IF NOT EXISTS gold.dim_customer (
    customer_key BIGSERIAL PRIMARY KEY,
    phone VARCHAR(10) NOT NULL UNIQUE,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);
SELECT COUNT(*) AS total_customers
FROM gold.dim_customer;

SELECT *
FROM gold.dim_customer
LIMIT 10;

SELECT
    column_name,
    data_type
FROM information_schema.columns
WHERE table_schema = 'gold'
  AND table_name = 'fact_ad_performance'
ORDER BY ordinal_position;
CREATE TABLE IF NOT EXISTS gold.dim_campaign (
    campaign_key BIGSERIAL PRIMARY KEY,
    campaign_id VARCHAR UNIQUE NOT NULL,
    campaign_name VARCHAR,
    platform VARCHAR
);

INSERT INTO gold.dim_campaign (
    campaign_id,
    campaign_name,
    platform
)
SELECT DISTINCT ON (campaign_id)
    campaign_id,
    campaign_name,
    platform
FROM gold.fact_ad_performance
WHERE campaign_id IS NOT NULL
ORDER BY campaign_id, ad_date DESC
ON CONFLICT (campaign_id) DO UPDATE
SET
    campaign_name = EXCLUDED.campaign_name,
    platform = EXCLUDED.platform;

SELECT
    COUNT(*) AS total_leads,
    COUNT(DISTINCT lead_id) AS unique_leads,
    COUNT(*) FILTER (
        WHERE dc.customer_key IS NOT NULL
    ) AS matched_customers,
    COUNT(*) FILTER (
        WHERE dc.customer_key IS NULL
    ) AS unmatched_customers
FROM gold.dim_leads dl
LEFT JOIN gold.dim_customer dc
    ON dc.phone = RIGHT(
        REGEXP_REPLACE(dl.phone, '[^0-9]', '', 'g'), 10
    );
CREATE TABLE IF NOT EXISTS gold.fact_leads (
    lead_key BIGINT PRIMARY KEY,
    customer_key BIGINT REFERENCES gold.dim_customer(customer_key),
    campaign_key BIGINT REFERENCES gold.dim_campaign(campaign_key),
    lead_id VARCHAR UNIQUE NOT NULL,
    created_at TIMESTAMPTZ,
    status VARCHAR,
    lead_source VARCHAR,
    utm_campaign VARCHAR
);

SELECT
    COUNT(*) AS total_leads,
    COUNT(*) FILTER (
        WHERE dc.campaign_key IS NOT NULL
    ) AS matched_campaigns,
    COUNT(*) FILTER (
        WHERE dc.campaign_key IS NULL
    ) AS unmatched_campaigns
FROM gold.dim_leads dl
LEFT JOIN gold.dim_campaign dc
    ON LOWER(TRIM(dc.campaign_name)) = LOWER(TRIM(dl.utm_campaign));

SELECT DISTINCT utm_campaign
FROM gold.dim_leads
ORDER BY utm_campaign
LIMIT 20;
SELECT DISTINCT campaign_name
FROM gold.dim_campaign
ORDER BY campaign_name
LIMIT 20;
SELECT table_schema, table_name
FROM information_schema.tables
WHERE table_schema IN ('raw', 'staging')
ORDER BY table_schema, table_name;
SELECT *
FROM staging.leads
LIMIT 10;

SELECT *
FROM raw.crm_lead_records
LIMIT 10;


SELECT
    payload ->> 'lead_id' AS lead_id,
    payload ->> 'utm_campaign' AS utm_campaign,
    payload ->> 'campaign' AS campaign,
    payload ->> 'campaign_name' AS campaign_name,
    payload ->> 'utm_source' AS utm_source
FROM raw.crm_lead_records
LIMIT 10;


CREATE TABLE IF NOT EXISTS gold.fact_leads (
    lead_key BIGINT PRIMARY KEY,
    customer_key BIGINT REFERENCES gold.dim_customer(customer_key),
    campaign_key BIGINT REFERENCES gold.dim_campaign(campaign_key),
    lead_id VARCHAR UNIQUE NOT NULL,
    created_at TIMESTAMPTZ,
    status VARCHAR,
    lead_source VARCHAR,
    utm_campaign VARCHAR
);

INSERT INTO gold.fact_leads (
    lead_key,
    customer_key,
    campaign_key,
    lead_id,
    created_at,
    status,
    lead_source,
    utm_campaign
)
SELECT
    dl.lead_key,
    dc.customer_key,
    NULL,
    dl.lead_id,
    dl.created_at,
    dl.status,
    dl.lead_source,
    dl.utm_campaign
FROM gold.dim_leads dl
LEFT JOIN gold.dim_customer dc
    ON dc.phone = RIGHT(
        REGEXP_REPLACE(dl.phone, '[^0-9]', '', 'g'), 10
    )
ON CONFLICT (lead_key) DO NOTHING;


SELECT
    COUNT(*) AS total_leads,
    COUNT(customer_key) AS linked_customers,
    COUNT(campaign_key) AS linked_campaigns
FROM gold.fact_leads;


CREATE TABLE IF NOT EXISTS gold.fact_ad_spend_daily (
    campaign_key BIGINT REFERENCES gold.dim_campaign(campaign_key),
    ad_date DATE NOT NULL,
    spend NUMERIC(14,2),
    impressions BIGINT,
    clicks BIGINT,
    PRIMARY KEY (campaign_key, ad_date)
);


INSERT INTO gold.fact_ad_spend_daily (
    campaign_key,
    ad_date,
    spend,
    impressions,
    clicks
)
SELECT
    dc.campaign_key,
    fa.ad_date,
    SUM(fa.spend),
    SUM(fa.impressions),
    SUM(fa.clicks)
FROM gold.fact_ad_performance fa
JOIN gold.dim_campaign dc
    ON dc.campaign_id = fa.campaign_id
GROUP BY dc.campaign_key, fa.ad_date
ON CONFLICT (campaign_key, ad_date) DO UPDATE
SET
    spend = EXCLUDED.spend,
    impressions = EXCLUDED.impressions,
    clicks = EXCLUDED.clicks;


CREATE TABLE IF NOT EXISTS gold.rejected_rows (
    rejection_id BIGSERIAL PRIMARY KEY,
    run_id UUID,
    source_table VARCHAR(100) NOT NULL,
    record_id VARCHAR(100),
    rule_name VARCHAR(150) NOT NULL,
    reason TEXT NOT NULL,
    original_data JSONB NOT NULL,
    rejected_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);


SELECT column_name, data_type
FROM information_schema.columns
WHERE table_schema = 'gold'
  AND table_name = 'rejected_rows'
ORDER BY ordinal_position;


CREATE TABLE IF NOT EXISTS gold.pipeline_runs (
    run_id UUID PRIMARY KEY,
    start_time TIMESTAMPTZ NOT NULL,
    end_time TIMESTAMPTZ,
    rows_read BIGINT DEFAULT 0,
    rows_loaded BIGINT DEFAULT 0,
    rows_rejected BIGINT DEFAULT 0,
    duplicates_removed BIGINT DEFAULT 0,
    status VARCHAR(30) NOT NULL
);


SELECT column_name, data_type
FROM information_schema.columns
WHERE table_schema = 'gold'
  AND table_name = 'pipeline_runs'
ORDER BY ordinal_position;


SELECT
    table_name
FROM information_schema.tables
WHERE table_schema = 'gold'
  AND table_name IN (
      'dim_campaign',
      'fact_ad_spend_daily',
      'dim_customer',
      'fact_leads',
      'fact_orders',
      'fact_order_items',
      'rejected_rows',
      'pipeline_runs'
  )
ORDER BY table_name;

SELECT
    table_name,
    column_name,
    data_type
FROM information_schema.columns
WHERE table_schema = 'staging'
  AND table_name IN (
      'ads',
      'leads',
      'orders',
      'order_items'
  )
ORDER BY table_name, ordinal_position;


SELECT 'ads' AS source, COUNT(*) AS rejected
FROM staging.ads
WHERE is_valid = FALSE

UNION ALL

SELECT 'leads', COUNT(*)
FROM staging.leads
WHERE is_valid = FALSE

UNION ALL

SELECT 'orders', COUNT(*)
FROM staging.orders
WHERE is_valid = FALSE

UNION ALL

SELECT 'order_items', COUNT(*)
FROM staging.order_items
WHERE is_valid = FALSE;



INSERT INTO gold.rejected_rows (
    source_table,
    record_id,
    rule_name,
    reason,
    original_data
)

SELECT
    'ads',
    s.raw_id::VARCHAR,
    'staging_validation',
    s.rejection_reason,
    r.payload
FROM staging.ads s
JOIN raw.ads_api_records r ON r.raw_id = s.raw_id
WHERE s.is_valid = FALSE

UNION ALL

SELECT
    'leads',
    s.raw_id::VARCHAR,
    'staging_validation',
    s.rejection_reason,
    r.payload
FROM staging.leads s
JOIN raw.crm_lead_records r ON r.raw_id = s.raw_id
WHERE s.is_valid = FALSE

UNION ALL

SELECT
    'orders',
    s.raw_id::VARCHAR,
    'staging_validation',
    s.rejection_reason,
    r.payload
FROM staging.orders s
JOIN raw.store_order_records r ON r.raw_id = s.raw_id
WHERE s.is_valid = FALSE;

SELECT
    source_table,
    COUNT(*) AS rejected_records
FROM gold.rejected_rows
GROUP BY source_table
ORDER BY source_table;

SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'raw';

SELECT
    staging_item_id,
    raw_id,
    order_id,
    sku,
    qty,
    rejection_reason,
    run_id
FROM staging.order_items
WHERE is_valid = FALSE;

INSERT INTO gold.rejected_rows (
    run_id,
    source_table,
    record_id,
    rule_name,
    reason,
    original_data
)
SELECT
    oi.run_id,
    'order_items',
    oi.staging_item_id::VARCHAR,
    'staging_validation',
    oi.rejection_reason,
    r.payload
FROM staging.order_items oi
JOIN raw.store_order_records r
    ON r.raw_id = oi.raw_id
WHERE oi.is_valid = FALSE;

SELECT
    source_table,
    COUNT(*) AS rejected_records
FROM gold.rejected_rows
GROUP BY source_table
ORDER BY source_table;


INSERT INTO gold.pipeline_runs (
    run_id,
    start_time,
    end_time,
    rows_read,
    rows_loaded,
    rows_rejected,
    duplicates_removed,
    status
)
SELECT
    gen_random_uuid(),
    CURRENT_TIMESTAMP,
    CURRENT_TIMESTAMP,
    8371,
    8006,
    365,
    0,
    'SUCCESS';


SELECT *
FROM gold.pipeline_runs
ORDER BY start_time DESC;


SELECT
    'ads' AS source,
    COUNT(*) AS rows_read,
    COUNT(*) FILTER (WHERE is_valid = TRUE) AS rows_loaded,
    COUNT(*) FILTER (WHERE is_valid = FALSE) AS rows_rejected
FROM staging.ads

UNION ALL

SELECT
    'leads',
    COUNT(*),
    COUNT(*) FILTER (WHERE is_valid = TRUE),
    COUNT(*) FILTER (WHERE is_valid = FALSE)
FROM staging.leads

UNION ALL

SELECT
    'orders',
    COUNT(*),
    COUNT(*) FILTER (WHERE is_valid = TRUE),
    COUNT(*) FILTER (WHERE is_valid = FALSE)
FROM staging.orders

UNION ALL

SELECT
    'order_items',
    COUNT(*),
    COUNT(*) FILTER (WHERE is_valid = TRUE),
    COUNT(*) FILTER (WHERE is_valid = FALSE)
FROM staging.order_items;

SELECT
    source_table,
    rule_name,
    COUNT(*) AS rejected_count
FROM gold.rejected_rows
GROUP BY source_table, rule_name
ORDER BY source_table, rule_name;


SELECT
    source_table,
    reason,
    COUNT(*) AS occurrences
FROM gold.rejected_rows
GROUP BY source_table, reason
ORDER BY source_table, occurrences DESC;


SELECT
    COUNT(*) AS total_orders,
    COUNT(*) FILTER (
        WHERE ABS(
            o.total_amount - COALESCE(i.item_total, 0)
        ) <= 1
    ) AS matching_orders,
    COUNT(*) FILTER (
        WHERE ABS(
            o.total_amount - COALESCE(i.item_total, 0)
        ) > 1
    ) AS mismatched_orders
FROM gold.fact_orders o
LEFT JOIN (
    SELECT
        order_id,
        SUM(line_total) AS item_total
    FROM gold.fact_order_items
    GROUP BY order_id
) i
    ON i.order_id = o.order_id;

SELECT
    column_name,
    data_type
FROM information_schema.columns
WHERE table_schema = 'gold'
  AND table_name = 'fact_order_items'
ORDER BY ordinal_position;



SELECT
    (SELECT COUNT(*) FROM gold.dim_campaign) AS campaigns,
    (SELECT COUNT(*) FROM gold.dim_customer) AS customers,
    (SELECT COUNT(*) FROM gold.fact_leads) AS leads,
    (SELECT COUNT(*) FROM gold.fact_ad_spend_daily) AS ad_records,
    (SELECT COUNT(*) FROM gold.fact_orders) AS orders,
    (SELECT COUNT(*) FROM gold.fact_order_items) AS order_items,
    (SELECT COUNT(*) FROM gold.rejected_rows) AS rejected;