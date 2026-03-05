from fastapi import APIRouter, Depends

from app.api.deps import get_booking_service, get_current_user_id
from app.core.responses import envelope
from app.core.serializers import to_jsonable
from app.models.booking import BookingCreateRequest, RescheduleRequest
from app.services.booking_service import BookingService

router = APIRouter(prefix="/bookings", tags=["Bookings"])


@router.post("")
async def create_booking(
    payload: BookingCreateRequest,
    user_id: str = Depends(get_current_user_id),
    service: BookingService = Depends(get_booking_service),
):
    booking = await service.create_booking(user_id, payload)
    return envelope(to_jsonable(booking))


@router.get("/{booking_id}")
async def get_booking(booking_id: str, service: BookingService = Depends(get_booking_service)):
    booking = await service.get_booking(booking_id)
    return envelope(to_jsonable(booking))


@router.patch("/{booking_id}/cancel")
async def cancel_booking(booking_id: str, service: BookingService = Depends(get_booking_service)):
    booking = await service.cancel_booking(booking_id)
    return envelope(to_jsonable(booking))


@router.patch("/{booking_id}/reschedule")
async def reschedule_booking(
    booking_id: str,
    payload: RescheduleRequest,
    service: BookingService = Depends(get_booking_service),
):
    booking = await service.reschedule_booking(booking_id, payload)
    return envelope(to_jsonable(booking))


@router.patch("/{booking_id}/confirm")
async def confirm_booking(booking_id: str, service: BookingService = Depends(get_booking_service)):
    booking = await service.confirm_booking(booking_id)
    return envelope(to_jsonable(booking))
