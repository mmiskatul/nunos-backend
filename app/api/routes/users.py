from fastapi import APIRouter, Depends

from app.api.deps import get_auth_service, get_current_user
from app.schemas.auth import UserPublic
from app.schemas.user import LocationPreferenceUpdate
from app.services.auth_service import AuthService

router = APIRouter(prefix="/users", tags=["Users"])


@router.patch("/me/location", response_model=UserPublic)
def update_location(
    payload: LocationPreferenceUpdate,
    current_user: dict = Depends(get_current_user),
    auth_service: AuthService = Depends(get_auth_service),
) -> UserPublic:
    return auth_service.update_location_preference(current_user["id"], payload.enable_location)

