
import csv
import random
from pathlib import Path
from datetime import datetime, timedelta, timezone

from faker import Faker

fake = Faker()
random.seed(42)
Faker.seed(42)

# Project directory
PROJECT_ROOT = Path(__file__).resolve().parents[2]

OUTPUT_DIR = PROJECT_ROOT / "data" / "raw" / "crm"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

OUTPUT_FILE = OUTPUT_DIR / "crm_leads.csv"

# Configuration
NUM_LEADS = 1500

INDUSTRIES = [
    "Technology",
    "Finance",
    "Healthcare",
    "Retail",
    "Manufacturing",
    "Education",
    "Telecommunications",
    "Real Estate"
]

LEAD_SOURCES = [
    "Website",
    "LinkedIn",
    "Email Campaign",
    "Referral",
    "Google Ads",
    "Trade Show"
]

STATUSES = [
    "New",
    "Contacted",
    "Qualified",
    "Converted",
    "Lost"
]


def generate_leads():

    leads = []

    for i in range(1, NUM_LEADS + 1):

        created_at = fake.date_time_between(
            start_date="-90d",
            end_date="now",
            tzinfo=timezone.utc
        )

        updated_at = created_at + timedelta(
            days=random.randint(0, 15)
        )

        lead = {
            "lead_id": f"LEAD{i:05d}",
            "first_name": fake.first_name(),
            "last_name": fake.last_name(),
            "email": fake.email(),
            "phone": fake.phone_number(),
            "company": fake.company(),
            "job_title": fake.job(),
            "industry": random.choice(INDUSTRIES),
            "country": fake.country(),
            "lead_source": random.choice(LEAD_SOURCES),
            "status": random.choice(STATUSES),
            "created_at": created_at.isoformat(),
            "updated_at": updated_at.isoformat()
        }

        leads.append(lead)

    return leads


def introduce_dirty_data(leads):

    dirty_leads = [lead.copy() for lead in leads]

    for i, lead in enumerate(dirty_leads):

        # Missing email
        if i % 100 == 0:
            lead["email"] = ""

        # Invalid email
        if i % 120 == 0:
            lead["email"] = "invalid_email"

        # Missing phone
        if i % 150 == 0:
            lead["phone"] = None

        # Extra whitespace
        if i % 80 == 0:
            lead["company"] = f"  {lead['company']}  "

        # Invalid status
        if i % 200 == 0:
            lead["status"] = "Unknown"

        # Missing industry
        if i % 250 == 0:
            lead["industry"] = None

        # Duplicate lead IDs
        if i > 0 and i % 300 == 0:
            lead["lead_id"] = dirty_leads[i - 1]["lead_id"]

        # Missing company
        if i % 350 == 0:
            lead["company"] = ""

    return dirty_leads


def save_csv(leads):

    fieldnames = list(leads[0].keys())

    with open(
        OUTPUT_FILE,
        "w",
        newline="",
        encoding="utf-8"
    ) as file:

        writer = csv.DictWriter(
            file,
            fieldnames=fieldnames
        )

        writer.writeheader()
        writer.writerows(leads)


def main():

    print("Generating CRM leads...")

    leads = generate_leads()

    print("Introducing data-quality issues...")

    leads = introduce_dirty_data(leads)

    print("Saving CRM CSV...")

    save_csv(leads)

    print("\nCRM GENERATION COMPLETED")

    print("Total leads:", len(leads))
    print("Output file:", OUTPUT_FILE)


if __name__ == "__main__":
    main()
