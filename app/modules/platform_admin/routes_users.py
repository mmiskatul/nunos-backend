from fastapi import APIRouter, Depends, HTTPException, Query, status
from bson.errors import InvalidId

from app.modules.platform_admin.deps import get_user_repository
from app.modules.platform_admin.schemas import AdminUserListResponse, UserStatusUpdateRequest
from app.repositories.user_repository import UserRepository

router = APIRouter(prefix="/platform-admin/users", tags=["Platform Admin - Users (Live)"])


@router.get("", response_model=AdminUserListResponse)
def list_users(
    limit: int = Query(default=50, ge=1, le=200),
    skip: int = Query(default=0, ge=0),
    search: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    user_repo: UserRepository = Depends(get_user_repository),
) -> AdminUserListResponse:
    users = user_repo.list_users(limit=limit, skip=skip, search=search, status=status_filter)
    total = user_repo.count_users(search=search, status=status_filter)
    return AdminUserListResponse(users=users, total=total)


@router.get("/{user_id}", response_model=dict)
def get_user(
    user_id: str,
    user_repo: UserRepository = Depends(get_user_repository),
) -> dict:
    try:
        user = user_repo.get_by_id(user_id)
    except InvalidId as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.") from exc
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
    return user


@router.patch("/{user_id}/status", response_model=dict)
def update_user_status(
    user_id: str,
    payload: UserStatusUpdateRequest,
    user_repo: UserRepository = Depends(get_user_repository),
) -> dict:
    try:
        updated = user_repo.update_status(user_id, payload.status)
    except InvalidId as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.") from exc
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
    return updated

