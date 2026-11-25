import os
import json
import time
import uuid
import requests

from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from requests.exceptions import RequestException


API_URL = "http://127.0.0.1:8000/ads"

BATCH_SIZE = 100
MAX_RETRIES = 5
TIMEOUT = 15


def get_connection():
    import pg8000

    return pg8000.connect(
        host=os.getenv("DB_HOST", "localhost"),
        database=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        port=int(os.getenv("DB_PORT", 5432))
    )


def parse_timestamp(value):
    if not value:
        return None

    parsed = datetime.fromisoformat(
        value.replace("Z", "+00:00")
    )

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)

    return parsed.astimezone(timezone.utc)


def get_watermark(cursor):
    cursor.execute("""
        SELECT last_updated_at
        FROM public.etl_watermarks
        WHERE source_name = 'ads'
    """)

    result = cursor.fetchone()
    return result[0] if result else None


def fetch_page(skip, limit):
    for attempt in range(MAX_RETRIES):
        try:
            response = requests.get(
                API_URL,
                params={"skip": skip, "limit": limit},
                timeout=TIMEOUT
            )

            if response.status_code in (429, 500, 502, 503, 504):
                if attempt == MAX_RETRIES - 1:
                    response.raise_for_status()

                retry_after = response.headers.get("Retry-After")

                try:
                    wait = float(retry_after)
                except (TypeError, ValueError):
                    try:
                        wait = (
                            parsedate_to_datetime(retry_after)
                            - datetime.now(timezone.utc)
                        ).total_seconds()
                    except (TypeError, ValueError):
                        wait = 2 ** attempt

                time.sleep(max(0, min(wait, 30)))
                continue

            response.raise_for_status()
            return response.json()

        except RequestException:
            if attempt == MAX_RETRIES - 1:
                raise

            time.sleep(min(2 ** attempt, 30))

    raise RuntimeError("Ads API request failed")


def create_pipeline_run(cursor, run_id):
    cursor.execute("""
        INSERT INTO public.pipeline_runs
            (run_id, start_time, status)
        VALUES (%s, CURRENT_TIMESTAMP, 'RUNNING')
    """, (run_id,))


def load_raw_records(cursor, run_id, page_number, records):
    for record in records:
        cursor.execute("""
            INSERT INTO raw.ads_api_records
                (run_id, source_page, payload)
            VALUES (%s, %s, %s)
        """, (
            run_id,
            page_number,
            json.dumps(record)
        ))


def update_pipeline_run(
    cursor,
    run_id,
    rows_read,
    rows_loaded,
    status
):
    cursor.execute("""
        UPDATE public.pipeline_runs
        SET end_time = CURRENT_TIMESTAMP,
            rows_read = %s,
            rows_loaded = %s,
            status = %s
        WHERE run_id = %s
    """, (
        rows_read,
        rows_loaded,
        status,
        run_id
    ))


def extract_ads():
    run_id = str(uuid.uuid4())
    conn = get_connection()

    rows_read = 0
    rows_loaded = 0

    try:
        cursor = conn.cursor()

        create_pipeline_run(cursor, run_id)
        conn.commit()

        watermark = get_watermark(cursor)
        max_updated_at = watermark

        skip = 0
        page_number = 0

        while True:
            response = fetch_page(skip, BATCH_SIZE)

            records = response.get("data", [])
            total = response.get("total", 0)

            if not records:
                break

            rows_read += len(records)

            incremental_records = []

            for record in records:
                updated_at = parse_timestamp(
                    record.get("updated_at")
                )

                if updated_at is None:
                    continue

                if watermark is None or updated_at > watermark:
                    incremental_records.append(record)

                    if (
                        max_updated_at is None
                        or updated_at > max_updated_at
                    ):
                        max_updated_at = updated_at

            if incremental_records:
                load_raw_records(
                    cursor,
                    run_id,
                    page_number,
                    incremental_records
                )

                rows_loaded += len(incremental_records)

            skip += BATCH_SIZE
            page_number += 1

            if skip >= total:
                break

        # Persist watermark and final run status.
        if max_updated_at is not None:
            cursor.execute("""
                INSERT INTO public.etl_watermarks
                    (source_name, last_updated_at)
                VALUES ('ads', %s)
                ON CONFLICT (source_name)
                DO UPDATE SET
                    last_updated_at = EXCLUDED.last_updated_at
            """, (max_updated_at,))

        update_pipeline_run(
            cursor,
            run_id,
            rows_read,
            rows_loaded,
            "SUCCESS"
        )

        conn.commit()

        print(f"Run ID: {run_id}")
        print(f"Rows read: {rows_read}")
        print(f"Rows loaded: {rows_loaded}")

    except Exception as error:
        conn.rollback()

        cursor = conn.cursor()

        update_pipeline_run(
            cursor,
            run_id,
            rows_read,
            rows_loaded,
            "FAILED"
        )

        conn.commit()
        raise error

    finally:
        conn.close()


if __name__ == "__main__":
    extract_ads()