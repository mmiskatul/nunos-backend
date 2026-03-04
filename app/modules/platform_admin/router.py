from fastapi import APIRouter

from app.modules.schemas import GenericPatchRequest, MessageCreateRequest, PlannedEndpointResponse, StatusUpdateRequest

router = APIRouter(prefix="/platform-admin")


def _planned(endpoint: str, description: str, connected_from: list[str]) -> PlannedEndpointResponse:
    return PlannedEndpointResponse(
        endpoint=endpoint,
        module="platform_admin",
        description=description,
        connected_from=connected_from,
    )


@router.get("/dashboard/overview", tags=["Platform Admin - Dashboard"], response_model=PlannedEndpointResponse)
def get_platform_dashboard_overview() -> PlannedEndpointResponse:
    return _planned("/platform-admin/dashboard/overview", "Platform KPI summary cards.", ["Platform dashboard"])


@router.get("/dashboard/revenue-growth", tags=["Platform Admin - Dashboard"], response_model=PlannedEndpointResponse)
def get_platform_revenue_growth() -> PlannedEndpointResponse:
    return _planned("/platform-admin/dashboard/revenue-growth", "Revenue growth chart data.", ["Platform dashboard"])


@router.get("/dashboard/booking-insights", tags=["Platform Admin - Dashboard"], response_model=PlannedEndpointResponse)
def get_platform_booking_insights() -> PlannedEndpointResponse:
    return _planned("/platform-admin/dashboard/booking-insights", "Booking insight donut data.", ["Platform dashboard"])


@router.get("/dashboard/vendor-performance", tags=["Platform Admin - Dashboard"], response_model=PlannedEndpointResponse)
def get_platform_vendor_performance() -> PlannedEndpointResponse:
    return _planned("/platform-admin/dashboard/vendor-performance", "Vendor performance table.", ["Platform dashboard"])


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
