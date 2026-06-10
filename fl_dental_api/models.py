import re
from typing import Optional
from pydantic import BaseModel, field_validator

LICENSE_RE = re.compile(r'^[A-Za-z]{2}\d+$')


class LookupRequest(BaseModel):
    first_name: str
    last_name: str
    license_number: str

    @field_validator("first_name", "last_name")
    @classmethod
    def not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("must not be blank")
        return v

    @field_validator("license_number")
    @classmethod
    def normalize_license(cls, v: str) -> str:
        v = v.strip().upper()
        if not LICENSE_RE.match(v):
            raise ValueError("must be format like DN12345 (two letters followed by digits)")
        return v


class ProviderData(BaseModel):
    name: Optional[str] = None
    license_number: Optional[str] = None
    profession: Optional[str] = None
    status: Optional[str] = None
    expiration_date: Optional[str] = None
    original_issue_date: Optional[str] = None
    address: Optional[str] = None
    controlled_substance_prescriber: Optional[str] = None
    discipline_on_file: Optional[str] = None
    public_complaint: Optional[str] = None


class LookupResponse(BaseModel):
    snapshot_url: str
    name_mismatch: bool
    data: ProviderData
