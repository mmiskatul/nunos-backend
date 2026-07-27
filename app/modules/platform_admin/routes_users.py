import asyncio
from datetime import date, datetime

from bson import ObjectId
from bson.errors import InvalidId
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pymongo.database import Database

from app.core.serializers import to_jsonable
from app.api.deps import get_auth_service
from app.models.user import ForgotPasswordRequest
from app.modules.platform_admin.deps import get_platform_admin_db, get_user_repository
from app.modules.platform_admin.deps_auth import get_current_platform_admin
from app.modules.platform_admin.schemas import AdminUserListResponse, UserStatusUpdateRequest
from app.repositories.user_repository import UserRepository

router = APIRouter(
    prefix="/platform-admin/users",
    tags=["Platform Admin - Users (Live)"],
    dependencies=[Depends(get_current_platform_admin)],
)


def _normalize_user_status(user: dict) -> str:
    raw_status = str(user.get("status") or "").lower()
    if raw_status in {"active", "blocked"}:
        return raw_status
    if user.get("is_active") is False:
        return "blocked"
    return "active"


def _parse_date_of_birth(value: object) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value)
        except ValueError:
            return None
    return None


def _compute_age(user: dict) -> int | None:
    dob = _parse_date_of_birth(user.get("date_of_birth"))
    if not dob:
        return None
    today = datetime.utcnow().date()
    years = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
    return years if years >= 0 else None


def _format_joined_date(value: object) -> str:
    if isinstance(value, datetime):
        return value.strftime("%b %d, %Y")
    return "Unknown"


def _format_member_since(value: object) -> str:
    if isinstance(value, datetime):
        return value.strftime("%b %Y")
    return "Unknown"


def _extract_booking_amount(booking: dict) -> float:
    amount = booking.get("total_amount")
    if isinstance(amount, (int, float)):
        return float(amount)

    details = booking.get("details")
    if isinstance(details, dict):
        price_breakdown = details.get("price_breakdown")
        if isinstance(price_breakdown, dict):
            total = price_breakdown.get("total")
            if isinstance(total, (int, float)):
                return float(total)
    return 0.0


def _booking_title(booking: dict, listing_name: str | None) -> str:
    if listing_name:
        return listing_name
    booking_type = str(booking.get("booking_type") or "booking").strip()
    return booking_type.replace("_", " ").title() or "Booking"


def _booking_range(booking: dict) -> str:
    details = booking.get("details")
    if isinstance(details, dict):
        check_in = details.get("check_in")
        check_out = details.get("check_out")
        if isinstance(check_in, str) and isinstance(check_out, str):
            return f"{check_in} - {check_out}"

        booking_date = details.get("date")
        booking_time = details.get("time")
        if isinstance(booking_date, str) and isinstance(booking_time, str):
            return f"{booking_date} {booking_time}"
        if isinstance(booking_date, str):
            return booking_date

    scheduled_at = booking.get("scheduled_at")
    if isinstance(scheduled_at, datetime):
        return scheduled_at.strftime("%b %d, %Y")
    if isinstance(scheduled_at, str):
        return scheduled_at
    return "Scheduled"


def _avatar_url(user: dict) -> str:
    if isinstance(user.get("profile_image_url"), str) and user["profile_image_url"]:
        return user["profile_image_url"]
    identity = str(user.get("_id") or user.get("email") or user.get("full_name") or "user")
    return f"https://i.pravatar.cc/120?u={identity}"


def _location_value(user: dict) -> str:
    latitude = user.get("latitude")
    longitude = user.get("longitude")
    if isinstance(latitude, (int, float)) and isinstance(longitude, (int, float)):
        return f"{latitude:.4f}, {longitude:.4f}"
    return "Location unavailable"


