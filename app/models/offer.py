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


class AdminOfferProviderBreakdown(BaseModel):
    provider_id: str
    provider_name: str
    vendor_category: str = "Uncategorized"
    status: str = "inactive"
    redemptions: int = 0
    engaged_users: int = 0
    active: bool = True


class AdminOfferResponse(BaseModel):
    id: str
    name: str
    title: str
    discount_type: str
    discount_value: float
    discount_percent: float | None = None
    require_code: bool = False
    promo_code: str | None = None
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    applied_to: str = "All Vendors"
    selected_vendor_ids: list[str] = []
    is_active: bool = True
    redemptions: int = 0
    provider_count: int = 0
    engaged_users: int = 0
    provider_breakdown: list[AdminOfferProviderBreakdown] = []
    created_at: datetime | None = None
    updated_at: datetime | None = None
