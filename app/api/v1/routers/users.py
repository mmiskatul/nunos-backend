from fastapi import APIRouter, Depends, Query

from app.api.deps import (
    get_booking_service,
    get_current_user_id,
    get_loyalty_service,
    get_user_repo,
)
from app.core.responses import envelope
from app.core.serializers import to_jsonable
from app.repositories.user_repository import UserRepository
from app.services.booking_service import BookingService
from app.services.loyalty_service import LoyaltyService

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("/me")
async def get_me(
    user_id: str = Depends(get_current_user_id),
    user_repo: UserRepository = Depends(get_user_repo),
):
    user = await user_repo.find_by_id(user_id)
    return envelope(to_jsonable(user))


@router.get("/me/bookings")
async def my_bookings(
    status: str | None = Query(default=None, pattern="^(upcoming|past)$"),
    user_id: str = Depends(get_current_user_id),
    service: BookingService = Depends(get_booking_service),
):
    bookings = await service.list_my_bookings(user_id, status)
    return envelope(to_jsonable(bookings), meta={"count": len(bookings), "status_filter": status})


@router.get("/me/loyalty")
async def my_loyalty(
    user_id: str = Depends(get_current_user_id),
    service: LoyaltyService = Depends(get_loyalty_service),
):
    loyalty = await service.get_loyalty(user_id)
    return envelope(loyalty)
