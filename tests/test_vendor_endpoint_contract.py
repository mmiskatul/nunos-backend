import pytest

from app.modules.vendor.schemas_portal import (
    AssetUploadRequest,
    PromotionUpdateRequest,
    RoomUpsertRequest,
    ServiceUpsertRequest,
    VendorEventUpsertRequest,
)
from app.modules.platform_admin.deps_auth import get_current_platform_admin


FRONTEND_VENDOR_ENDPOINTS = {
    ("POST", "/api/v1/vendor/auth/register/request-code"),
    ("POST", "/api/v1/vendor/auth/register/verify-code"),
    ("POST", "/api/v1/vendor/auth/register"),
    ("GET", "/api/v1/vendor/auth/registration-form-config"),
    ("POST", "/api/v1/vendor/auth/upload-document"),
    ("GET", "/api/v1/vendor/auth/registration-status"),
    ("POST", "/api/v1/vendor/auth/login"),
    ("POST", "/api/v1/vendor/auth/refresh"),
    ("POST", "/api/v1/vendor/auth/logout"),
    ("POST", "/api/v1/vendor/auth/forgot-password/request"),
    ("POST", "/api/v1/vendor/auth/forgot-password/verify-code"),
    ("POST", "/api/v1/vendor/auth/forgot-password/reset"),
    ("POST", "/api/v1/vendor/auth/kyc/submit"),
    ("GET", "/api/v1/vendor/auth/kyc/status"),
    ("GET", "/api/v1/vendor/legal/{doc_type}"),
    ("GET", "/api/v1/vendor/dashboard/overview"),
    ("GET", "/api/v1/vendor/dashboard/booking-trends"),
    ("GET", "/api/v1/vendor/dashboard/calendar-preview"),
    ("GET", "/api/v1/vendor/dashboard/upcoming-bookings"),
    ("GET", "/api/v1/vendor/dashboard/recent-reviews"),
    ("POST", "/api/v1/vendor/uploads/image"),
    ("GET", "/api/v1/vendor/booking-management/bookings"),
    ("GET", "/api/v1/vendor/booking-management/bookings/{booking_id}"),
    ("PATCH", "/api/v1/vendor/booking-management/bookings/{booking_id}/status"),
    ("PATCH", "/api/v1/vendor/booking-management/bookings/{booking_id}/reschedule"),
    ("POST", "/api/v1/vendor/booking-management/bookings/{booking_id}/receipt"),
    ("GET", "/api/v1/vendor/menu-services/assets"),
    ("POST", "/api/v1/vendor/menu-services/assets"),
    ("GET", "/api/v1/vendor/menu-services/overview"),
    ("POST", "/api/v1/vendor/menu-services/menu-assets"),
    ("POST", "/api/v1/vendor/menu-services/gallery-assets"),
    ("DELETE", "/api/v1/vendor/menu-services/assets/{asset_id}"),
    ("GET", "/api/v1/vendor/rooms-services/rooms"),
    ("POST", "/api/v1/vendor/rooms-services/rooms"),
    ("GET", "/api/v1/vendor/rooms-services/rooms/{room_id}"),
    ("PATCH", "/api/v1/vendor/rooms-services/rooms/{room_id}"),
    ("PATCH", "/api/v1/vendor/rooms-services/rooms/{room_id}/availability"),
    ("DELETE", "/api/v1/vendor/rooms-services/rooms/{room_id}"),
    ("GET", "/api/v1/vendor/rooms-services/services"),
    ("POST", "/api/v1/vendor/rooms-services/services"),
    ("GET", "/api/v1/vendor/rooms-services/services/{service_id}"),
    ("PATCH", "/api/v1/vendor/rooms-services/services/{service_id}"),
    ("PATCH", "/api/v1/vendor/rooms-services/services/{service_id}/status"),
    ("DELETE", "/api/v1/vendor/rooms-services/services/{service_id}"),
    ("GET", "/api/v1/vendor/events"),
    ("POST", "/api/v1/vendor/events"),
    ("GET", "/api/v1/vendor/events/{event_id}"),
    ("PATCH", "/api/v1/vendor/events/{event_id}"),
    ("PATCH", "/api/v1/vendor/events/{event_id}/status"),
    ("DELETE", "/api/v1/vendor/events/{event_id}"),
    ("GET", "/api/v1/vendor/happy-hours"),
    ("POST", "/api/v1/vendor/happy-hours"),
    ("GET", "/api/v1/vendor/happy-hours/{happy_hour_id}"),
    ("PATCH", "/api/v1/vendor/happy-hours/{happy_hour_id}"),
    ("PATCH", "/api/v1/vendor/happy-hours/{happy_hour_id}/status"),
    ("DELETE", "/api/v1/vendor/happy-hours/{happy_hour_id}"),
    ("GET", "/api/v1/vendor/promotions"),
    ("POST", "/api/v1/vendor/promotions"),
    ("GET", "/api/v1/vendor/promotions/{promotion_id}"),
    ("PATCH", "/api/v1/vendor/promotions/{promotion_id}"),
    ("PATCH", "/api/v1/vendor/promotions/{promotion_id}/status"),
    ("DELETE", "/api/v1/vendor/promotions/{promotion_id}"),
    ("PATCH", "/api/v1/vendor/promotions/platform-campaigns/{campaign_id}/join"),
    ("GET", "/api/v1/vendor/analytics/overview"),
    ("GET", "/api/v1/vendor/analytics/demographics"),
    ("GET", "/api/v1/vendor/analytics/occupancy"),
    ("GET", "/api/v1/vendor/analytics/reviews-summary"),
    ("GET", "/api/v1/vendor/analytics/export"),
    ("GET", "/api/v1/vendor/loyalty/settings"),
    ("PATCH", "/api/v1/vendor/loyalty/settings"),
    ("GET", "/api/v1/vendor/reviews"),
    ("POST", "/api/v1/vendor/reviews/{review_id}/reply"),
    ("GET", "/api/v1/vendor/settings"),
    ("GET", "/api/v1/vendor/settings/general"),
    ("PATCH", "/api/v1/vendor/settings/general"),
    ("GET", "/api/v1/vendor/settings/commission"),
    ("GET", "/api/v1/vendor/settings/legal/{doc_type}"),
    ("PATCH", "/api/v1/vendor/settings/legal/{doc_type}"),
    ("GET", "/api/v1/vendor/settings/profile"),
    ("PATCH", "/api/v1/vendor/settings/profile"),
    ("POST", "/api/v1/vendor/settings/services/{service_type}/amenities"),
    ("POST", "/api/v1/vendor/settings/profile/avatar"),
    ("PATCH", "/api/v1/vendor/settings/password"),
    ("GET", "/api/v1/vendor/support/tickets"),
    ("POST", "/api/v1/vendor/support/tickets"),
    ("GET", "/api/v1/vendor/support/tickets/{ticket_id}"),
    ("POST", "/api/v1/vendor/support/tickets/{ticket_id}/messages"),
    ("GET", "/api/v1/vendor/users"),
    ("GET", "/api/v1/vendor/users/{user_id}"),
    ("GET", "/api/v1/vendor/notifications"),
    ("POST", "/api/v1/vendor/notifications/{notification_id}/action"),
    ("DELETE", "/api/v1/vendor/notifications/clear"),
    ("GET", "/api/v1/vendor/notifications/settings"),
    ("PATCH", "/api/v1/vendor/notifications/settings"),
}


