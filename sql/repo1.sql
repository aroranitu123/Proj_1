
CREATE SCHEMA IF NOT EXISTS raw;

CREATE SCHEMA IF NOT EXISTS staging;

CREATE SCHEMA IF NOT EXISTS public
SELECT schema_name
FROM information_schema.schemata
WHERE schema_name IN ('raw', 'staging', 'public')
ORDER BY schema_name;


-- 1. Advertising API raw records
CREATE TABLE raw.ads_api_records (
    raw_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    run_id UUID NOT NULL,
    source_page INTEGER,
    payload JSONB NOT NULL,
    loaded_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 2. CRM raw records
CREATE TABLE raw.crm_lead_records (
    raw_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    run_id UUID NOT NULL,
    source_file VARCHAR(255) NOT NULL,
    payload JSONB NOT NULL,
    loaded_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 3. Store order raw records
CREATE TABLE raw.store_order_records (
    raw_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    run_id UUID NOT NULL,
    source_file VARCHAR(255),
    payload JSONB NOT NULL,
    loaded_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for pipeline execution tracking
CREATE INDEX idx_ads_run_id
ON raw.ads_api_records(run_id);

CREATE INDEX idx_crm_run_id
ON raw.crm_lead_records(run_id);

CREATE INDEX idx_orders_run_id
ON raw.store_order_records(run_id);

SELECT table_schema, table_name
FROM information_schema.tables
WHERE table_schema = 'raw'
ORDER BY table_name;


-- 1. Clean advertising data
CREATE TABLE staging.ads (
    staging_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    raw_id BIGINT REFERENCES raw.ads_api_records(raw_id),
    campaign_id VARCHAR(100),
    campaign_name VARCHAR(255),
    platform VARCHAR(50),
    ad_date DATE,
    spend NUMERIC(14,2),
    impressions BIGINT,
    clicks BIGINT,
    updated_at TIMESTAMPTZ,
    is_valid BOOLEAN DEFAULT TRUE,
    rejection_reason TEXT,
    processed_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- 2. Clean CRM leads
CREATE TABLE staging.leads (
    staging_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    raw_id BIGINT REFERENCES raw.crm_lead_records(raw_id),
    lead_id VARCHAR(100),
    name VARCHAR(255),
    phone VARCHAR(10),
    email VARCHAR(255),
    utm_campaign VARCHAR(255),
    created_at TIMESTAMPTZ,
    is_valid BOOLEAN DEFAULT TRUE,
    rejection_reason TEXT,
    processed_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- 3. Clean store orders
CREATE TABLE staging.orders (
    staging_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    raw_id BIGINT REFERENCES raw.store_order_records(raw_id),
    order_id VARCHAR(100),
    customer_phone VARCHAR(10),
    order_ts TIMESTAMPTZ,
    status VARCHAR(30),
    payment_mode VARCHAR(50),
    total_amount NUMERIC(14,2),
    is_valid BOOLEAN DEFAULT TRUE,
    rejection_reason TEXT,
    processed_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- 4. Clean order items
CREATE TABLE staging.order_items (
    staging_item_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    raw_id BIGINT REFERENCES raw.store_order_records(raw_id),
    order_id VARCHAR(100),
    sku VARCHAR(100),
    qty INTEGER,
    unit_price NUMERIC(14,2),
    is_valid BOOLEAN DEFAULT TRUE,
    rejection_reason TEXT,
    processed_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

SELECT table_schema, table_name
FROM information_schema.tables
WHERE table_schema = 'staging'
ORDER BY table_name;



-- ==========================================
-- 1. CAMPAIGN DIMENSION
-- ==========================================

CREATE TABLE IF NOT EXISTS public.dim_campaign (
    campaign_key BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    campaign_id VARCHAR(100) NOT NULL UNIQUE,
    platform VARCHAR(50) NOT NULL,
    clean_campaign_name VARCHAR(255) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);


-- ==========================================
-- 2. CUSTOMER DIMENSION
-- ==========================================

CREATE TABLE IF NOT EXISTS public.dim_customer (
    customer_key BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    phone VARCHAR(10) NOT NULL UNIQUE,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_customer_phone
        CHECK (phone ~ '^[0-9]{10}$')
);


-- ==========================================
-- 3. DAILY AD SPEND FACT
-- ==========================================

CREATE TABLE IF NOT EXISTS public.fact_ad_spend_daily (
    spend_key BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    campaign_key BIGINT NOT NULL
        REFERENCES public.dim_campaign(campaign_key),
    ad_date DATE NOT NULL,
    spend NUMERIC(14,2) NOT NULL CHECK (spend >= 0),
    impressions BIGINT NOT NULL CHECK (impressions >= 0),
    clicks BIGINT NOT NULL CHECK (
        clicks >= 0 AND clicks <= impressions
    ),
    updated_at TIMESTAMPTZ,
    CONSTRAINT uq_campaign_daily
        UNIQUE (campaign_key, ad_date)
);


-- ==========================================
-- 4. LEADS FACT
-- ==========================================

CREATE TABLE IF NOT EXISTS public.fact_leads (
    lead_key BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    lead_id VARCHAR(100) NOT NULL UNIQUE,
    customer_key BIGINT
        REFERENCES public.dim_customer(customer_key),
    campaign_key BIGINT
        REFERENCES public.dim_campaign(campaign_key),
    lead_name VARCHAR(255),
    email VARCHAR(255),
    created_at TIMESTAMPTZ NOT NULL,
    utm_campaign_raw VARCHAR(255)
);


-- ==========================================
-- 5. ORDERS FACT
-- ==========================================

CREATE TABLE IF NOT EXISTS public.fact_orders (
    order_key BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    order_id VARCHAR(100) NOT NULL UNIQUE,
    customer_key BIGINT
        REFERENCES public.dim_customer(customer_key),
    order_ts TIMESTAMPTZ NOT NULL,
    status VARCHAR(30) NOT NULL,
    payment_mode VARCHAR(50),
    total_amount NUMERIC(14,2) NOT NULL
        CHECK (total_amount >= 0),
    updated_at TIMESTAMPTZ,
    CONSTRAINT chk_order_status
        CHECK (status IN (
            'PENDING',
            'PLACED',
            'SHIPPED',
            'DELIVERED',
            'CANCELLED',
            'RETURNED'
        ))
);


-- ==========================================
-- 6. ORDER ITEMS FACT
-- ==========================================

CREATE TABLE IF NOT EXISTS public.fact_order_items (
    item_key BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    order_key BIGINT NOT NULL
        REFERENCES public.fact_orders(order_key),
    sku VARCHAR(100) NOT NULL,
    qty INTEGER NOT NULL CHECK (qty > 0),
    unit_price NUMERIC(14,2) NOT NULL
        CHECK (unit_price >= 0)
);

-- ==========================================
-- 7. PIPELINE RUNS
-- ==========================================

CREATE TABLE IF NOT EXISTS public.pipeline_runs (
    run_id UUID PRIMARY KEY,
    start_time TIMESTAMPTZ NOT NULL,
    end_time TIMESTAMPTZ,
    rows_read BIGINT NOT NULL DEFAULT 0,
    rows_loaded BIGINT NOT NULL DEFAULT 0,
    rows_rejected BIGINT NOT NULL DEFAULT 0,
    duplicates_removed BIGINT NOT NULL DEFAULT 0,
    source_counts JSONB,
    status VARCHAR(20) NOT NULL DEFAULT 'RUNNING',

    CONSTRAINT chk_pipeline_counts CHECK (
        rows_read >= 0
        AND rows_loaded >= 0
        AND rows_rejected >= 0
        AND duplicates_removed >= 0
    ),

    CONSTRAINT chk_pipeline_status
        CHECK (status IN ('RUNNING', 'SUCCESS', 'FAILED'))
);


-- ==========================================
-- 8. REJECTED ROWS
-- ==========================================

CREATE TABLE IF NOT EXISTS public.rejected_rows (
    rejection_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    run_id UUID NOT NULL
        REFERENCES public.pipeline_runs(run_id),
    source VARCHAR(50) NOT NULL,
    record_identifier VARCHAR(100),
    rule_name VARCHAR(100) NOT NULL,
    reason TEXT NOT NULL,
    original_data JSONB NOT NULL,
    rejected_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_leads_customer
ON public.fact_leads(customer_key);

CREATE INDEX IF NOT EXISTS idx_leads_campaign
ON public.fact_leads(campaign_key);

CREATE INDEX IF NOT EXISTS idx_orders_customer
ON public.fact_orders(customer_key);

CREATE INDEX IF NOT EXISTS idx_orders_timestamp
ON public.fact_orders(order_ts);

CREATE INDEX IF NOT EXISTS idx_order_items_order
ON public.fact_order_items(order_key);

CREATE INDEX IF NOT EXISTS idx_rejected_run
ON public.rejected_rows(run_id);


SELECT
    table_name,
    table_type
FROM information_schema.tables
WHERE table_schema = 'public'
AND table_name IN (
    'dim_campaign',
    'dim_customer',
    'fact_ad_spend_daily',
    'fact_leads',
    'fact_orders',
    'fact_order_items',
    'pipeline_runs',
    'rejected_rows'
)
ORDER BY table_name;

SELECT
    tc.table_name,
    tc.constraint_name,
    tc.constraint_type,
    kcu.column_name
FROM information_schema.table_constraints tc
LEFT JOIN information_schema.key_column_usage kcu
    ON tc.constraint_name = kcu.constraint_name
    AND tc.table_schema = kcu.table_schema
WHERE tc.table_schema = 'public'
AND tc.constraint_type IN ('PRIMARY KEY', 'FOREIGN KEY', 'UNIQUE')
ORDER BY tc.table_name, tc.constraint_type;

SELECT schemaname, tablename
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY tablename;
