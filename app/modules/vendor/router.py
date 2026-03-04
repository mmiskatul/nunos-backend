from fastapi import APIRouter

from app.modules.schemas import (
    AssetUploadRequest,
    GenericPatchRequest,
    MessageCreateRequest,
    PlannedEndpointResponse,
    StatusUpdateRequest,
)

router = APIRouter(prefix="/vendor")


def _planned(endpoint: str, description: str, connected_from: list[str]) -> PlannedEndpointResponse:
    return PlannedEndpointResponse(
        endpoint=endpoint,
        module="vendor",
        description=description,
        connected_from=connected_from,
    )


@router.get("/dashboard/overview", tags=["Vendor - Dashboard"], response_model=PlannedEndpointResponse)
def get_vendor_dashboard_overview() -> PlannedEndpointResponse:
    return _planned("/vendor/dashboard/overview", "Business KPI cards for vendor dashboard.", ["Vendor dashboard"])


@router.get("/dashboard/booking-trends", tags=["Vendor - Dashboard"], response_model=PlannedEndpointResponse)
def get_vendor_booking_trends() -> PlannedEndpointResponse:
    return _planned("/vendor/dashboard/booking-trends", "Monthly booking trend chart.", ["Vendor dashboard"])


@router.get("/dashboard/calendar-preview", tags=["Vendor - Dashboard"], response_model=PlannedEndpointResponse)
def get_vendor_calendar_preview() -> PlannedEndpointResponse:
    return _planned("/vendor/dashboard/calendar-preview", "Calendar events preview.", ["Vendor dashboard"])


@router.get("/dashboard/upcoming-bookings", tags=["Vendor - Dashboard"], response_model=PlannedEndpointResponse)
def get_vendor_upcoming_bookings() -> PlannedEndpointResponse:
    return _planned("/vendor/dashboard/upcoming-bookings", "Upcoming bookings table.", ["Vendor dashboard"])


@router.get("/dashboard/recent-reviews", tags=["Vendor - Dashboard"], response_model=PlannedEndpointResponse)
def get_vendor_recent_reviews() -> PlannedEndpointResponse:
    return _planned("/vendor/dashboard/recent-reviews", "Recent customer reviews panel.", ["Vendor dashboard"])


@router.get("/booking-management/bookings", tags=["Vendor - Bookings"], response_model=PlannedEndpointResponse)
def list_vendor_bookings() -> PlannedEndpointResponse:
    return _planned("/vendor/booking-management/bookings", "List and filter vendor bookings.", ["Booking management table"])


@router.get("/booking-management/bookings/{booking_id}", tags=["Vendor - Bookings"], response_model=PlannedEndpointResponse)
def get_vendor_booking(booking_id: str) -> PlannedEndpointResponse:
    _ = booking_id
    return _planned("/vendor/booking-management/bookings/{booking_id}", "View booking detail side panel.", ["Booking detail panel"])


@router.patch(
    "/booking-management/bookings/{booking_id}/status",
    tags=["Vendor - Bookings"],
    response_model=PlannedEndpointResponse,
)
def update_vendor_booking_status(booking_id: str, payload: StatusUpdateRequest) -> PlannedEndpointResponse:
    _ = (booking_id, payload)
    return _planned(
        "/vendor/booking-management/bookings/{booking_id}/status",
        "Update booking status (confirmed, check-in, complete, canceled).",
        ["Booking table action", "Detail panel action"],
    )


@router.patch(
    "/booking-management/bookings/{booking_id}/reschedule",
    tags=["Vendor - Bookings"],
    response_model=PlannedEndpointResponse,
)
def reschedule_vendor_booking(booking_id: str, payload: GenericPatchRequest) -> PlannedEndpointResponse:
    _ = (booking_id, payload)
    return _planned(
        "/vendor/booking-management/bookings/{booking_id}/reschedule",
        "Reschedule booking date/time.",
        ["Detail panel action"],
    )


@router.post(
    "/booking-management/bookings/{booking_id}/receipt",
    tags=["Vendor - Bookings"],
    response_model=PlannedEndpointResponse,
)
def generate_vendor_booking_receipt(booking_id: str) -> PlannedEndpointResponse:
    _ = booking_id
    return _planned(
        "/vendor/booking-management/bookings/{booking_id}/receipt",
        "Generate booking receipt.",
        ["Detail panel action"],
    )


@router.post("/menu-services/menu-assets", tags=["Vendor - Menu/Services"], response_model=PlannedEndpointResponse)
def upload_vendor_menu_asset(payload: AssetUploadRequest) -> PlannedEndpointResponse:
    _ = payload
    return _planned("/vendor/menu-services/menu-assets", "Upload menu image or document.", ["Menu/services upload"])


@router.post("/menu-services/gallery-assets", tags=["Vendor - Menu/Services"], response_model=PlannedEndpointResponse)
def upload_vendor_gallery_asset(payload: AssetUploadRequest) -> PlannedEndpointResponse:
    _ = payload
    return _planned("/vendor/menu-services/gallery-assets", "Upload gallery media asset.", ["Menu/services upload"])


