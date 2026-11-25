
import json
from pathlib import Path

from fastapi import FastAPI, Query, HTTPException

app = FastAPI(
    title="Horrazon Advertising API",
    description="Synthetic advertising campaign data source",
    version="1.0.0"
)

# Locate the project root
PROJECT_ROOT = Path(__file__).resolve().parents[2]

DATA_FILE = (
    PROJECT_ROOT
    / "data"
    / "raw"
    / "ads"
    / "ads_data.json"
)


def load_data():
    """Load the generated advertising JSON."""

    if not DATA_FILE.exists():
        raise HTTPException(
            status_code=500,
            detail="Advertising dataset not found"
        )

    with open(DATA_FILE, "r", encoding="utf-8") as file:
        return json.load(file)


@app.get("/")
def home():
    return {
        "message": "Horrazon Advertising API is running",
        "status": "healthy"
    }


@app.get("/campaigns")
def get_campaigns():
    data = load_data()

    return {
        "total": len(data["campaigns"]),
        "campaigns": data["campaigns"]
    }


@app.get("/ads")
def get_ads(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500)
):
    data = load_data()

    records = data["records"]

    paginated_records = records[skip:skip + limit]

    return {
        "total": len(records),
        "skip": skip,
        "limit": limit,
        "returned": len(paginated_records),
        "data": paginated_records
    }


@app.get("/ads/{campaign_id}")
def get_campaign_ads(campaign_id: str):
    data = load_data()

    records = [
        record
        for record in data["records"]
        if record["campaign_id"] == campaign_id
    ]

    if not records:
        raise HTTPException(
            status_code=404,
            detail="Campaign not found"
        )

    return {
        "campaign_id": campaign_id,
        "total": len(records),
        "data": records
    }
