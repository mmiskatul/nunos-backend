from datetime import UTC, datetime

from pydantic import BaseModel, Field


class ItineraryStep(BaseModel):
    time: str
    title: str
    listing_id: str | None = None
    listing_name: str | None = None
    note: str | None = None


class BookingSuggestion(BaseModel):
    booking_type: str
    listing_id: str
    reason: str


class AIPlan(BaseModel):
    summary: str
    estimated_budget: str
    steps: list[ItineraryStep] = Field(default_factory=list)
    booking_suggestions: list[BookingSuggestion] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
