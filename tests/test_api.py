from datetime import UTC, datetime, timedelta

import pytest

from app.core.session_tokens import session_is_active
from app.core.security import hash_password


def test_session_is_active_accepts_naive_mongo_datetime():
    expires_at = datetime.now() + timedelta(minutes=5)

    assert session_is_active(
        {
            "audience": "customer",
            "role": "customer",
            "revoked_at": None,
            "expires_at": expires_at,
        },
        audience="customer",
    )


@pytest.mark.asyncio
async def test_register_verify_and_login(client, test_db):
    register_res = await client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Test User",
            "email": "test@example.com",
            "phone": "+15550001111",
            "password": "StrongPass123!",
            "location_enabled": True,
            "latitude": 23.8103,
            "longitude": 90.4125,
            "location_accuracy_meters": 18.25,
        },
    )
    assert register_res.status_code == 200
    assert register_res.json()["data"]["message"] == "Verification code sent to email."

    pending_signup = await test_db.pending_signups.find_one({"email": "test@example.com"})
    assert pending_signup
    assert pending_signup["location_enabled"] is True
    assert pending_signup["latitude"] == pytest.approx(23.8103)
    assert pending_signup["longitude"] == pytest.approx(90.4125)
    assert pending_signup["location_accuracy_meters"] == pytest.approx(18.25)

    signup_code = await test_db.otp_codes.find_one({"email": "test@example.com", "purpose": "signup_verification"})
    assert signup_code

    verify_res = await client.post(
        "/api/v1/auth/verify-email",
        json={"email": "test@example.com", "otp": signup_code["code"]},
    )
    assert verify_res.status_code == 200
    assert verify_res.json()["data"]["access_token"]
    assert verify_res.json()["data"]["refresh_token"]

    created_user = await test_db.users.find_one({"email": "test@example.com"})
    assert created_user
    assert created_user["role"] == "customer"
    assert created_user["status"] == "active"
    assert created_user["location_enabled"] is True
    assert created_user["latitude"] == pytest.approx(23.8103)
    assert created_user["longitude"] == pytest.approx(90.4125)
    assert created_user["location_accuracy_meters"] == pytest.approx(18.25)

    login_res = await client.post(
        "/api/v1/auth/login",
        json={"email_or_phone": "test@example.com", "password": "StrongPass123!"},
    )
    assert login_res.status_code == 200
    assert login_res.json()["data"]["refresh_token"]

    refresh_res = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": login_res.json()["data"]["refresh_token"]},
    )
    assert refresh_res.status_code == 200
    assert refresh_res.json()["data"]["access_token"]


@pytest.mark.asyncio
async def test_personal_details_get_and_update(client, test_db):
    register_res = await client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Profile User",
            "email": "profile@example.com",
            "phone": "+15550002222",
            "password": "StrongPass123!",
        },
    )
    assert register_res.status_code == 200

    signup_code = await test_db.otp_codes.find_one({"email": "profile@example.com", "purpose": "signup_verification"})
    verify_res = await client.post(
        "/api/v1/auth/verify-email",
        json={"email": "profile@example.com", "otp": signup_code["code"]},
    )
    token = verify_res.json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    get_res = await client.get("/api/v1/users/me", headers=headers)
    assert get_res.status_code == 200
    assert get_res.json()["data"]["email"] == "profile@example.com"
    assert "password_hash" not in get_res.json()["data"]

    patch_res = await client.patch(
        "/api/v1/users/me/personal-details",
        headers=headers,
        json={
            "full_name": "Updated Profile User",
            "email": "profile@example.com",
            "phone": "+15550003333",
            "date_of_birth": "1992-03-15",
        },
    )
    assert patch_res.status_code == 200
    assert patch_res.json()["data"]["full_name"] == "Updated Profile User"
    assert patch_res.json()["data"]["phone"] == "+15550003333"
    assert patch_res.json()["data"]["date_of_birth"] == "1992-03-15"