def test_every_frontend_vendor_endpoint_exists(app):
    actual = {
        (method, route.path)
        for route in app.routes
        for method in (getattr(route, "methods", None) or set())
    }
    missing = FRONTEND_VENDOR_ENDPOINTS - actual
    assert not missing, f"Frontend vendor endpoints missing from FastAPI: {sorted(missing)}"


def test_platform_admin_routes_require_admin_authentication(app):
    protected_prefixes = (
        "/api/v1/platform-admin/dashboard",
        "/api/v1/platform-admin/users",
        "/api/v1/platform-admin/vendors",
        "/api/v1/platform-admin/offers",
        "/api/v1/platform-admin/billing",
        "/api/v1/platform-admin/support",
        "/api/v1/platform-admin/settings",
        "/api/v1/platform-admin/moderation",
    )
    protected_routes = [
        route
        for route in app.routes
        if any(route.path.startswith(prefix) for prefix in protected_prefixes)
        and getattr(route, "methods", None)
    ]
    assert protected_routes
    for route in protected_routes:
        dependency_calls = {dependency.call for dependency in route.dependant.dependencies}
        assert get_current_platform_admin in dependency_calls, route.path


def test_promotion_patch_accepts_frontend_partial_payload():
    payload = PromotionUpdateRequest(
        promotion_name="Summer offer",
        internal_description="Updated copy",
        discount_value=20,
        start_date="2026-07-01",
        end_date="2026-08-01",
        active=True,
    )
    assert payload.model_dump(exclude_unset=True)["discount_value"] == 20


