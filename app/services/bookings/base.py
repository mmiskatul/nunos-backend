from abc import ABC, abstractmethod
from datetime import UTC, datetime

from app.models.booking import RescheduleRequest


class BookingStrategy(ABC):
    @abstractmethod
    def normalize_for_create(self, payload, listing: dict) -> tuple[dict, datetime]:
        raise NotImplementedError

    @abstractmethod
    def normalize_for_reschedule(self, existing_details: dict, payload: RescheduleRequest) -> tuple[dict, datetime]:
        raise NotImplementedError

    def ensure_future(self, scheduled_at: datetime) -> None:
        if scheduled_at <= datetime.now(UTC):
            raise ValueError("Booking date/time must be in the future")