@pytest.mark.asyncio
async def test_vendor_signup_rejects_existing_user_email(client, test_db):
    register_res = await client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Existing User",
            "email": "shared@example.com",
            "phone": "+15550004444",
            "password": "StrongPass123!",
        },
    )
    assert register_res.status_code == 200

    signup_code = await test_db.otp_codes.find_one({"email": "shared@example.com", "purpose": "signup_verification"})
    verify_res = await client.post(
        "/api/v1/auth/verify-email",
        json={"email": "shared@example.com", "otp": signup_code["code"]},
    )
    assert verify_res.status_code == 200

    vendor_code_res = await client.post(
        "/api/v1/vendor/auth/register/request-code",
        json={"email_or_phone": "shared@example.com"},
    )
    assert vendor_code_res.status_code == 409
    assert vendor_code_res.json()["detail"] == "This email is already in use by another account."


@pytest.mark.asyncio
async def test_vendor_signup_rejects_existing_user_phone(client, test_db):
    register_res = await client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Existing User",
            "email": "phone-shared@example.com",
            "phone": "+15550009999",
            "password": "StrongPass123!",
        },
    )
    assert register_res.status_code == 200

    signup_code = await test_db.otp_codes.find_one({"email": "phone-shared@example.com", "purpose": "signup_verification"})
    verify_res = await client.post(
        "/api/v1/auth/verify-email",
        json={"email": "phone-shared@example.com", "otp": signup_code["code"]},
    )
    assert verify_res.status_code == 200

    vendor_code_res = await client.post(
        "/api/v1/vendor/auth/register/request-code",
        json={"email_or_phone": "new-vendor@example.com"},
    )
    assert vendor_code_res.status_code == 200
    signup_token = (
        await client.post(
            "/api/v1/vendor/auth/register/verify-code",
            json={"email_or_phone": "new-vendor@example.com", "validation_code": vendor_code_res.json()["validation_code"]},
        )
    ).json()["signup_token"]

    register_vendor_res = await client.post(
        "/api/v1/vendor/auth/register",
        json={
            "business_name": "Phone Conflict Vendor",
            "owner_full_name": "Vendor Owner",
            "email_or_phone": "new-vendor@example.com",
            "phone": "+15550009999",
            "address": "123 Market Street",
            "city": "Dhaka",
            "website": "https://vendor.example.com",
            "business_description": "A demo service provider account for testing.",
            "trade_license_number": "TL-12345",
            "trade_license_document_url": "https://files.example.com/license.pdf",
            "owner_manager_id_document_url": "https://files.example.com/id.pdf",
            "terms_accepted": True,
            "password": "VendorPass123!",
            "confirm_password": "VendorPass123!",
            "signup_token": signup_token,
        },
    )
    assert register_vendor_res.status_code == 409
    assert register_vendor_res.json()["detail"] == "Phone already exists"


@pytest.mark.asyncio
async def test_personal_details_rejects_vendor_email(client, test_db):
    await test_db.vendors.insert_one(
        {
            "business_name": "Shared Vendor",
            "owner_full_name": "Vendor Owner",
            "email": "vendor-shared@example.com",
            "phone": "+15550005555",
            "password_hash": hash_password("StrongPass123!"),
            "role": "vendor",
            "status": "approved",
            "created_at": datetime.now(UTC),
            "updated_at": datetime.now(UTC),
        }
    )

    register_res = await client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Profile User",
            "email": "profile-shared@example.com",
            "phone": "+15550006666",
            "password": "StrongPass123!",
        },
    )
    assert register_res.status_code == 200

    signup_code = await test_db.otp_codes.find_one({"email": "profile-shared@example.com", "purpose": "signup_verification"})
    verify_res = await client.post(
        "/api/v1/auth/verify-email",
        json={"email": "profile-shared@example.com", "otp": signup_code["code"]},
    )
    token = verify_res.json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    patch_res = await client.patch(
        "/api/v1/users/me/personal-details",
        headers=headers,
        json={
            "full_name": "Updated Profile User",
            "email": "vendor-shared@example.com",
            "phone": "+15550006666",
            "date_of_birth": "1992-03-15",
        },
    )
    assert patch_res.status_code == 409
    assert patch_res.json()["detail"] == "This email is already in use by another account."


