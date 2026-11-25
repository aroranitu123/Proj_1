
# Problem 1: The Unified Marketing Pipeline

**Horrazon AI – Round 2 Technical Assessment**  
**Role:** Data Engineering Intern  
**Candidate:** Nitya Arora  
**Project:** Unified Marketing Data Pipeline  
**Database:** PostgreSQL

---

## 1. Project Overview

The Unified Marketing Pipeline is a Python-based ETL pipeline designed to integrate advertising, CRM, and e-commerce store data into a central PostgreSQL database.

The project addresses the challenge of working with multiple data sources that have inconsistent formats, duplicate records, missing values, and data quality issues.

The pipeline implements a three-layer architecture:

- **Raw Layer:** Preserves source data as received.
- **Staging Layer:** Performs data cleaning, standardisation, and validation.
- **Final Layer:** Stores structured, relational data ready for analytics and downstream applications.

### Key Objectives

- Integrate multiple heterogeneous data sources.
- Implement incremental data ingestion.
- Maintain idempotency across pipeline executions.
- Identify and isolate invalid records.
- Maintain data quality and reconciliation checks.
- Prepare reliable data for dashboards, ML models, and AI agents.

---

## 2. Technology Stack

| Technology | Purpose |
|---|---|
| Python 3.9+ | ETL development |
| PostgreSQL | Relational database |
| [API framework] | Mock advertising API |
| Pandas | [Actual usage] |
| Requests | API integration |
| Pytest | Unit and integration testing |
| [Other tools] | [Actual usage] |

---

## 3. Architecture

Insert your actual architecture diagram here.

The pipeline follows the following workflow:

```text
Advertising API       CRM CSV       Store JSON
       |                 |               |
       +-----------------+---------------+
                         |
                         v
                  EXTRACTION
               Pagination / Retries
                         |
                         v
                    RAW LAYER
              Original Source Records
                         |
                         v
                  STAGING LAYER
             Cleaning / Transformation
                  Data Validation
                         |
                         v
                   FINAL LAYER
                    PostgreSQL
                         |
             +-----------+-----------+
             |           |           |
          Analytics      ML       AI Agents
```

---

## 4. Data Sources

### 4.1 Advertising Platform API

- Source: Mock REST API representing Meta Ads and Google Ads.
- Format: Paginated JSON.
- Important attributes: campaign_id, campaign_name, platform, date, spend, impressions, clicks and updated_at.
- Extraction: [Describe your pagination and retry implementation.]

### 4.2 CRM Leads

- Source: Daily CSV exports.
- Important attributes: lead_id, name, phone, email, utm_campaign and created_at.
- Processing: [Describe your CSV ingestion, encoding handling and deduplication.]

### 4.3 Store Orders

- Source: JSON exports.
- Important attributes: order_id, customer_phone, order_ts, status, payment_mode, total_amount and items.
- Processing: [Describe your field mapping, timestamp normalisation and order processing.]

---

## 5. Data Processing Architecture

### Raw Layer

Purpose:
- Preserve incoming source records.
- Maintain ingestion metadata.
- Track pipeline execution using run_id and loaded_at.
- Retain source information for auditing and debugging.

### Staging Layer

Purpose:
- Standardise data types and formats.
- Normalise campaign names and phone numbers.
- Convert monetary values into a consistent unit.
- Resolve duplicate records.
- Validate business rules.
- Identify unmatched records.

### Final Layer

The final PostgreSQL layer contains:

| Table | Purpose |
|---|---|
| dim_campaign | Campaign master records |
| fact_ad_spend_daily | Daily campaign performance |
| dim_customer | Standardised customer records |
| fact_leads | CRM lead records |
| fact_orders | Order-level information |
| fact_order_items | Individual order items |
| rejected_rows | Invalid records and rejection reasons |
| pipeline_runs | Pipeline execution metadata |

---

## 6. Data Quality and Validation

Document the validation rules actually implemented.

