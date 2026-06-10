"""
Redfin Stingray API client.
Shared by scraper.py (bulk) and main.py (FastAPI).
"""

import json
import time
import logging
from typing import Optional

import requests

from config import settings
from exceptions import CityNotFoundError, RateLimitedError, SiteUnavailableError

log = logging.getLogger(__name__)

PROPERTY_TYPE_MAP = {
    1: "Single Family",
    2: "Condo",
    3: "Townhouse",
    4: "Land",
    5: "Other",
    6: "Multi-Family",
    13: "Mobile/Manufactured",
}

POOL_MAP = {
    5: "No",
}


# Known city → (region_id, region_type, url_slug) for the most common cities.
# region_type 6 = city. Used as fallback when autocomplete is blocked.
# region_id values verified from Redfin city page URLs: redfin.com/city/{id}/{STATE}/{City}
KNOWN_CITIES: dict[tuple[str, str], tuple[str, str, str]] = {
    # Florida
    ("miami", "fl"):           ("11458", "6", "FL/Miami"),
    ("orlando", "fl"):         ("13054", "6", "FL/Orlando"),
    ("tampa", "fl"):           ("16958", "6", "FL/Tampa"),
    ("jacksonville", "fl"):    ("8227",  "6", "FL/Jacksonville"),
    ("fort lauderdale", "fl"): ("4763",  "6", "FL/Fort-Lauderdale"),
    ("st. petersburg", "fl"):  ("16661", "6", "FL/St.-Petersburg"),
    ("hialeah", "fl"):         ("6678",  "6", "FL/Hialeah"),
    ("tallahassee", "fl"):     ("16889", "6", "FL/Tallahassee"),
    # Other major US cities
    ("new york", "ny"):        ("17867", "6", "NY/New-York"),
    ("los angeles", "ca"):     ("11203", "6", "CA/Los-Angeles"),
    ("chicago", "il"):         ("29470", "6", "IL/Chicago"),
    ("houston", "tx"):         ("7103",  "6", "TX/Houston"),
    ("phoenix", "az"):         ("14188", "6", "AZ/Phoenix"),
    ("philadelphia", "pa"):    ("14217", "6", "PA/Philadelphia"),
    ("san antonio", "tx"):     ("15362", "6", "TX/San-Antonio"),
    ("san diego", "ca"):       ("16904", "6", "CA/San-Diego"),
    ("dallas", "tx"):          ("30827", "6", "TX/Dallas"),
    ("austin", "tx"):          ("30818", "6", "TX/Austin"),
    ("seattle", "wa"):         ("16163", "6", "WA/Seattle"),
    ("denver", "co"):          ("14812", "6", "CO/Denver"),
    ("boston", "ma"):          ("1826",  "6", "MA/Boston"),
    ("atlanta", "ga"):         ("15154", "6", "GA/Atlanta"),
    ("nashville", "tn"):       ("12536", "6", "TN/Nashville"),
    ("charlotte", "nc"):       ("9765",  "6", "NC/Charlotte"),
    ("las vegas", "nv"):       ("9397",  "6", "NV/Las-Vegas"),
    ("portland", "or"):        ("30892", "6", "OR/Portland"),
    ("minneapolis", "mn"):     ("11640", "6", "MN/Minneapolis"),
    ("san francisco", "ca"):   ("17151", "6", "CA/San-Francisco"),
}


def _session() -> requests.Session:
    """Create a requests session that mimics a real browser visit (seeds cookies)."""
    s = requests.Session()
    s.headers.update({
        "User-Agent": settings.user_agent,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Referer": "https://www.redfin.com/",
    })
    # Seed cookies by visiting the homepage — required for API calls to succeed
    try:
        s.get("https://www.redfin.com/", timeout=settings.request_timeout_s)
    except Exception:
        pass  # Best-effort; continue without cookies
    return s


def _parse_json(text: str) -> dict:
    """Strip the '{}&&' prefix Redfin prepends to all JSON responses."""
    text = text.strip()
    if text.startswith("{}&&"):
        text = text[4:]
    return json.loads(text)