@pytest.mark.asyncio
async def test_personal_details_rejects_vendor_phone(client, test_db):
    await test_db.vendors.insert_one(
        {
            "business_name": "Shared Vendor",
            "owner_full_name": "Vendor Owner",
            "email": "vendor-phone@example.com",
            "phone": "+15550007777",
            "password_hash": hash_password("StrongPass123!"),
            "role": "vendor",
            "status": "approved",
            "created_at": datetime.now(UTC),
            "updated_at": datetime.now(UTC),
        }
    )

    register_res = await client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Profile User",
            "email": "profile-phone@example.com",
            "phone": "+15550008888",
            "password": "StrongPass123!",
        },
    )
    assert register_res.status_code == 200

    signup_code = await test_db.otp_codes.find_one({"email": "profile-phone@example.com", "purpose": "signup_verification"})
    verify_res = await client.post(
        "/api/v1/auth/verify-email",
        json={"email": "profile-phone@example.com", "otp": signup_code["code"]},
    )
    token = verify_res.json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    patch_res = await client.patch(
        "/api/v1/users/me/personal-details",
        headers=headers,
        json={
            "full_name": "Updated Profile User",
            "email": "profile-phone@example.com",
            "phone": "+15550007777",
            "date_of_birth": "1992-03-15",
        },
    )
    assert patch_res.status_code == 409
    assert patch_res.json()["detail"] == "Phone already exists"


@pytest.mark.asyncio
async def test_table_booking_flow(client, test_db):
    now = datetime.now(UTC)
    listing_id = (
        await test_db.listings.insert_one(
            {
                "name": "Demo Restaurant",
                "type": "restaurant",
                "description": "Near metro",
                "images": [],
                "location": {"type": "Point", "coordinates": [90.4125, 23.8103]},
                "price_level": 3,
                "near_metro_station": "Agargaon",
                "has_offers": True,
                "rating_summary": {"average": 4.3, "count": 10},
                "created_at": now,
                "updated_at": now,
            }
        )
    ).inserted_id

    register = await client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Booker",
            "email": "booker@example.com",
            "password": "StrongPass123!",
        },
    )
    assert register.status_code == 200
    signup_code = await test_db.otp_codes.find_one({"email": "booker@example.com", "purpose": "signup_verification"})
    auth = await client.post(
        "/api/v1/auth/verify-email",
        json={"email": "booker@example.com", "otp": signup_code["code"]},
    )
    token = auth.json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    target_date = (datetime.now(UTC) + timedelta(days=2)).date().isoformat()
    create_res = await client.post(
        "/api/v1/bookings",
        headers=headers,
        json={
            "listing_id": str(listing_id),
            "booking_type": "table",
            "status": "pending",
            "details": {
                "date": target_date,
                "time": "20:00:00",
                "guests": 2,
                "seating_preference": "indoor",
                "special_notes": "Anniversary",
            },
        },
    )
    assert create_res.status_code == 200
    booking_id = create_res.json()["data"]["_id"]

    get_res = await client.get(f"/api/v1/bookings/{booking_id}", headers=headers)
    assert get_res.status_code == 200
    assert get_res.json()["data"]["booking_type"] == "table"


@pytest.mark.asyncio
async def test_ai_plan_stub(client, test_db):
    now = datetime.now(UTC)
    await test_db.listings.insert_one(
        {
            "name": "Metro Spa",
            "type": "spa",
            "description": "Relaxation service",
            "images": [],
            "location": {"type": "Point", "coordinates": [90.4125, 23.8103]},
            "price_level": 2,
            "near_metro_station": "Agargaon",
            "has_offers": True,
            "rating_summary": {"average": 4.7, "count": 14},
            "created_at": now,
            "updated_at": now,
        }
    )

    res = await client.post(
        "/api/v1/ai/plan",
        json={
            "mood": "relaxed",
            "budget_range": "medium",
            "time_window": "afternoon",
            "location": {"metro_station": "Agargaon"},
            "preferences": ["spa"],
            "near_metro": True,
            "offers": True,
        },
    )
    assert res.status_code == 200
    assert "steps" in res.json()["data"]


