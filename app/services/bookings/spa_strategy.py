from datetime import UTC, datetime

from app.models.booking import RescheduleRequest, SpaBookingCreate
from app.services.bookings.base import BookingStrategy


class SpaBookingStrategy(BookingStrategy):
    def normalize_for_create(self, payload: SpaBookingCreate, listing: dict) -> tuple[dict, datetime]:
        _ = listing
        details = payload.details
        scheduled_at = datetime.combine(details.date, details.time).replace(tzinfo=UTC)
        self.ensure_future(scheduled_at)

        normalized = details.model_dump(mode="json")
        return normalized, scheduled_at

    def normalize_for_reschedule(self, existing_details: dict, payload: RescheduleRequest) -> tuple[dict, datetime]:
        if payload.time is None:
            raise ValueError("time is required for spa reschedule")

        scheduled_at = datetime.combine(payload.date, payload.time).replace(tzinfo=UTC)
        self.ensure_future(scheduled_at)

        existing_details["date"] = payload.date.isoformat()
        existing_details["time"] = payload.time.isoformat()
        return existing_details, scheduled_at
