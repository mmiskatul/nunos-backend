from datetime import UTC, datetime, timedelta

import pytest

from app.core.security import hash_password


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
