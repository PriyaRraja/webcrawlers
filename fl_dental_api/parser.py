import re
import logging
from typing import Optional
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# Suffix noise appended by the site on some fields
_CLICK_NOISE = re.compile(r'\s*-?\s*Click on.*$', re.IGNORECASE)
# Help text that appears instead of a real address when address is absent
_HELP_TEXT = re.compile(r'if further information is needed', re.IGNORECASE)


def _clean(value: Optional[str]) -> Optional[str]:
    """Strip trailing noise and return None for empty or help-text values."""
    if not value:
        return None
    value = _CLICK_NOISE.sub("", value).strip().rstrip("/").strip()
    if _HELP_TEXT.search(value):
        return None
    return value or None


def _dt_dd_map(soup: BeautifulSoup) -> dict[str, str]:
    """Build a label → value map from all <dt>/<dd> pairs on the page."""
    mapping: dict[str, str] = {}
    for dt in soup.find_all("dt"):
        label = dt.get_text(" ", strip=True)
        if not label:
            continue
        dd = dt.find_next_sibling("dd")
        if dd:
            mapping[label] = dd.get_text(" ", strip=True)
    return mapping


def _match(mapping: dict[str, str], *prefixes: str) -> Optional[str]:
    """Return the first mapping value whose key starts with any of the given prefixes (case-insensitive)."""
    for key, val in mapping.items():
        for prefix in prefixes:
            if key.strip().lower().startswith(prefix.lower()):
                return val
    return None


def parse_detail(html: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    m = _dt_dd_map(soup)

    # Name: lives in the first <h3> that doesn't start with "License Number"
    name: Optional[str] = None
    for h3 in soup.find_all("h3"):
        text = h3.get_text(" ", strip=True)
        if not text.lower().startswith("license number"):
            name = text
            break

    # License number: in <h3> like "License Number: DN17478", also in dt/dd as "License"
    license_number: Optional[str] = None
    for h3 in soup.find_all("h3"):
        text = h3.get_text(" ", strip=True)
        if text.lower().startswith("license number"):
            parts = text.split(":", 1)
            if len(parts) == 2:
                license_number = parts[1].strip()
            break
    if not license_number:
        license_number = _match(m, "License")

    return {
        "name": _clean(name),
        "license_number": _clean(license_number),
        "profession": _clean(_match(m, "Profession")),
        "status": _clean(_match(m, "License Status")),
        "expiration_date": _clean(_match(m, "License Expiration Date", "Expiration Date")),
        "original_issue_date": _clean(_match(m, "License Original Issue Date", "Original Issue Date")),
        "address": _clean(_match(m, "Address of Record", "Primary Address", "Address")),
        "controlled_substance_prescriber": _clean(_match(m, "Controlled Substance")),
        "discipline_on_file": _clean(_match(m, "Discipline on File")),
        "public_complaint": _clean(_match(m, "Public Complaint")),
    }
