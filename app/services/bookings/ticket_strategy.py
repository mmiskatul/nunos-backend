from datetime import UTC, datetime

from app.models.booking import RescheduleRequest, TicketBookingCreate
from app.services.bookings.base import BookingStrategy


class TicketBookingStrategy(BookingStrategy):
    def normalize_for_create(self, payload: TicketBookingCreate, listing: dict) -> tuple[dict, datetime]:
        details = payload.details.model_dump(mode="json")

        event_dt = listing.get("event_datetime")
        if isinstance(event_dt, datetime):
            scheduled_at = event_dt if event_dt.tzinfo else event_dt.replace(tzinfo=UTC)
        else:
            scheduled_at = datetime.now(UTC)

        return details, scheduled_at

    def normalize_for_reschedule(self, existing_details: dict, payload: RescheduleRequest) -> tuple[dict, datetime]:
        _ = payload
        raise ValueError("Ticket bookings cannot be rescheduled")
