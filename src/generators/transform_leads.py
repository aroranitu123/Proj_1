
import os
import json
import re
from collections import Counter
from datetime import datetime

import pg8000.dbapi
from dotenv import load_dotenv

load_dotenv()


# ==========================================
# DATABASE CONNECTION
# ==========================================

def get_connection():
    return pg8000.dbapi.connect(
        host=os.getenv("DB_HOST"),
        port=int(os.getenv("DB_PORT", 5432)),
        database=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD")
    )


# ==========================================
# HELPER FUNCTIONS
# ==========================================

VALID_STATUSES = [
    "New",
    "Contacted",
    "Qualified",
    "Converted",
    "Lost"
]


def parse_timestamp(value):

    if not value:
        return None

    try:
        return datetime.fromisoformat(
            str(value).replace("Z", "+00:00")
        )
    except ValueError:
        return None


def validate_email(email):

    if not email:
        return False

    pattern = r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$"

    return bool(re.fullmatch(pattern, email.strip()))


def validate_phone(phone):

    if not phone:
        return False

    digits = re.sub(r"\D", "", phone)

    return 7 <= len(digits) <= 15


# ==========================================
# STEP 1: EXTRACT RAW LEADS
# ==========================================

def extract_leads(cursor):

    cursor.execute("""
        SELECT raw_id, payload
        FROM raw.crm_lead_records
        ORDER BY raw_id
    """)

    records = cursor.fetchall()

    print(f"RAW CRM records fetched: {len(records)}")

    return records


# ==========================================
# STEP 2: TRANSFORM AND VALIDATE
# ==========================================

def validate_leads(records):

    transformed = []

    # Identify duplicate lead IDs across the dataset

    lead_ids = []

    for raw_id, payload in records:

        if isinstance(payload, str):
            payload = json.loads(payload)

        lead_ids.append(payload.get("lead_id"))

    id_counts = Counter(
        lead_id for lead_id in lead_ids if lead_id
    )

    for raw_id, payload in records:

        if isinstance(payload, str):
            payload = json.loads(payload)

        reasons = []

        lead_id = payload.get("lead_id")

        first_name = payload.get("first_name")
        last_name = payload.get("last_name")

        email = payload.get("email")
        phone = payload.get("phone")

        company = payload.get("company")
        job_title = payload.get("job_title")
        industry = payload.get("industry")
        country = payload.get("country")

        lead_source = payload.get("lead_source")
        status = payload.get("status")

        created_at = parse_timestamp(
            payload.get("created_at")
        )

        updated_at = parse_timestamp(
            payload.get("updated_at")
        )

        # Normalize text fields

        first_name = first_name.strip() if isinstance(first_name, str) else None
        last_name = last_name.strip() if isinstance(last_name, str) else None

        email = email.strip().lower() if isinstance(email, str) else None
        phone = phone.strip() if isinstance(phone, str) else None

        company = company.strip() if isinstance(company, str) else None
        job_title = job_title.strip() if isinstance(job_title, str) else None
        industry = industry.strip() if isinstance(industry, str) else None
        country = country.strip() if isinstance(country, str) else None
        lead_source = lead_source.strip() if isinstance(lead_source, str) else None

        status = status.strip() if isinstance(status, str) else None

        # Required field validation

        if not lead_id:
            reasons.append("Missing lead_id")

        elif id_counts[lead_id] > 1:
            reasons.append("Duplicate lead_id")

        if not first_name:
            reasons.append("Missing first_name")

        if not last_name:
            reasons.append("Missing last_name")

        if not email:
            reasons.append("Missing email")

        elif not validate_email(email):
            reasons.append("Invalid email")

        if not phone:
            reasons.append("Missing phone")

        elif not validate_phone(phone):
            reasons.append("Invalid phone")

        if not status or status not in VALID_STATUSES:
            reasons.append("Invalid lead status")

        if created_at is None:
            reasons.append("Invalid created_at")

        # Build combined name

        name = " ".join(
            part for part in [first_name, last_name] if part
        )

        is_valid = len(reasons) == 0

        transformed.append((
            raw_id,
            lead_id,
            name or None,
            phone,
            email,
            None,  # utm_campaign is not present in RAW source
            created_at,
            is_valid,
            "; ".join(reasons) if reasons else None,
            datetime.now().astimezone(),
            first_name,
            last_name,
            company,
            job_title,
            industry,
            country,
            lead_source,
            status,
            updated_at
        ))

    return transformed


# ==========================================
# STEP 3: LOAD INTO STAGING
# ==========================================

def load_leads(cursor, records):

    query = """
        INSERT INTO staging.leads (
            raw_id,
            lead_id,
            name,
            phone,
            email,
            utm_campaign,
            created_at,
            is_valid,
            rejection_reason,
            processed_at,
            first_name,
            last_name,
            company,
            job_title,
            industry,
            country,
            lead_source,
            status,
            updated_at
        )
        VALUES (
            %s, %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s
        )
    """

    # Full refresh of CRM staging table

    cursor.execute("DELETE FROM staging.leads")

    batch_size = 500

    for i in range(0, len(records), batch_size):

        batch = records[i:i + batch_size]

        cursor.executemany(query, batch)

        print(
            f"Leads processed: "
            f"{min(i + batch_size, len(records))}/{len(records)}"
        )


# ==========================================
# STEP 4: SUMMARY
# ==========================================

def print_summary(records):

    valid = sum(1 for r in records if r[7] is True)

    rejected = len(records) - valid

    print("\n========================================")
    print("CRM LEADS TRANSFORMATION COMPLETED")
    print("========================================")

    print(f"Total leads: {len(records)}")
    print(f"Valid leads: {valid}")
    print(f"Rejected leads: {rejected}")


# ==========================================
# MAIN PIPELINE
# ==========================================

def transform_leads():

    connection = get_connection()

    try:

        cursor = connection.cursor()

        print("\nHORRAZON CRM LEADS TRANSFORMATION")
        print("========================================")

        print("\nSTEP 1: Extracting RAW records...")

        raw_records = extract_leads(cursor)

        print("\nSTEP 2: Transforming and validating...")

        transformed = validate_leads(raw_records)

        print(f"Leads transformed: {len(transformed)}")

        print("\nSTEP 3: Loading into staging...")

        load_leads(cursor, transformed)

        connection.commit()

        print_summary(transformed)

        cursor.close()

    except Exception:

        connection.rollback()
        raise

    finally:

        connection.close()


if __name__ == "__main__":
    transform_leads()
