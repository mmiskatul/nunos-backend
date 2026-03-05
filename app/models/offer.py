from datetime import datetime

from pydantic import BaseModel, Field


class OfferCreate(BaseModel):
    listing_id: str
    title: str
    discount_percent: float = Field(ge=0, le=100)
    require_code: bool = False
    promo_code: str | None = None
    starts_at: datetime | None = None
    ends_at: datetime | None = None


class OfferResponse(BaseModel):
    id: str
    listing_id: str
    title: str
    discount_percent: float
    require_code: bool
    promo_code: str | None = None
    starts_at: datetime | None = None
    ends_at: datetime | None = None