@pytest.mark.asyncio
async def test_dashboard_login(client, test_db):
    await test_db.platform_admins.insert_one(
        {
            "full_name": "Admin User",
            "email": "admin@example.com",
            "password_hash": hash_password("StrongPass123!"),
            "role": "platform_admin",
            "status": "active",
        }
    )

    res = await client.post(
        "/api/v1/dashboard/auth/login",
        json={"email_or_phone": "admin@example.com", "password": "StrongPass123!"},
    )
    assert res.status_code == 200
    assert res.json()["data"]["access_token"]
    assert res.json()["data"]["admin"]["email"] == "admin@example.com"


@pytest.mark.asyncio
async def test_dashboard_forgot_password_flow(client, test_db):
    await test_db.platform_admins.insert_one(
        {
            "full_name": "Reset Admin",
            "email": "reset-admin@example.com",
            "password_hash": hash_password("OldStrongPass123!"),
            "role": "platform_admin",
            "status": "active",
        }
    )

    request_res = await client.post(
        "/api/v1/dashboard/auth/forgot-password/request",
        json={"email_or_phone": "reset-admin@example.com"},
    )
    assert request_res.status_code == 200

    otp_doc = await test_db.otp_codes.find_one(
        {"email": "reset-admin@example.com", "purpose": "dashboard_forgot_password"}
    )
    assert otp_doc

    verify_res = await client.post(
        "/api/v1/dashboard/auth/forgot-password/verify-code",
        json={"email_or_phone": "reset-admin@example.com", "code": otp_doc["code"]},
    )
    assert verify_res.status_code == 200
    reset_token = verify_res.json()["data"]["reset_token"]

    reset_res = await client.post(
        "/api/v1/dashboard/auth/forgot-password/reset",
        json={"reset_token": reset_token, "new_password": "NewStrongPass123!"},
    )
    assert reset_res.status_code == 200

    login_res = await client.post(
        "/api/v1/dashboard/auth/login",
        json={"email_or_phone": "reset-admin@example.com", "password": "NewStrongPass123!"},
    )
    assert login_res.status_code == 200


@pytest.mark.asyncio
async def test_vendor_register_and_login_flow(client, test_db):
    request_code_res = await client.post(
        "/api/v1/vendor/auth/register/request-code",
        json={"email_or_phone": "vendor@example.com"},
    )
    assert request_code_res.status_code == 200
    verification_code = request_code_res.json()["validation_code"]
    assert verification_code

    verify_code_res = await client.post(
        "/api/v1/vendor/auth/register/verify-code",
        json={"email_or_phone": "vendor@example.com", "validation_code": verification_code},
    )
    assert verify_code_res.status_code == 200
    signup_token = verify_code_res.json()["signup_token"]
    assert signup_token

    register_res = await client.post(
        "/api/v1/vendor/auth/register",
        json={
            "business_name": "Demo Vendor",
            "owner_full_name": "Vendor Owner",
            "email_or_phone": "vendor@example.com",
            "phone": "+15550110011",
            "address": "123 Market Street",
            "city": "Dhaka",
            "website": "https://vendor.example.com",
            "business_description": "A demo service provider account for testing.",
            "trade_license_number": "TL-12345",
            "trade_license_document_url": "https://files.example.com/license.pdf",
            "owner_manager_id_document_url": "https://files.example.com/id.pdf",
            "terms_accepted": True,
            "password": "VendorPass123!",
            "confirm_password": "VendorPass123!",
            "signup_token": signup_token,
        },
    )
    assert register_res.status_code == 201
    assert register_res.json()["vendor"]["email"] == "vendor@example.com"
    assert register_res.json()["vendor"]["status"] == "pending_approval"

    vendor = await test_db.vendors.find_one({"email": "vendor@example.com"})
    assert vendor
    await test_db.vendors.update_one({"_id": vendor["_id"]}, {"$set": {"status": "approved"}})

    login_res = await client.post(
        "/api/v1/vendor/auth/login",
        json={"email_or_phone": "vendor@example.com", "password": "VendorPass123!"},
    )
    assert login_res.status_code == 200
    assert login_res.json()["access_token"]
    assert login_res.json()["vendor"]["email"] == "vendor@example.com"


