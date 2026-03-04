from datetime import datetime

from pydantic import BaseModel, Field


class CustomerBookingQuoteRequest(BaseModel):
    provider_id: str = Field(min_length=24, max_length=24)
    provider_type: str = Field(default="restaurant", pattern="^(restaurant|spa|hotel|event)$")
    date: str = Field(min_length=10, max_length=10)
    time: str = Field(min_length=3, max_length=20)
    guests: int = Field(ge=1, le=20)
    seating_preference: str | None = Field(
        default=None, pattern="^(indoor|outdoor|no_preference)$"
    )
    special_notes: str | None = Field(default=None, max_length=2000)


class CustomerBookingCreateRequest(CustomerBookingQuoteRequest):
    auto_confirm: bool = False


class CustomerBookingRescheduleRequest(BaseModel):
    date: str = Field(min_length=10, max_length=10)
    time: str = Field(min_length=3, max_length=20)
    note: str | None = Field(default=None, max_length=1000)


class CustomerBookingCancelRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=1000)


class CustomerAvailabilityRequest(BaseModel):
    provider_id: str = Field(min_length=24, max_length=24)
    date: str = Field(min_length=10, max_length=10)


class CustomerMessageResponse(BaseModel):
    message: str


class CustomerBookingActionResponse(BaseModel):
    id: str
    booking_code: str
    status: str
    updated_at: datetime | str

