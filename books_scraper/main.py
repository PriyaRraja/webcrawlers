import asyncio
import logging
from fastapi import FastAPI, HTTPException
from models import SearchRequest, SearchResponse, BookItem
from scraper import scrape_books
from exceptions import SiteUnavailableError, NoResultsError

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

app = FastAPI(
    title="Books to Scrape API",
    description="Search books from books.toscrape.com by title with optional filters.",
    version="1.0.0",
)


@app.post("/search", response_model=SearchResponse)
async def search(req: SearchRequest):
    """Search books by title with optional rating, price, and availability filters."""
    try:
        records = await asyncio.to_thread(
            scrape_books,
            req.title,
            req.min_rating,
            req.max_price,
            req.availability,
            req.limit,
        )
    except NoResultsError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except SiteUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc))

    books = [
        BookItem(
            title=r["Title"],
            price=r["Price"],
            rating=r["Rating"],
            availability=r["Availability"],
        )
        for r in records
    ]

    return SearchResponse(
        query=req.title or "(all books)",
        total_matched=len(books),
        returned=len(books),
        books=books,
    )


@app.get("/health")
async def health():
    return {"status": "ok"}