@pytest.mark.asyncio
async def test_admin_credentials_cannot_login_on_customer_or_vendor_routes(client, test_db):
    await test_db.platform_admins.insert_one(
        {
            "full_name": "Admin User",
            "email": "wrong-surface-admin@example.com",
            "password_hash": hash_password("StrongPass123!"),
            "role": "platform_admin",
            "status": "active",
            "created_at": datetime.now(UTC),
            "updated_at": datetime.now(UTC),
        }
    )

    customer_res = await client.post(
        "/api/v1/auth/login",
        json={"email_or_phone": "wrong-surface-admin@example.com", "password": "StrongPass123!"},
    )
    assert customer_res.status_code == 401

    vendor_res = await client.post(
        "/api/v1/vendor/auth/login",
        json={"email_or_phone": "wrong-surface-admin@example.com", "password": "StrongPass123!"},
    )
    assert vendor_res.status_code == 401


@pytest.mark.asyncio
async def test_vendor_credentials_cannot_login_on_customer_route(client, test_db):
    await test_db.vendors.insert_one(
        {
            "business_name": "Approved Vendor",
            "owner_full_name": "Vendor Owner",
            "email": "wrong-surface-vendor@example.com",
            "phone": "+15550001119",
            "password_hash": hash_password("VendorPass123!"),
            "role": "vendor",
            "status": "approved",
            "created_at": datetime.now(UTC),
            "updated_at": datetime.now(UTC),
        }
    )

    customer_res = await client.post(
        "/api/v1/auth/login",
        json={"email_or_phone": "wrong-surface-vendor@example.com", "password": "VendorPass123!"},
    )
    assert customer_res.status_code == 401


@pytest.mark.asyncio
async def test_customer_credentials_cannot_login_on_vendor_or_admin_routes(client, test_db):
    await test_db.users.insert_one(
        {
            "full_name": "Customer User",
            "email": "wrong-surface-customer@example.com",
            "phone": "+15550001120",
            "password_hash": hash_password("StrongPass123!"),
            "role": "customer",
            "status": "active",
            "is_active": True,
            "created_at": datetime.now(UTC),
            "updated_at": datetime.now(UTC),
        }
    )

    vendor_res = await client.post(
        "/api/v1/vendor/auth/login",
        json={"email_or_phone": "wrong-surface-customer@example.com", "password": "StrongPass123!"},
    )
    assert vendor_res.status_code == 401

    admin_res = await client.post(
        "/api/v1/platform-admin/auth/login",
        json={"email_or_phone": "wrong-surface-customer@example.com", "password": "StrongPass123!"},
    )
    assert admin_res.status_code == 401


@pytest.mark.asyncio
async def test_vendor_credentials_cannot_login_on_admin_route(client, test_db):
    await test_db.vendors.insert_one(
        {
            "business_name": "Approved Vendor",
            "owner_full_name": "Vendor Owner",
            "email": "wrong-surface-vendor-admin@example.com",
            "phone": "+15550001121",
            "password_hash": hash_password("VendorPass123!"),
            "role": "vendor",
            "status": "approved",
            "created_at": datetime.now(UTC),
            "updated_at": datetime.now(UTC),
        }
    )

    admin_res = await client.post(
        "/api/v1/platform-admin/auth/login",
        json={"email_or_phone": "wrong-surface-vendor-admin@example.com", "password": "VendorPass123!"},
    )
    assert admin_res.status_code == 401


