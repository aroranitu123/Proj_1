# Horrazon – Unified Marketing Pipeline

**Data Engineering Technical Assessment | Round 2**

A Python and PostgreSQL-based data engineering pipeline designed to integrate advertising campaign data, e-commerce orders, and CRM leads into a unified analytical data model.

---

## 1. Project Overview

The Unified Marketing Pipeline consolidates data from three independent sources:

- **Advertising API:** Campaign and advertising performance data.
- **Store Orders:** E-commerce transaction and order-item data in JSON format.
- **CRM Leads:** Customer and lead information in CSV format.

The objective is to transform heterogeneous source data into a structured, validated, and analysis-ready PostgreSQL database.

The pipeline follows a three-layer architecture:

1. **Raw Layer:** Preserves source data in its original form.
2. **Staging Layer:** Performs data cleaning, standardisation, validation, and deduplication.
3. **Gold Layer:** Stores structured analytical tables for reporting and downstream analysis.

## 2. Architecture

### Three-Layer Data Architecture

| Layer | Purpose |
|---|---|
| Raw | Stores source records as received, along with run identifiers and ingestion metadata. |
| Staging | Handles type conversion, data cleaning, standardisation, validation, and deduplication. |
| Gold | Contains final dimension tables, fact tables, and supporting operational tables. |

### Pipeline Flow

```text
              SOURCE SYSTEMS
                    |
       +------------+------------+
       |            |            |
     Ads API    Store Orders   CRM Leads
       |            |            |
       +------------+------------+
                    |
                    v
              RAW LAYER
          Original source records
                    |
                    v
            STAGING LAYER
       Cleaning and transformation
       Standardisation and validation
       Deduplication and rejection
                    |
                    v
              GOLD LAYER
       Dimensions and Fact Tables
                    |
                    v
          ANALYTICAL CONSUMPTION
```

## 3. Technology Stack

| Technology | Purpose |
|---|---|
| Python | Extraction and transformation logic |
| PostgreSQL | Relational database and storage |
| pg8000 | Python–PostgreSQL connectivity |
| Requests | Advertising API integration |
| JSON | Store orders ingestion |
| CSV | CRM lead ingestion |
| python-dotenv | Environment configuration |
| Pytest | Unit and integration testing |

## 4. Source Systems

### 4.1 Advertising API

The advertising API provides campaign and advertisement performance data.

Extraction capabilities include:
- Paginated API requests using `skip` and `limit`.
- Configurable request timeout.
- Retry handling for transient HTTP failures.
- Exponential backoff between retries.
- Raw response preservation.

**API Endpoint:** `/ads`

### 4.2 Store Orders

The store orders source provides e-commerce transaction data in JSON format.

The records contain information such as:
- Order ID
- Customer ID
- Order date
- Order status
- Payment method
- Shipping information
- Total order amount
- Individual order items

### 4.3 CRM Leads

The CRM source contains customer and lead information in CSV format.

The data supports customer identification, lead analysis, and campaign attribution.

## 5. Database Design

The Gold layer uses a dimensional model consisting of dimension tables, fact tables, and operational tables.

### Dimension Tables

**dim_customer**

Stores customer-level information.

Key attributes:
- customer_id (Primary Key)
- phone
- email
- customer_name
- country
- created_date

**dim_campaign**

Stores advertising campaign information.

Key attributes:
- campaign_id (Primary Key)
- utm_campaign
- campaign_name
- platform
- campaign_status
- start_date
- end_date

### Fact Tables

**fact_ad_spend_daily**

Stores daily advertising performance metrics.

Key attributes:
- ad_spend_id (Primary Key)
- campaign_id (Foreign Key)
- spend_date
- impressions
- clicks
- spend
- currency

**fact_leads**

Stores lead-level records and their associated customer and campaign references.

Key attributes:
- lead_id (Primary Key)
- campaign_id (Foreign Key)
- customer_id (Foreign Key)
- lead_date
- utm_campaign
- lead_source
- status

**fact_orders**

Stores e-commerce transaction information.

Key attributes:
- order_id (Primary Key)
- customer_id (Foreign Key)
- order_date
- order_status
- payment_method
- shipping_city
- shipping_country
- total_amount

**fact_order_items**

Stores individual products associated with each order.

Key attributes:
- order_item_id (Primary Key)
- order_id (Foreign Key)
- sku
- product_name
- quantity
- unit_price
- line_total

### Supporting Tables

**pipeline_runs**

Maintains pipeline execution information, including:
- run_id
- start_time
- end_time
- rows_read
- rows_loaded
- rows_rejected
- duplicates_removed
- source_counts
- status

**rejected_rows**

Maintains records that fail data quality checks, including:
- rejection_id
- run_id
- source_table
- record_id
- rule_name
- reason
- original_data
- rejected_at

## 6. Data Quality and Standardisation

The pipeline is designed to apply validation and standardisation rules before records enter the final analytical layer.

### Validation Rules

The following checks form the data quality framework:

1. Advertising spend must not be negative.
2. Clicks must not exceed impressions.
3. Advertising campaign names must be present.
4. Advertising platform must be valid.
5. Phone numbers must follow a standardised format.
6. Email addresses must follow a valid format.
7. Lead IDs must be unique.
8. Order IDs must be unique.
9. Order quantities must be greater than zero.
10. Unit prices must not be negative.
11. Order totals must reconcile with their item totals within ₹1.
12. Order statuses must belong to an allowed set.

Invalid records are retained in the rejection tracking mechanism rather than silently discarded.

### Standardisation

The transformation layer addresses:

