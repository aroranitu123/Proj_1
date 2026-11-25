
import json
import random
from datetime import date, timedelta
from pathlib import Path

# Reproducible synthetic data
random.seed(42)

# Project root directory
PROJECT_ROOT = Path(__file__).resolve().parents[2]

OUTPUT_DIR = PROJECT_ROOT / "data" / "raw" / "ads"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

OUTPUT_FILE = OUTPUT_DIR / "ads_data.json"

# Configuration
NUM_CAMPAIGNS = 90
NUM_DAYS = 30

PLATFORMS = [
    "Google Ads",
    "Meta Ads",
    "LinkedIn Ads",
    "Instagram Ads"
]

CAMPAIGN_TYPES = [
    "Brand Awareness",
    "Lead Generation",
    "Conversions",
    "Retargeting",
    "Product Promotion"
]

CAMPAIGN_NAMES = [
    "Summer Sale",
    "Winter Collection",
    "Festive Offers",
    "New Customer Acquisition",
    "Product Launch",
    "Brand Awareness",
    "Holiday Campaign",
    "Flash Sale",
    "Customer Retention",
    "Premium Products"
]

# Date range: last 30 days including today
END_DATE = date.today()
START_DATE = END_DATE - timedelta(days=NUM_DAYS - 1)


def generate_campaigns():
    """Generate campaign master records."""

    campaigns = []

    for i in range(1, NUM_CAMPAIGNS + 1):

        campaign = {
            "campaign_id": f"CMP{i:04d}",
            "campaign_name": (
                f"{random.choice(CAMPAIGN_NAMES)} {i}"
            ),
            "platform": random.choice(PLATFORMS),
            "campaign_type": random.choice(CAMPAIGN_TYPES)
        }

        campaigns.append(campaign)

    return campaigns


def generate_daily_records(campaigns):
    """Generate daily advertising metrics."""

    records = []

    for campaign in campaigns:

        for day_number in range(NUM_DAYS):

            ad_date = START_DATE + timedelta(days=day_number)

            impressions = random.randint(1000, 50000)

            clicks = random.randint(
                10,
                max(10, int(impressions * 0.15))
            )

            spend = round(
                random.uniform(100, 10000),
                2
            )

            record = {
                "campaign_id": campaign["campaign_id"],
                "campaign_name": campaign["campaign_name"],
                "platform": campaign["platform"],
                "ad_date": ad_date.isoformat(),
                "spend": spend,
                "impressions": impressions,
                "clicks": clicks,
                "updated_at": (
                    f"{ad_date.isoformat()}T23:59:00"
                )
            }

            records.append(record)

    return records


def introduce_dirty_data(records):
    """Introduce deliberate data-quality issues."""

    dirty_records = [record.copy() for record in records]

    for i, record in enumerate(dirty_records):

        # Whitespace in campaign names
        if i % 100 == 0:
            record["campaign_name"] = (
                f"  {record['campaign_name']}  "
            )

        # Spend stored as currency text
        if i % 120 == 0:
            record["spend"] = f"₹{record['spend']}"

        # Negative spend
        if i % 250 == 0:
            record["spend"] = -500

        # Clicks greater than impressions
        if i % 300 == 0:
            record["clicks"] = (
                record["impressions"] + 100
            )

        # Missing platform
        if i % 350 == 0:
            record["platform"] = None

        # Missing campaign name
        if i % 400 == 0:
            record["campaign_name"] = None

    return dirty_records


def main():

    print("Generating advertising campaigns...")

    campaigns = generate_campaigns()

    print("Generating daily advertising records...")

    records = generate_daily_records(campaigns)

    print("Introducing data-quality issues...")

    records = introduce_dirty_data(records)

    output = {
        "metadata": {
            "source": "Advertising API",
            "generated_date": date.today().isoformat(),
            "total_campaigns": len(campaigns),
            "total_records": len(records),
            "start_date": START_DATE.isoformat(),
            "end_date": END_DATE.isoformat()
        },
        "campaigns": campaigns,
        "records": records
    }

    with open(OUTPUT_FILE, "w", encoding="utf-8") as file:
        json.dump(
            output,
            file,
            indent=4,
            ensure_ascii=False
        )

    print("\nGeneration completed!")
    print("Campaigns:", len(campaigns))
    print("Advertising records:", len(records))
    print("Output file:", OUTPUT_FILE)


if __name__ == "__main__":
    main()