@pytest.mark.asyncio
async def test_admin_credentials_cannot_login_on_platform_app_routes_except_admin(client, test_db):
    await test_db.platform_admins.insert_one(
        {
            "full_name": "Admin User",
            "email": "wrong-surface-admin-dashboard@example.com",
            "password_hash": hash_password("StrongPass123!"),
            "role": "platform_admin",
            "status": "active",
            "created_at": datetime.now(UTC),
            "updated_at": datetime.now(UTC),
        }
    )

    admin_res = await client.post(
        "/api/v1/platform-admin/auth/login",
        json={"email_or_phone": "wrong-surface-admin-dashboard@example.com", "password": "StrongPass123!"},
    )
    assert admin_res.status_code == 200
    assert admin_res.json()["admin"]["email"] == "wrong-surface-admin-dashboard@example.com"


@pytest.mark.asyncio
async def test_vendor_request_code_allows_repeat_before_registration(client):
    first_res = await client.post(
        "/api/v1/vendor/auth/register/request-code",
        json={"email_or_phone": "repeat-vendor@example.com"},
    )
    assert first_res.status_code == 200
    first_code = first_res.json()["validation_code"]
    assert first_code

    second_res = await client.post(
        "/api/v1/vendor/auth/register/request-code",
        json={"email_or_phone": "repeat-vendor@example.com"},
    )
    assert second_res.status_code == 200
    second_code = second_res.json()["validation_code"]
    assert second_code


@pytest.mark.asyncio
async def test_vendor_request_code_reports_pending_vendor_status(client, test_db):
    await test_db.vendors.insert_one(
        {
            "business_name": "Pending Vendor",
            "owner_full_name": "Pending Owner",
            "email": "pending-vendor@example.com",
            "password_hash": "hashed",
            "role": "vendor",
            "status": "pending_approval",
            "kyc_status": "pending_review",
        }
    )

    response = await client.post(
        "/api/v1/vendor/auth/register/request-code",
        json={"email_or_phone": "pending-vendor@example.com"},
    )
    assert response.status_code == 409
    assert response.json()["detail"] == "A service provider account for this email already exists and is pending admin approval."


