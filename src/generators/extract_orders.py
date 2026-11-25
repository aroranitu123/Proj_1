
import os
import json
import uuid
import pg8000

from pathlib import Path
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()

# Project configuration
PROJECT_ROOT = Path(__file__).resolve().parents[2]

JSON_FILE = (
    PROJECT_ROOT
    / "data"
    / "raw"
    / "orders"
    / "store_orders.json"
)

SOURCE_FILE = "store_orders.json"
BATCH_SIZE = 500


def get_connection():

    return pg8000.connect(
        host=os.getenv("DB_HOST"),
        port=int(os.getenv("DB_PORT")),
        database=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD")
    )


def read_json():

    if not JSON_FILE.exists():
        raise FileNotFoundError(
            f"Orders JSON not found: {JSON_FILE}"
        )

    with open(
        JSON_FILE,
        "r",
        encoding="utf-8"
    ) as file:

        data = json.load(file)

    if "orders" not in data:
        raise ValueError(
            "Invalid JSON structure: orders key missing"
        )

    return data["orders"]


def create_pipeline_run(cursor, run_id):

    cursor.execute(
        """
        INSERT INTO public.pipeline_runs (
            run_id,
            start_time,
            status
        )
        VALUES (%s::uuid, %s, 'RUNNING')
        """,
        (
            run_id,
            datetime.now(timezone.utc)
        )
    )


def load_raw_records(cursor, run_id, records):

    insert_query = """
        INSERT INTO raw.store_order_records (
            run_id,
            source_file,
            payload
        )
        VALUES (
            %s::uuid,
            %s,
            %s::jsonb
        )
    """

    values = [
        (
            run_id,
            SOURCE_FILE,
            json.dumps(record, ensure_ascii=False)
        )
        for record in records
    ]

    cursor.executemany(insert_query, values)


def update_pipeline_run(
    cursor,
    run_id,
    rows_read,
    rows_loaded,
    status
):

    cursor.execute(
        """
        UPDATE public.pipeline_runs
        SET
            end_time = %s,
            rows_read = %s,
            rows_loaded = %s,
            source_counts = %s::jsonb,
            status = %s
        WHERE run_id = %s::uuid
        """,
        (
            datetime.now(timezone.utc),
            rows_read,
            rows_loaded,
            json.dumps({"store_orders": rows_loaded}),
            status,
            run_id
        )
    )


def extract_orders():

    run_id = str(uuid.uuid4())

    rows_read = 0
    rows_loaded = 0

    conn = None
    cursor = None

    print("=" * 50)
    print("HORRAZON STORE ORDERS EXTRACTOR")
    print("=" * 50)

    print("Pipeline Run ID:", run_id)

    try:

        # Read source JSON
        records = read_json()

        rows_read = len(records)

        print("\nJSON records found:", rows_read)

        # Connect to PostgreSQL
        conn = get_connection()
        cursor = conn.cursor()

        # Register pipeline execution
        create_pipeline_run(cursor, run_id)
        conn.commit()

        print("Pipeline run registered.")

        # Batch loading
        for start in range(0, rows_read, BATCH_SIZE):

            batch = records[start:start + BATCH_SIZE]

            print(
                f"\nLoading batch "
                f"{start // BATCH_SIZE + 1}..."
            )

            load_raw_records(
                cursor,
                run_id,
                batch
            )

            conn.commit()

            rows_loaded += len(batch)

            print("Records loaded:", rows_loaded)

        # Mark execution successful
        update_pipeline_run(
            cursor,
            run_id,
            rows_read,
            rows_loaded,
            "SUCCESS"
        )

        conn.commit()

        print("\n" + "=" * 50)
        print("STORE ORDERS EXTRACTION COMPLETED")
        print("=" * 50)

        print("Run ID:", run_id)
        print("Rows read:", rows_read)
        print("Rows loaded:", rows_loaded)

    except Exception as error:

        print("\nSTORE ORDERS EXTRACTION FAILED:", error)

        if conn is not None:

            conn.rollback()

            try:

                if cursor is None:
                    cursor = conn.cursor()

                update_pipeline_run(
                    cursor,
                    run_id,
                    rows_read,
                    rows_loaded,
                    "FAILED"
                )

                conn.commit()

            except Exception as logging_error:

                print("Pipeline logging failed:", logging_error)
                conn.rollback()

        raise

    finally:

        if cursor is not None:
            cursor.close()

        if conn is not None:
            conn.close()


if __name__ == "__main__":
    extract_orders()
