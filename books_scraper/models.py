from typing import Optional, Literal
from pydantic import BaseModel, field_validator


class SearchRequest(BaseModel):
    title: str = ""
    min_rating: int = 1
    max_price: Optional[float] = None
    availability: Literal["all", "in_stock"] = "all"
    limit: int = 50

    @field_validator("min_rating")
    @classmethod
    def rating_range(cls, v: int) -> int:
        if not 1 <= v <= 5:
            raise ValueError("min_rating must be between 1 and 5")
        return v

    @field_validator("limit")
    @classmethod
    def limit_positive(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("limit must be a positive integer")
        return v

    @field_validator("max_price")
    @classmethod
    def price_positive(cls, v: Optional[float]) -> Optional[float]:
        if v is not None and v <= 0:
            raise ValueError("max_price must be positive")
        return v


class BookItem(BaseModel):
    title: str
    price: float
    rating: int
    availability: str


class SearchResponse(BaseModel):
    query: str
    total_matched: int
    returned: int
    books: list[BookItem]