@pytest.mark.asyncio
async def test_vendor_event_crud_respects_vendor_categories(client, test_db):
    request_code_res = await client.post(
        "/api/v1/vendor/auth/register/request-code",
        json={"email_or_phone": "events-vendor@example.com"},
    )
    assert request_code_res.status_code == 200

    verify_code_res = await client.post(
        "/api/v1/vendor/auth/register/verify-code",
        json={
            "email_or_phone": "events-vendor@example.com",
            "validation_code": request_code_res.json()["validation_code"],
        },
    )
    assert verify_code_res.status_code == 200
    signup_token = verify_code_res.json()["signup_token"]

    register_res = await client.post(
        "/api/v1/vendor/auth/register",
        json={
            "business_name": "Eventful Vendor",
            "owner_full_name": "Event Owner",
            "email_or_phone": "events-vendor@example.com",
            "phone": "+15550110021",
            "address": "123 Event Street",
            "city": "Dhaka",
            "website": "https://events.example.com",
            "business_description": "Vendor account for event management testing.",
            "trade_license_number": "TL-67890",
            "trade_license_document_url": "https://files.example.com/license.pdf",
            "owner_manager_id_document_url": "https://files.example.com/id.pdf",
            "terms_accepted": True,
            "password": "VendorPass123!",
            "confirm_password": "VendorPass123!",
            "signup_token": signup_token,
            "category": "Restaurant",
            "categories": ["Restaurant", "Event Venue"],
        },
    )
    assert register_res.status_code == 201

    vendor = await test_db.vendors.find_one({"email": "events-vendor@example.com"})
    assert vendor
    await test_db.vendors.update_one({"_id": vendor["_id"]}, {"$set": {"status": "approved"}})

    login_res = await client.post(
        "/api/v1/vendor/auth/login",
        json={"email_or_phone": "events-vendor@example.com", "password": "VendorPass123!"},
    )
    assert login_res.status_code == 200
    headers = {"Authorization": f"Bearer {login_res.json()['access_token']}"}

    create_res = await client.post(
        "/api/v1/vendor/events",
        headers=headers,
        json={
            "title": "Sunset Networking Dinner",
            "category": "Event Venue",
            "event_type": "Corporate Gala",
            "event_date": "2026-07-20",
            "start_time": "18:00",
            "end_time": "21:00",
            "timezone": "Asia/Dhaka",
            "venue": "Skyline Hall",
            "capacity": 180,
            "ticket_price": 49,
            "registration_deadline": "2026-07-19T23:59:00+06:00",
            "description": "An evening networking event for founders and operators.",
            "banner_image_url": "https://files.example.com/events/banner.jpg",
            "active_status": True,
            "status": "draft",
        },
    )
    assert create_res.status_code == 200
    created = create_res.json()
    assert created["category"] == "Event Venue"
    assert created["status"] == "draft"

    list_res = await client.get("/api/v1/vendor/events", headers=headers)
    assert list_res.status_code == 200
    assert len(list_res.json()["items"]) == 1

    update_res = await client.patch(
        f"/api/v1/vendor/events/{created['id']}",
        headers=headers,
        json={
            "title": "Sunset Networking Dinner Updated",
            "category": "Restaurant",
            "event_type": "Private Dinner",
            "event_date": "2026-07-21",
            "start_time": "19:00",
            "end_time": "22:00",
            "timezone": "Asia/Dhaka",
            "venue": "Chef's Table Hall",
            "capacity": 120,
            "ticket_price": 59,
            "registration_deadline": "2026-07-20T23:59:00+06:00",
            "description": "Updated dinner event.",
            "banner_image_url": "https://files.example.com/events/banner-2.jpg",
            "active_status": True,
            "status": "published",
        },
    )
    assert update_res.status_code == 200
    assert update_res.json()["title"] == "Sunset Networking Dinner Updated"
    assert update_res.json()["category"] == "Restaurant"

    bad_category_res = await client.post(
        "/api/v1/vendor/events",
        headers=headers,
        json={
            "title": "Spa Only Event",
            "category": "Spa",
            "event_type": "Wellness Pop-up",
            "event_date": "2026-08-01",
            "start_time": "10:00",
            "end_time": "12:00",
            "timezone": "Asia/Dhaka",
            "venue": "Wellness Wing",
            "capacity": 25,
            "ticket_price": 15,
            "registration_deadline": "2026-07-31T23:59:00+06:00",
            "description": "Should be blocked because Spa is not enabled.",
            "banner_image_url": None,
            "active_status": True,
            "status": "draft",
        },
    )
    assert bad_category_res.status_code == 422
    assert "not enabled for this vendor" in bad_category_res.json()["detail"]

    status_res = await client.patch(
        f"/api/v1/vendor/events/{created['id']}/status",
        headers=headers,
        json={"status": "archived"},
    )
    assert status_res.status_code == 200
    assert status_res.json()["status"] == "archived"

    delete_res = await client.delete(f"/api/v1/vendor/events/{created['id']}", headers=headers)
    assert delete_res.status_code == 200

    final_list_res = await client.get("/api/v1/vendor/events", headers=headers)
    assert final_list_res.status_code == 200
    assert final_list_res.json()["items"] == []


@pytest.mark.asyncio
async def test_vendor_registration_form_config_endpoint(client):
    response = await client.get("/api/v1/vendor/auth/registration-form-config")
    assert response.status_code == 200
    payload = response.json()
    assert any(item["id"] == "Cafe" for item in payload["categories"])
    assert "Corporate Gala" in payload["event_type_options"]
    assert "equipment_options" in payload
