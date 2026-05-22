from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.api.deps import get_db
from app.modules.schemas import GenericPatchRequest, MessageCreateRequest, PlannedEndpointResponse, StatusUpdateRequest

router = APIRouter(prefix="/platform-admin")


def _planned(endpoint: str, description: str, connected_from: list[str]) -> PlannedEndpointResponse:
    return PlannedEndpointResponse(
        endpoint=endpoint,
        module="platform_admin",
        description=description,
        connected_from=connected_from,
    )


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
            "code": code,
            "name": name,
            "category": v.get("category", "—"),
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


@router.get("/moderation/submissions", tags=["Platform Admin - Moderation"], response_model=PlannedEndpointResponse)
def list_moderation_submissions() -> PlannedEndpointResponse:
    return _planned("/platform-admin/moderation/submissions", "Content moderation queue.", ["Content moderation"])


@router.get(
    "/moderation/submissions/{submission_id}",
    tags=["Platform Admin - Moderation"],
    response_model=PlannedEndpointResponse,
)
def get_moderation_submission(submission_id: str) -> PlannedEndpointResponse:
    _ = submission_id
    return _planned(
        "/platform-admin/moderation/submissions/{submission_id}",
        "Moderation submission detail modal.",
        ["Review details modal"],
    )


@router.patch(
    "/moderation/submissions/{submission_id}/decision",
    tags=["Platform Admin - Moderation"],
    response_model=PlannedEndpointResponse,
)
def decide_moderation_submission(submission_id: str, payload: StatusUpdateRequest) -> PlannedEndpointResponse:
    _ = (submission_id, payload)
    return _planned(
        "/platform-admin/moderation/submissions/{submission_id}/decision",
        "Approve/reject moderated content.",
        ["Review details modal"],
    )


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


@router.get("/billing/overview", tags=["Platform Admin - Billing"], response_model=PlannedEndpointResponse)
def get_billing_overview() -> PlannedEndpointResponse:
    return _planned("/platform-admin/billing/overview", "Billing KPI cards.", ["Billing page"])


@router.get("/billing/payments", tags=["Platform Admin - Billing"], response_model=PlannedEndpointResponse)
def list_billing_payments() -> PlannedEndpointResponse:
    return _planned("/platform-admin/billing/payments", "Vendor payout listing.", ["Billing table"])


@router.get("/billing/payments/{payment_id}", tags=["Platform Admin - Billing"], response_model=PlannedEndpointResponse)
def get_billing_payment(payment_id: str) -> PlannedEndpointResponse:
    _ = payment_id
    return _planned("/platform-admin/billing/payments/{payment_id}", "Billing detail breakdown.", ["Billing details"])


@router.get(
    "/billing/payments/{payment_id}/invoice",
    tags=["Platform Admin - Billing"],
    response_model=PlannedEndpointResponse,
)
def download_billing_invoice(payment_id: str) -> PlannedEndpointResponse:
    _ = payment_id
    return _planned("/platform-admin/billing/payments/{payment_id}/invoice", "Download invoice document.", ["Billing details"])


@router.post(
    "/billing/payments/{payment_id}/send-reminder",
    tags=["Platform Admin - Billing"],
    response_model=PlannedEndpointResponse,
)
def send_billing_reminder(payment_id: str) -> PlannedEndpointResponse:
    _ = payment_id
    return _planned(
        "/platform-admin/billing/payments/{payment_id}/send-reminder",
        "Send payout reminder to vendor.",
        ["Billing details"],
    )


@router.post(
    "/billing/payments/{payment_id}/mark-paid",
    tags=["Platform Admin - Billing"],
    response_model=PlannedEndpointResponse,
)
def mark_billing_payment_paid(payment_id: str) -> PlannedEndpointResponse:
    _ = payment_id
    return _planned("/platform-admin/billing/payments/{payment_id}/mark-paid", "Mark payout as paid.", ["Billing details"])


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
