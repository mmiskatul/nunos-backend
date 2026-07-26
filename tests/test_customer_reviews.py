from datetime import UTC, datetime

import mongomock
from bson import ObjectId

from app.modules.customer.repositories_customer import CustomerRepository
from app.modules.vendor.repositories_portal import VendorPortalRepository


def test_booking_review_is_visible_to_customer_public_feed_and_vendor():
    database = mongomock.MongoClient().nuno
    customer_id = ObjectId()
    vendor_id = ObjectId()
    booking_id = ObjectId()
    database.users.insert_one(
        {
            "_id": customer_id,
            "full_name": "Review Customer",
            "profile_image_url": "https://example.com/customer.jpg",
        }
    )
    database.vendors.insert_one(
        {
            "_id": vendor_id,
            "status": "approved",
            "business_name": "Review Restaurant",
        }
    )
    database.vendor_bookings.insert_one(
        {
            "_id": booking_id,
            "booking_code": "#REVIEW-1",
            "vendor_id": vendor_id,
            "customer_id": customer_id,
            "provider_type": "restaurant",
            "service": "Table Booking",
            "status": "complete",
            "created_at": datetime.now(UTC),
        }
    )
    customer_repository = CustomerRepository(database)
    vendor_repository = VendorPortalRepository(database)

    created = customer_repository.create_booking_review(
        str(customer_id),
        str(booking_id),
        5,
        "Excellent service.",
    )

    assert created["rating"] == 5
    customer_reviews = customer_repository.list_customer_reviews(str(customer_id), limit=20, skip=0)
    assert customer_reviews["total"] == 1
    assert customer_reviews["items"][0]["provider_name"] == "Review Restaurant"
    assert customer_reviews["items"][0]["booking_code"] == "#REVIEW-1"

    public_reviews = customer_repository.get_provider_reviews_payload(str(vendor_id))
    assert public_reviews["total_reviews"] == 1
    assert public_reviews["items"][0]["comment"] == "Excellent service."
    assert public_reviews["items"][0]["avatar"] == "https://example.com/customer.jpg"

    vendor_reviews = vendor_repository.list_reviews(str(vendor_id), limit=20, skip=0)
    assert vendor_reviews["total"] == 1
    assert vendor_reviews["items"][0]["star_rating"] == 5
    assert vendor_reviews["items"][0]["avatar_url"] == "https://example.com/customer.jpg"

    vendor_repository.reply_review(
        str(vendor_id),
        vendor_reviews["items"][0]["id"],
        "Thank you for your feedback.",
    )
    refreshed_customer_reviews = customer_repository.list_customer_reviews(
        str(customer_id),
        limit=20,
        skip=0,
    )
    refreshed_public_reviews = customer_repository.get_provider_reviews_payload(str(vendor_id))
    assert refreshed_customer_reviews["items"][0]["vendor_reply"] == "Thank you for your feedback."
    assert refreshed_public_reviews["items"][0]["vendor_reply"] == "Thank you for your feedback."


def test_vendor_review_contract_supports_legacy_review_fields():
    database = mongomock.MongoClient().nuno
    vendor_id = ObjectId()
    database.vendor_reviews.insert_one(
        {
            "vendor_id": vendor_id,
            "customer_name": "Legacy Customer",
            "avatar_url": "https://example.com/legacy.jpg",
            "star_rating": 4,
            "comment": "Legacy review.",
            "created_at": datetime.now(UTC),
        }
    )
    repository = VendorPortalRepository(database)

    result = repository.list_reviews(
        str(vendor_id),
        limit=20,
        skip=0,
        star_rating=4,
    )
    summary = repository.get_reviews_summary(str(vendor_id))

    assert result["total"] == 1
    assert result["items"][0]["rating"] == 4
    assert result["items"][0]["review_text"] == "Legacy review."
    assert summary["average_rating"] == 4.0


def test_hotel_and_restaurant_review_totals_are_calculated_separately():
    database = mongomock.MongoClient().nuno
    vendor_id = ObjectId()
    now = datetime.now(UTC)
    database.vendor_reviews.insert_many(
        [
            {
                "vendor_id": vendor_id,
                "provider_type": "restaurant",
                "rating": 5,
                "review_text": "Excellent restaurant.",
                "created_at": now,
            },
            {
                "vendor_id": vendor_id,
                "provider_type": "hotel",
                "rating": 2,
                "review_text": "Hotel needs improvement.",
                "created_at": now,
            },
            {
                "vendor_id": vendor_id,
                "provider_type": "hotel_room",
                "rating": 4,
                "review_text": "Comfortable room.",
                "created_at": now,
            },
        ]
    )
    customer_repository = CustomerRepository(database)
    vendor_repository = VendorPortalRepository(database)

    restaurant_reviews = customer_repository.get_provider_reviews_payload(str(vendor_id), "restaurant")
    hotel_reviews = customer_repository.get_hotel_reviews_payload(str(vendor_id))
    restaurant_bundle = customer_repository._get_vendor_bundle(vendor_id, "restaurant")
    hotel_bundle = customer_repository._get_vendor_bundle(vendor_id, "hotel")

    assert restaurant_reviews["total_reviews"] == 1
    assert restaurant_reviews["average_rating"] == 5.0
    assert hotel_reviews["total_reviews"] == 2
    assert hotel_reviews["average_rating"] == 3.0
    assert restaurant_bundle["reviews_count"] == 1
    assert restaurant_bundle["rating"] == 5.0
    assert hotel_bundle["reviews_count"] == 2
    assert hotel_bundle["rating"] == 3.0

    vendor_restaurant_summary = vendor_repository.get_reviews_summary(
        str(vendor_id),
        provider_type="restaurant",
    )
    vendor_hotel_summary = vendor_repository.get_reviews_summary(
        str(vendor_id),
        provider_type="hotel",
    )
    assert vendor_restaurant_summary["total_reviews"] == 1
    assert vendor_restaurant_summary["average_rating"] == 5.0
    assert vendor_hotel_summary["total_reviews"] == 2
    assert vendor_hotel_summary["average_rating"] == 3.0