def _first_text(*values: object) -> str:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _serialize_booking_for_admin(
    booking: dict,
    listing_name: str | None,
    vendor_booking: dict | None = None,
    image_url: str | None = None,
) -> dict:
    details = booking.get("details") if isinstance(booking.get("details"), dict) else {}
    source = vendor_booking or booking
    check_in = _first_text(source.get("check_in_date"), details.get("check_in"))
    check_out = _first_text(source.get("check_out_date"), details.get("check_out"))
    service = _first_text(source.get("service"), source.get("room_type"), listing_name, source.get("booking_type"), "Booking")
    booking_date = _first_text(source.get("scheduled_date"), source.get("date"), details.get("date"))
    booking_time = _first_text(source.get("scheduled_time"), source.get("time"), details.get("time"))
    return {
        "id": str(booking.get("_id", "")),
        "title": listing_name or service,
        "service": service,
        "range": _booking_range(booking),
        "date": booking_date,
        "time": booking_time,
        "booking_code": _first_text(source.get("booking_code"), booking.get("booking_code")),
        "amount": _extract_booking_amount(booking),
        "status": str(source.get("status") or "pending").upper(),
        "payment_status": _first_text(source.get("payment_status"), "Unknown").upper(),
        "guests": source.get("guests") or source.get("quantity") or details.get("guests"),
        "staff": _first_text(source.get("staff_name"), source.get("assigned_staff"), source.get("staff"), "Not assigned"),
        "notes": _first_text(source.get("special_requests"), source.get("notes"), "None"),
        "seating": _first_text(source.get("seating_preference"), "Not specified"),
        "check_in": check_in,
        "check_out": check_out,
        "created_at": source.get("created_at") or booking.get("created_at"),
        "requested_at": source.get("requested_at") or source.get("created_at") or booking.get("created_at"),
        "accepted_at": source.get("accepted_at"),
        "completed_at": source.get("completed_at"),
        "canceled_at": source.get("canceled_at"),
        "status_history": source.get("status_history") or [{
            "status": "pending",
            "at": source.get("created_at") or booking.get("created_at"),
            "actor": "customer",
            "label": "Booking request sent by customer",
        }],
        "image": _first_text(
            source.get("image"), source.get("image_url"), source.get("cover_image_url"), image_url,
            f"https://picsum.photos/seed/{booking.get('_id', 'booking')}/320/180",
        ),
    }


def _summaries_for_users_sync(db: Database, users: list[dict]) -> tuple[dict[str, int], dict[str, float]]:
    user_ids = [user.get("_id") for user in users if isinstance(user.get("_id"), ObjectId)]
    if not user_ids:
        return {}, {}

    pipeline = [
        {"$match": {"user_id": {"$in": user_ids}}},
        {
            "$group": {
                "_id": "$user_id",
                "total_bookings": {"$sum": 1},
                "total_spent": {"$sum": {"$ifNull": ["$total_amount", 0]}},
            }
        },
    ]

    counts: dict[str, int] = {}
    totals: dict[str, float] = {}
    for row in db.bookings.aggregate(pipeline):
        user_id = str(row["_id"])
        counts[user_id] = int(row.get("total_bookings", 0))
        totals[user_id] = float(row.get("total_spent", 0) or 0)
    return counts, totals


def _recent_bookings_for_user_sync(db: Database, user_id: str, limit: int = 5) -> list[dict]:
    bookings = list(
        db.bookings.find({"user_id": ObjectId(user_id)}).sort("created_at", -1).limit(limit)
    )

    listing_ids = [booking.get("listing_id") for booking in bookings if isinstance(booking.get("listing_id"), ObjectId)]
    listings_by_id: dict[ObjectId, str] = {}
    if listing_ids:
        for listing in db.listings.find({"_id": {"$in": listing_ids}}, {"name": 1}):
            listings_by_id[listing["_id"]] = str(listing.get("name") or "")

    booking_ids = [booking.get("booking_id") for booking in bookings if isinstance(booking.get("booking_id"), ObjectId)]
    vendor_bookings_by_id = {}
    if booking_ids and hasattr(db, "vendor_bookings"):
        vendor_bookings_by_id = {
            row.get("_id"): row for row in db.vendor_bookings.find({"_id": {"$in": booking_ids}})
        }

    vendor_ids = [row.get("vendor_id") for row in vendor_bookings_by_id.values() if isinstance(row.get("vendor_id"), ObjectId)]
    vendor_images: dict[ObjectId, str] = {}
    if vendor_ids and hasattr(db, "vendor_portal_settings"):
        for settings in db.vendor_portal_settings.find({"vendor_id": {"$in": vendor_ids}}, {"vendor_id": 1, "general.cover_image_url": 1}):
            image = ((settings.get("general") or {}).get("cover_image_url") if isinstance(settings.get("general"), dict) else "")
            if image:
                vendor_images[settings["vendor_id"]] = str(image)

    return [
        _serialize_booking_for_admin(
            booking,
            listings_by_id.get(booking.get("listing_id")),
            vendor_bookings_by_id.get(booking.get("booking_id")),
            vendor_images.get((vendor_bookings_by_id.get(booking.get("booking_id")) or {}).get("vendor_id")),
        )
        for booking in bookings
    ]


