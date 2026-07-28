from datetime import UTC, datetime, timedelta

import mongomock
from bson import ObjectId

from app.modules.customer.repositories_customer import CustomerRepository
from app.modules.vendor.repositories_portal import VendorPortalRepository


def test_active_promotion_changes_booking_quote_and_estimated_points():
    database = mongomock.MongoClient().nuno
    vendor_id = ObjectId()
    customer_id = ObjectId()
    today = datetime.now(UTC).date()
    database.vendors.insert_one(
        {"_id": vendor_id, "status": "approved", "business_name": "Offer Restaurant"}
    )
    database.users.insert_one({"_id": customer_id, "full_name": "Offer Customer"})
    database.vendor_rooms.insert_one(
        {"vendor_id": vendor_id, "available": True, "base_price": 100}
    )
    database.vendor_promotions.insert_one(
        {
            "vendor_id": vendor_id,
            "promotion_name": "Twenty off",
            "offer_type": "percentage",
            "discount_value": 20,
            "applicable_to": "Restaurant",
            "start_date": (today - timedelta(days=1)).isoformat(),
            "end_date": (today + timedelta(days=1)).isoformat(),
            "active": True,
        }
    )
    database.vendor_loyalty_settings.insert_one(
        {
            "vendor_id": vendor_id,
            "enable_loyalty_program": True,
            "points_rule_type": "points_per_currency",
            "points_earned": 1,
            "currency_unit": 1,
        }
    )

    quote = CustomerRepository(database).get_booking_quote(
        str(vendor_id),
        "restaurant",
        guests=2,
        date=today.isoformat(),
        time="18:00",
        seating_preference=None,
        customer_id=str(customer_id),
    )

    assert quote["original_subtotal"] == 200
    assert quote["discount_amount"] == 40
    assert quote["subtotal"] == 160
    assert quote["total"] == 180.8
    assert quote["promotion_name"] == "Twenty off"
    assert quote["estimated_points"] == 180


def test_loyalty_awards_and_promotion_usage_are_idempotent():
    database = mongomock.MongoClient().nuno
    vendor_id = ObjectId()
    customer_id = ObjectId()
    promotion_id = database.vendor_promotions.insert_one(
        {
            "vendor_id": vendor_id,
            "promotion_name": "Tracked promotion",
            "active": True,
            "usage_count": 0,
            "total_promo_revenue": 0,
        }
    ).inserted_id
    database.users.insert_one(
        {"_id": customer_id, "full_name": "Loyal Customer", "points_balance": 0}
    )
    database.vendor_loyalty_settings.insert_one(
        {
            "vendor_id": vendor_id,
            "enable_loyalty_program": True,
            "points_rule_type": "points_per_currency",
            "points_earned": 2,
            "currency_unit": 1,
            "first_booking_bonus": 10,
            "review_bonus_points": 25,
            "points_expiry_policy": "1 Year",
        }
    )
    booking_id = database.vendor_bookings.insert_one(
        {
            "vendor_id": vendor_id,
            "customer_id": customer_id,
            "customer_name": "Loyal Customer",
            "booking_code": "#LOYAL-1",
            "status": "confirmed",
            "total_amount": 100,
            "promotion_id": promotion_id,
            "created_at": datetime.now(UTC),
        }
    ).inserted_id
    repository = VendorPortalRepository(database)

    completed = repository.update_booking_status(
        str(vendor_id), str(booking_id), "complete"
    )
    repository.update_booking_status(str(vendor_id), str(booking_id), "pending")
    completed_again = repository.update_booking_status(
        str(vendor_id), str(booking_id), "complete"
    )

    assert completed["points_awarded"] == 210
    assert completed_again["points_awarded"] == 210
    assert database.users.find_one({"_id": customer_id})["points_balance"] == 210
    promotion = database.vendor_promotions.find_one({"_id": promotion_id})
    assert promotion["usage_count"] == 1
    assert promotion["total_promo_revenue"] == 100
    analytics = repository.get_loyalty_settings(str(vendor_id))
    assert analytics["total_points_issued"] == 210
    assert analytics["active_members"] == 1
    assert analytics["recent_activity"][0]["reference"] == "#LOYAL-1"


def test_verified_review_awards_configured_bonus():
    database = mongomock.MongoClient().nuno
    vendor_id = ObjectId()
    customer_id = ObjectId()
    booking_id = ObjectId()
    database.vendors.insert_one(
        {"_id": vendor_id, "status": "approved", "business_name": "Review Vendor"}
    )
    database.users.insert_one(
        {"_id": customer_id, "full_name": "Review Customer", "points_balance": 10}
    )
    database.vendor_bookings.insert_one(
        {
            "_id": booking_id,
            "vendor_id": vendor_id,
            "customer_id": customer_id,
            "customer_name": "Review Customer",
            "booking_code": "#REVIEW-BONUS",
            "provider_type": "restaurant",
            "status": "complete",
            "points_awarded": 10,
            "created_at": datetime.now(UTC),
        }
    )
    database.vendor_loyalty_settings.insert_one(
        {
            "vendor_id": vendor_id,
            "enable_loyalty_program": True,
            "review_bonus_points": 25,
            "points_expiry_policy": "No Expiry",
        }
    )

    review = CustomerRepository(database).create_booking_review(
        str(customer_id), str(booking_id), 5, "Excellent."
    )

    assert review["points_awarded"] == 25
    assert database.users.find_one({"_id": customer_id})["points_balance"] == 35
    analytics = VendorPortalRepository(database).get_loyalty_settings(str(vendor_id))
    assert analytics["total_points_issued"] == 35
    assert any(activity["type"] == "review" for activity in analytics["recent_activity"])
