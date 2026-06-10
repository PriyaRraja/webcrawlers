import asyncio
import logging
from fastapi import FastAPI, HTTPException
from models import LookupRequest, LookupResponse, ProviderData
from scraper import search_by_license
from parser import parse_detail
from exceptions import ProviderNotFoundError, AmbiguousResultsError, SiteUnavailableError

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

app = FastAPI(
    title="FL Dental License Lookup",
    description="Search Florida MQA for dental provider license information by license number.",
    version="1.0.0",
)


def _names_match(result_name: str | None, first: str, last: str) -> bool:
    if not result_name:
        return False
    n = result_name.lower()
    return first.strip().lower() in n and last.strip().lower() in n


@app.post("/lookup", response_model=LookupResponse)
async def lookup(req: LookupRequest):
    """
    Look up a Florida dental provider by license number.
    Returns the MQA snapshot URL and extracted license details.
    """
    try:
        snapshot_url, html = await asyncio.to_thread(
            search_by_license,
            req.license_number,
            req.first_name,
            req.last_name,
        )
    except ProviderNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except AmbiguousResultsError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except SiteUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc))

    data_dict = parse_detail(html)
    provider = ProviderData(**data_dict)
    name_mismatch = not _names_match(provider.name, req.first_name, req.last_name)

    return LookupResponse(
        snapshot_url=snapshot_url,
        name_mismatch=name_mismatch,
        data=provider,
    )


@app.get("/health")
async def health():
    return {"status": "ok"}
