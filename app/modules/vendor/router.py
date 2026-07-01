from bson.errors import InvalidId
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from pydantic import BaseModel

from app.core.security import hash_password, verify_password
from app.modules.vendor.deps_auth import (
    get_current_vendor,
    get_vendor_auth_service,
    get_vendor_portal_repository,
    get_vendor_portal_service,
    get_vendor_repository,
)
from app.modules.vendor.schemas_auth import VendorDocumentUploadResponse
from app.modules.vendor.schemas_portal import (
    AssetUploadRequest,  # kept for backward-compat but no longer used by file-upload endpoints
    BookingRescheduleRequest,
    BookingStatusUpdateRequest,
    LoyaltySettingsRequest,
    NotificationActionRequest,
    NotificationSettingsRequest,
    PlatformCampaignJoinRequest,
    PromotionStatusRequest,
    PromotionUpsertRequest,
    ReviewReplyRequest,
    RoomAvailabilityRequest,
    RoomUpsertRequest,
    ServiceUpsertRequest,
    VendorLegalDocRequest,
    VendorPasswordChangeRequest,
    VendorSettingsCommissionRequest,
    VendorSettingsGeneralRequest,
    VendorSettingsProfileRequest,
    VendorSupportTicketCreateRequest,
    VendorSupportTicketMessageRequest,
)
from app.modules.vendor.service_auth import VendorAuthService
from app.modules.vendor.service_portal import VendorPortalService

router = APIRouter(prefix="/vendor")


class MessageResponse(BaseModel):
    message: str


def _vendor_id(current_vendor: dict) -> str:
    return current_vendor["id"]


def _safe_call(func, *args, detail: str = "Operation failed", **kwargs):
    """Wrap a repository/service call with proper error handling."""
    try:
        return func(*args, **kwargs)
    except HTTPException:
        raise
    except InvalidId as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid ID format: {exc}",
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"{detail}: {exc}",
        ) from exc


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------


@router.get("/legal/{doc_type}", tags=["Vendor - Public"])
def get_public_vendor_legal_doc(
    doc_type: str,
    portal_service: VendorPortalService = Depends(get_vendor_portal_service),
) -> dict:
    return portal_service.repo.get_legal_doc("public", doc_type)


@router.get("/dashboard/overview", tags=["Vendor - Dashboard"])
def get_vendor_dashboard_overview(
    current_vendor: dict = Depends(get_current_vendor),
    portal_service: VendorPortalService = Depends(get_vendor_portal_service),
) -> dict:
    vendor_id = _vendor_id(current_vendor)
    portal_service.initialize(vendor_id)
    return _safe_call(portal_service.repo.get_dashboard_overview, vendor_id, detail="Failed to load dashboard")


@router.get("/dashboard/booking-trends", tags=["Vendor - Dashboard"])
def get_vendor_booking_trends(
    current_vendor: dict = Depends(get_current_vendor),
    portal_service: VendorPortalService = Depends(get_vendor_portal_service),
) -> dict:
    vendor_id = _vendor_id(current_vendor)
    portal_service.initialize(vendor_id)
    return {"trends": _safe_call(portal_service.repo.get_booking_trends, vendor_id, detail="Failed to load booking trends")}


@router.get("/dashboard/calendar-preview", tags=["Vendor - Dashboard"])
def get_vendor_calendar_preview(
    current_vendor: dict = Depends(get_current_vendor),
    portal_service: VendorPortalService = Depends(get_vendor_portal_service),
) -> dict:
    vendor_id = _vendor_id(current_vendor)
    portal_service.initialize(vendor_id)
    return _safe_call(portal_service.repo.get_calendar_preview, vendor_id, detail="Failed to load calendar")


@router.get("/dashboard/upcoming-bookings", tags=["Vendor - Dashboard"])
def get_vendor_upcoming_bookings(
    limit: int = Query(default=10, ge=1, le=50),
    current_vendor: dict = Depends(get_current_vendor),
    portal_service: VendorPortalService = Depends(get_vendor_portal_service),
) -> dict:
    vendor_id = _vendor_id(current_vendor)
    portal_service.initialize(vendor_id)
    return _safe_call(portal_service.repo.list_bookings, vendor_id, limit=limit, skip=0, status="upcoming", detail="Failed to load bookings")


@router.get("/dashboard/recent-reviews", tags=["Vendor - Dashboard"])
def get_vendor_recent_reviews(
    limit: int = Query(default=5, ge=1, le=20),
    current_vendor: dict = Depends(get_current_vendor),
    portal_service: VendorPortalService = Depends(get_vendor_portal_service),
) -> dict:
    vendor_id = _vendor_id(current_vendor)
    portal_service.initialize(vendor_id)
    return _safe_call(portal_service.repo.list_reviews, vendor_id, limit=limit, skip=0, detail="Failed to load reviews")


