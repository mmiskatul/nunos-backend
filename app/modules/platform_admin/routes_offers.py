from datetime import UTC, datetime

from bson import ObjectId
from bson.errors import InvalidId
from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from pymongo.database import Database

from app.modules.platform_admin.deps import get_platform_admin_db
from app.modules.platform_admin.deps_auth import get_current_platform_admin

router = APIRouter(
    prefix="/platform-admin/offers",
    tags=["Platform Admin - Offers (Live)"],
    dependencies=[Depends(get_current_platform_admin)],
)


def _serialize_offer(document: dict | None) -> dict | None:
    if not document:
        return None
    serialized = {**document}
    serialized["id"] = str(serialized.pop("_id"))
    selected_vendor_ids = serialized.get("selected_vendor_ids")
    if isinstance(selected_vendor_ids, list):
        serialized["selected_vendor_ids"] = [str(item) for item in selected_vendor_ids]
    else:
        serialized["selected_vendor_ids"] = []
    return serialized


def _ensure_offer_assignment_indexes(db: Database) -> None:
    assignments = db["offer_provider_assignments"]
    assignments.create_index([("offer_id", 1), ("vendor_id", 1)], unique=True)
    assignments.create_index("offer_id")
    assignments.create_index("vendor_id")


def _vendor_name(vendor: dict) -> str:
    return str(vendor.get("business_name") or vendor.get("owner_full_name") or vendor.get("email") or "Unknown Vendor")


def _vendor_category(vendor: dict) -> str:
    categories = vendor.get("categories")
    if isinstance(categories, list):
        normalized = [str(item).strip() for item in categories if str(item).strip()]
        if normalized:
            return ", ".join(normalized)
    return str(vendor.get("category") or vendor.get("business_type") or "Uncategorized")


def _vendor_status(vendor: dict) -> str:
    return str(vendor.get("status") or "inactive").lower()


def _eligible_vendor_query() -> dict:
    return {"$or": [{"status": "approved"}, {"status": "active"}, {"status": {"$exists": False}}]}


def _normalize_object_ids(values: list | None) -> list[ObjectId]:
    normalized: list[ObjectId] = []
    for value in values or []:
        try:
            normalized.append(ObjectId(str(value)))
        except (InvalidId, ValueError):
            continue
    return normalized


def _resolve_assignment_vendors(db: Database, applied_to: str, selected_vendor_ids: list[str]) -> list[dict]:
    normalized_scope = applied_to.strip().lower()
    vendors = db["vendors"]
    if normalized_scope in {"all vendors", "platform wide"}:
        return list(vendors.find(_eligible_vendor_query()))

    selected_ids = _normalize_object_ids(selected_vendor_ids)
    if not selected_ids:
        return []
    return list(vendors.find({"_id": {"$in": selected_ids}}))


def _sync_offer_assignments(
    db: Database,
    *,
    offer_id: ObjectId,
    applied_to: str,
    selected_vendor_ids: list[str],
    is_active: bool,
) -> None:
    _ensure_offer_assignment_indexes(db)
    assignments = db["offer_provider_assignments"]
    vendors = _resolve_assignment_vendors(db, applied_to, selected_vendor_ids)
    now = datetime.now(UTC)

    if not vendors:
        assignments.delete_many({"offer_id": offer_id})
        return

    assignment_docs: list[dict] = []
    vendor_object_ids: list[ObjectId] = []
    for vendor in vendors:
        vendor_id = vendor.get("_id")
        if not isinstance(vendor_id, ObjectId):
            continue
        vendor_object_ids.append(vendor_id)
        assignment_docs.append(
            {
                "offer_id": offer_id,
                "vendor_id": vendor_id,
                "vendor_name": _vendor_name(vendor),
                "vendor_category": _vendor_category(vendor),
                "vendor_status": _vendor_status(vendor),
                "assignment_scope": applied_to,
                "active": bool(is_active) and _vendor_status(vendor) not in {"rejected", "blocked", "inactive"},
                "assigned_at": now,
                "updated_at": now,
            }
        )

    assignments.delete_many({"offer_id": offer_id, "vendor_id": {"$nin": vendor_object_ids}})
    for assignment_doc in assignment_docs:
        assignments.update_one(
            {"offer_id": assignment_doc["offer_id"], "vendor_id": assignment_doc["vendor_id"]},
            {"$set": assignment_doc, "$setOnInsert": {"created_at": now}},
            upsert=True,
        )


def _load_offer_assignments(db: Database, offer: dict) -> list[dict]:
    offer_id = offer.get("_id")
    if not isinstance(offer_id, ObjectId):
        return []

    _sync_offer_assignments(
        db,
        offer_id=offer_id,
        applied_to=str(offer.get("applied_to") or "All Vendors"),
        selected_vendor_ids=[str(item) for item in offer.get("selected_vendor_ids") or []],
        is_active=bool(offer.get("is_active", True)),
    )
    _ensure_offer_assignment_indexes(db)
    assignments = db["offer_provider_assignments"]
    return list(assignments.find({"offer_id": offer_id}).sort("vendor_name", 1))


