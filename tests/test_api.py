from datetime import UTC, datetime, timedelta

import pytest


@pytest.mark.asyncio
async def test_register_and_login(client):
    register_res = await client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Test User",
            "email": "test@example.com",
            "phone": "+15550001111",
            "password": "StrongPass123!",
        },
    )
    assert register_res.status_code == 200
    assert register_res.json()["data"]["access_token"]

    login_res = await client.post(
        "/api/v1/auth/login",
        json={"email_or_phone": "test@example.com", "password": "StrongPass123!"},
    )
    assert login_res.status_code == 200
    assert login_res.json()["data"]["refresh_token"]


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

    auth = await client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Booker",
            "email": "booker@example.com",
            "password": "StrongPass123!",
        },
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