# ---------------------------------------------------------------------------
# Uploads — Cloudinary image upload with optional MongoDB persistence
# ---------------------------------------------------------------------------


@router.post("/uploads/image", response_model=VendorDocumentUploadResponse, tags=["Vendor - Uploads"])
async def upload_vendor_image(
    file: UploadFile = File(...),
    context: str | None = Query(
        default=None,
        pattern="^(profile_avatar|cover_image|logo)$",
        description="Optional: where to save the returned URL in MongoDB.",
    ),
    current_vendor: dict = Depends(get_current_vendor),
    auth_service: VendorAuthService = Depends(get_vendor_auth_service),
    portal_repo=Depends(get_vendor_portal_repository),
) -> VendorDocumentUploadResponse:
    """Upload an image file to Cloudinary.

    Optionally saves the returned URL to MongoDB based on *context*:
    - ``profile_avatar`` → ``vendor_portal_settings.profile.avatar_url``
    - ``cover_image``    → ``vendor_portal_settings.general.cover_image_url``
    - ``logo``           → ``vendor_portal_settings.general.logo_url``
    """
    vendor_id = _vendor_id(current_vendor)
    result = await auth_service.upload_registration_document(
        file,
        folder_suffix=f"vendor-{vendor_id}/images",
    )
    if context == "profile_avatar":
        portal_repo.update_avatar_url(vendor_id, result.url)
    elif context == "cover_image":
        portal_repo.update_cover_image_url(vendor_id, result.url)
    elif context == "logo":
        portal_repo.update_logo_url(vendor_id, result.url)
    return result


# ---------------------------------------------------------------------------
# Booking Management
# ---------------------------------------------------------------------------


@router.get("/booking-management/bookings", tags=["Vendor - Bookings"])
def list_vendor_bookings(
    limit: int = Query(default=50, ge=1, le=200),
    skip: int = Query(default=0, ge=0),
    search: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
    current_vendor: dict = Depends(get_current_vendor),
    portal_service: VendorPortalService = Depends(get_vendor_portal_service),
) -> dict:
    return portal_service.list_bookings(
        _vendor_id(current_vendor),
        limit=limit,
        skip=skip,
        search=search,
        status=status_filter,
        date_from=date_from,
        date_to=date_to,
    )


@router.get("/booking-management/bookings/{booking_id}", tags=["Vendor - Bookings"])
def get_vendor_booking(
    booking_id: str,
    current_vendor: dict = Depends(get_current_vendor),
    portal_service: VendorPortalService = Depends(get_vendor_portal_service),
) -> dict:
    return portal_service.get_booking_or_404(_vendor_id(current_vendor), booking_id)


@router.patch("/booking-management/bookings/{booking_id}/status", tags=["Vendor - Bookings"])
def update_vendor_booking_status(
    booking_id: str,
    payload: BookingStatusUpdateRequest,
    current_vendor: dict = Depends(get_current_vendor),
    portal_service: VendorPortalService = Depends(get_vendor_portal_service),
) -> dict:
    vendor_id = _vendor_id(current_vendor)
    try:
        row = portal_service.repo.update_booking_status(vendor_id, booking_id, payload.status, payload.note)
    except InvalidId as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found.") from exc
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found.")
    return row


@router.patch("/booking-management/bookings/{booking_id}/reschedule", tags=["Vendor - Bookings"])
def reschedule_vendor_booking(
    booking_id: str,
    payload: BookingRescheduleRequest,
    current_vendor: dict = Depends(get_current_vendor),
    portal_service: VendorPortalService = Depends(get_vendor_portal_service),
) -> dict:
    vendor_id = _vendor_id(current_vendor)
    try:
        row = portal_service.repo.reschedule_booking(vendor_id, booking_id, payload.date, payload.time, payload.note)
    except InvalidId as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found.") from exc
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found.")
    return row


@router.post("/booking-management/bookings/{booking_id}/receipt", tags=["Vendor - Bookings"])
def generate_vendor_booking_receipt(
    booking_id: str,
    current_vendor: dict = Depends(get_current_vendor),
    portal_service: VendorPortalService = Depends(get_vendor_portal_service),
) -> dict:
    vendor_id = _vendor_id(current_vendor)
    try:
        receipt = portal_service.repo.generate_receipt(vendor_id, booking_id)
    except InvalidId as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found.") from exc
    if not receipt:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found.")
    return receipt


# ---------------------------------------------------------------------------
# Menu / Services — file upload endpoints (Cloudinary + MongoDB persistence)
# ---------------------------------------------------------------------------


