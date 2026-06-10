import asyncio
import logging
from fastapi import FastAPI, HTTPException
from models import SearchRequest, SearchResponse, ListingData, PROPERTY_TYPE_CODES, STATUS_CODES
from redfin_client import search_city
from exceptions import CityNotFoundError, RateLimitedError, SiteUnavailableError

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

app = FastAPI(
    title="Redfin Property Listings API",
    description="Search Redfin property listings by city/state and return structured JSON.",
    version="1.0.0",
)


def _to_listing_data(record: dict) -> ListingData:
    """Map a flat scraper dict to the ListingData Pydantic model."""
    return ListingData(
        address=record.get("Address"),
        unit=record.get("Unit"),
        city=record.get("City"),
        state=record.get("State"),
        zip=record.get("Zip"),
        neighborhood=record.get("Neighborhood"),
        price=record.get("Price"),
        beds=record.get("Beds"),
        baths=record.get("Baths"),
        full_baths=record.get("Full Baths"),
        sqft=record.get("Sqft"),
        price_per_sqft=record.get("Price/Sqft"),
        lot_size=record.get("Lot Size (sqft)"),
        year_built=record.get("Year Built"),
        stories=record.get("Stories"),
        property_type=record.get("Property Type"),
        status=record.get("MLS Status"),
        days_on_market=record.get("Days on Market"),
        hoa_fee=record.get("HOA Fee"),
        garage_spaces=record.get("Garage Spaces"),
        parking_spaces=record.get("Parking Spaces"),
        has_pool=record.get("Has Pool"),
        latitude=record.get("Latitude"),
        longitude=record.get("Longitude"),
        mls_number=record.get("MLS Number"),
        property_id=record.get("Property ID"),
        listing_id=record.get("Listing ID"),
        listing_agent=record.get("Listing Agent"),
        listing_broker=record.get("Listing Broker"),
        key_features=record.get("Key Features"),
        description=record.get("Description"),
        has_virtual_tour=record.get("Has Virtual Tour"),
        has_3d_tour=record.get("Has 3D Tour"),
        is_new_construction=record.get("Is New Construction"),
        is_hot_listing=record.get("Is Hot Listing"),
        redfin_url=record.get("Redfin URL"),
    )


@app.post("/search", response_model=SearchResponse)
async def search(req: SearchRequest):
    """
    Search Redfin listings for a city/state with optional filters.
    Returns up to `limit` listings as structured JSON.
    """
    prop_code   = PROPERTY_TYPE_CODES[req.property_type]
    status_code = STATUS_CODES[req.status]

    try:
        records, total_found = await asyncio.to_thread(
            search_city,
            req.city,
            req.state,
            prop_code,
            status_code,
            req.min_beds,
            req.min_baths,
            req.min_price,
            req.max_price,
            req.limit,
        )
    except CityNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except RateLimitedError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except SiteUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc))

    listings = [_to_listing_data(r) for r in records]

    return SearchResponse(
        city=req.city,
        state=req.state,
        total_found=total_found,
        returned=len(listings),
        listings=listings,
    )


@app.get("/health")
async def health():
    return {"status": "ok"}
