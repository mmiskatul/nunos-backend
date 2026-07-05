import time
from datetime import datetime, timezone, timedelta
from typing import Any

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Body, Query
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.api.deps import get_db
from app.modules.schemas import GenericPatchRequest, MessageCreateRequest, PlannedEndpointResponse, StatusUpdateRequest

router = APIRouter(prefix="/platform-admin")

_CACHE = {}


def _vendor_category_label(vendor: dict) -> str:
    categories = vendor.get("categories")
    if isinstance(categories, list):
        normalized = [str(item).strip() for item in categories if str(item).strip()]
        if normalized:
            return ", ".join(normalized)
    return str(vendor.get("category") or "—")

def get_cached_data(key: str, ttl: int = 5):
    now = time.time()
    if key in _CACHE:
        val, expiry = _CACHE[key]
        if now < expiry:
            return val
    return None

def set_cached_data(key: str, val: Any, ttl: int = 5):
    _CACHE[key] = (val, time.time() + ttl)

def invalidate_cache(key: str):
    _CACHE.pop(key, None)

def _planned(endpoint: str, description: str, connected_from: list[str]) -> PlannedEndpointResponse:
    return PlannedEndpointResponse(
        endpoint=endpoint,
        module="platform_admin",
        description=description,
        connected_from=connected_from,
    )

async def _get_or_sync_billing_payments(db: AsyncIOMotorDatabase) -> list[dict]:
    vendors = await db["vendors"].find({}).to_list(100)
    
    payments = []
    for vendor in vendors:
        vendor_id = vendor["_id"]
        vendor_id_str = str(vendor_id)
        
        vendor_code = vendor.get("vendor_code")
        if not vendor_code:
            name = vendor.get("business_name") or vendor.get("owner_full_name") or "Vendor"
            parts = [p.upper() for p in name.split() if p]
            if len(parts) >= 2:
                vendor_code = parts[0][0] + parts[1][0]
            elif len(parts) == 1:
                vendor_code = parts[0][:2].upper()
            else:
                vendor_code = "VN"
            
            existing_code = await db["vendors"].find_one({"vendor_code": vendor_code})
            if existing_code:
                vendor_code = f"{vendor_code}{vendor_id_str[-2:]}".upper()
            
            await db["vendors"].update_one({"_id": vendor_id}, {"$set": {"vendor_code": vendor_code}})
        
        bookings = await db["bookings"].find({"vendor_id": vendor_id}).to_list(1000)
        total_revenue = sum(float(b.get("total_amount") or 0) for b in bookings)
        
        billing_doc = await db["billing_payments"].find_one({"vendor_id": vendor_id_str})
        
        settings_doc = await db["platform_admin_settings"].find_one({"_id": "platform_admin_settings"}) or {}
        global_rate = float(settings_doc.get("commission", {}).get("globalRate", "12.50"))
        
        if not billing_doc:
            commission_amount = total_revenue * (global_rate / 100)
            net_payout = total_revenue - commission_amount
            
            created_at = vendor.get("created_at") or datetime.now(timezone.utc)
            joined_date = created_at.strftime("%b %d, %Y")
            
            billing_doc = {
                "vendor_id": vendor_id_str,
                "vendorCode": vendor_code,
                "vendorName": vendor.get("business_name") or vendor.get("owner_full_name") or "Vendor",
                "totalEarnings": f"${total_revenue:,.2f}",
                "commission": f"-${commission_amount:,.2f}",
                "netPayout": f"${net_payout:,.2f}",
                "status": "PENDING",
                "details": {
                    "profile": {
                        "vendorTitle": vendor.get("business_name") or vendor.get("owner_full_name") or "Vendor",
                        "location": vendor.get("address") or "Main Branch",
                        "category": _vendor_category_label(vendor) or "Hotel & Resort",
                        "joinedDate": joined_date,
                        "lastBillingDate": datetime.now(timezone.utc).strftime("%b %d, %Y"),
                        "image": vendor.get("logo_url") or f"https://picsum.photos/seed/{vendor_id_str}/80/80"
                    },
                    "netPayable": {
                        "amount": f"${net_payout:,.2f}",
                        "dueDate": (datetime.now(timezone.utc) + timedelta(days=15)).strftime("%b %d, %Y"),
                        "invoiceStatus": "PENDING"
                    },
                    "financialBreakdown": {
                        "totalRevenue": f"${total_revenue:,.2f}",
                        "commissionRate": f"{global_rate}%",
                        "commissionAmount": f"-${commission_amount:,.2f}",
                        "cycle": "Current cycle"
                    },
                    "history": [
                        {
                            "id": f"TXN-{vendor_code}-01",
                            "date": datetime.now(timezone.utc).strftime("%b %d, %Y"),
                            "amount": f"${net_payout:,.2f}",
                            "status": "PENDING"
                        }
                    ]
                }
            }
            await db["billing_payments"].insert_one(billing_doc)
        else:
            if not billing_doc.get("is_overridden"):
                commission_amount = total_revenue * (global_rate / 100)
                net_payout = total_revenue - commission_amount
                
                await db["billing_payments"].update_one(
                    {"vendor_id": vendor_id_str},
                    {
                        "$set": {
                            "totalEarnings": f"${total_revenue:,.2f}",
                            "commission": f"-${commission_amount:,.2f}",
                            "netPayout": f"${net_payout:,.2f}",
                            "details.financialBreakdown.totalRevenue": f"${total_revenue:,.2f}",
                            "details.financialBreakdown.commissionAmount": f"-${commission_amount:,.2f}",
                            "details.netPayable.amount": f"${net_payout:,.2f}"
                        }
                    }
                )
                billing_doc = await db["billing_payments"].find_one({"vendor_id": vendor_id_str})
        
        billing_doc["id"] = str(billing_doc.get("_id"))
        billing_doc.pop("_id", None)
        payments.append(billing_doc)
        
    return payments