@router.get("/menu-services/assets", tags=["Vendor - Menu/Services"])
def list_menu_assets(
    asset_type: str | None = Query(default=None),
    current_vendor: dict = Depends(get_current_vendor),
    portal_service: VendorPortalService = Depends(get_vendor_portal_service),
) -> dict:
    vendor_id = _vendor_id(current_vendor)
    portal_service.initialize(vendor_id)
    return {"items": portal_service.repo.list_assets(vendor_id, asset_type=asset_type)}


@router.get("/menu-services/overview", tags=["Vendor - Menu/Services"])
def get_menu_services_overview(
    current_vendor: dict = Depends(get_current_vendor),
    portal_service: VendorPortalService = Depends(get_vendor_portal_service),
) -> dict:
    vendor_id = _vendor_id(current_vendor)
    portal_service.initialize(vendor_id)
    return {
        "menu_assets": portal_service.repo.list_assets(vendor_id, asset_type="menu"),
        "gallery_assets": portal_service.repo.list_assets(vendor_id, asset_type="gallery"),
        "upload_guidelines": "Use high-resolution images for gallery and high-contrast pages for menu OCR.",
    }


@router.post("/menu-services/menu-assets", tags=["Vendor - Menu/Services"])
async def upload_vendor_menu_asset(
    file: UploadFile = File(..., description="Menu image or PDF to upload"),
    file_name: str | None = Form(default=None),
    mime_type: str | None = Form(default=None),
    current_vendor: dict = Depends(get_current_vendor),
    portal_service: VendorPortalService = Depends(get_vendor_portal_service),
    auth_service: VendorAuthService = Depends(get_vendor_auth_service),
) -> dict:
    """Upload a menu asset file to Cloudinary and save the URL in MongoDB."""
    vendor_id = _vendor_id(current_vendor)
    result = await auth_service.upload_registration_document(
        file,
        folder_suffix=f"vendor-{vendor_id}/menu",
    )
    data = {
        "asset_url": result.url,
        "asset_type": "menu",
        "file_name": file_name or file.filename,
        "mime_type": mime_type or file.content_type,
    }
    return portal_service.repo.add_asset(vendor_id, data)


@router.post("/menu-services/gallery-assets", tags=["Vendor - Menu/Services"])
async def upload_vendor_gallery_asset(
    file: UploadFile = File(..., description="Gallery image to upload"),
    file_name: str | None = Form(default=None),
    mime_type: str | None = Form(default=None),
    current_vendor: dict = Depends(get_current_vendor),
    portal_service: VendorPortalService = Depends(get_vendor_portal_service),
    auth_service: VendorAuthService = Depends(get_vendor_auth_service),
) -> dict:
    """Upload a gallery image to Cloudinary and save the URL in MongoDB."""
    vendor_id = _vendor_id(current_vendor)
    result = await auth_service.upload_registration_document(
        file,
        folder_suffix=f"vendor-{vendor_id}/gallery",
    )
    data = {
        "asset_url": result.url,
        "asset_type": "gallery",
        "file_name": file_name or file.filename,
        "mime_type": mime_type or file.content_type,
    }
    return portal_service.repo.add_asset(vendor_id, data)


@router.delete("/menu-services/assets/{asset_id}", tags=["Vendor - Menu/Services"], response_model=MessageResponse)
def delete_vendor_asset(
    asset_id: str,
    current_vendor: dict = Depends(get_current_vendor),
    portal_service: VendorPortalService = Depends(get_vendor_portal_service),
) -> MessageResponse:
    try:
        deleted = portal_service.repo.delete_asset(_vendor_id(current_vendor), asset_id)
    except InvalidId as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found.") from exc
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found.")
    return MessageResponse(message="Asset deleted.")


# ---------------------------------------------------------------------------
# Rooms / Services
# ---------------------------------------------------------------------------


@router.get("/rooms-services/rooms", tags=["Vendor - Rooms/Services"])
def list_vendor_rooms(
    current_vendor: dict = Depends(get_current_vendor),
    portal_service: VendorPortalService = Depends(get_vendor_portal_service),
) -> dict:
    vendor_id = _vendor_id(current_vendor)
    portal_service.initialize(vendor_id)
    return {"items": portal_service.repo.list_rooms(vendor_id)}


@router.post("/rooms-services/rooms", tags=["Vendor - Rooms/Services"])
def create_vendor_room(
    payload: RoomUpsertRequest,
    current_vendor: dict = Depends(get_current_vendor),
    portal_service: VendorPortalService = Depends(get_vendor_portal_service),
) -> dict:
    return portal_service.repo.create_room(_vendor_id(current_vendor), payload.model_dump())


