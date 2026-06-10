import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch

from main import app

client = TestClient(app)

MOCK_BOOKS = [
    {"Title": "A Light in the Attic", "Price": 51.77, "Rating": 3, "Availability": "In stock"},
    {"Title": "Tipping the Velvet",   "Price": 53.74, "Rating": 1, "Availability": "In stock"},
    {"Title": "Sharp Objects",        "Price": 47.82, "Rating": 4, "Availability": "In stock"},
    {"Title": "The Dark Secret",      "Price": 19.99, "Rating": 5, "Availability": "In stock"},
]

VALID_REQUEST = {"title": "light", "limit": 10}


# ── Happy path ────────────────────────────────────────────────────────────────

def test_successful_search():
    with patch("main.scrape_books", return_value=[MOCK_BOOKS[0]]):
        r = client.post("/search", json=VALID_REQUEST)
    assert r.status_code == 200
    body = r.json()
    assert body["total_matched"] == 1
    assert body["returned"] == 1
    assert body["books"][0]["title"] == "A Light in the Attic"
    assert body["books"][0]["price"] == 51.77
    assert body["books"][0]["rating"] == 3
    assert body["books"][0]["availability"] == "In stock"


def test_all_fields_present():
    with patch("main.scrape_books", return_value=[MOCK_BOOKS[0]]):
        r = client.post("/search", json=VALID_REQUEST)
    book = r.json()["books"][0]
    for field in ["title", "price", "rating", "availability"]:
        assert field in book, f"Missing field: {field}"


def test_search_returns_multiple_books():
    with patch("main.scrape_books", return_value=MOCK_BOOKS):
        r = client.post("/search", json={"limit": 10})
    assert r.status_code == 200
    assert r.json()["returned"] == 4


# ── Input validation ──────────────────────────────────────────────────────────

def test_invalid_min_rating_too_low():
    r = client.post("/search", json={"min_rating": 0, "limit": 10})
    assert r.status_code == 422


def test_invalid_min_rating_too_high():
    r = client.post("/search", json={"min_rating": 6, "limit": 10})
    assert r.status_code == 422


def test_negative_limit_rejected():
    r = client.post("/search", json={"limit": -1})
    assert r.status_code == 422


def test_zero_limit_rejected():
    r = client.post("/search", json={"limit": 0})
    assert r.status_code == 422


def test_invalid_max_price_rejected():
    r = client.post("/search", json={"max_price": -5.0, "limit": 10})
    assert r.status_code == 422


def test_invalid_availability_rejected():
    r = client.post("/search", json={"availability": "maybe", "limit": 10})
    assert r.status_code == 422


# ── Filter passthrough ────────────────────────────────────────────────────────

def test_title_filter_passed_through():
    with patch("main.scrape_books", return_value=[MOCK_BOOKS[0]]) as mock:
        client.post("/search", json={"title": "light", "limit": 5})
    assert mock.call_args.args[0] == "light"


def test_min_rating_passed_through():
    with patch("main.scrape_books", return_value=[MOCK_BOOKS[2]]) as mock:
        client.post("/search", json={"min_rating": 4, "limit": 5})
    assert mock.call_args.args[1] == 4


def test_max_price_passed_through():
    with patch("main.scrape_books", return_value=[MOCK_BOOKS[3]]) as mock:
        client.post("/search", json={"max_price": 20.0, "limit": 5})
    assert mock.call_args.args[2] == 20.0


def test_availability_in_stock_passed_through():
    with patch("main.scrape_books", return_value=MOCK_BOOKS) as mock:
        client.post("/search", json={"availability": "in_stock", "limit": 5})
    assert mock.call_args.args[3] == "in_stock"


# ── Error handling ────────────────────────────────────────────────────────────

def test_no_results_returns_404():
    from exceptions import NoResultsError
    with patch("main.scrape_books", side_effect=NoResultsError("no books")):
        r = client.post("/search", json=VALID_REQUEST)
    assert r.status_code == 404
    assert "no books" in r.json()["detail"]


def test_site_unavailable_returns_503():
    from exceptions import SiteUnavailableError
    with patch("main.scrape_books", side_effect=SiteUnavailableError("down")):
        r = client.post("/search", json=VALID_REQUEST)
    assert r.status_code == 503


# ── Limit passthrough ─────────────────────────────────────────────────────────

def test_limit_passed_through():
    with patch("main.scrape_books", return_value=[MOCK_BOOKS[0]]) as mock:
        client.post("/search", json={"limit": 7})
    assert mock.call_args.args[4] == 7


# ── Additional validation edge cases ──────────────────────────────────────────

def test_max_price_zero_rejected():
    r = client.post("/search", json={"max_price": 0.0, "limit": 10})
    assert r.status_code == 422


def test_min_rating_boundary_low_valid():
    with patch("main.scrape_books", return_value=[MOCK_BOOKS[0]]):
        r = client.post("/search", json={"min_rating": 1, "limit": 10})
    assert r.status_code == 200


def test_min_rating_boundary_high_valid():
    with patch("main.scrape_books", return_value=[MOCK_BOOKS[3]]):
        r = client.post("/search", json={"min_rating": 5, "limit": 10})
    assert r.status_code == 200


def test_query_field_is_all_books_when_no_title():
    with patch("main.scrape_books", return_value=MOCK_BOOKS):
        r = client.post("/search", json={"limit": 10})
    assert r.json()["query"] == "(all books)"


def test_query_field_echoes_title():
    with patch("main.scrape_books", return_value=[MOCK_BOOKS[0]]):
        r = client.post("/search", json={"title": "light", "limit": 10})
    assert r.json()["query"] == "light"


# ── Health check ──────────────────────────────────────────────────────────────

def test_health_endpoint():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}
