from bson.errors import InvalidId
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel

from app.modules.platform_admin.deps import get_user_repository
from app.modules.vendor.deps_auth import get_current_vendor
from app.repositories.user_repository import UserRepository

router = APIRouter(prefix="/vendor/users", tags=["Vendor - Users (Live)"])


class VendorUserListResponse(BaseModel):
    users: list[dict]
    total: int


@router.get("", response_model=VendorUserListResponse)
def list_all_users(
    limit: int = Query(default=50, ge=1, le=200),
    skip: int = Query(default=0, ge=0),
    search: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    _: dict = Depends(get_current_vendor),
    user_repo: UserRepository = Depends(get_user_repository),
) -> VendorUserListResponse:
    users = user_repo.list_users(limit=limit, skip=skip, search=search, status=status_filter)
    total = user_repo.count_users(search=search, status=status_filter)
    return VendorUserListResponse(users=users, total=total)


@router.get("/{user_id}", response_model=dict)
def get_user_details(
    user_id: str,
    _: dict = Depends(get_current_vendor),
    user_repo: UserRepository = Depends(get_user_repository),
) -> dict:
    try:
        user = user_repo.get_by_id(user_id)
    except InvalidId as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.") from exc
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
    return user