@router.get("/rooms-services/rooms/{room_id}", tags=["Vendor - Rooms/Services"])
def get_vendor_room(
    room_id: str,
    current_vendor: dict = Depends(get_current_vendor),
    portal_service: VendorPortalService = Depends(get_vendor_portal_service),
) -> dict:
    return portal_service.get_room_or_404(_vendor_id(current_vendor), room_id)


@router.patch("/rooms-services/rooms/{room_id}", tags=["Vendor - Rooms/Services"])
def update_vendor_room(
    room_id: str,
    payload: RoomUpsertRequest,
    current_vendor: dict = Depends(get_current_vendor),
    portal_service: VendorPortalService = Depends(get_vendor_portal_service),
) -> dict:
    try:
        row = portal_service.repo.update_room(_vendor_id(current_vendor), room_id, payload.model_dump())
    except InvalidId as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Room not found.") from exc
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Room not found.")
    return row


@router.patch("/rooms-services/rooms/{room_id}/availability", tags=["Vendor - Rooms/Services"])
def update_vendor_room_availability(
    room_id: str,
    payload: RoomAvailabilityRequest,
    current_vendor: dict = Depends(get_current_vendor),
    portal_service: VendorPortalService = Depends(get_vendor_portal_service),
) -> dict:
    try:
        row = portal_service.repo.update_room_availability(
            _vendor_id(current_vendor), room_id, payload.available, payload.maintenance_note
        )
    except InvalidId as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Room not found.") from exc
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Room not found.")
    return row


@router.delete("/rooms-services/rooms/{room_id}", tags=["Vendor - Rooms/Services"], response_model=MessageResponse)
def delete_vendor_room(
    room_id: str,
    current_vendor: dict = Depends(get_current_vendor),
    portal_service: VendorPortalService = Depends(get_vendor_portal_service),
) -> MessageResponse:
    try:
        deleted = portal_service.repo.delete_room(_vendor_id(current_vendor), room_id)
    except InvalidId as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Room not found.") from exc
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Room not found.")
    return MessageResponse(message="Room deleted.")


@router.get("/rooms-services/services", tags=["Vendor - Rooms/Services"])
def list_vendor_services(
    current_vendor: dict = Depends(get_current_vendor),
    portal_service: VendorPortalService = Depends(get_vendor_portal_service),
) -> dict:
    vendor_id = _vendor_id(current_vendor)
    portal_service.initialize(vendor_id)
    return {"items": portal_service.repo.list_services(vendor_id)}


@router.post("/rooms-services/services", tags=["Vendor - Rooms/Services"])
def create_vendor_service(
    payload: ServiceUpsertRequest,
    current_vendor: dict = Depends(get_current_vendor),
    portal_service: VendorPortalService = Depends(get_vendor_portal_service),
) -> dict:
    return portal_service.repo.create_service(_vendor_id(current_vendor), payload.model_dump())


@router.get("/rooms-services/services/{service_id}", tags=["Vendor - Rooms/Services"])
def get_vendor_service(
    service_id: str,
    current_vendor: dict = Depends(get_current_vendor),
    portal_service: VendorPortalService = Depends(get_vendor_portal_service),
) -> dict:
    return portal_service.get_service_or_404(_vendor_id(current_vendor), service_id)


@router.patch("/rooms-services/services/{service_id}", tags=["Vendor - Rooms/Services"])
def update_vendor_service(
    service_id: str,
    payload: ServiceUpsertRequest,
    current_vendor: dict = Depends(get_current_vendor),
    portal_service: VendorPortalService = Depends(get_vendor_portal_service),
) -> dict:
    try:
        row = portal_service.repo.update_service(_vendor_id(current_vendor), service_id, payload.model_dump())
    except InvalidId as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Service not found.") from exc
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Service not found.")
    return row


@router.patch("/rooms-services/services/{service_id}/status", tags=["Vendor - Rooms/Services"])
def update_vendor_service_status(
    service_id: str,
    active: bool,
    current_vendor: dict = Depends(get_current_vendor),
    portal_service: VendorPortalService = Depends(get_vendor_portal_service),
) -> dict:
    try:
        row = portal_service.repo.update_service_status(_vendor_id(current_vendor), service_id, active)
    except InvalidId as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Service not found.") from exc
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Service not found.")
    return row


@router.delete("/rooms-services/services/{service_id}", tags=["Vendor - Rooms/Services"], response_model=MessageResponse)
def delete_vendor_service(
    service_id: str,
    current_vendor: dict = Depends(get_current_vendor),
    portal_service: VendorPortalService = Depends(get_vendor_portal_service),
) -> MessageResponse:
    try:
        deleted = portal_service.repo.delete_service(_vendor_id(current_vendor), service_id)
    except InvalidId as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Service not found.") from exc
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Service not found.")
    return MessageResponse(message="Service deleted.")