def test_event_schema_supports_multi_day_and_legacy_single_day_events():
    shared = {
        "title": "Weekend Festival",
        "category": "Event",
        "event_type": "Festival",
        "event_date": "2026-08-01",
        "start_time": "18:00",
        "end_time": "10:00",
        "venue": "Festival Ground",
        "capacity": 500,
        "ticket_price": 25,
    }
    multi_day = VendorEventUpsertRequest(
        **shared,
        end_date="2026-08-03",
    )
    assert multi_day.end_date == "2026-08-03"

    single_day = VendorEventUpsertRequest(
        **{**shared, "end_time": "22:00"},
    )
    assert single_day.end_date == single_day.event_date

    with pytest.raises(ValueError):
        VendorEventUpsertRequest(
            **shared,
            end_date="2026-07-31",
        )


def test_event_registration_deadline_is_normalized_to_date_only():
    shared = {
        "title": "Registration Event",
        "category": "Event",
        "event_type": "Workshop",
        "event_date": "2026-08-10",
        "start_time": "10:00",
        "end_time": "12:00",
        "venue": "Workshop Hall",
        "capacity": 50,
        "ticket_price": 10,
    }
    date_only = VendorEventUpsertRequest(
        **shared,
        registration_deadline="2026-08-09",
    )
    legacy_datetime = VendorEventUpsertRequest(
        **shared,
        registration_deadline="2026-08-09T18:30:00+06:00",
    )
    assert date_only.registration_deadline == "2026-08-09"
    assert legacy_datetime.registration_deadline == "2026-08-09"


def test_asset_registration_rejects_unsafe_url_schemes():
    with pytest.raises(ValueError):
        AssetUploadRequest(asset_url="javascript:alert(1)", asset_type="gallery")

    payload = AssetUploadRequest(
        asset_url="https://res.cloudinary.com/example/image/upload/file.jpg",
        asset_type="gallery",
        service_type="spa",
    )
    assert payload.asset_url.startswith("https://")
    assert payload.service_type == "spa"


def test_room_and_service_schemas_preserve_ui_specific_fields():
    room = RoomUpsertRequest(
        name="Deluxe Room",
        size_sqm=35,
        max_guests=2,
        bed_type="King",
        number_of_beds=1,
        base_price=200,
        weekend_price=250,
        default_discount_percent=10,
        tax_included=False,
        min_stay_nights=2,
        max_stay_nights=10,
    )
    service = ServiceUpsertRequest(
        name="Breakfast delivery",
        service_type="hotel",
        category="Food",
        price=25,
    )

    assert room.model_dump()["tax_included"] is False
    assert service.model_dump()["service_type"] == "hotel"


def test_mobile_service_alias_endpoints_exist(app):
    actual = {
        (method, route.path)
        for route in app.routes
        for method in (getattr(route, "methods", None) or set())
    }
    expected = {
        ("GET", "/api/v1/restaurants"),
        ("GET", "/api/v1/restaurants/{restaurant_id}"),
        ("GET", "/api/v1/restaurants/{restaurant_id}/menu"),
        ("GET", "/api/v1/hotels"),
        ("GET", "/api/v1/hotels/{hotel_id}"),
        ("GET", "/api/v1/hotels/{hotel_id}/rooms"),
        ("GET", "/api/v1/spas"),
        ("GET", "/api/v1/spas/{spa_id}"),
        ("GET", "/api/v1/spas/{spa_id}/services"),
    }
    assert expected <= actual