def _serialize_user_for_admin(
    user: dict,
    *,
    total_bookings: int = 0,
    total_spent: float = 0,
    recent_bookings: list[dict] | None = None,
) -> dict:
    created_at = user.get("created_at")
    normalized_status = _normalize_user_status(user)
    age = _compute_age(user)
    return {
        "id": str(user.get("_id", "")),
        "full_name": user.get("full_name") or "Unknown User",
        "email": user.get("email") or "",
        "phone": user.get("phone") or "",
        "status": normalized_status,
        "created_at": created_at,
        "updated_at": user.get("updated_at"),
        "joined_date": _format_joined_date(created_at),
        "member_since": _format_member_since(created_at),
        "total_bookings": total_bookings,
        "total_spent": total_spent,
        "age": age,
        "avatar": _avatar_url(user),
        "profile_image_url": user.get("profile_image_url"),
        "location": _location_value(user),
        "points_balance": int(user.get("points_balance") or 0),
        "recent_bookings": recent_bookings or [],
    }


@router.get("", response_model=AdminUserListResponse)
async def list_users(
    limit: int = Query(default=50, ge=1, le=200),
    skip: int = Query(default=0, ge=0),
    search: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    user_repo: UserRepository = Depends(get_user_repository),
    db: Database = Depends(get_platform_admin_db),
) -> AdminUserListResponse:
    users = await user_repo.list_users(limit=limit, skip=skip, search=search, status=status_filter)
    total = await user_repo.count_users(search=search, status=status_filter)
    booking_counts, spending_totals = await asyncio.to_thread(_summaries_for_users_sync, db, users)
    serialized = [
        _serialize_user_for_admin(
            user,
            total_bookings=booking_counts.get(str(user.get("_id")), 0),
            total_spent=spending_totals.get(str(user.get("_id")), 0),
        )
        for user in users
    ]
    return AdminUserListResponse(users=to_jsonable(serialized), total=total)


@router.post("/{user_id}/password-reset-request", response_model=dict)
async def request_user_password_reset(
    user_id: str,
    user_repo: UserRepository = Depends(get_user_repository),
    auth_service=Depends(get_auth_service),
) -> dict:
    try:
        user = await user_repo.get_by_id(user_id)
    except (InvalidId, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.") from exc
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    email = str(user.get("email") or "").strip().lower()
    if not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This user does not have an email address for password recovery.",
        )
    await auth_service.forgot_password(ForgotPasswordRequest(email=email))
    return {"message": "Password reset instructions sent."}


@router.get("/{user_id}", response_model=dict)
async def get_user(
    user_id: str,
    user_repo: UserRepository = Depends(get_user_repository),
    db: Database = Depends(get_platform_admin_db),
) -> dict:
    try:
        user = await user_repo.get_by_id(user_id)
    except (InvalidId, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.") from exc
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
    booking_counts, spending_totals = await asyncio.to_thread(_summaries_for_users_sync, db, [user])
    recent_bookings = await asyncio.to_thread(_recent_bookings_for_user_sync, db, user_id)
    payload = _serialize_user_for_admin(
        user,
        total_bookings=booking_counts.get(str(user.get("_id")), 0),
        total_spent=spending_totals.get(str(user.get("_id")), 0),
        recent_bookings=recent_bookings,
    )
    return to_jsonable(payload)


@router.patch("/{user_id}/status", response_model=dict)
async def update_user_status(
    user_id: str,
    payload: UserStatusUpdateRequest,
    user_repo: UserRepository = Depends(get_user_repository),
    db: Database = Depends(get_platform_admin_db),
) -> dict:
    try:
        updated = await user_repo.update_status(user_id, payload.status)
    except (InvalidId, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.") from exc
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
    booking_counts, spending_totals = await asyncio.to_thread(_summaries_for_users_sync, db, [updated])
    recent_bookings = await asyncio.to_thread(_recent_bookings_for_user_sync, db, user_id)
    payload = _serialize_user_for_admin(
        updated,
        total_bookings=booking_counts.get(str(updated.get("_id")), 0),
        total_spent=spending_totals.get(str(updated.get("_id")), 0),
        recent_bookings=recent_bookings,
    )
    return to_jsonable(payload)


@router.get("/{user_id}/bookings", response_model=dict)
async def get_user_bookings(
    user_id: str,
    user_repo: UserRepository = Depends(get_user_repository),
    db: Database = Depends(get_platform_admin_db),
) -> dict:
    try:
        user = await user_repo.get_by_id(user_id)
    except (InvalidId, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.") from exc
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    bookings = await asyncio.to_thread(_recent_bookings_for_user_sync, db, user_id, 20)
    return to_jsonable({"user_id": user_id, "bookings": bookings, "total": len(bookings)})