# ---------------------------------------------------------------------------
# Promotions
# ---------------------------------------------------------------------------


@router.get("/promotions", tags=["Vendor - Promotions"])
def list_vendor_promotions(
    search: str | None = Query(default=None),
    active: bool | None = Query(default=None),
    current_vendor: dict = Depends(get_current_vendor),
    portal_service: VendorPortalService = Depends(get_vendor_portal_service),
) -> dict:
    vendor_id = _vendor_id(current_vendor)
    portal_service.initialize(vendor_id)
    business_promotions = portal_service.repo.list_promotions(vendor_id, search=search, active=active)
    platform_campaigns = portal_service.repo.list_platform_campaigns(vendor_id)
    return {
        "summary": portal_service.repo.summarize_promotions(business_promotions),
        "business_promotions": business_promotions,
        "platform_campaigns": platform_campaigns,
    }


@router.post("/promotions", tags=["Vendor - Promotions"])
def create_vendor_promotion(
    payload: PromotionUpsertRequest,
    current_vendor: dict = Depends(get_current_vendor),
    portal_service: VendorPortalService = Depends(get_vendor_portal_service),
) -> dict:
    return portal_service.repo.create_promotion(_vendor_id(current_vendor), payload.model_dump())


@router.get("/promotions/{promotion_id}", tags=["Vendor - Promotions"])
def get_vendor_promotion(
    promotion_id: str,
    current_vendor: dict = Depends(get_current_vendor),
    portal_service: VendorPortalService = Depends(get_vendor_portal_service),
) -> dict:
    return portal_service.get_promotion_or_404(_vendor_id(current_vendor), promotion_id)


@router.patch("/promotions/{promotion_id}", tags=["Vendor - Promotions"])
def update_vendor_promotion(
    promotion_id: str,
    payload: PromotionUpsertRequest,
    current_vendor: dict = Depends(get_current_vendor),
    portal_service: VendorPortalService = Depends(get_vendor_portal_service),
) -> dict:
    try:
        row = portal_service.repo.update_promotion(_vendor_id(current_vendor), promotion_id, payload.model_dump())
    except InvalidId as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Promotion not found.") from exc
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Promotion not found.")
    return row


@router.patch("/promotions/{promotion_id}/status", tags=["Vendor - Promotions"])
def update_vendor_promotion_status(
    promotion_id: str,
    payload: PromotionStatusRequest,
    current_vendor: dict = Depends(get_current_vendor),
    portal_service: VendorPortalService = Depends(get_vendor_portal_service),
) -> dict:
    try:
        row = portal_service.repo.update_promotion_status(
            _vendor_id(current_vendor), promotion_id, payload.active
        )
    except InvalidId as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Promotion not found.") from exc
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Promotion not found.")
    return row


@router.delete("/promotions/{promotion_id}", tags=["Vendor - Promotions"], response_model=MessageResponse)
def delete_vendor_promotion(
    promotion_id: str,
    current_vendor: dict = Depends(get_current_vendor),
    portal_service: VendorPortalService = Depends(get_vendor_portal_service),
) -> MessageResponse:
    try:
        deleted = portal_service.repo.delete_promotion(_vendor_id(current_vendor), promotion_id)
    except InvalidId as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Promotion not found.") from exc
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Promotion not found.")
    return MessageResponse(message="Promotion deleted.")


@router.patch("/promotions/platform-campaigns/{campaign_id}/join", tags=["Vendor - Promotions"])
def join_platform_campaign(
    campaign_id: str,
    payload: PlatformCampaignJoinRequest,
    current_vendor: dict = Depends(get_current_vendor),
    portal_service: VendorPortalService = Depends(get_vendor_portal_service),
) -> dict:
    try:
        return portal_service.repo.set_platform_campaign_join(
            _vendor_id(current_vendor), campaign_id, payload.join
        )
    except InvalidId as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


# ---------------------------------------------------------------------------
# Analytics
# ---------------------------------------------------------------------------


@router.get("/analytics/overview", tags=["Vendor - Analytics"])
def get_vendor_analytics_overview(
    current_vendor: dict = Depends(get_current_vendor),
    portal_service: VendorPortalService = Depends(get_vendor_portal_service),
) -> dict:
    vendor_id = _vendor_id(current_vendor)
    portal_service.initialize(vendor_id)
    return portal_service.repo.get_analytics_overview(vendor_id)


@router.get("/analytics/demographics", tags=["Vendor - Analytics"])
def get_vendor_analytics_demographics(
    current_vendor: dict = Depends(get_current_vendor),
    portal_service: VendorPortalService = Depends(get_vendor_portal_service),
) -> dict:
    vendor_id = _vendor_id(current_vendor)
    portal_service.initialize(vendor_id)
    return portal_service.repo.get_demographics(vendor_id)


