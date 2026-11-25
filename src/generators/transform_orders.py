
import os
import json
from decimal import Decimal, InvalidOperation
from datetime import datetime
from pathlib import Path

import pg8000
from dotenv import load_dotenv

load_dotenv()

# --------------------------------------------------
# CONFIGURATION
# --------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[2]

BATCH_SIZE = 500

ALLOWED_STATUSES = {
    "Placed",
    "Processing",
    "Shipped",
    "Delivered",
    "Cancelled"
}


# --------------------------------------------------
# DATABASE CONNECTION
# --------------------------------------------------

def get_connection():

    return pg8000.connect(
        host=os.getenv("DB_HOST"),
        port=int(os.getenv("DB_PORT", 5432)),
        database=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD")
    )


# --------------------------------------------------
# HELPER FUNCTIONS
# --------------------------------------------------

def parse_decimal(value):

    if value is None:
        return None

    try:
        return Decimal(str(value))

    except (InvalidOperation, ValueError):
        return None


def parse_datetime(value):

    if not value:
        return None

    try:
        return datetime.fromisoformat(
            str(value).replace("Z", "+00:00")
        )

    except (ValueError, TypeError):
        return None


def parse_json(payload):

    if isinstance(payload, str):
        return json.loads(payload)

    return payload


# --------------------------------------------------
# ORDER VALIDATION
# --------------------------------------------------

def validate_order(order):

    errors = []

    if not order.get("customer_id"):
        errors.append("Missing customer_id")

    if order.get("order_status") not in ALLOWED_STATUSES:
        errors.append("Invalid order_status")

    total = parse_decimal(order.get("total_amount"))

    if total is None:
        errors.append("Missing or invalid total_amount")

    elif total < 0:
        errors.append("Negative total_amount")

    return len(errors) == 0, "; ".join(errors), total


# --------------------------------------------------
# ITEM VALIDATION
# --------------------------------------------------

def validate_item(item):

    errors = []

    sku = item.get("sku")

    if not sku:
        errors.append("Missing SKU")

    try:
        qty = int(item["qty"])

        if qty <= 0:
            errors.append("Invalid quantity")

    except (KeyError, TypeError, ValueError):
        qty = None
        errors.append("Missing or invalid quantity")

    price = parse_decimal(item.get("unit_price"))

    if price is None:
        errors.append("Missing or invalid unit price")

    elif price < 0:
        errors.append("Negative unit price")

    return (
        len(errors) == 0,
        "; ".join(errors),
        qty,
        price
    )


# --------------------------------------------------
# STEP 1: EXTRACT RAW DATA
# --------------------------------------------------

def extract_raw_records(cursor):

    cursor.execute("""
        SELECT
            raw_id,
            run_id,
            payload
        FROM raw.store_order_records
        ORDER BY raw_id
    """)

    records = cursor.fetchall()

    return records


# --------------------------------------------------
# STEP 2: TRANSFORM ORDERS AND ITEMS
# --------------------------------------------------

def transform_records(raw_records):

    orders = []
    order_items = []

    order_valid_count = 0
    order_rejected_count = 0

    item_valid_count = 0
    item_rejected_count = 0

    for raw_id, run_id, payload in raw_records:

        order = parse_json(payload)

        order_id = order.get("order_id")

        if not order_id:
            raise ValueError(
                f"Missing order_id in raw record {raw_id}"
            )

        run_id = str(run_id)

        # ------------------------------------------
        # VALIDATE ORDER
        # ------------------------------------------

        is_valid, reason, total = validate_order(order)

        if is_valid:
            order_valid_count += 1
        else:
            order_rejected_count += 1

        # ------------------------------------------
        # PREPARE ORDER RECORD
        # ------------------------------------------

        orders.append((
            order_id,
            raw_id,  # Original RAW ID
            order.get("customer_id"),
            parse_datetime(order.get("order_date")),
            order.get("order_status"),
            total,
            run_id,
            is_valid,
            reason or None,
            order.get("payment_method"),
            order.get("shipping_city"),
            order.get("shipping_country")
        ))

        # ------------------------------------------
        # FLATTEN NESTED ITEMS
        # ------------------------------------------

        items = order.get("items", [])

        if not isinstance(items, list):
            raise ValueError(
                f"Invalid items array for order {order_id}"
            )

        for item_index, item in enumerate(items, start=1):

            item_valid, item_reason, qty, price = (
                validate_item(item)
            )

            if item_valid:
                item_valid_count += 1
            else:
                item_rejected_count += 1

            order_items.append((
                order_id,
                raw_id,  # Original RAW ID
                item.get("sku"),
                item.get("product_name"),
                qty,
                price,
                item_valid,
                item_reason or None,
                run_id,
                item_index
            ))

    # ------------------------------------------
    # TRANSFORMATION SUMMARY
    # ------------------------------------------

    summary = {
        "orders_valid": order_valid_count,
        "orders_rejected": order_rejected_count,
        "items_valid": item_valid_count,
        "items_rejected": item_rejected_count
    }

    return orders, order_items, summary


# --------------------------------------------------
# STEP 3: LOAD ORDERS INTO STAGING
# --------------------------------------------------