@router.delete(
    "/menu-services/assets/{asset_id}",
    tags=["Vendor - Menu/Services"],
    response_model=PlannedEndpointResponse,
)
def delete_vendor_asset(asset_id: str) -> PlannedEndpointResponse:
    _ = asset_id
    return _planned("/vendor/menu-services/assets/{asset_id}", "Delete menu/gallery asset.", ["Menu/services upload"])


@router.get("/rooms-services/rooms", tags=["Vendor - Rooms/Services"], response_model=PlannedEndpointResponse)
def list_vendor_rooms() -> PlannedEndpointResponse:
    return _planned("/vendor/rooms-services/rooms", "List vendor room inventory.", ["Rooms & services"])


@router.post("/rooms-services/rooms", tags=["Vendor - Rooms/Services"], response_model=PlannedEndpointResponse)
def create_vendor_room(payload: GenericPatchRequest) -> PlannedEndpointResponse:
    _ = payload
    return _planned("/vendor/rooms-services/rooms", "Create a new room listing.", ["Add new room"])


@router.get("/rooms-services/rooms/{room_id}", tags=["Vendor - Rooms/Services"], response_model=PlannedEndpointResponse)
def get_vendor_room(room_id: str) -> PlannedEndpointResponse:
    _ = room_id
    return _planned("/vendor/rooms-services/rooms/{room_id}", "Get room details.", ["Rooms & services"])


@router.patch("/rooms-services/rooms/{room_id}", tags=["Vendor - Rooms/Services"], response_model=PlannedEndpointResponse)
def update_vendor_room(room_id: str, payload: GenericPatchRequest) -> PlannedEndpointResponse:
    _ = (room_id, payload)
    return _planned("/vendor/rooms-services/rooms/{room_id}", "Update room listing details.", ["Rooms & services"])


@router.patch(
    "/rooms-services/rooms/{room_id}/availability",
    tags=["Vendor - Rooms/Services"],
    response_model=PlannedEndpointResponse,
)
def update_vendor_room_availability(room_id: str, payload: StatusUpdateRequest) -> PlannedEndpointResponse:
    _ = (room_id, payload)
    return _planned(
        "/vendor/rooms-services/rooms/{room_id}/availability",
        "Toggle room availability / maintenance state.",
        ["Rooms & services card toggle"],
    )


@router.delete("/rooms-services/rooms/{room_id}", tags=["Vendor - Rooms/Services"], response_model=PlannedEndpointResponse)
def delete_vendor_room(room_id: str) -> PlannedEndpointResponse:
    _ = room_id
    return _planned("/vendor/rooms-services/rooms/{room_id}", "Delete room listing.", ["Rooms & services"])


@router.get("/promotions", tags=["Vendor - Promotions"], response_model=PlannedEndpointResponse)
def list_vendor_promotions() -> PlannedEndpointResponse:
    return _planned("/vendor/promotions", "List vendor promotions and campaign cards.", ["Promotions list"])


@router.post("/promotions", tags=["Vendor - Promotions"], response_model=PlannedEndpointResponse)
def create_vendor_promotion(payload: GenericPatchRequest) -> PlannedEndpointResponse:
    _ = payload
    return _planned("/vendor/promotions", "Create promotion.", ["Add promotion form"])


@router.get("/promotions/{promotion_id}", tags=["Vendor - Promotions"], response_model=PlannedEndpointResponse)
def get_vendor_promotion(promotion_id: str) -> PlannedEndpointResponse:
    _ = promotion_id
    return _planned("/vendor/promotions/{promotion_id}", "Get promotion details.", ["Promotions list"])


@router.patch("/promotions/{promotion_id}", tags=["Vendor - Promotions"], response_model=PlannedEndpointResponse)
def update_vendor_promotion(promotion_id: str, payload: GenericPatchRequest) -> PlannedEndpointResponse:
    _ = (promotion_id, payload)
    return _planned("/vendor/promotions/{promotion_id}", "Update promotion details.", ["Promotion details"])


@router.patch(
    "/promotions/{promotion_id}/status",
    tags=["Vendor - Promotions"],
    response_model=PlannedEndpointResponse,
)
def update_vendor_promotion_status(promotion_id: str, payload: StatusUpdateRequest) -> PlannedEndpointResponse:
    _ = (promotion_id, payload)
    return _planned(
        "/vendor/promotions/{promotion_id}/status",
        "Enable/disable a promotion campaign.",
        ["Promotions list switch"],
    )


@router.delete("/promotions/{promotion_id}", tags=["Vendor - Promotions"], response_model=PlannedEndpointResponse)
def delete_vendor_promotion(promotion_id: str) -> PlannedEndpointResponse:
    _ = promotion_id
    return _planned("/vendor/promotions/{promotion_id}", "Delete promotion.", ["Promotions list"])


@router.get("/analytics/overview", tags=["Vendor - Analytics"], response_model=PlannedEndpointResponse)
def get_vendor_analytics_overview() -> PlannedEndpointResponse:
    return _planned("/vendor/analytics/overview", "Primary analytics KPIs.", ["Analytics"])