@router.get("/analytics/occupancy", tags=["Vendor - Analytics"])
def get_vendor_analytics_occupancy(
    current_vendor: dict = Depends(get_current_vendor),
    portal_service: VendorPortalService = Depends(get_vendor_portal_service),
) -> dict:
    vendor_id = _vendor_id(current_vendor)
    portal_service.initialize(vendor_id)
    return portal_service.repo.get_occupancy_metrics(vendor_id)


@router.get("/analytics/reviews-summary", tags=["Vendor - Analytics"])
def get_vendor_analytics_reviews_summary(
    current_vendor: dict = Depends(get_current_vendor),
    portal_service: VendorPortalService = Depends(get_vendor_portal_service),
) -> dict:
    vendor_id = _vendor_id(current_vendor)
    portal_service.initialize(vendor_id)
    return portal_service.repo.get_reviews_summary(vendor_id)


@router.get("/analytics/export", tags=["Vendor - Analytics"])
def export_vendor_analytics(
    current_vendor: dict = Depends(get_current_vendor),
    portal_service: VendorPortalService = Depends(get_vendor_portal_service),
) -> dict:
    return portal_service.repo.export_analytics(_vendor_id(current_vendor))


# ---------------------------------------------------------------------------
# Loyalty
# ---------------------------------------------------------------------------


@router.get("/loyalty/settings", tags=["Vendor - Loyalty"])
def get_vendor_loyalty_settings(
    current_vendor: dict = Depends(get_current_vendor),
    portal_service: VendorPortalService = Depends(get_vendor_portal_service),
) -> dict:
    vendor_id = _vendor_id(current_vendor)
    portal_service.initialize(vendor_id)
    return portal_service.repo.get_loyalty_settings(vendor_id)


@router.patch("/loyalty/settings", tags=["Vendor - Loyalty"])
def update_vendor_loyalty_settings(
    payload: LoyaltySettingsRequest,
    current_vendor: dict = Depends(get_current_vendor),
    portal_service: VendorPortalService = Depends(get_vendor_portal_service),
) -> dict:
    return portal_service.repo.update_loyalty_settings(_vendor_id(current_vendor), payload.model_dump())


# ---------------------------------------------------------------------------
# Reviews
# ---------------------------------------------------------------------------


@router.get("/reviews", tags=["Vendor - Reviews"])
def list_vendor_reviews(
    limit: int = Query(default=50, ge=1, le=200),
    skip: int = Query(default=0, ge=0),
    search: str | None = Query(default=None),
    star_rating: int | None = Query(default=None, ge=1, le=5),
    replied: bool | None = Query(default=None),
    current_vendor: dict = Depends(get_current_vendor),
    portal_service: VendorPortalService = Depends(get_vendor_portal_service),
) -> dict:
    vendor_id = _vendor_id(current_vendor)
    portal_service.initialize(vendor_id)
    return portal_service.repo.list_reviews(
        vendor_id, limit=limit, skip=skip, search=search, star_rating=star_rating, replied=replied
    )


@router.post("/reviews/{review_id}/reply", tags=["Vendor - Reviews"])
def reply_vendor_review(
    review_id: str,
    payload: ReviewReplyRequest,
    current_vendor: dict = Depends(get_current_vendor),
    portal_service: VendorPortalService = Depends(get_vendor_portal_service),
) -> dict:
    try:
        row = portal_service.repo.reply_review(_vendor_id(current_vendor), review_id, payload.reply_text)
    except InvalidId as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Review not found.") from exc
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Review not found.")
    return row


# ---------------------------------------------------------------------------
# Settings — general, profile, commission, legal
# ---------------------------------------------------------------------------


@router.get("/settings/general", tags=["Vendor - Settings"])
def get_vendor_settings_general(
    current_vendor: dict = Depends(get_current_vendor),
    portal_service: VendorPortalService = Depends(get_vendor_portal_service),
) -> dict:
    vendor_id = _vendor_id(current_vendor)
    portal_service.initialize(vendor_id)
    return portal_service.repo.get_settings_general(vendor_id)


@router.get("/settings", tags=["Vendor - Settings"])
def get_vendor_settings_bundle(
    current_vendor: dict = Depends(get_current_vendor),
    portal_service: VendorPortalService = Depends(get_vendor_portal_service),
) -> dict:
    vendor_id = _vendor_id(current_vendor)
    portal_service.initialize(vendor_id)
    return portal_service.repo.get_settings(vendor_id)


@router.patch("/settings/general", tags=["Vendor - Settings"])
def update_vendor_settings_general(
    payload: VendorSettingsGeneralRequest,
    current_vendor: dict = Depends(get_current_vendor),
    portal_service: VendorPortalService = Depends(get_vendor_portal_service),
) -> dict:
    return portal_service.repo.update_settings_general(_vendor_id(current_vendor), payload.model_dump())


