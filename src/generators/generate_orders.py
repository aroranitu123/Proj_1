
import json
import random

from pathlib import Path
from datetime import datetime, timedelta, timezone

from faker import Faker

fake = Faker()
random.seed(42)
Faker.seed(42)

# Project directory
PROJECT_ROOT = Path(__file__).resolve().parents[2]

OUTPUT_DIR = PROJECT_ROOT / "data" / "raw" / "orders"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

OUTPUT_FILE = OUTPUT_DIR / "store_orders.json"

# Configuration
NUM_ORDERS = 1200

PRODUCTS = [
    {"sku": "SKU001", "name": "Laptop", "price": 65000},
    {"sku": "SKU002", "name": "Wireless Mouse", "price": 1200},
    {"sku": "SKU003", "name": "Keyboard", "price": 2500},
    {"sku": "SKU004", "name": "Monitor", "price": 18000},
    {"sku": "SKU005", "name": "Headphones", "price": 3500},
    {"sku": "SKU006", "name": "USB Hub", "price": 900},
    {"sku": "SKU007", "name": "Webcam", "price": 4200},
    {"sku": "SKU008", "name": "External SSD", "price": 7500},
    {"sku": "SKU009", "name": "Laptop Stand", "price": 1800},
    {"sku": "SKU010", "name": "Tablet", "price": 28000}
]

ORDER_STATUSES = [
    "Placed",
    "Processing",
    "Shipped",
    "Delivered",
    "Cancelled"
]

PAYMENT_METHODS = [
    "UPI",
    "Credit Card",
    "Debit Card",
    "Net Banking",
    "Cash on Delivery"
]


def generate_orders():

    orders = []

    for i in range(1, NUM_ORDERS + 1):

        order_date = fake.date_time_between(
            start_date="-90d",
            end_date="now",
            tzinfo=timezone.utc
        )

        num_items = random.randint(1, 4)

        selected_products = random.sample(
            PRODUCTS,
            num_items
        )

        items = []

        for product in selected_products:

            quantity = random.randint(1, 5)

            item = {
                "sku": product["sku"],
                "product_name": product["name"],
                "qty": quantity,
                "unit_price": product["price"]
            }

            items.append(item)

        total_amount = round(
            sum(
                item["qty"] * item["unit_price"]
                for item in items
            ),
            2
        )

        order = {
            "order_id": f"ORD{i:05d}",
            "customer_id": f"CUST{random.randint(1, 500):04d}",
            "order_date": order_date.isoformat(),
            "order_status": random.choice(ORDER_STATUSES),
            "payment_method": random.choice(PAYMENT_METHODS),
            "shipping_city": fake.city(),
            "shipping_country": fake.country(),
            "total_amount": total_amount,
            "items": items
        }

        orders.append(order)

    return orders


def introduce_dirty_data(orders):

    dirty_orders = [
        json.loads(json.dumps(order))
        for order in orders
    ]

    for i, order in enumerate(dirty_orders):

        # Missing customer ID
        if i % 100 == 0:
            order["customer_id"] = None

        # Invalid order status
        if i % 150 == 0:
            order["order_status"] = "Unknown"

        # Negative order total
        if i % 200 == 0:
            order["total_amount"] = -500

        # Duplicate order ID
        if i > 0 and i % 300 == 0:
            order["order_id"] = (
                dirty_orders[i - 1]["order_id"]
            )

        # Invalid item quantity
        if i % 120 == 0:
            order["items"][0]["qty"] = -2

        # Negative unit price
        if i % 250 == 0:
            order["items"][0]["unit_price"] = -100

        # Missing shipping city
        if i % 350 == 0:
            order["shipping_city"] = None

    return dirty_orders


def save_json(orders):

    output = {
        "metadata": {
            "source": "Store Orders System",
            "generated_at": datetime.now(
                timezone.utc
            ).isoformat(),
            "total_orders": len(orders),
            "total_items": sum(
                len(order["items"])
                for order in orders
            )
        },
        "orders": orders
    }

    with open(
        OUTPUT_FILE,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            output,
            file,
            indent=4,
            ensure_ascii=False
        )


def main():

    print("Generating store orders...")

    orders = generate_orders()

    print("Introducing data-quality issues...")

    orders = introduce_dirty_data(orders)

    print("Saving JSON dataset...")

    save_json(orders)

    total_items = sum(
        len(order["items"])
        for order in orders
    )

    print("\nSTORE ORDERS GENERATION COMPLETED")
    print("Total orders:", len(orders))
    print("Total order items:", total_items)
    print("Output file:", OUTPUT_FILE)


if __name__ == "__main__":
    main()
