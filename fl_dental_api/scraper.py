import time
import logging
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
from config import settings
from exceptions import ProviderNotFoundError, AmbiguousResultsError, SiteUnavailableError

logger = logging.getLogger(__name__)

NO_RESULT_PHRASES = [
    "no records found",
    "no results",
    "0 records",
    "no matching",
    "did not return any",
]

MAINTENANCE_PHRASES = [
    "performing maintenance",
    "under maintenance",
    "temporarily unavailable",
]


def _normalize(text: str) -> str:
    return text.strip().lower().replace(",", "").replace(".", "")


def _find_input(page, *selectors):
    for sel in selectors:
        el = page.query_selector(sel)
        if el:
            return el
    return None


def _find_button(page, *selectors):
    for sel in selectors:
        el = page.query_selector(sel)
        if el:
            return el
    return None


def search_by_license(
    license_number: str,
    first_name: str,
    last_name: str,
) -> tuple[str, str]:
    """
    Drives the MQA search page with Playwright.
    Returns (detail_page_url, detail_page_html).
    Raises ProviderNotFoundError, AmbiguousResultsError, or SiteUnavailableError.
    """
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=settings.headless)
            try:
                page = browser.new_page()
                page.set_default_timeout(settings.browser_timeout_ms)

                # ── 1. Load search page ──────────────────────────────────────
                logger.info("Loading MQA search page")
                try:
                    page.goto(settings.mqa_base_url)
                    page.wait_for_load_state("networkidle")
                except PWTimeout:
                    raise SiteUnavailableError("MQA site timed out loading the search page")

                # ── 2. Maintenance check ─────────────────────────────────────
                body_text = page.inner_text("body").lower()
                if any(phrase in body_text for phrase in MAINTENANCE_PHRASES):
                    # Only bail if there's no form present either
                    if not page.query_selector("form"):
                        raise SiteUnavailableError("MQA site is under maintenance")

                # ── 3. Fill license number ───────────────────────────────────
                lic_input = _find_input(
                    page,
                    'input[id*="LicenseNumber"]',
                    'input[name*="LicenseNumber"]',
                    'input[id*="licenseNumber"]',
                    'input[name*="licenseNumber"]',
                    'input[id*="license"]',
                    'input[placeholder*="License"]',
                )
                if not lic_input:
                    raise SiteUnavailableError(
                        "Could not locate the license number input field on the MQA page"
                    )
                lic_input.fill(license_number)
                logger.info("Filled license number: %s", license_number)

                # ── 4. Submit form ───────────────────────────────────────────
                submit_btn = _find_button(
                    page,
                    'input[type="submit"]',
                    'button[type="submit"]',
                    'button:has-text("Search")',
                    'a:has-text("Search")',
                )
                if not submit_btn:
                    raise SiteUnavailableError("Could not find a search submit button on the MQA page")

                try:
                    submit_btn.click()
                    page.wait_for_load_state("networkidle")
                except PWTimeout:
                    raise SiteUnavailableError("MQA site timed out after submitting the search")

                time.sleep(settings.politeness_delay_s)

                # ── 5. Direct redirect to detail page? ───────────────────────
                current_url = page.url
                if "LicenseVerification" in current_url:
                    logger.info("Redirected directly to detail page: %s", current_url)
                    return current_url, page.content()

                # ── 6. No-results check ──────────────────────────────────────
                result_text = page.inner_text("body").lower()
                if any(phrase in result_text for phrase in NO_RESULT_PHRASES):
                    raise ProviderNotFoundError(
                        f"No provider found for license number: {license_number}"
                    )

                # ── 7. Collect result rows ───────────────────────────────────
                rows = page.query_selector_all("table tbody tr")
                if not rows:
                    # Some result pages use divs instead of tables
                    rows = page.query_selector_all('[class*="result"] [class*="row"]')

                if not rows:
                    raise ProviderNotFoundError(
                        f"Search returned no rows for license number: {license_number}"
                    )

                logger.info("Found %d result row(s)", len(rows))

                # ── 8. Resolve to a single detail URL ────────────────────────
                fn_lower = first_name.strip().lower()
                ln_lower = last_name.strip().lower()
                detail_url: Optional[str] = None
                matched_count = 0

                for row in rows:
                    link = row.query_selector("a[href]")
                    if not link:
                        continue

                    href = link.get_attribute("href") or ""
                    if not href:
                        continue

                    full_url = (
                        href
                        if href.startswith("http")
                        else settings.mqa_base_url.rsplit("/HealthCareProviders", 1)[0] + href
                    )

                    if len(rows) == 1:
                        # Only one row — take it without name matching
                        detail_url = full_url
                        break

                    # Multiple rows — require name match
                    row_text = _normalize(row.inner_text())
                    if fn_lower in row_text and ln_lower in row_text:
                        detail_url = full_url
                        matched_count += 1

                if matched_count > 1:
                    raise AmbiguousResultsError(
                        f"Multiple providers matched license {license_number} and name "
                        f"{first_name} {last_name}. Please provide a more specific license number."
                    )

                if not detail_url:
                    if len(rows) > 1:
                        raise AmbiguousResultsError(
                            f"Multiple results returned for license {license_number} but none "
                            f"matched the name {first_name} {last_name}."
                        )
                    raise ProviderNotFoundError(
                        f"No provider found for license {license_number}"
                    )

                # ── 9. Load detail page ──────────────────────────────────────
                logger.info("Navigating to detail page: %s", detail_url)
                try:
                    page.goto(detail_url)
                    page.wait_for_load_state("networkidle")
                except PWTimeout:
                    raise SiteUnavailableError(
                        f"Timed out loading provider detail page: {detail_url}"
                    )

                return page.url, page.content()

            finally:
                browser.close()

    except (ProviderNotFoundError, AmbiguousResultsError, SiteUnavailableError):
        raise
    except Exception as exc:
        logger.exception("Unexpected error in scraper")
        raise SiteUnavailableError(f"Unexpected browser error: {exc}") from exc