def _get_with_retry(session: requests.Session, url: str, params: dict) -> Optional[requests.Response]:
    """GET with exponential backoff on 403/429/5xx."""
    delay = 2
    for attempt in range(settings.max_retries):
        try:
            resp = session.get(url, params=params, timeout=settings.request_timeout_s)
            if resp.status_code == 200:
                return resp
            if resp.status_code in (403, 429):
                log.warning("Rate limited (attempt %d/%d) — waiting %ds", attempt + 1, settings.max_retries, delay)
                time.sleep(delay)
                delay *= 2
                continue
            if resp.status_code >= 500:
                log.warning("Server error %d (attempt %d/%d)", resp.status_code, attempt + 1, settings.max_retries)
                time.sleep(delay)
                delay *= 2
                continue
            log.warning("Unexpected status %d for %s", resp.status_code, url)
            return None
        except requests.exceptions.Timeout:
            log.warning("Request timed out (attempt %d/%d)", attempt + 1, settings.max_retries)
            time.sleep(delay)
            delay *= 2
        except requests.exceptions.ConnectionError as e:
            raise SiteUnavailableError(f"Cannot reach Redfin: {e}") from e

    raise RateLimitedError(f"Exceeded {settings.max_retries} retries for {url}")


def lookup_region(session: requests.Session, city: str, state: str) -> tuple[str, str]:
    """
    Resolve city + state to a (region_id, region_type) pair.

    Strategy:
    1. Check KNOWN_CITIES map (instant, no network call)
    2. Scrape the Redfin city landing page and extract region_id from JSON embed
    3. Raise CityNotFoundError if both strategies fail
    """
    key = (city.strip().lower(), state.strip().lower())

    # Strategy 1: known city map
    if key in KNOWN_CITIES:
        region_id, region_type, _ = KNOWN_CITIES[key]
        log.info("Resolved '%s, %s' from known-city map → region_id=%s", city, state, region_id)
        return region_id, region_type

    # Strategy 2: fetch the Redfin search page for the city and parse region_id from redirect URL
    # Redfin city URLs: /city/{region_id}/{STATE}/{City-Name}
    import re
    city_slug = city.strip().replace(" ", "-").title()
    state_up  = state.strip().upper()
    # Try common URL patterns Redfin uses
    candidates = [
        f"https://www.redfin.com/{state_up}/{city_slug.replace('-', '%20')}",
        f"https://www.redfin.com/{state_up}/{city_slug}",
    ]

    for candidate_url in candidates:
        try:
            resp = session.get(candidate_url, timeout=settings.request_timeout_s, allow_redirects=True)
            if resp.status_code == 200:
                m = re.search(r'/city/(\d+)/', resp.url)
                if m:
                    region_id = m.group(1)
                    log.info("Resolved '%s, %s' from redirect → region_id=%s", city, state, region_id)
                    return region_id, "6"
        except Exception as e:
            log.warning("City page lookup failed for %s: %s", candidate_url, e)

    raise CityNotFoundError(
        f"Could not resolve region for: {city}, {state}. "
        f"If this is a valid city, add it to KNOWN_CITIES in redfin_client.py."
    )


def fetch_listings_page(
    session: requests.Session,
    region_id: str,
    region_type: str,
    page_number: int,
    status_code: str,
    property_type_code: str,
    min_beds: Optional[int] = None,
    min_baths: Optional[float] = None,
    min_price: Optional[int] = None,
    max_price: Optional[int] = None,
    min_year_built: Optional[int] = None,
) -> tuple[list[dict], int]:
    """
    Fetch one page of listings from the GIS API.
    Returns (homes_list, total_count).
    total_count is only accurate on page 1; subsequent pages return 0 for it.
    """
    params: dict = {
        "al": "1",
        "region_id": region_id,
        "region_type": region_type,
        "num_homes": str(settings.page_size),
        "page_number": str(page_number),
        "status": status_code,
        "uipt": property_type_code,
        "v": "8",
    }
    if min_beds is not None:
        params["min_beds"] = str(min_beds)
    if min_baths is not None:
        params["min_baths"] = str(min_baths)
    if min_price is not None:
        params["min_price"] = str(min_price)
    if max_price is not None:
        params["max_price"] = str(max_price)

    resp = _get_with_retry(session, settings.redfin_gis_url, params)
    if not resp:
        return [], 0

    data = _parse_json(resp.text)
    payload = data.get("payload", {})
    homes = payload.get("homes", [])
    total = payload.get("numHomes", 0) or payload.get("totalCount", 0) or 0

    return homes, total


