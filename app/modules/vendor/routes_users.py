from bson import ObjectId
from bson.errors import InvalidId
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel

from app.core.serializers import to_jsonable
from app.modules.vendor.deps_auth import get_current_vendor, get_vendor_portal_repository
from app.modules.vendor.repositories_portal import VendorPortalRepository
from app.modules.platform_admin.deps import get_user_repository
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
    current_vendor: dict = Depends(get_current_vendor),
    portal_repo: VendorPortalRepository = Depends(get_vendor_portal_repository),
) -> VendorUserListResponse:
    match: dict = {"vendor_id": ObjectId(current_vendor["id"])}
    if search:
        match["$or"] = [
            {"customer_name": {"$regex": search, "$options": "i"}},
            {"customer_email": {"$regex": search, "$options": "i"}},
            {"customer_phone": {"$regex": search, "$options": "i"}},
        ]

    pipeline = [
        {"$match": match},
        {"$sort": {"created_at": -1}},
        {
            "$group": {
                "_id": {
                    "email": "$customer_email",
                    "phone": "$customer_phone",
                    "name": "$customer_name",
                },
                "customer_name": {"$first": "$customer_name"},
                "email": {"$first": "$customer_email"},
                "phone": {"$first": "$customer_phone"},
                "latest_booking_at": {"$first": "$created_at"},
            }
        },
        {"$sort": {"latest_booking_at": -1}},
        {"$skip": skip},
        {"$limit": limit},
    ]
    total_pipeline = [
        {"$match": match},
        {
            "$group": {
                "_id": {
                    "email": "$customer_email",
                    "phone": "$customer_phone",
                    "name": "$customer_name",
                }
            }
        },
        {"$count": "total"},
    ]
    rows = list(portal_repo.bookings.aggregate(pipeline))
    users = [
        {
            "id": f"{(row.get('email') or '').lower()}|{row.get('phone') or ''}",
            "full_name": row.get("customer_name"),
            "email": row.get("email"),
            "phone": row.get("phone"),
            "latest_booking_at": row.get("latest_booking_at"),
        }
        for row in rows
    ]
    total_row = list(portal_repo.bookings.aggregate(total_pipeline))
    total = int(total_row[0]["total"]) if total_row else 0
    return VendorUserListResponse(users=users, total=total)


@router.get("/{user_id}", response_model=dict)
async def get_user_details(
    user_id: str,
    current_vendor: dict = Depends(get_current_vendor),
    portal_repo: VendorPortalRepository = Depends(get_vendor_portal_repository),
    user_repo: UserRepository = Depends(get_user_repository),
) -> dict:
    try:
        user = await user_repo.get_by_id(user_id)
    except (InvalidId, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.") from exc
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
    contact_filters = []
    if user.get("email"):
        contact_filters.append({"customer_email": user["email"]})
    if user.get("phone"):
        contact_filters.append({"customer_phone": user["phone"]})
    if not contact_filters:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
    has_relationship = (
        portal_repo.bookings.count_documents(
            {"vendor_id": ObjectId(current_vendor["id"]), "$or": contact_filters}
        )
        > 0
    )
    if not has_relationship:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
    return to_jsonable(user)
