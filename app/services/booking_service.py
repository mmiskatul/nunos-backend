from fastapi import HTTPException, status

from app.core.config import Settings
from app.domain.enums import BookingStatus
from app.models.booking import BookingCreateRequest, RescheduleRequest
from app.repositories.base import oid
from app.repositories.booking_repository import BookingRepository
from app.repositories.listing_repository import ListingRepository
from app.repositories.user_repository import UserRepository
from app.services.bookings.factory import BookingStrategyFactory


class BookingService:
    def __init__(
        self,
        booking_repo: BookingRepository,
        listing_repo: ListingRepository,
        user_repo: UserRepository,
        strategy_factory: BookingStrategyFactory,
        settings: Settings,
    ):
        self.booking_repo = booking_repo
        self.listing_repo = listing_repo
        self.user_repo = user_repo
        self.strategy_factory = strategy_factory
        self.settings = settings

    async def create_booking(self, user_id: str, payload: BookingCreateRequest) -> dict:
        listing = await self.listing_repo.get_by_id(payload.listing_id)
        if not listing:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Listing not found")

        strategy = self.strategy_factory.get(payload.booking_type.value)
        try:
            normalized_details, scheduled_at = strategy.normalize_for_create(payload, listing)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

        booking_doc = {
            "user_id": oid(user_id),
            "listing_id": oid(payload.listing_id),
            "booking_type": payload.booking_type.value,
            "status": payload.status.value,
            "details": normalized_details,
            "scheduled_at": scheduled_at,
            "promo_code": payload.promo_code,
        }

        booking = await self.booking_repo.create(booking_doc)

        if payload.status == BookingStatus.confirmed:
            await self.user_repo.add_points(user_id, self.settings.loyalty_points_on_confirm)

        return booking

    async def get_booking(self, booking_id: str) -> dict:
        booking = await self.booking_repo.get_by_id(booking_id)
        if not booking:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")
        return booking

    async def cancel_booking(self, booking_id: str) -> dict:
        booking = await self.booking_repo.update_status(booking_id, BookingStatus.cancelled.value)
        if not booking:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")
        return booking

    async def confirm_booking(self, booking_id: str) -> dict:
        booking = await self.booking_repo.get_by_id(booking_id)
        if not booking:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")

        if booking.get("status") != BookingStatus.confirmed.value:
            booking = await self.booking_repo.update_status(booking_id, BookingStatus.confirmed.value)
            await self.user_repo.add_points(str(booking["user_id"]), self.settings.loyalty_points_on_confirm)
        return booking

    async def reschedule_booking(self, booking_id: str, payload: RescheduleRequest) -> dict:
        booking = await self.booking_repo.get_by_id(booking_id)
        if not booking:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")

        strategy = self.strategy_factory.get(booking["booking_type"])
        try:
            details, scheduled_at = strategy.normalize_for_reschedule(dict(booking["details"]), payload)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

        updated = await self.booking_repo.reschedule(booking_id, details, scheduled_at)
        if not updated:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")
        return updated

    async def list_my_bookings(self, user_id: str, status_filter: str | None) -> list[dict]:
        if status_filter == "upcoming":
            return await self.booking_repo.list_for_user(user_id, upcoming=True)
        if status_filter == "past":
            return await self.booking_repo.list_for_user(user_id, upcoming=False)
        return await self.booking_repo.list_for_user(user_id, upcoming=None)
