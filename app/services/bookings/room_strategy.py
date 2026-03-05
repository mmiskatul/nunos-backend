from datetime import UTC, datetime, time

from app.models.booking import RescheduleRequest, RoomBookingCreate
from app.services.bookings.base import BookingStrategy


class RoomBookingStrategy(BookingStrategy):
    def normalize_for_create(self, payload: RoomBookingCreate, listing: dict) -> tuple[dict, datetime]:
        _ = listing
        details = payload.details

        nights = details.nights
        if nights is None:
            nights = (details.check_out - details.check_in).days
        if nights <= 0:
            raise ValueError("nights must be greater than 0")

        scheduled_at = datetime.combine(details.check_in, time(14, 0)).replace(tzinfo=UTC)
        self.ensure_future(scheduled_at)

        normalized = details.model_dump(mode="json")
        normalized["nights"] = nights
        return normalized, scheduled_at

    def normalize_for_reschedule(self, existing_details: dict, payload: RescheduleRequest) -> tuple[dict, datetime]:
        scheduled_at = datetime.combine(payload.date, time(14, 0)).replace(tzinfo=UTC)
        self.ensure_future(scheduled_at)

        existing_details["check_in"] = payload.date.isoformat()
        return existing_details, scheduled_at
