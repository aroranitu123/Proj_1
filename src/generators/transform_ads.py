
import os
import json
from decimal import Decimal, InvalidOperation
from datetime import datetime, date

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

def parse_number(value):
    if value is None:
        return None

    try:
        cleaned = str(value).replace("$", "").replace(",", "").strip()
        return Decimal(cleaned)
    except (InvalidOperation, ValueError):
        return None


def parse_integer(value):
    number = parse_number(value)

    if number is None:
        return None

    if number != number.to_integral_value():
        return None

    return int(number)


def parse_date(value):
    if not value:
        return None

    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def parse_timestamp(value):
    if not value:
        return None

    try:
        return datetime.fromisoformat(
            str(value).replace("Z", "+00:00")
        )
    except ValueError:
        return None


# ==========================================
# STEP 1: EXTRACT RAW ADS
# ==========================================

def extract_ads(cursor):

    cursor.execute("""
        SELECT raw_id, payload
        FROM raw.ads_api_records
        ORDER BY raw_id
    """)

    records = cursor.fetchall()

    print(f"RAW advertising records fetched: {len(records)}")

    return records


# ==========================================
# STEP 2: TRANSFORM AND VALIDATE
# ==========================================

def validate_ads(records):

    transformed = []

    for raw_id, payload in records:

        if isinstance(payload, str):
            payload = json.loads(payload)

        reasons = []

        campaign_id = payload.get("campaign_id")
        campaign_name = payload.get("campaign_name")
        platform = payload.get("platform")

        ad_date = parse_date(payload.get("ad_date"))
        spend = parse_number(payload.get("spend"))

        impressions = parse_integer(
            payload.get("impressions")
        )

        clicks = parse_integer(
            payload.get("clicks")
        )

        updated_at = parse_timestamp(
            payload.get("updated_at")
        )

        # Required field validation

        if not campaign_id:
            reasons.append("Missing campaign_id")

        if not campaign_name:
            reasons.append("Missing campaign_name")

        if not platform:
            reasons.append("Missing platform")

        if ad_date is None:
            reasons.append("Invalid ad_date")

        if spend is None:
            reasons.append("Invalid spend")

        elif spend < 0:
            reasons.append("Negative spend")

        if impressions is None:
            reasons.append("Invalid impressions")

        elif impressions < 0:
            reasons.append("Negative impressions")

        if clicks is None:
            reasons.append("Invalid clicks")

        elif clicks < 0:
            reasons.append("Negative clicks")

        if (
            clicks is not None
            and impressions is not None
            and clicks > impressions
        ):
            reasons.append("Clicks exceed impressions")

        is_valid = len(reasons) == 0

        transformed.append((
            raw_id,
            campaign_id,
            campaign_name,
            platform,
            ad_date,
            spend,
            impressions,
            clicks,
            updated_at,
            is_valid,
            "; ".join(reasons) if reasons else None,
            datetime.now().astimezone()
        ))

    return transformed


# ==========================================
# STEP 3: LOAD INTO STAGING
# ==========================================

def load_ads(cursor, records):

    query = """
        INSERT INTO staging.ads (
            raw_id,
            campaign_id,
            campaign_name,
            platform,
            ad_date,
            spend,
            impressions,
            clicks,
            updated_at,
            is_valid,
            rejection_reason,
            processed_at
        )
        VALUES (
            %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s, %s
        )
    """

    # Full refresh of advertising staging table
    cursor.execute("DELETE FROM staging.ads")

    batch_size = 500

    for i in range(0, len(records), batch_size):

        batch = records[i:i + batch_size]

        cursor.executemany(query, batch)

        print(
            f"Ads processed: "
            f"{min(i + batch_size, len(records))}/{len(records)}"
        )


# ==========================================
# STEP 4: SUMMARY
# ==========================================

def print_summary(records):

    valid = sum(1 for r in records if r[9] is True)

    rejected = len(records) - valid

    print("\n========================================")
    print("ADVERTISING TRANSFORMATION COMPLETED")
    print("========================================")

    print(f"Total ads: {len(records)}")
    print(f"Valid ads: {valid}")
    print(f"Rejected ads: {rejected}")


# ==========================================
# MAIN PIPELINE
# ==========================================

def transform_ads():

    connection = get_connection()

    try:

        cursor = connection.cursor()

        print("\nHORRAZON ADVERTISING TRANSFORMATION")
        print("========================================")

        print("\nSTEP 1: Extracting RAW records...")

        raw_records = extract_ads(cursor)

        print("\nSTEP 2: Transforming and validating...")

        transformed = validate_ads(raw_records)

        print(f"Ads transformed: {len(transformed)}")

        print("\nSTEP 3: Loading into staging...")

        load_ads(cursor, transformed)

        connection.commit()

        print_summary(transformed)

        cursor.close()

    except Exception:

        connection.rollback()
        raise

    finally:

        connection.close()


if __name__ == "__main__":
    transform_ads()
