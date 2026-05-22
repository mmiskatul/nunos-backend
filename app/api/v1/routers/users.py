from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import (
    get_booking_service,
    get_current_user_id,
    get_loyalty_service,
    get_user_repo,
)
from app.core.responses import envelope
from app.core.serializers import to_jsonable
from app.repositories.user_repository import UserRepository
from app.schemas.user import PersonalDetailsResponse, PersonalDetailsUpdate
from app.services.booking_service import BookingService
from app.services.loyalty_service import LoyaltyService

router = APIRouter(prefix="/users", tags=["Users"])


def serialize_personal_details(user: dict) -> PersonalDetailsResponse:
    return PersonalDetailsResponse(
        id=str(user["_id"]),
        full_name=user.get("full_name", ""),
        email=user.get("email"),
        phone=user.get("phone"),
        date_of_birth=user.get("date_of_birth"),
        profile_image_url=user.get("profile_image_url"),
        created_at=user["created_at"],
        points_balance=user.get("points_balance", 0),
        location_enabled=user.get("location_enabled", False),
    )


@router.get("/me")
async def get_me(
    user_id: str = Depends(get_current_user_id),
    user_repo: UserRepository = Depends(get_user_repo),
):
    user = await user_repo.find_by_id(user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return envelope(to_jsonable(serialize_personal_details(user).model_dump()))


@router.patch("/me/personal-details")
async def update_personal_details(
    payload: PersonalDetailsUpdate,
    user_id: str = Depends(get_current_user_id),
    user_repo: UserRepository = Depends(get_user_repo),
):
    current_user = await user_repo.find_by_id(user_id)
    if not current_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    normalized_email = payload.email.lower() if payload.email else None
    normalized_phone = payload.phone.strip() if payload.phone else None

    if normalized_email and normalized_email != current_user.get("email"):
        existing_email_user = await user_repo.find_by_email(normalized_email)
        if existing_email_user and str(existing_email_user["_id"]) != user_id:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already exists")

    if normalized_phone and normalized_phone != current_user.get("phone"):
        existing_phone_user = await user_repo.find_by_phone(normalized_phone)
        if existing_phone_user and str(existing_phone_user["_id"]) != user_id:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Phone already exists")

    updated_user = await user_repo.update_profile(
        user_id,
        {
            "full_name": payload.full_name.strip(),
            "email": normalized_email,
            "phone": normalized_phone,
            "date_of_birth": payload.date_of_birth.isoformat() if payload.date_of_birth else None,
        },
    )
    if not updated_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    return envelope(to_jsonable(serialize_personal_details(updated_user).model_dump()))


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