@router.patch("/settings/commission", tags=["Vendor - Settings"])
def update_vendor_settings_commission(
    payload: VendorSettingsCommissionRequest,
    current_vendor: dict = Depends(get_current_vendor),
    portal_service: VendorPortalService = Depends(get_vendor_portal_service),
) -> dict:
    return portal_service.repo.update_settings_commission(_vendor_id(current_vendor), payload.model_dump())


@router.get("/settings/legal/{doc_type}", tags=["Vendor - Settings"])
def get_vendor_legal_doc(
    doc_type: str,
    current_vendor: dict = Depends(get_current_vendor),
    portal_service: VendorPortalService = Depends(get_vendor_portal_service),
) -> dict:
    return portal_service.repo.get_legal_doc(_vendor_id(current_vendor), doc_type)


@router.patch("/settings/legal/{doc_type}", tags=["Vendor - Settings"])
def update_vendor_legal_doc(
    doc_type: str,
    payload: VendorLegalDocRequest,
    current_vendor: dict = Depends(get_current_vendor),
    portal_service: VendorPortalService = Depends(get_vendor_portal_service),
) -> dict:
    return portal_service.repo.update_legal_doc(
        _vendor_id(current_vendor), doc_type, payload.content, payload.audience
    )


@router.get("/settings/profile", tags=["Vendor - Settings"])
def get_vendor_profile_settings(
    current_vendor: dict = Depends(get_current_vendor),
    portal_service: VendorPortalService = Depends(get_vendor_portal_service),
) -> dict:
    vendor_id = _vendor_id(current_vendor)
    portal_service.initialize(vendor_id)
    return portal_service.repo.get_settings_profile(vendor_id)


@router.patch("/settings/profile", tags=["Vendor - Settings"])
def update_vendor_profile_settings(
    payload: VendorSettingsProfileRequest,
    current_vendor: dict = Depends(get_current_vendor),
    portal_service: VendorPortalService = Depends(get_vendor_portal_service),
) -> dict:
    return portal_service.repo.update_settings_profile(_vendor_id(current_vendor), payload.model_dump())


# ---------------------------------------------------------------------------
# Settings — image upload endpoints (Cloudinary → MongoDB)
# ---------------------------------------------------------------------------


@router.post("/settings/general/logo", tags=["Vendor - Settings"])
async def upload_vendor_logo(
    file: UploadFile = File(..., description="Logo image to upload"),
    current_vendor: dict = Depends(get_current_vendor),
    auth_service: VendorAuthService = Depends(get_vendor_auth_service),
    portal_repo=Depends(get_vendor_portal_repository),
) -> dict:
    """Upload a logo image to Cloudinary and save the URL to vendor general settings."""
    vendor_id = _vendor_id(current_vendor)
    result = await auth_service.upload_registration_document(
        file,
        folder_suffix=f"vendor-{vendor_id}/logo",
    )
    saved = portal_repo.update_logo_url(vendor_id, result.url)
    return {"logo_url": result.url, "settings": saved, "message": "Logo updated successfully."}


@router.post("/settings/general/cover-image", tags=["Vendor - Settings"])
async def upload_vendor_cover_image(
    file: UploadFile = File(..., description="Cover image to upload"),
    current_vendor: dict = Depends(get_current_vendor),
    auth_service: VendorAuthService = Depends(get_vendor_auth_service),
    portal_repo=Depends(get_vendor_portal_repository),
) -> dict:
    """Upload a cover image to Cloudinary and save the URL to vendor general settings."""
    vendor_id = _vendor_id(current_vendor)
    result = await auth_service.upload_registration_document(
        file,
        folder_suffix=f"vendor-{vendor_id}/cover",
    )
    saved = portal_repo.update_cover_image_url(vendor_id, result.url)
    return {"cover_image_url": result.url, "settings": saved, "message": "Cover image updated successfully."}


@router.post("/settings/profile/avatar", tags=["Vendor - Settings"])
async def upload_vendor_profile_avatar(
    file: UploadFile = File(..., description="Profile avatar image to upload"),
    current_vendor: dict = Depends(get_current_vendor),
    auth_service: VendorAuthService = Depends(get_vendor_auth_service),
    portal_repo=Depends(get_vendor_portal_repository),
) -> dict:
    """Upload a profile avatar image to Cloudinary and save the URL to vendor profile settings."""
    vendor_id = _vendor_id(current_vendor)
    result = await auth_service.upload_registration_document(
        file,
        folder_suffix=f"vendor-{vendor_id}/avatar",
    )
    saved = portal_repo.update_avatar_url(vendor_id, result.url)
    return {"avatar_url": result.url, "settings": saved, "message": "Avatar updated successfully."}


