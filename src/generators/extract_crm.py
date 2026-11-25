
import os
import csv
import json
import uuid
import pg8000

from pathlib import Path
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()

# Project configuration
PROJECT_ROOT = Path(__file__).resolve().parents[2]

CSV_FILE = (
    PROJECT_ROOT
    / "data"
    / "raw"
    / "crm"
    / "crm_leads.csv"
)

SOURCE_FILE = "crm_leads.csv"
BATCH_SIZE = 500


def get_connection():

    return pg8000.connect(
        host=os.getenv("DB_HOST"),
        port=int(os.getenv("DB_PORT")),
        database=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD")
    )


def read_csv():

    if not CSV_FILE.exists():
        raise FileNotFoundError(
            f"CRM CSV not found: {CSV_FILE}"
        )

    with open(
        CSV_FILE,
        "r",
        encoding="utf-8",
        newline=""
    ) as file:

        reader = csv.DictReader(file)

        required_columns = {
            "lead_id",
            "first_name",
            "last_name",
            "email",
            "phone",
            "company",
            "job_title",
            "industry",
            "country",
            "lead_source",
            "status",
            "created_at",
            "updated_at"
        }

        actual_columns = set(reader.fieldnames or [])

        missing = required_columns - actual_columns

        if missing:
            raise ValueError(
                f"Missing CSV columns: {missing}"
            )

        return list(reader)


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
        INSERT INTO raw.crm_lead_records (
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
            json.dumps({"crm_csv": rows_loaded}),
            status,
            run_id
        )
    )


def extract_crm():

    run_id = str(uuid.uuid4())

    rows_read = 0
    rows_loaded = 0

    conn = None

    print("=" * 50)
    print("HORRAZON CRM CSV EXTRACTOR")
    print("=" * 50)

    print("Pipeline Run ID:", run_id)

    try:

        # Read source CSV
        records = read_csv()

        rows_read = len(records)

        print("\nCSV records found:", rows_read)

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

        # Mark successful execution
        update_pipeline_run(
            cursor,
            run_id,
            rows_read,
            rows_loaded,
            "SUCCESS"
        )

        conn.commit()

        print("\n" + "=" * 50)
        print("CRM EXTRACTION COMPLETED")
        print("=" * 50)

        print("Run ID:", run_id)
        print("Rows read:", rows_read)
        print("Rows loaded:", rows_loaded)

        cursor.close()

    except Exception as error:

        print("\nCRM EXTRACTION FAILED:", error)

        if conn is not None:

            conn.rollback()

            try:

                cursor = conn.cursor()

                update_pipeline_run(
                    cursor,
                    run_id,
                    rows_read,
                    rows_loaded,
                    "FAILED"
                )

                conn.commit()
                cursor.close()

            except Exception as logging_error:

                print(
                    "Pipeline logging failed:",
                    logging_error
                )

                conn.rollback()

        raise

    finally:

        if conn is not None:
            conn.close()


if __name__ == "__main__":
    extract_crm()