def _build_booking_query(offer: dict, vendor_ids: list[ObjectId]) -> dict:
    query: dict = {"vendor_id": {"$in": vendor_ids}}
    starts_at = offer.get("starts_at")
    ends_at = offer.get("ends_at")
    created_at_filters: dict = {}
    if isinstance(starts_at, datetime):
        created_at_filters["$gte"] = starts_at
    if isinstance(ends_at, datetime):
        created_at_filters["$lte"] = ends_at
    if created_at_filters:
        query["created_at"] = created_at_filters
    return query


def _offer_assignment_analytics(db: Database, offer: dict, assignments: list[dict]) -> tuple[int, int, list[dict]]:
    if not assignments:
        return 0, 0, []

    vendor_ids = [row.get("vendor_id") for row in assignments if isinstance(row.get("vendor_id"), ObjectId)]
    if not vendor_ids:
        return 0, 0, []

    bookings = db["bookings"]
    booking_query = _build_booking_query(offer, vendor_ids)
    booking_rows = list(bookings.find(booking_query, {"vendor_id": 1, "customer_id": 1}))

    redemption_counts: dict[ObjectId, int] = {}
    engaged_user_sets: dict[ObjectId, set[str]] = {}
    total_engaged_users: set[str] = set()

    for booking in booking_rows:
        vendor_id = booking.get("vendor_id")
        if not isinstance(vendor_id, ObjectId):
            continue
        redemption_counts[vendor_id] = redemption_counts.get(vendor_id, 0) + 1

        customer_id = booking.get("customer_id")
        if isinstance(customer_id, ObjectId):
            customer_key = str(customer_id)
            engaged_user_sets.setdefault(vendor_id, set()).add(customer_key)
            total_engaged_users.add(customer_key)

    provider_breakdown: list[dict] = []
    for assignment in assignments:
        vendor_id = assignment.get("vendor_id")
        if not isinstance(vendor_id, ObjectId):
            continue
        provider_breakdown.append(
            {
                "provider_id": str(vendor_id),
                "provider_name": str(assignment.get("vendor_name") or "Unknown Vendor"),
                "vendor_category": str(assignment.get("vendor_category") or "Uncategorized"),
                "status": str(assignment.get("vendor_status") or "inactive").lower(),
                "redemptions": int(redemption_counts.get(vendor_id, 0)),
                "engaged_users": len(engaged_user_sets.get(vendor_id, set())),
                "active": bool(assignment.get("active", True)),
            }
        )

    total_redemptions = sum(item["redemptions"] for item in provider_breakdown)
    return len(provider_breakdown), len(total_engaged_users), provider_breakdown


def _serialize_admin_offer(document: dict | None, db: Database) -> dict | None:
    serialized = _serialize_offer(document)
    if not serialized:
        return None

    applied_to = str(serialized.get("applied_to") or "All Vendors")
    serialized["applied_to"] = applied_to
    assignments = _load_offer_assignments(db, document or {})
    provider_count, engaged_users, provider_breakdown = _offer_assignment_analytics(db, document or {}, assignments)
    stored_redemptions = int(serialized.get("redemptions") or 0)
    serialized["provider_count"] = provider_count
    serialized["engaged_users"] = engaged_users
    serialized["provider_breakdown"] = provider_breakdown
    serialized["redemptions"] = sum(item.get("redemptions", 0) for item in provider_breakdown) or stored_redemptions
    return serialized


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid date format.") from exc
    return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed.astimezone(UTC)


def _normalize_offer_payload(payload: dict, existing: dict | None = None) -> dict:
    existing_name = existing.get("name") if existing else ""
    name = str(payload.get("name") or existing_name or "").strip()
    if not name:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Offer name is required.")

    discount_type = str(payload.get("discountType") or existing.get("discount_type") or "PERCENT").upper()
    if discount_type not in {"PERCENT", "FLAT", "BOGO"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid discount type.")

    raw_value = payload.get("discountValue", existing.get("discount_value") if existing else 0)
    try:
        discount_value = float(raw_value or 0)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid discount value.") from exc

    if discount_type == "PERCENT" and not (0 <= discount_value <= 100):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Percent discount must be between 0 and 100.")
    if discount_type == "FLAT" and discount_value < 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Flat discount must be non-negative.")
    if discount_type == "BOGO":
        discount_value = 0

    starts_at = _parse_datetime(payload.get("startDate")) if "startDate" in payload else existing.get("starts_at") if existing else None
    ends_at = _parse_datetime(payload.get("endDate")) if "endDate" in payload else existing.get("ends_at") if existing else None
    if starts_at and ends_at and ends_at < starts_at:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="End date must be after start date.")

    existing_applied_to = existing.get("applied_to") if existing else "All Vendors"
    applied_to = str(payload.get("appliedTo") or existing_applied_to or "All Vendors").strip() or "All Vendors"
    raw_selected_vendor_ids = payload.get("selectedVendorIds")
    if raw_selected_vendor_ids is None:
        raw_selected_vendor_ids = payload.get("vendorIds")
    if raw_selected_vendor_ids is None:
        raw_selected_vendor_ids = existing.get("selected_vendor_ids") if existing else []
    if not isinstance(raw_selected_vendor_ids, list):
        raw_selected_vendor_ids = []
    selected_vendor_ids = [str(item).strip() for item in raw_selected_vendor_ids if str(item).strip()]
    is_active = bool(payload.get("active")) if "active" in payload else bool(existing.get("is_active")) if existing else True

    return {
        "name": name,
        "title": name,
        "discount_type": discount_type,
        "discount_value": discount_value,
        "discount_percent": discount_value if discount_type == "PERCENT" else None,
        "require_code": False,
        "promo_code": None,
        "starts_at": starts_at,
        "ends_at": ends_at,
        "applied_to": applied_to,
        "selected_vendor_ids": selected_vendor_ids if applied_to.lower() == "selected vendors" else [],
        "is_active": is_active,
        "updated_at": datetime.now(UTC),
    }