# ---------------------------------------------------------------------------
# Settings — password change
# ---------------------------------------------------------------------------


@router.patch("/settings/password", tags=["Vendor - Settings"], response_model=MessageResponse)
def update_vendor_password(
    payload: VendorPasswordChangeRequest,
    current_vendor: dict = Depends(get_current_vendor),
    vendor_repo=Depends(get_vendor_repository),
) -> MessageResponse:
    if not verify_password(payload.old_password, current_vendor["password_hash"]):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Old password is incorrect.")
    vendor_repo.update_password_hash(current_vendor["id"], hash_password(payload.new_password))
    return MessageResponse(message="Password updated successfully.")


# ---------------------------------------------------------------------------
# Support
# ---------------------------------------------------------------------------


@router.get("/support/tickets", tags=["Vendor - Support"])
def list_support_tickets(
    limit: int = Query(default=50, ge=1, le=200),
    skip: int = Query(default=0, ge=0),
    current_vendor: dict = Depends(get_current_vendor),
    portal_service: VendorPortalService = Depends(get_vendor_portal_service),
) -> dict:
    vendor_id = _vendor_id(current_vendor)
    portal_service.initialize(vendor_id)
    return portal_service.repo.list_support_tickets(vendor_id, limit=limit, skip=skip)


@router.post("/support/tickets", tags=["Vendor - Support"])
def submit_support_ticket(
    payload: VendorSupportTicketCreateRequest,
    current_vendor: dict = Depends(get_current_vendor),
    portal_service: VendorPortalService = Depends(get_vendor_portal_service),
) -> dict:
    return portal_service.repo.create_support_ticket(
        _vendor_id(current_vendor), payload.subject, payload.description
    )


@router.get("/support/tickets/{ticket_id}", tags=["Vendor - Support"])
def get_support_ticket(
    ticket_id: str,
    current_vendor: dict = Depends(get_current_vendor),
    portal_service: VendorPortalService = Depends(get_vendor_portal_service),
) -> dict:
    return portal_service.get_support_ticket_or_404(_vendor_id(current_vendor), ticket_id)


@router.post("/support/tickets/{ticket_id}/messages", tags=["Vendor - Support"])
def add_support_ticket_message(
    ticket_id: str,
    payload: VendorSupportTicketMessageRequest,
    current_vendor: dict = Depends(get_current_vendor),
    portal_service: VendorPortalService = Depends(get_vendor_portal_service),
) -> dict:
    vendor_id = _vendor_id(current_vendor)
    try:
        row = portal_service.repo.add_support_ticket_message(vendor_id, ticket_id, payload.message, payload.metadata)
    except InvalidId as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found.") from exc
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found.")
    return row


# ---------------------------------------------------------------------------
# Notifications
# ---------------------------------------------------------------------------


@router.get("/notifications", tags=["Vendor - Notifications"])
def list_notifications(
    limit: int = Query(default=50, ge=1, le=200),
    skip: int = Query(default=0, ge=0),
    current_vendor: dict = Depends(get_current_vendor),
    portal_service: VendorPortalService = Depends(get_vendor_portal_service),
) -> dict:
    vendor_id = _vendor_id(current_vendor)
    portal_service.initialize(vendor_id)
    return portal_service.repo.list_notifications(vendor_id, limit=limit, skip=skip)


@router.patch("/notifications/settings", tags=["Vendor - Notifications"])
def update_notification_settings(
    payload: NotificationSettingsRequest,
    current_vendor: dict = Depends(get_current_vendor),
    portal_service: VendorPortalService = Depends(get_vendor_portal_service),
) -> dict:
    return portal_service.repo.update_notification_settings(_vendor_id(current_vendor), payload.model_dump())


@router.delete("/notifications/clear", tags=["Vendor - Notifications"], response_model=MessageResponse)
def clear_notifications(
    current_vendor: dict = Depends(get_current_vendor),
    portal_service: VendorPortalService = Depends(get_vendor_portal_service),
) -> MessageResponse:
    count = portal_service.repo.clear_notifications(_vendor_id(current_vendor))
    return MessageResponse(message=f"Cleared {count} notifications.")


@router.post("/notifications/{notification_id}/action", tags=["Vendor - Notifications"])
def perform_notification_action(
    notification_id: str,
    payload: NotificationActionRequest,
    current_vendor: dict = Depends(get_current_vendor),
    portal_service: VendorPortalService = Depends(get_vendor_portal_service),
) -> dict:
    try:
        row = portal_service.repo.apply_notification_action(
            _vendor_id(current_vendor), notification_id, payload.action
        )
    except InvalidId as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found.") from exc
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found.")
    return row