@router.get("/analytics/demographics", tags=["Vendor - Analytics"], response_model=PlannedEndpointResponse)
def get_vendor_analytics_demographics() -> PlannedEndpointResponse:
    return _planned("/vendor/analytics/demographics", "Customer demographic charts.", ["Analytics"])


@router.get("/analytics/occupancy", tags=["Vendor - Analytics"], response_model=PlannedEndpointResponse)
def get_vendor_analytics_occupancy() -> PlannedEndpointResponse:
    return _planned("/vendor/analytics/occupancy", "Occupancy utilization metrics.", ["Analytics"])


@router.get("/analytics/reviews-summary", tags=["Vendor - Analytics"], response_model=PlannedEndpointResponse)
def get_vendor_analytics_reviews_summary() -> PlannedEndpointResponse:
    return _planned("/vendor/analytics/reviews-summary", "Ratings and sentiment summary.", ["Analytics"])


@router.get("/analytics/export", tags=["Vendor - Analytics"], response_model=PlannedEndpointResponse)
def export_vendor_analytics() -> PlannedEndpointResponse:
    return _planned("/vendor/analytics/export", "Export analytics report.", ["Analytics export"])


@router.get("/loyalty/settings", tags=["Vendor - Loyalty"], response_model=PlannedEndpointResponse)
def get_vendor_loyalty_settings() -> PlannedEndpointResponse:
    return _planned("/vendor/loyalty/settings", "Get loyalty points configuration.", ["Loyalty settings"])


@router.patch("/loyalty/settings", tags=["Vendor - Loyalty"], response_model=PlannedEndpointResponse)
def update_vendor_loyalty_settings(payload: GenericPatchRequest) -> PlannedEndpointResponse:
    _ = payload
    return _planned("/vendor/loyalty/settings", "Update loyalty points configuration.", ["Loyalty settings"])


@router.get("/reviews", tags=["Vendor - Reviews"], response_model=PlannedEndpointResponse)
def list_vendor_reviews() -> PlannedEndpointResponse:
    return _planned("/vendor/reviews", "List and filter reviews.", ["Review management"])


@router.post("/reviews/{review_id}/reply", tags=["Vendor - Reviews"], response_model=PlannedEndpointResponse)
def reply_vendor_review(review_id: str, payload: MessageCreateRequest) -> PlannedEndpointResponse:
    _ = (review_id, payload)
    return _planned("/vendor/reviews/{review_id}/reply", "Reply to customer review.", ["Review management"])


@router.get("/settings/general", tags=["Vendor - Settings"], response_model=PlannedEndpointResponse)
def get_vendor_settings_general() -> PlannedEndpointResponse:
    return _planned("/vendor/settings/general", "Get vendor general settings.", ["Settings"])


@router.patch("/settings/general", tags=["Vendor - Settings"], response_model=PlannedEndpointResponse)
def update_vendor_settings_general(payload: GenericPatchRequest) -> PlannedEndpointResponse:
    _ = payload
    return _planned("/vendor/settings/general", "Update vendor general settings.", ["Settings"])


@router.patch("/settings/commission", tags=["Vendor - Settings"], response_model=PlannedEndpointResponse)
def update_vendor_settings_commission(payload: GenericPatchRequest) -> PlannedEndpointResponse:
    _ = payload
    return _planned("/vendor/settings/commission", "Update commission configuration values.", ["Settings"])


@router.get("/settings/legal/{doc_type}", tags=["Vendor - Settings"], response_model=PlannedEndpointResponse)
def get_vendor_legal_doc(doc_type: str) -> PlannedEndpointResponse:
    _ = doc_type
    return _planned("/vendor/settings/legal/{doc_type}", "Get legal content draft.", ["Legal editor"])


@router.patch("/settings/legal/{doc_type}", tags=["Vendor - Settings"], response_model=PlannedEndpointResponse)
def update_vendor_legal_doc(doc_type: str, payload: GenericPatchRequest) -> PlannedEndpointResponse:
    _ = (doc_type, payload)
    return _planned("/vendor/settings/legal/{doc_type}", "Update legal content draft.", ["Legal editor"])


@router.get("/settings/profile", tags=["Vendor - Settings"], response_model=PlannedEndpointResponse)
def get_vendor_profile_settings() -> PlannedEndpointResponse:
    return _planned("/vendor/settings/profile", "Get vendor profile settings.", ["Profile settings"])


@router.patch("/settings/profile", tags=["Vendor - Settings"], response_model=PlannedEndpointResponse)
def update_vendor_profile_settings(payload: GenericPatchRequest) -> PlannedEndpointResponse:
    _ = payload
    return _planned("/vendor/settings/profile", "Update vendor profile settings.", ["Profile settings"])


@router.patch("/settings/password", tags=["Vendor - Settings"], response_model=PlannedEndpointResponse)
def update_vendor_password(payload: GenericPatchRequest) -> PlannedEndpointResponse:
    _ = payload
    return _planned("/vendor/settings/password", "Update vendor account password.", ["Settings password"])

