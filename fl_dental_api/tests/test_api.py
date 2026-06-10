import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch

from main import app

client = TestClient(app)

# ── Fixtures ──────────────────────────────────────────────────────────────────

MOCK_DETAIL_URL = (
    "https://mqa-internet.doh.state.fl.us/MQASearchServices/"
    "HealthCareProviders/LicenseVerification?LicInd=16893&ProCde=701"
)

# Mock HTML mirrors the real MQA detail page structure:
# - name in <h3>, license number in <h3 "License Number: ...">
# - all other fields as <dt>/<dd> pairs
MOCK_HTML = """
<html><body>
  <h3>BONNIE  RAE</h3>
  <h3>License Number: DN17478</h3>
  <dl>
    <dt>Profession</dt><dd>Dentist</dd>
    <dt>License</dt><dd>DN17478</dd>
    <dt>License Status</dt><dd>Disc Relinquish/</dd>
    <dt>License Expiration Date</dt><dd>02/28/2022</dd>
    <dt>License Original Issue Date</dt><dd>03/23/2006</dd>
    <dt>Address of Record</dt><dd></dd>
    <dt>Controlled Substance Prescriber (for the Treatment of Chronic Non-malignant Pain)</dt><dd>No</dd>
    <dt>Discipline on File</dt><dd>Yes -Click on Discipline/Admin Action tab to see more details</dd>
    <dt>Public Complaint</dt><dd>Yes -Click on Discipline/Admin Action tab to see more details</dd>
  </dl>
</body></html>
"""

VALID_REQUEST = {
    "first_name": "Bonnie",
    "last_name": "Rae",
    "license_number": "DN17478",
}


# ── Happy path ────────────────────────────────────────────────────────────────

def test_successful_lookup():
    with patch("main.search_by_license", return_value=(MOCK_DETAIL_URL, MOCK_HTML)):
        r = client.post("/lookup", json=VALID_REQUEST)
    assert r.status_code == 200
    body = r.json()
    assert body["snapshot_url"] == MOCK_DETAIL_URL
    assert body["name_mismatch"] is False
    assert body["data"]["name"] == "BONNIE  RAE"
    assert body["data"]["license_number"] == "DN17478"
    assert body["data"]["profession"] == "Dentist"
    assert body["data"]["status"] == "Disc Relinquish"
    assert body["data"]["expiration_date"] == "02/28/2022"
    assert body["data"]["original_issue_date"] == "03/23/2006"
    # noise suffix stripped by parser
    assert body["data"]["discipline_on_file"] == "Yes"
    assert body["data"]["public_complaint"] == "Yes"


def test_address_is_null_when_empty():
    with patch("main.search_by_license", return_value=(MOCK_DETAIL_URL, MOCK_HTML)):
        r = client.post("/lookup", json=VALID_REQUEST)
    assert r.json()["data"]["address"] is None


# ── Input validation ──────────────────────────────────────────────────────────

def test_blank_first_name_rejected():
    r = client.post("/lookup", json={**VALID_REQUEST, "first_name": "   "})
    assert r.status_code == 422


def test_blank_last_name_rejected():
    r = client.post("/lookup", json={**VALID_REQUEST, "last_name": ""})
    assert r.status_code == 422


def test_invalid_license_no_letters():
    r = client.post("/lookup", json={**VALID_REQUEST, "license_number": "12345"})
    assert r.status_code == 422


def test_invalid_license_no_digits():
    r = client.post("/lookup", json={**VALID_REQUEST, "license_number": "DNABCD"})
    assert r.status_code == 422


def test_license_normalized_to_uppercase():
    with patch("main.search_by_license", return_value=(MOCK_DETAIL_URL, MOCK_HTML)) as mock:
        r = client.post("/lookup", json={**VALID_REQUEST, "license_number": "dn17478"})
    assert r.status_code == 200
    # scraper was called with uppercase
    mock.assert_called_once_with("DN17478", "Bonnie", "Rae")


def test_missing_required_field():
    r = client.post("/lookup", json={"first_name": "Bonnie", "last_name": "Rae"})
    assert r.status_code == 422


# ── Error handling ────────────────────────────────────────────────────────────

def test_provider_not_found_returns_404():
    from exceptions import ProviderNotFoundError
    with patch("main.search_by_license", side_effect=ProviderNotFoundError("not found")):
        r = client.post("/lookup", json=VALID_REQUEST)
    assert r.status_code == 404
    assert "not found" in r.json()["detail"]


def test_ambiguous_results_returns_404():
    from exceptions import AmbiguousResultsError
    with patch("main.search_by_license", side_effect=AmbiguousResultsError("multiple")):
        r = client.post("/lookup", json=VALID_REQUEST)
    assert r.status_code == 404


def test_site_unavailable_returns_503():
    from exceptions import SiteUnavailableError
    with patch("main.search_by_license", side_effect=SiteUnavailableError("down")):
        r = client.post("/lookup", json=VALID_REQUEST)
    assert r.status_code == 503
    assert "down" in r.json()["detail"]


# ── Name mismatch ─────────────────────────────────────────────────────────────

def test_name_mismatch_flagged_when_names_differ():
    with patch("main.search_by_license", return_value=(MOCK_DETAIL_URL, MOCK_HTML)):
        r = client.post("/lookup", json={**VALID_REQUEST, "first_name": "Wrong", "last_name": "Name"})
    assert r.status_code == 200
    assert r.json()["name_mismatch"] is True


def test_name_mismatch_false_when_names_match():
    with patch("main.search_by_license", return_value=(MOCK_DETAIL_URL, MOCK_HTML)):
        r = client.post("/lookup", json=VALID_REQUEST)
    assert r.json()["name_mismatch"] is False


def test_name_match_is_case_insensitive():
    with patch("main.search_by_license", return_value=(MOCK_DETAIL_URL, MOCK_HTML)):
        r = client.post("/lookup", json={**VALID_REQUEST, "first_name": "BONNIE", "last_name": "RAE"})
    assert r.json()["name_mismatch"] is False


# ── Health check ──────────────────────────────────────────────────────────────

def test_health_endpoint():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}
