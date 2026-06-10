import re
from typing import Optional
from pydantic import BaseModel, field_validator

STATE_RE = re.compile(r'^[A-Za-z]{2}$')

VALID_PROPERTY_TYPES = {"all", "house", "condo", "townhouse", "land", "multifamily", "other"}
VALID_STATUSES = {"for_sale", "sold"}

PROPERTY_TYPE_CODES = {
    "all":        "1,2,3,4,5,6",
    "house":      "1",
    "condo":      "2",
    "townhouse":  "3",
    "land":       "4",
    "other":      "5",
    "multifamily": "6",
}

STATUS_CODES = {
    "for_sale": "1",
    "sold":     "9",
}


class SearchRequest(BaseModel):
    city: str
    state: str
    property_type: str = "all"
    status: str = "for_sale"
    min_beds: Optional[int] = None
    min_baths: Optional[float] = None
    min_price: Optional[int] = None
    max_price: Optional[int] = None
    limit: int = 50

    @field_validator("city")
    @classmethod
    def city_not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("city must not be blank")
        return v

    @field_validator("state")
    @classmethod
    def valid_state(cls, v: str) -> str:
        v = v.strip().upper()
        if not STATE_RE.match(v):
            raise ValueError("state must be a 2-letter code (e.g. FL, CA)")
        return v

    @field_validator("property_type")
    @classmethod
    def valid_property_type(cls, v: str) -> str:
        v = v.strip().lower()
        if v not in VALID_PROPERTY_TYPES:
            raise ValueError(f"property_type must be one of: {', '.join(sorted(VALID_PROPERTY_TYPES))}")
        return v

    @field_validator("status")
    @classmethod
    def valid_status(cls, v: str) -> str:
        v = v.strip().lower()
        if v not in VALID_STATUSES:
            raise ValueError(f"status must be one of: {', '.join(sorted(VALID_STATUSES))}")
        return v

    @field_validator("limit")
    @classmethod
    def positive_limit(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("limit must be a positive integer")
        return v


class ListingData(BaseModel):
    address: Optional[str] = None
    unit: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip: Optional[str] = None
    neighborhood: Optional[str] = None
    price: Optional[str] = None
    beds: Optional[int] = None
    baths: Optional[float] = None
    full_baths: Optional[int] = None
    sqft: Optional[int] = None
    price_per_sqft: Optional[str] = None
    lot_size: Optional[int] = None
    year_built: Optional[int] = None
    stories: Optional[float] = None
    property_type: Optional[str] = None
    status: Optional[str] = None
    days_on_market: Optional[int] = None
    hoa_fee: Optional[str] = None
    garage_spaces: Optional[int] = None
    parking_spaces: Optional[int] = None
    has_pool: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    mls_number: Optional[str] = None
    property_id: Optional[int] = None
    listing_id: Optional[int] = None
    listing_agent: Optional[str] = None
    listing_broker: Optional[str] = None
    key_features: Optional[str] = None
    description: Optional[str] = None
    has_virtual_tour: Optional[bool] = None
    has_3d_tour: Optional[bool] = None
    is_new_construction: Optional[bool] = None
    is_hot_listing: Optional[bool] = None
    redfin_url: Optional[str] = None


class SearchResponse(BaseModel):
    city: str
    state: str
    total_found: int
    returned: int
    listings: list[ListingData]