def parse_listing(home: dict) -> dict:
    """
    Convert a raw Redfin home dict (from GIS API) into a flat dict
    with all available fields, ready for Excel or JSON response.
    """
    def nested(key: str, sub: str = "value"):
        val = home.get(key)
        if isinstance(val, dict):
            return val.get(sub)
        return val

    def fmt_price(val) -> Optional[str]:
        if val is None:
            return None
        try:
            return f"${int(val):,}"
        except (TypeError, ValueError):
            return str(val)

    prop_type_code = home.get("propertyType") or home.get("uiPropertyType")
    prop_type_label = PROPERTY_TYPE_MAP.get(prop_type_code, str(prop_type_code) if prop_type_code else None)

    pool_code = home.get("skPoolType")
    has_pool = "No" if pool_code == 5 else ("Yes" if pool_code is not None else None)

    tags = home.get("listingTags") or []
    key_features = ", ".join(tags) if tags else None

    key_facts = home.get("keyFacts") or []
    key_facts_str = ", ".join(f["description"] for f in key_facts if f.get("description")) or None

    url_path = home.get("url", "")
    redfin_url = f"https://www.redfin.com{url_path}" if url_path else None

    hoa_val = nested("hoa")
    hoa_str = fmt_price(hoa_val) if hoa_val else None

    return {
        "Address":           nested("streetLine"),
        "Unit":              nested("unitNumber"),
        "City":              home.get("city"),
        "State":             home.get("state"),
        "Zip":               home.get("zip"),
        "Neighborhood":      nested("location"),
        "Price":             fmt_price(nested("price")),
        "Beds":              home.get("beds"),
        "Baths":             home.get("baths"),
        "Full Baths":        home.get("fullBaths"),
        "Sqft":              nested("sqFt"),
        "Price/Sqft":        fmt_price(nested("pricePerSqFt")),
        "Lot Size (sqft)":   nested("lotSize"),
        "Year Built":        nested("yearBuilt"),
        "Stories":           home.get("stories"),
        "Property Type":     prop_type_label,
        "MLS Status":        home.get("mlsStatus"),
        "Days on Market":    nested("dom"),
        "HOA Fee":           hoa_str,
        "Garage Spaces":     home.get("skGarageSpaces"),
        "Parking Spaces":    home.get("skParkingSpaces"),
        "Has Pool":          has_pool,
        "Latitude":          nested("latLong", "value") and home.get("latLong", {}).get("value", {}).get("latitude"),
        "Longitude":         nested("latLong", "value") and home.get("latLong", {}).get("value", {}).get("longitude"),
        "MLS Number":        nested("mlsId"),
        "Property ID":       home.get("propertyId"),
        "Listing ID":        home.get("listingId"),
        "Listing Agent":     (home.get("listingAgent") or {}).get("name"),
        "Listing Broker":    (home.get("listingBroker") or {}).get("name"),
        "Key Features":      key_features or key_facts_str,
        "Description":       home.get("listingRemarks"),
        "Has Virtual Tour":  home.get("hasVirtualTour"),
        "Has 3D Tour":       home.get("has3DTour"),
        "Is New Construction": home.get("isNewConstruction"),
        "Is Hot Listing":    home.get("isHot"),
        "Redfin URL":        redfin_url,
    }


def search_city(
    city: str,
    state: str,
    property_type_code: str = "1,2,3,4,5,6",
    status_code: str = "1",
    min_beds: Optional[int] = None,
    min_baths: Optional[float] = None,
    min_price: Optional[int] = None,
    max_price: Optional[int] = None,
    min_year_built: Optional[int] = None,
    limit: int = 0,
) -> tuple[list[dict], int]:
    """
    Full city search — paginates until all results collected.
    Returns (list_of_parsed_dicts, total_count_from_api).
    limit=0 means no limit (collect all).
    """
    session = _session()
    region_id, region_type = lookup_region(session, city, state)

    all_records: list[dict] = []
    total_count = 0
    page_num = 1

    while True:
        homes, count = fetch_listings_page(
            session, region_id, region_type, page_num,
            status_code, property_type_code,
            min_beds, min_baths, min_price, max_price, min_year_built,
        )

        if page_num == 1:
            total_count = count
            log.info("[%s %s] %d total listings — paginating...", city, state, total_count)

        if not homes:
            break

        for home in homes:
            if limit and len(all_records) >= limit:
                break
            record = parse_listing(home)
            if min_year_built is not None:
                year = record.get("Year Built")
                if year is None or int(year) < min_year_built:
                    continue
            all_records.append(record)

        log.info("[%s %s] Page %d | %d records collected", city, state, page_num, len(all_records))

        if limit and len(all_records) >= limit:
            break

        if len(homes) < settings.page_size:
            break

        page_num += 1
        time.sleep(settings.politeness_delay_s)

    log.info("[%s %s] Done — %d records", city, state, len(all_records))
    return all_records, total_count