| Validation | Expected behaviour |
|---|---|
| Negative spend | Reject invalid values |
| Clicks greater than impressions | Reject invalid records |
| Invalid phone numbers | Reject or flag records |
| Invalid email addresses | Reject or flag records |
| Invalid order status | Standardise or reject |
| Quantity less than or equal to zero | Reject |
| Duplicate order IDs | Retain latest version |
| Duplicate lead IDs | Retain one record |
| Invalid campaign mapping | Preserve as unmatched |
| Order total mismatch | Validate against item totals |

**Rejected Records:** [Insert actual rejected record count and breakdown.]

---

## 7. Incremental Loading and Idempotency

Explain your actual implementation:

- Advertising API: [Watermark implementation.]
- Store orders: [Updated timestamp tracking.]
- CRM: [Processed file tracking.]
- Deduplication: [Primary key/upsert strategy.]
- Idempotency: [How you verified repeated execution.]

### Expected behaviour

Repeated executions using identical source data should not introduce duplicate records or change previously reconciled totals.

---

## 8. Database Design

Document:
- Primary keys.
- Foreign keys.
- Unique constraints.
- Relationships between campaigns, customers, leads and orders.
- Monetary data types.
- Indexes implemented.

Insert your actual ER diagram here.

---

## 9. Pipeline Execution

### Prerequisites

- Python 3.9 or higher
- PostgreSQL
- pip

### Installation

```bash
git clone <YOUR_REPOSITORY_URL>
cd <PROJECT_DIRECTORY>

python -m venv venv
```

Activate the environment and install dependencies:

```bash
pip install -r requirements.txt
```

Configure your database credentials using the environment variables documented in your project.

### Run the Pipeline

```bash
<YOUR_ACTUAL_PIPELINE_COMMAND>
```

### Run Tests

```bash
pytest
```

Replace these placeholders with the exact commands supported by your repository.

---

## 10. Testing

Document your actual tests.

| Test | What it verifies | Result |
|---|---|---|
| Phone normalisation | Consistent phone format | [PASS/FAIL] |
| Currency conversion | Paise to rupees | [PASS/FAIL] |
| Deduplication | Latest record retained | [PASS/FAIL] |
| Date parsing | Date standardisation | [PASS/FAIL] |
| Validation | Invalid records detected | [PASS/FAIL] |
| Idempotency | Two runs produce identical results | [PASS/FAIL] |

---

## 11. Control Totals and Execution Summary

Insert actual results from your pipeline.

| Metric | Actual result |
|---|---:|
| Total rows read | [Value] |
| Rows loaded | [Value] |
| Rows rejected | [Value] |
| Duplicates removed | [Value] |
| Total advertising spend | [Value] |
| Total order value | [Value] |
| Pipeline execution status | [Value] |

Reconciliation:

```text
Rows Read = Rows Loaded
          + Rows Rejected
          + Duplicates Removed
```

---

## 12. Design Decisions

Document the reasoning behind your implementation.

Examples of decisions to discuss:

- Why a three-layer architecture was selected.
- Why PostgreSQL was used.
- Why upserts were preferred over blind inserts.
- How incremental extraction reduces unnecessary processing.
- Why invalid records are preserved instead of silently discarded.
- Why NUMERIC is preferred over FLOAT for monetary values.

---

## 13. Known Limitations

[Document features that are incomplete, assumptions made, and limitations of the current implementation.]

---

## 14. Future Improvements

Potential extensions:

- Automated scheduling using Apache Airflow.
- Docker Compose-based deployment.
- Historical backfill support.
- Pipeline freshness monitoring.
- Improved observability and alerting.
- Campaign history tracking.
- Scalable ingestion for larger datasets.

---

## 15. Conclusion

[Summarise what your implementation successfully achieves, the engineering concepts demonstrated, and what you would improve in a production deployment.]

---

**Horrazon AI – Round 2 Technical Assessment**  
**Problem 1: The Unified Marketing Pipeline**
