import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch

from main import app

client = TestClient(app)

# ── Mock data ─────────────────────────────────────────────────────────────────

MOCK_RECORD = {
    "Address": "4118 NE Senate St",
    "Unit": None,
    "City": "Miami",
    "State": "FL",
    "Zip": "33101",
    "Neighborhood": "Brickell",
    "Price": "$670,000",
    "Beds": 3,
    "Baths": 3.0,
    "Full Baths": 3,
    "Sqft": 2266,
    "Price/Sqft": "$296",
    "Lot Size (sqft)": 3484,
    "Year Built": 1995,
    "Stories": 2.0,
    "Property Type": "Single Family",
    "MLS Status": "Active",
    "Days on Market": 5,
    "HOA Fee": None,
    "Garage Spaces": 1,
    "Parking Spaces": 1,
    "Has Pool": "No",
    "Latitude": 25.7617,
    "Longitude": -80.1918,
    "MLS Number": "A12345678",
    "Property ID": 26411123,
    "Listing ID": 215882246,
    "Listing Agent": "Jane Doe",
    "Listing Broker": "Redfin",
    "Key Features": "UPDATED KITCHEN,HARDWOOD FLOORS",
    "Description": "Beautiful home in Miami.",
    "Has Virtual Tour": True,
    "Has 3D Tour": False,
    "Is New Construction": False,
    "Is Hot Listing": False,
    "Redfin URL": "https://www.redfin.com/FL/Miami/4118-NE-Senate-St/home/26411123",
}

VALID_REQUEST = {
    "city": "Miami",
    "state": "FL",
    "property_type": "house",
    "status": "for_sale",
    "limit": 10,
}


# ── Happy path ────────────────────────────────────────────────────────────────

def test_successful_search():
    with patch("main.search_city", return_value=([MOCK_RECORD], 1842)):
        r = client.post("/search", json=VALID_REQUEST)
    assert r.status_code == 200
    body = r.json()
    assert body["city"] == "Miami"
    assert body["state"] == "FL"
    assert body["total_found"] == 1842
    assert body["returned"] == 1
    assert len(body["listings"]) == 1
    listing = body["listings"][0]
    assert listing["address"] == "4118 NE Senate St"
    assert listing["price"] == "$670,000"
    assert listing["beds"] == 3
    assert listing["sqft"] == 2266
    assert listing["property_type"] == "Single Family"
    assert listing["redfin_url"].startswith("https://www.redfin.com")


def test_all_fields_present_in_response():
    with patch("main.search_city", return_value=([MOCK_RECORD], 1)):
        r = client.post("/search", json=VALID_REQUEST)
    listing = r.json()["listings"][0]
    expected_fields = [
        "address", "city", "state", "zip", "price", "beds", "baths",
        "sqft", "year_built", "property_type", "status", "redfin_url",
        "latitude", "longitude", "listing_agent",
    ]
    for field in expected_fields:
        assert field in listing, f"Missing field: {field}"


# ── Input validation ──────────────────────────────────────────────────────────

def test_blank_city_rejected():
    r = client.post("/search", json={**VALID_REQUEST, "city": "   "})
    assert r.status_code == 422


def test_invalid_state_code():
    r = client.post("/search", json={**VALID_REQUEST, "state": "Florida"})
    assert r.status_code == 422


def test_invalid_property_type():
    r = client.post("/search", json={**VALID_REQUEST, "property_type": "mansion"})
    assert r.status_code == 422


def test_invalid_status():
    r = client.post("/search", json={**VALID_REQUEST, "status": "pending"})
    assert r.status_code == 422


def test_negative_limit_rejected():
    r = client.post("/search", json={**VALID_REQUEST, "limit": -1})
    assert r.status_code == 422


def test_state_normalized_to_uppercase():
    with patch("main.search_city", return_value=([MOCK_RECORD], 1)) as mock:
        r = client.post("/search", json={**VALID_REQUEST, "state": "fl"})
    assert r.status_code == 200
    mock.assert_called_once()
    call_args = mock.call_args
    assert call_args.args[1] == "FL"  # state normalized


def test_missing_city_field():
    r = client.post("/search", json={"state": "FL"})
    assert r.status_code == 422


# ── Error handling ────────────────────────────────────────────────────────────

def test_city_not_found_returns_404():
    from exceptions import CityNotFoundError
    with patch("main.search_city", side_effect=CityNotFoundError("not found")):
        r = client.post("/search", json=VALID_REQUEST)
    assert r.status_code == 404
    assert "not found" in r.json()["detail"]


def test_rate_limited_returns_503():
    from exceptions import RateLimitedError
    with patch("main.search_city", side_effect=RateLimitedError("rate limited")):
        r = client.post("/search", json=VALID_REQUEST)
    assert r.status_code == 503


def test_site_unavailable_returns_503():
    from exceptions import SiteUnavailableError
    with patch("main.search_city", side_effect=SiteUnavailableError("down")):
        r = client.post("/search", json=VALID_REQUEST)
    assert r.status_code == 503


# ── Optional filters ─────────────────────────────────────────────────────────

def test_optional_filters_passed_through():
    with patch("main.search_city", return_value=([MOCK_RECORD], 1)) as mock:
        r = client.post("/search", json={
            **VALID_REQUEST,
            "min_beds": 3,
            "min_baths": 2.0,
            "min_price": 300000,
            "max_price": 900000,
        })
    assert r.status_code == 200
    call_args = mock.call_args
    assert call_args.args[4] == 3        # min_beds
    assert call_args.args[5] == 2.0      # min_baths
    assert call_args.args[6] == 300000   # min_price
    assert call_args.args[7] == 900000   # max_price


def test_sold_status_accepted():
    with patch("main.search_city", return_value=([MOCK_RECORD], 1)):
        r = client.post("/search", json={**VALID_REQUEST, "status": "sold"})
    assert r.status_code == 200


# ── Health check ──────────────────────────────────────────────────────────────

def test_health_endpoint():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}
