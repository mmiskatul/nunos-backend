from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, conlist

from app.domain.enums import ListingType


class GeoPoint(BaseModel):
    type: str = "Point"
    coordinates: conlist(float, min_length=2, max_length=2)


class RatingSummary(BaseModel):
    average: float = 0.0
    count: int = 0


class ListingCreate(BaseModel):
    name: str
    type: ListingType
    description: str
    images: list[str] = Field(default_factory=list)
    location: GeoPoint
    price_level: int = Field(ge=1, le=5)
    near_metro_station: str | None = None
    has_offers: bool = False
    event_datetime: datetime | None = None


class ListingSummary(BaseModel):
    id: str
    name: str
    type: ListingType
    description: str
    images: list[str]
    location: GeoPoint
    price_level: int
    near_metro_station: str | None = None
    has_offers: bool
    rating_summary: RatingSummary


class ListingSearchQuery(BaseModel):
    q: str | None = None
    lat: float | None = None
    lng: float | None = None
    radius_meters: int | None = Field(default=3000, ge=100, le=30000)
    budget: int | None = Field(default=None, ge=1, le=5)
    near_metro: str | None = None
    offers: bool | None = None
    rating: float | None = Field(default=None, ge=0, le=5)
    types: list[ListingType] | None = None
    limit: int = Field(default=20, ge=1, le=100)


class ReviewCreateRequest(BaseModel):
    rating: int = Field(ge=1, le=5)
    comment: str = Field(min_length=2, max_length=1000)


class ReviewResponse(BaseModel):
    id: str
    user_id: str
    listing_id: str
    rating: int
    comment: str
    created_at: datetime


class ListingDetail(ListingSummary):
    reviews: list[ReviewResponse] = Field(default_factory=list)


class FavoriteToggleRequest(BaseModel):
    listing_id: str


class PromoValidationRequest(BaseModel):
    listing_id: str
    promo_code: str | None = None


class PromoValidationResult(BaseModel):
    valid: bool
    message: str
    discount_percent: float | None = None
    offer_id: str | None = None
