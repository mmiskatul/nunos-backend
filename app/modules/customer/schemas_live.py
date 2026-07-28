from datetime import datetime

from pydantic import BaseModel, Field


class CustomerBookingQuoteRequest(BaseModel):
    provider_id: str = Field(min_length=24, max_length=24)
    provider_type: str = Field(default="restaurant", pattern="^(restaurant|spa|hotel|event)$")
    date: str = Field(min_length=10, max_length=10)
    time: str = Field(min_length=3, max_length=20)
    guests: int = Field(ge=1, le=20)
    seating_preference: str | None = Field(default=None, max_length=50)
    special_notes: str | None = Field(default=None, max_length=2000)
    promo_code: str | None = Field(default=None, max_length=80)


class CustomerBookingCreateRequest(CustomerBookingQuoteRequest):
    auto_confirm: bool = False


class CustomerRestaurantBookingCreateRequest(BaseModel):
    date: str = Field(min_length=10, max_length=10)
    time: str = Field(min_length=3, max_length=20)
    guests: int = Field(ge=1, le=20)
    seating_preference: str | None = Field(default=None, max_length=50)
    special_notes: str | None = Field(default=None, max_length=2000)
    auto_confirm: bool = False
    promo_code: str | None = Field(default=None, max_length=80)


class CustomerHotelBookingCreateRequest(BaseModel):
    check_in_date: str = Field(min_length=10, max_length=10)
    check_out_date: str = Field(min_length=10, max_length=10)
    guests: int = Field(ge=1, le=10)
    special_notes: str | None = Field(default=None, max_length=2000)
    auto_confirm: bool = False
    guest_name: str | None = Field(default=None, max_length=200)
    guest_email: str | None = Field(default=None, max_length=200)
    guest_phone: str | None = Field(default=None, max_length=40)
    promo_code: str | None = Field(default=None, max_length=80)


class CustomerHotelBookingQuoteRequest(BaseModel):
    check_in_date: str = Field(min_length=10, max_length=10)
    check_out_date: str = Field(min_length=10, max_length=10)
    guests: int = Field(ge=1, le=10)
    room_id: str | None = Field(default=None, min_length=24, max_length=24)
    promo_code: str | None = Field(default=None, max_length=80)


class CustomerSpaBookingCreateRequest(BaseModel):
    date: str = Field(min_length=10, max_length=10)
    time: str = Field(min_length=3, max_length=20)
    guests: int = Field(default=1, ge=1, le=10)
    service_id: str | None = Field(default=None, min_length=24, max_length=24)
    special_notes: str | None = Field(default=None, max_length=2000)
    auto_confirm: bool = False
    promo_code: str | None = Field(default=None, max_length=80)


class CustomerBookingRescheduleRequest(BaseModel):
    date: str = Field(min_length=10, max_length=10)
    time: str = Field(min_length=3, max_length=20)
    note: str | None = Field(default=None, max_length=1000)


class CustomerBookingCancelRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=1000)


class CustomerBookingReviewRequest(BaseModel):
    rating: int = Field(ge=1, le=5)
    review_text: str = Field(min_length=2, max_length=1000)


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


class CustomerEventTicketBookingRequest(BaseModel):
    quantity: int = Field(default=1, ge=1, le=20)
    notes: str | None = Field(default=None, max_length=2000)
    auto_confirm: bool = False
    promo_code: str | None = Field(default=None, max_length=80)