- Date and timezone consistency.
- Conversion of paise into rupees where applicable.
- Conversion of advertising spend text into numeric values.
- Phone number normalisation.
- Campaign name standardisation.
- Order and lead status standardisation.
- Mapping renamed source fields to consistent target names.

## 7. Data Relationships

The Gold layer establishes relationships between customers, campaigns, leads, and transactions.

| Relationship | Cardinality |
|---|---|
| dim_campaign → fact_ad_spend_daily | One-to-many |
| dim_campaign → fact_leads | One-to-many |
| dim_customer → fact_leads | One-to-many |
| dim_customer → fact_orders | One-to-many |
| fact_orders → fact_order_items | One-to-many |

Leads are linked to campaigns through `utm_campaign`.

Leads and orders are linked to customers using phone-based matching.

Unmatched records are retained and accounted for rather than being automatically dropped.

## 8. Incremental Loading and Idempotency

Incremental processing is intended to minimise unnecessary reprocessing.

The design includes:

- Watermark tracking for supported timestamp-based sources.
- Processing only previously unprocessed CRM files.
- Primary-key-based record identification.
- Upsert-based loading to prevent duplicate final records.
- Reconciliation of repeated pipeline executions.

**Source limitations:** The documented Ads API exposes pagination but does not document a server-side `updated_at` filter. The supplied Orders JSON sample contains `order_date` but does not show an `updated_at` field. Therefore, true update-based incremental extraction for these sources requires additional source metadata or an explicitly documented alternative strategy.

## 9. Control Totals and Pipeline Monitoring

Pipeline execution is tracked using the `pipeline_runs` table.

The reconciliation principle is:

**Rows Read = Rows Loaded + Rows Rejected + Duplicates Removed**

Previously recorded source-level control totals:

| Source | Rows Read | Valid / Loaded | Rejected |
|---|---:|---:|---:|
| Ads | 2,700 | 2,656 | 44 |
| CRM Leads | 1,500 | 1,209 | 291 |
| Orders | 1,197 | 1,181 | 16 |
| Order Items | 2,974 | 2,960 | 14 |
| **Total** | **8,371** | **8,006** | **365** |

These figures represent the recorded validation results and should be distinguished from automatically generated execution metrics.

The pipeline monitoring design supports:
- Run-level execution tracking.
- Source-level record counts.
- Rejected record tracking.
- Duplicate accounting.
- Execution status and timestamps.

## 10. Testing

The testing strategy uses Pytest.

The required unit-test coverage includes:

| Test | Objective |
|---|---|
| Phone cleaning | Verify phone number normalisation |
| Paise conversion | Verify monetary unit conversion |
| Deduplication | Verify latest-record selection |
| Validation | Verify rejection of invalid records |
| Date parsing | Verify date and timezone handling |
| Idempotency | Verify consistent results across repeated runs |

Run the test suite using:

```bash
python -m pytest tests/ -v
```

## 11. Project Setup

### Prerequisites

- Python 3.10 or later
- PostgreSQL
- pip
- Access to the Horrazon Advertising API
- Git

### Step 1: Clone the Repository

```bash
git clone <repository-url>
cd <project-folder>
```

### Step 2: Create a Virtual Environment

```bash
python -m venv venv
```

Activate it on Windows:

```powershell
.\venv\Scripts\activate
```

### Step 3: Install Dependencies

```bash
pip install -r requirements.txt
```

### Step 4: Configure Environment Variables

Create a `.env` file in the project root:

```env
DB_HOST=localhost
DB_PORT=5432
DB_NAME=your_database
DB_USER=your_username
DB_PASSWORD=your_password
```

Do not commit credentials or sensitive configuration files to GitHub.

### Step 5: Start the Advertising API

Start the provided API service and verify that it is accessible at:

```text
http://127.0.0.1:8000
```

### Step 6: Execute Extractors

Run the relevant extractor modules from the project root.

Example:

```bash
python -m src.extractors.extract_ads
```

```bash
python -m src.extractors.extract_orders
```

Use the corresponding CRM extractor module for CRM ingestion.

### Step 7: Run Tests

```bash
python -m pytest tests/ -v
```

## 12. Known Limitations

- The Ads API documentation does not expose a server-side timestamp filter.
- The supplied Orders JSON sample does not expose an order modification timestamp.
- Campaign attribution depends on the availability and consistency of `utm_campaign` in the CRM source.
- Financial reconciliation exceptions require investigation rather than automatic adjustment.
- Incremental loading and idempotency should be verified through repeated execution tests.

## 13. Future Improvements

Potential improvements include:

- Implementing robust source-specific watermark management.
- Introducing overlap windows for timestamp-based extraction.
- Adding automated schema evolution detection.
- Improving API observability and structured logging.
- Adding automated reconciliation reports.
- Expanding unit and integration test coverage.
- Introducing orchestration using Apache Airflow.
- Containerising the complete pipeline using Docker.
- Adding a dashboard for pipeline health and data quality monitoring.

## 14. Conclusion

The Unified Marketing Pipeline demonstrates an end-to-end data engineering workflow involving heterogeneous source ingestion, layered data architecture, relational modelling, data quality validation, and analytical data preparation.

By consolidating advertising, CRM, and transaction data into a unified PostgreSQL model, the project establishes a foundation for campaign attribution, customer analysis, advertising performance monitoring, and business reporting.

---

**Project:** Horrazon – Unified Marketing Pipeline  
**Domain:** Data Engineering  
**Database:** PostgreSQL  
**Language:** Python  
**Testing Framework:** Pytest




