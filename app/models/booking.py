from datetime import date, datetime, time
from typing import Annotated, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.domain.enums import BookingStatus, BookingType


class TableBookingDetails(BaseModel):
    date: date
    time: time
    guests: int = Field(ge=1, le=20)
    seating_preference: str | None = None
    special_notes: str | None = None


class RoomPriceBreakdown(BaseModel):
    base_price: float = Field(ge=0)
    taxes: float = Field(ge=0)
    fees: float = Field(ge=0)
    total: float = Field(ge=0)


class RoomCancellationPolicy(BaseModel):
    free_cancellation_until: datetime | None = None
    cancellation_fee_percent: float = Field(default=0, ge=0, le=100)


class RoomBookingDetails(BaseModel):
    check_in: date
    check_out: date
    nights: int | None = None
    guests: int = Field(ge=1, le=10)
    room_id: str
    price_breakdown: RoomPriceBreakdown
    cancellation_policy: RoomCancellationPolicy

    @model_validator(mode="after")
    def validate_dates(self) -> "RoomBookingDetails":
        if self.check_out <= self.check_in:
            raise ValueError("check_out must be after check_in")
        if self.nights is not None and self.nights <= 0:
            raise ValueError("nights must be greater than 0")
        return self


class SpaBookingDetails(BaseModel):
    service_id: str
    date: date
    time: time
    notes: str | None = None


class TicketBookingDetails(BaseModel):
    event_id: str
    quantity: int = Field(ge=1, le=20)


class BaseBookingCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    listing_id: str
    status: BookingStatus = BookingStatus.pending
    promo_code: str | None = None


class TableBookingCreate(BaseBookingCreate):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "listing_id": "67c91f56fa9c73de7f8de001",
                "booking_type": "table",
                "status": "pending",
                "details": {
                    "date": "2026-03-20",
                    "time": "19:30:00",
                    "guests": 4,
                    "seating_preference": "window",
                    "special_notes": "Birthday dinner",
                },
            }
        }
    )

    booking_type: Literal[BookingType.table]
    details: TableBookingDetails


class RoomBookingCreate(BaseBookingCreate):
    booking_type: Literal[BookingType.room]
    details: RoomBookingDetails


class SpaBookingCreate(BaseBookingCreate):
    booking_type: Literal[BookingType.spa]
    details: SpaBookingDetails


class TicketBookingCreate(BaseBookingCreate):
    booking_type: Literal[BookingType.ticket]
    details: TicketBookingDetails


BookingCreateRequest = Annotated[
    Union[TableBookingCreate, RoomBookingCreate, SpaBookingCreate, TicketBookingCreate],
    Field(discriminator="booking_type"),
]


class BookingResponse(BaseModel):
    id: str
    user_id: str
    listing_id: str
    booking_type: BookingType
    status: BookingStatus
    details: dict
    scheduled_at: datetime
    promo_code: str | None = None
    created_at: datetime
    updated_at: datetime


class RescheduleRequest(BaseModel):
    date: date
    time: time | None = None


class BookingTimelineFilter(BaseModel):
    status: Literal["upcoming", "past"] | None = None