@router.get("")
def list_platform_offers(
    limit: int = Query(default=100, ge=1, le=500),
    skip: int = Query(default=0, ge=0),
    search: str | None = Query(default=None),
    db: Database = Depends(get_platform_admin_db),
) -> dict:
    query: dict = {}
    if search:
        query["name"] = {"$regex": search, "$options": "i"}

    cursor = db.offers.find(query).sort("created_at", -1).skip(skip).limit(limit)
    offers = [_serialize_admin_offer(doc, db) for doc in cursor]
    total = int(db.offers.count_documents(query))
    return {"offers": offers, "total": total}


@router.post("")
def create_platform_offer(
    payload: dict = Body(...),
    db: Database = Depends(get_platform_admin_db),
) -> dict:
    now = datetime.now(UTC)
    normalized = _normalize_offer_payload(payload)
    normalized["created_at"] = now
    normalized["redemptions"] = 0
    result = db.offers.insert_one(normalized)
    _sync_offer_assignments(
        db,
        offer_id=result.inserted_id,
        applied_to=str(normalized.get("applied_to") or "All Vendors"),
        selected_vendor_ids=[str(item) for item in normalized.get("selected_vendor_ids") or []],
        is_active=bool(normalized.get("is_active", True)),
    )
    created = db.offers.find_one({"_id": result.inserted_id})
    return _serialize_admin_offer(created, db) or {}


@router.get("/{offer_id}")
def get_platform_offer(
    offer_id: str,
    db: Database = Depends(get_platform_admin_db),
) -> dict:
    try:
        offer = db.offers.find_one({"_id": ObjectId(offer_id)})
    except (InvalidId, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Offer not found.") from exc
    if not offer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Offer not found.")
    return _serialize_admin_offer(offer, db) or {}


@router.patch("/{offer_id}")
def update_platform_offer(
    offer_id: str,
    payload: dict = Body(...),
    db: Database = Depends(get_platform_admin_db),
) -> dict:
    try:
        existing = db.offers.find_one({"_id": ObjectId(offer_id)})
    except (InvalidId, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Offer not found.") from exc
    if not existing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Offer not found.")

    update_doc = _normalize_offer_payload(payload, existing)
    db.offers.update_one({"_id": existing["_id"]}, {"$set": update_doc})
    _sync_offer_assignments(
        db,
        offer_id=existing["_id"],
        applied_to=str(update_doc.get("applied_to") or "All Vendors"),
        selected_vendor_ids=[str(item) for item in update_doc.get("selected_vendor_ids") or []],
        is_active=bool(update_doc.get("is_active", True)),
    )
    updated = db.offers.find_one({"_id": existing["_id"]})
    return _serialize_admin_offer(updated, db) or {}


@router.patch("/{offer_id}/status")
def update_platform_offer_status(
    offer_id: str,
    payload: dict = Body(...),
    db: Database = Depends(get_platform_admin_db),
) -> dict:
    raw_status = payload.get("status")
    if raw_status is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Status is required.")

    status_text = str(raw_status).lower()
    if status_text not in {"active", "inactive"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid status.")

    try:
        result = db.offers.update_one(
            {"_id": ObjectId(offer_id)},
            {"$set": {"is_active": status_text == "active", "updated_at": datetime.now(UTC)}},
        )
    except (InvalidId, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Offer not found.") from exc

    if result.matched_count != 1:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Offer not found.")

    updated = db.offers.find_one({"_id": ObjectId(offer_id)})
    if updated:
        _sync_offer_assignments(
            db,
            offer_id=updated["_id"],
            applied_to=str(updated.get("applied_to") or "All Vendors"),
            selected_vendor_ids=[str(item) for item in updated.get("selected_vendor_ids") or []],
            is_active=bool(updated.get("is_active", True)),
        )
    return _serialize_admin_offer(updated, db) or {}


@router.delete("/{offer_id}")
def delete_platform_offer(
    offer_id: str,
    db: Database = Depends(get_platform_admin_db),
) -> dict:
    try:
        db["offer_provider_assignments"].delete_many({"offer_id": ObjectId(offer_id)})
        result = db.offers.delete_one({"_id": ObjectId(offer_id)})
    except (InvalidId, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Offer not found.") from exc

    if result.deleted_count != 1:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Offer not found.")
    return {"message": "Offer deleted successfully."}