def load_orders(cursor, orders):

    query = """
        INSERT INTO staging.orders (
            order_id,
            raw_id,
            customer_id,
            order_date,
            order_status,
            total_amount,
            run_id,
            is_valid,
            rejection_reason,
            payment_method,
            shipping_city,
            shipping_country
        )
        VALUES (
            %s, %s, %s, %s, %s, %s,
            %s::uuid, %s, %s, %s, %s, %s
        )

        ON CONFLICT (order_id)
        DO UPDATE SET
            raw_id = EXCLUDED.raw_id,
            customer_id = EXCLUDED.customer_id,
            order_date = EXCLUDED.order_date,
            order_status = EXCLUDED.order_status,
            total_amount = EXCLUDED.total_amount,
            run_id = EXCLUDED.run_id,
            is_valid = EXCLUDED.is_valid,
            rejection_reason = EXCLUDED.rejection_reason,
            payment_method = EXCLUDED.payment_method,
            shipping_city = EXCLUDED.shipping_city,
            shipping_country = EXCLUDED.shipping_country,
            processed_at = CURRENT_TIMESTAMP
    """

    for start in range(0, len(orders), BATCH_SIZE):

        batch = orders[start:start + BATCH_SIZE]

        cursor.executemany(query, batch)

        print(
            f"Orders processed: "
            f"{min(start + BATCH_SIZE, len(orders))}"
            f"/{len(orders)}"
        )


# --------------------------------------------------
# STEP 4: LOAD ORDER ITEMS INTO STAGING
# --------------------------------------------------

def load_order_items(cursor, items):

    query = """
        INSERT INTO staging.order_items (
            order_id,
            raw_id,
            sku,
            product_name,
            qty,
            unit_price,
            is_valid,
            rejection_reason,
            run_id,
            item_index
        )
        VALUES (
            %s, %s, %s, %s, %s,
            %s, %s, %s, %s::uuid, %s
        )

        ON CONFLICT (run_id, order_id, item_index)
        DO UPDATE SET
            raw_id = EXCLUDED.raw_id,
            sku = EXCLUDED.sku,
            product_name = EXCLUDED.product_name,
            qty = EXCLUDED.qty,
            unit_price = EXCLUDED.unit_price,
            is_valid = EXCLUDED.is_valid,
            rejection_reason = EXCLUDED.rejection_reason,
            processed_at = CURRENT_TIMESTAMP
    """

    for start in range(0, len(items), BATCH_SIZE):

        batch = items[start:start + BATCH_SIZE]

        cursor.executemany(query, batch)

        print(
            f"Order items processed: "
            f"{min(start + BATCH_SIZE, len(items))}"
            f"/{len(items)}"
        )


# --------------------------------------------------
# STEP 5: MAIN TRANSFORMATION PIPELINE
# --------------------------------------------------

def transform_orders():

    conn = None
    cursor = None

    print("\n" + "=" * 55)
    print("HORRAZON ORDER TRANSFORMATION PIPELINE")
    print("=" * 55)

    try:

        conn = get_connection()
        cursor = conn.cursor()

        # ------------------------------------------
        # STEP 1: EXTRACT
        # ------------------------------------------

        print("\nSTEP 1: Extracting RAW records...")

        raw_records = extract_raw_records(cursor)

        print("RAW orders fetched:", len(raw_records))

        # ------------------------------------------
        # STEP 2: TRANSFORM
        # ------------------------------------------

        print("\nSTEP 2: Transforming and validating...")

        orders, items, summary = transform_records(raw_records)

        print("Orders flattened:", len(orders))
        print("Items flattened:", len(items))

        # ------------------------------------------
        # STEP 3: LOAD ORDERS
        # ------------------------------------------

        print("\nSTEP 3: Loading orders...")

        load_orders(cursor, orders)

        # ------------------------------------------
        # STEP 4: LOAD ORDER ITEMS
        # ------------------------------------------

        print("\nSTEP 4: Loading order items...")

        load_order_items(cursor, items)

        # ------------------------------------------
        # COMMIT TRANSACTION
        # ------------------------------------------

        conn.commit()

        # ------------------------------------------
        # STEP 5: FINAL SUMMARY
        # ------------------------------------------

        print("\n" + "=" * 55)
        print("TRANSFORMATION COMPLETED SUCCESSFULLY")
        print("=" * 55)

        print("\nORDER SUMMARY")

        print("Valid orders:", summary["orders_valid"])
        print("Rejected orders:", summary["orders_rejected"])

        print("\nITEM SUMMARY")

        print("Valid items:", summary["items_valid"])
        print("Rejected items:", summary["items_rejected"])

        print("\nTotal orders:", len(orders))
        print("Total order items:", len(items))

    except Exception as error:

        if conn is not None:
            conn.rollback()

        print("\nTRANSFORMATION FAILED:", error)

        raise

    finally:

        if cursor is not None:
            cursor.close()

        if conn is not None:
            conn.close()


# --------------------------------------------------
# EXECUTION
# --------------------------------------------------

if __name__ == "__main__":
    transform_orders()