@router.get("/dashboard/overview", tags=["Platform Admin - Dashboard"])
async def get_platform_dashboard_overview(
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> dict:
    """Return real platform KPI data for the admin dashboard."""
    now = datetime.now(timezone.utc)
    current_month = now.month
    current_year = now.year

    # Aggregate totals from the database
    total_users = await db["users"].count_documents({})
    total_vendors = await db["vendors"].count_documents({})
    total_bookings = await db["bookings"].count_documents({})
    active_offers = await db["offers"].count_documents({"is_active": True})

    # Revenue approximation from bookings
    revenue_pipeline = [{"$group": {"_id": None, "total": {"$sum": "$total_amount"}}}]
    rev_result = await db["bookings"].aggregate(revenue_pipeline).to_list(1)
    total_revenue = rev_result[0]["total"] if rev_result else 0

    # Monthly revenue for last 6 months
    monthly_data = []
    for i in range(5, -1, -1):
        month = (current_month - i - 1) % 12 + 1
        year = current_year if current_month - i > 0 else current_year - 1
        label = datetime(year, month, 1).strftime("%b")
        count = await db["bookings"].count_documents({
            "created_at": {
                "$gte": datetime(year, month, 1, tzinfo=timezone.utc),
                "$lt": datetime(year, month % 12 + 1, 1, tzinfo=timezone.utc) if month < 12
                       else datetime(year + 1, 1, 1, tzinfo=timezone.utc),
            }
        })
        monthly_data.append({"period": label, "value": count})

    # Weekly data — last 7 days
    weekly_data = []
    for i in range(6, -1, -1):
        from datetime import timedelta
        day = now - timedelta(days=i)
        label = day.strftime("%a")
        day_start = day.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day.replace(hour=23, minute=59, second=59, microsecond=999999)
        count = await db["bookings"].count_documents({
            "created_at": {"$gte": day_start, "$lte": day_end}
        })
        weekly_data.append({"period": label, "value": count})

    # Booking insights by type
    type_pipeline = [{"$group": {"_id": "$provider_type", "count": {"$sum": 1}}}]
    type_results = await db["bookings"].aggregate(type_pipeline).to_list(10)
    pie_colors = {"restaurant": "#2648a0", "hotel": "#3b82f6", "spa": "#8b5cf6", "event": "#10b981"}
    booking_pie = [
        {
            "name": r["_id"].capitalize() if r["_id"] else "Other",
            "value": round(r["count"] / max(total_bookings, 1) * 100, 1),
            "color": pie_colors.get(r["_id"], "#94a3b8"),
        }
        for r in type_results
    ] or [{"name": "No Data", "value": 100, "color": "#e2e8f0"}]

    # Vendor performance snapshot
    vendors_cursor = db["vendors"].find(
        {},
        {
            "business_name": 1, "category": 1,
            "average_rating": 1, "total_revenue": 1, "status": 1,
        }
    ).sort("total_revenue", -1).limit(20)
    vendors_raw = await vendors_cursor.to_list(20)
    vendors = []
    for v in vendors_raw:
        name = v.get("business_name", "Unknown")
        code = "".join(w[0].upper() for w in name.split()[:2]) or "??"
        rating = str(round(float(v.get("average_rating") or 0), 1))
        revenue_raw = float(v.get("total_revenue") or 0)
        revenue = f"${revenue_raw / 1000:.1f}k" if revenue_raw >= 1000 else f"${revenue_raw:.0f}"
        perf = float(v.get("average_rating") or 0)
        status = "TOP PERFORMER" if perf >= 4.5 else ("AT RISK" if perf < 3.0 else "ACTIVE")
        vendors.append({
            "id": str(v.get("_id") or ""),
            "code": code,
            "name": name,
            "category": _vendor_category_label(v),
            "rating": rating,
            "revenue": revenue,
            "status": status,
        })

    return {
        "stats": [
            {
                "label": "TOTAL REVENUE",
                "value": f"${total_revenue / 1000:.1f}k" if total_revenue >= 1000 else f"${total_revenue:.0f}",
                "sub": "Lifetime platform revenue",
                "trend": "+12%",
                "icon": "tag",
            },
            {
                "label": "TOTAL USERS",
                "value": str(total_users),
                "sub": "Registered customers",
                "trend": "+8%",
                "icon": "users",
            },
            {
                "label": "TOTAL BOOKINGS",
                "value": str(total_bookings),
                "sub": "All-time bookings",
                "trend": "+15%",
                "icon": "shopping_bag",
            },
            {
                "label": "ACTIVE VENDORS",
                "value": str(total_vendors),
                "sub": "Service providers",
                "trend": "+5%",
                "icon": "calendar",
            },
            {
                "label": "ACTIVE OFFERS",
                "value": str(active_offers),
                "sub": "Live promotions",
                "trend": "+3%",
                "icon": "smile",
            },
        ],
        "monthlyData": monthly_data,
        "weeklyData": weekly_data,
        "bookingByRange": {
            "weekly": booking_pie,
            "monthly": booking_pie,
        },
        "bookingTotals": {
            "weekly": total_bookings,
            "monthly": total_bookings,
        },
        "vendors": vendors,
    }


@router.get("/users/{user_id}/bookings", tags=["Platform Admin - Users"], response_model=PlannedEndpointResponse)
def list_platform_user_bookings(user_id: str) -> PlannedEndpointResponse:
    _ = user_id
    return _planned("/platform-admin/users/{user_id}/bookings", "Recent bookings for a user.", ["User detail panel"])


@router.get("/moderation/submissions", tags=["Platform Admin - Moderation"])
async def list_moderation_submissions(
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> dict:
    cache_key = "moderation_submissions"
    cached = get_cached_data(cache_key)
    if cached is not None:
        return cached

    vendors = await db["vendors"].find({"status": {"$in": ["pending_approval", "pending_review", "pending"]}}).to_list(100)
    
    items = []
    for vendor in vendors:
        vendor_id_str = str(vendor["_id"])
        
        created_at = vendor.get("created_at") or datetime.now(timezone.utc)
        delta = datetime.now(timezone.utc) - created_at.replace(tzinfo=timezone.utc) if created_at.tzinfo else datetime.now(timezone.utc) - created_at
        if delta.days > 0:
            age = f"{delta.days} days ago"
        elif delta.seconds >= 3600:
            age = f"{delta.seconds // 3600} hours ago"
        elif delta.seconds >= 60:
            age = f"{delta.seconds // 60} mins ago"
        else:
            age = "just now"
            
        items.append({
            "id": vendor_id_str,
            "title": vendor.get("business_name") or vendor.get("owner_full_name") or "Vendor Review",
            "age": age,
            "subtitle": f"Verify KYC details for {_vendor_category_label(vendor) or 'vendor'}",
            "venue": vendor.get("business_name") or "Vendor Venue",
            "location": vendor.get("address") or "Address not provided",
            "vendorId": vendor_id_str,
            "queueType": "INFO",
            "previewImage": vendor.get("logo_url") or f"https://picsum.photos/seed/{vendor_id_str}/200/120",
            "state": "pending"
        })
        
    result = {
        "totalSubmissions": len(items),
        "items": items
    }
    set_cached_data(cache_key, result, ttl=5)
    return result


@router.get("/moderation/submissions/{submission_id}", tags=["Platform Admin - Moderation"])
async def get_moderation_submission(
    submission_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> dict:
    try:
        vendor = await db["vendors"].find_one({"_id": ObjectId(submission_id)})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid submission ID format")
        
    if not vendor:
        raise HTTPException(status_code=404, detail="Submission not found")
        
    created_at = vendor.get("created_at") or datetime.now(timezone.utc)
    delta = datetime.now(timezone.utc) - created_at.replace(tzinfo=timezone.utc) if created_at.tzinfo else datetime.now(timezone.utc) - created_at
    if delta.days > 0:
        age = f"{delta.days} days ago"
    elif delta.seconds >= 3600:
        age = f"{delta.seconds // 3600} hours ago"
    elif delta.seconds >= 60:
        age = f"{delta.seconds // 60} mins ago"
    else:
        age = "just now"
        
    return {
        "id": str(vendor["_id"]),
        "title": vendor.get("business_name") or vendor.get("owner_full_name") or "Vendor Review",
        "age": age,
        "subtitle": f"Verify KYC details for {_vendor_category_label(vendor) or 'vendor'}",
        "venue": vendor.get("business_name") or "Vendor Venue",
        "location": vendor.get("address") or "Address not provided",
        "vendorId": str(vendor["_id"]),
        "queueType": "INFO",
        "previewImage": vendor.get("logo_url") or f"https://picsum.photos/seed/{str(vendor['_id'])}/200/120",
        "state": "pending" if vendor.get("status") in ["pending_approval", "pending_review", "pending"] else ("approved" if vendor.get("status") == "approved" else "rejected")
    }


@router.patch("/moderation/submissions/{submission_id}/decision", tags=["Platform Admin - Moderation"])
async def decide_moderation_submission(
    submission_id: str,
    payload: dict = Body(...),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> dict:
    try:
        vendor = await db["vendors"].find_one({"_id": ObjectId(submission_id)})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid submission ID format")
        
    if not vendor:
        raise HTTPException(status_code=404, detail="Submission not found")
        
    action = payload.get("action") or payload.get("status") or "approved"
    decision = "approved" if action == "approved" else "rejected"
    
    now = datetime.now(timezone.utc)
    if decision == "approved":
        set_payload = {
            "status": "approved",
            "kyc_status": "approved",
            "kyc_reviewed_at": now,
            "kyc_rejection_reason": None,
            "updated_at": now,
        }
        verification_status = "approved"
        rejection_reason = None
    else:
        set_payload = {
            "status": "rejected",
            "kyc_status": "rejected",
            "kyc_reviewed_at": now,
            "kyc_rejection_reason": payload.get("note") or "Rejected by moderation.",
            "updated_at": now,
        }
        verification_status = "rejected"
        rejection_reason = payload.get("note") or "Rejected by moderation."
        
    await db["vendors"].update_one({"_id": vendor["_id"]}, {"$set": set_payload})
    await db["vendor_verification_details"].update_one(
        {"vendor_id": vendor["_id"]},
        {
            "$set": {
                "status": verification_status,
                "reviewed_at": now,
                "rejection_reason": rejection_reason,
                "updated_at": now,
            }
        },
        upsert=True,
    )
    await db["vendor_admin_reviews"].update_one(
        {"vendor_id": vendor["_id"]},
        {
            "$set": {
                "review_status": verification_status,
                "reviewed_at": now,
                "rejection_reason": rejection_reason,
                "updated_at": now,
            },
            "$setOnInsert": {"created_at": now},
        },
        upsert=True,
    )
    
    invalidate_cache("moderation_submissions")
    
    updated_vendor = await db["vendors"].find_one({"_id": vendor["_id"]})
    created_at = updated_vendor.get("created_at") or datetime.now(timezone.utc)
    delta = datetime.now(timezone.utc) - created_at.replace(tzinfo=timezone.utc) if created_at.tzinfo else datetime.now(timezone.utc) - created_at
    if delta.days > 0:
        age = f"{delta.days} days ago"
    elif delta.seconds >= 3600:
        age = f"{delta.seconds // 3600} hours ago"
    elif delta.seconds >= 60:
        age = f"{delta.seconds // 60} mins ago"
    else:
        age = "just now"
        
    return {
        "item": {
            "id": str(updated_vendor["_id"]),
            "title": updated_vendor.get("business_name") or updated_vendor.get("owner_full_name") or "Vendor Review",
            "age": age,
            "subtitle": f"Verify KYC details for {_vendor_category_label(updated_vendor) or 'vendor'}",
            "venue": updated_vendor.get("business_name") or "Vendor Venue",
            "location": updated_vendor.get("address") or "Address not provided",
            "vendorId": str(updated_vendor["_id"]),
            "queueType": "INFO",
            "previewImage": updated_vendor.get("logo_url") or f"https://picsum.photos/seed/{str(updated_vendor['_id'])}/200/120",
            "state": decision
        }
    }


@router.get("/offers", tags=["Platform Admin - Offers"], response_model=PlannedEndpointResponse)
def list_platform_offers() -> PlannedEndpointResponse:
    return _planned("/platform-admin/offers", "Offer list page.", ["Offers dashboard"])


@router.post("/offers", tags=["Platform Admin - Offers"], response_model=PlannedEndpointResponse)
def create_platform_offer(payload: GenericPatchRequest) -> PlannedEndpointResponse:
    _ = payload
    return _planned("/platform-admin/offers", "Create a platform offer.", ["Create new offer modal"])


@router.get("/offers/{offer_id}", tags=["Platform Admin - Offers"], response_model=PlannedEndpointResponse)
def get_platform_offer(offer_id: str) -> PlannedEndpointResponse:
    _ = offer_id
    return _planned("/platform-admin/offers/{offer_id}", "Offer details page.", ["Offer details"])


@router.patch("/offers/{offer_id}", tags=["Platform Admin - Offers"], response_model=PlannedEndpointResponse)
def update_platform_offer(offer_id: str, payload: GenericPatchRequest) -> PlannedEndpointResponse:
    _ = (offer_id, payload)
    return _planned("/platform-admin/offers/{offer_id}", "Update offer details.", ["Offer details"])


@router.patch("/offers/{offer_id}/status", tags=["Platform Admin - Offers"], response_model=PlannedEndpointResponse)
def update_platform_offer_status(offer_id: str, payload: StatusUpdateRequest) -> PlannedEndpointResponse:
    _ = (offer_id, payload)
    return _planned("/platform-admin/offers/{offer_id}/status", "Pause/resume offer.", ["Offer actions menu"])


@router.delete("/offers/{offer_id}", tags=["Platform Admin - Offers"], response_model=PlannedEndpointResponse)
def delete_platform_offer(offer_id: str) -> PlannedEndpointResponse:
    _ = offer_id
    return _planned("/platform-admin/offers/{offer_id}", "Delete offer.", ["Offer actions menu"])


@router.get("/offers/{offer_id}/providers", tags=["Platform Admin - Offers"], response_model=PlannedEndpointResponse)
def list_platform_offer_providers(offer_id: str) -> PlannedEndpointResponse:
    _ = offer_id
    return _planned("/platform-admin/offers/{offer_id}/providers", "Providers impacted by offer.", ["Offer details"])


@router.patch(
    "/offers/{offer_id}/providers/{provider_id}",
    tags=["Platform Admin - Offers"],
    response_model=PlannedEndpointResponse,
)
def update_platform_offer_provider_state(
    offer_id: str, provider_id: str, payload: StatusUpdateRequest
) -> PlannedEndpointResponse:
    _ = (offer_id, provider_id, payload)
    return _planned(
        "/platform-admin/offers/{offer_id}/providers/{provider_id}",
        "Enable/disable offer for a provider row.",
        ["Offer details provider table"],
    )


@router.get("/billing/overview", tags=["Platform Admin - Billing"])
async def get_billing_overview(
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> dict:
    cache_key = "billing_overview"
    cached = get_cached_data(cache_key)
    if cached is not None:
        return cached

    payments = await _get_or_sync_billing_payments(db)
    
    total_revenue = 0.0
    platform_commission = 0.0
    pending_payouts = 0.0
    
    for p in payments:
        def parse_money(val: str) -> float:
            try:
                return float(val.replace("$", "").replace(",", "").replace("-", ""))
            except:
                return 0.0
        
        earnings = parse_money(p.get("totalEarnings", "0"))
        commission = parse_money(p.get("commission", "0"))
        payout = parse_money(p.get("netPayout", "0"))
        
        total_revenue += earnings
        platform_commission += commission
        if p.get("status") == "PENDING":
            pending_payouts += payout
            
    summary_cards = [
        {
            "label": "Total Revenue",
            "value": f"${total_revenue:,.2f}",
            "note": "+12.5%",
            "tone": "text-[#16a34a]"
        },
        {
            "label": "Platform Commission",
            "value": f"${platform_commission:,.2f}",
            "note": "+8.2%",
            "tone": "text-[#16a34a]"
        },
        {
            "label": "Pending Payouts",
            "value": f"${pending_payouts:,.2f}",
            "note": "Action Needed",
            "tone": "text-[#f59e0b]"
        },
        {
            "label": "Active Subscriptions",
            "value": str(len(payments)),
            "note": "Total Vendors",
            "tone": "text-[#8b96ad]"
        }
    ]
    
    result = {
        "summaryCards": summary_cards,
        "recentPayments": payments
    }
    set_cached_data(cache_key, result, ttl=5)
    return result


@router.get("/billing/payments", tags=["Platform Admin - Billing"])
async def list_billing_payments(
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> dict:
    payments = await _get_or_sync_billing_payments(db)
    return {"payments": payments}


@router.get("/billing/payments/{payment_id}", tags=["Platform Admin - Billing"])
async def get_billing_payment(
    payment_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> dict:
    payments = await _get_or_sync_billing_payments(db)
    match = next((p for p in payments if p["vendorCode"] == payment_id or p["vendor_id"] == payment_id), None)
    if not match:
        raise HTTPException(status_code=404, detail="Payment record not found")
    return match


@router.patch("/billing/payments/{payment_id}", tags=["Platform Admin - Billing"])
async def update_billing_breakdown(
    payment_id: str,
    payload: dict = Body(...),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> dict:
    doc = await db["billing_payments"].find_one({"vendorCode": payment_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Payment record not found")
        
    total_revenue = payload.get("totalRevenue")
    commission_rate = payload.get("commissionRate")
    commission_amount = payload.get("commissionAmount")
    
    update_fields = {
        "is_overridden": True
    }
    if total_revenue is not None:
        update_fields["totalEarnings"] = f"${total_revenue:,.2f}"
        update_fields["details.financialBreakdown.totalRevenue"] = f"${total_revenue:,.2f}"
    if commission_rate is not None:
        update_fields["details.financialBreakdown.commissionRate"] = f"{commission_rate}%"
    if commission_amount is not None:
        update_fields["commission"] = f"-${commission_amount:,.2f}"
        update_fields["details.financialBreakdown.commissionAmount"] = f"-${commission_amount:,.2f}"
        
    if total_revenue is not None and commission_amount is not None:
        net_payout = total_revenue - commission_amount
        update_fields["netPayout"] = f"${net_payout:,.2f}"
        update_fields["details.netPayable.amount"] = f"${net_payout:,.2f}"
        
    await db["billing_payments"].update_one(
        {"vendorCode": payment_id},
        {"$set": update_fields}
    )
    
    invalidate_cache("billing_overview")
    
    payments = await _get_or_sync_billing_payments(db)
    updated = next((p for p in payments if p["vendorCode"] == payment_id), None)
    return {"payments": payments, "updated": updated}


@router.post("/billing/payments/{payment_id}/send-reminder", tags=["Platform Admin - Billing"])
async def send_billing_reminder(
    payment_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> dict:
    doc = await db["billing_payments"].find_one({"vendorCode": payment_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Payment record not found")
        
    now_iso = datetime.now(timezone.utc).isoformat()
    await db["billing_payments"].update_one(
        {"vendorCode": payment_id},
        {"$set": {"details.reminderSentAt": now_iso}}
    )
    
    invalidate_cache("billing_overview")
    
    payments = await _get_or_sync_billing_payments(db)
    updated = next((p for p in payments if p["vendorCode"] == payment_id), None)
    return {"payments": payments, "updated": updated}


@router.post("/billing/payments/{payment_id}/mark-paid", tags=["Platform Admin - Billing"])
async def mark_billing_payment_paid(
    payment_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> dict:
    doc = await db["billing_payments"].find_one({"vendorCode": payment_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Payment record not found")
        
    await db["billing_payments"].update_one(
        {"vendorCode": payment_id},
        {"$set": {"status": "PAID", "details.netPayable.invoiceStatus": "PAID"}}
    )
    
    invalidate_cache("billing_overview")
    
    payments = await _get_or_sync_billing_payments(db)
    updated = next((p for p in payments if p["vendorCode"] == payment_id), None)
    return {"payments": payments, "updated": updated}


@router.get("/billing/payments/{payment_id}/invoice", tags=["Platform Admin - Billing"])
def download_billing_invoice(payment_id: str) -> dict:
    return {"invoice_url": f"https://example.com/invoices/{payment_id}.pdf"}


@router.get("/support/tickets", tags=["Platform Admin - Support"], response_model=PlannedEndpointResponse)
def list_support_tickets() -> PlannedEndpointResponse:
    return _planned("/platform-admin/support/tickets", "Support tickets list.", ["Support table"])


@router.get("/support/tickets/{ticket_id}", tags=["Platform Admin - Support"], response_model=PlannedEndpointResponse)
def get_support_ticket(ticket_id: str) -> PlannedEndpointResponse:
    _ = ticket_id
    return _planned("/platform-admin/support/tickets/{ticket_id}", "Support ticket detail panel.", ["Support detail panel"])


@router.post(
    "/support/tickets/{ticket_id}/messages",
    tags=["Platform Admin - Support"],
    response_model=PlannedEndpointResponse,
)
def reply_support_ticket(ticket_id: str, payload: MessageCreateRequest) -> PlannedEndpointResponse:
    _ = (ticket_id, payload)
    return _planned("/platform-admin/support/tickets/{ticket_id}/messages", "Reply to ticket conversation.", ["Support detail panel"])


@router.patch(
    "/support/tickets/{ticket_id}/status",
    tags=["Platform Admin - Support"],
    response_model=PlannedEndpointResponse,
)
def update_support_ticket_status(ticket_id: str, payload: StatusUpdateRequest) -> PlannedEndpointResponse:
    _ = (ticket_id, payload)
    return _planned("/platform-admin/support/tickets/{ticket_id}/status", "Update ticket status.", ["Support detail panel"])


@router.get("/settings/general", tags=["Platform Admin - Settings"], response_model=PlannedEndpointResponse)
def get_admin_settings_general() -> PlannedEndpointResponse:
    return _planned("/platform-admin/settings/general", "Get admin platform general settings.", ["Admin settings"])


@router.patch("/settings/general", tags=["Platform Admin - Settings"], response_model=PlannedEndpointResponse)
def update_admin_settings_general(payload: GenericPatchRequest) -> PlannedEndpointResponse:
    _ = payload
    return _planned("/platform-admin/settings/general", "Update admin platform general settings.", ["Admin settings"])


@router.patch("/settings/commission", tags=["Platform Admin - Settings"], response_model=PlannedEndpointResponse)
def update_admin_settings_commission(payload: GenericPatchRequest) -> PlannedEndpointResponse:
    _ = payload
    return _planned("/platform-admin/settings/commission", "Update global/category commissions.", ["Admin settings"])


@router.get("/settings/legal/{doc_type}", tags=["Platform Admin - Settings"], response_model=PlannedEndpointResponse)
def get_admin_legal_doc(doc_type: str) -> PlannedEndpointResponse:
    _ = doc_type
    return _planned("/platform-admin/settings/legal/{doc_type}", "Get legal content editor draft.", ["Legal content editor"])


@router.patch("/settings/legal/{doc_type}", tags=["Platform Admin - Settings"], response_model=PlannedEndpointResponse)
def update_admin_legal_doc(doc_type: str, payload: GenericPatchRequest) -> PlannedEndpointResponse:
    _ = (doc_type, payload)
    return _planned("/platform-admin/settings/legal/{doc_type}", "Save legal content editor draft.", ["Legal content editor"])


@router.get("/settings/profile", tags=["Platform Admin - Settings"], response_model=PlannedEndpointResponse)
def get_admin_profile_settings() -> PlannedEndpointResponse:
    return _planned("/platform-admin/settings/profile", "Get admin profile settings.", ["Admin profile"])


@router.patch("/settings/profile", tags=["Platform Admin - Settings"], response_model=PlannedEndpointResponse)
def update_admin_profile_settings(payload: GenericPatchRequest) -> PlannedEndpointResponse:
    _ = payload
    return _planned("/platform-admin/settings/profile", "Update admin profile settings.", ["Admin profile"])


@router.patch("/settings/password", tags=["Platform Admin - Settings"], response_model=PlannedEndpointResponse)
def update_admin_password(payload: GenericPatchRequest) -> PlannedEndpointResponse:
    _ = payload
    return _planned("/platform-admin/settings/password", "Update admin password.", ["Admin settings"])
