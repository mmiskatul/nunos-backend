from datetime import UTC, datetime, timedelta

import mongomock
from bson import ObjectId

from app.modules.customer.repositories_customer import CustomerRepository
from app.modules.vendor.repositories_portal import VendorPortalRepository


def _happy_hour_payload(today) -> dict:
    return {
        "title": "Sunset drinks",
        "venue_type": "restaurant",
        "offer_text": "Buy one, get one free",
        "start_date": (today - timedelta(days=1)).isoformat(),
        "end_date": (today + timedelta(days=30)).isoformat(),
        "days_of_week": [
            "monday",
            "tuesday",
            "wednesday",
            "thursday",
            "friday",
            "saturday",
            "sunday",
        ],
        "start_time": "17:00",
        "end_time": "22:00",
        "timezone": "UTC",
        "venue": "Rooftop Bar",
        "latitude": 23.78,
        "longitude": 90.4,
        "original_price": 20,
        "happy_hour_price": 10,
        "discount_percent": 50,
        "description": "A recurring offer.",
        "terms_and_conditions": "Dine-in only.",
        "banner_image_url": None,
        "active_status": True,
        "status": "published",
    }


def test_happy_hour_writes_to_separate_collection_and_customer_feed():
    database = mongomock.MongoClient().nuno
    vendor_id = ObjectId()
    customer_id = ObjectId()
    today = datetime.now(UTC).date()
    database.vendors.insert_one(
        {
            "_id": vendor_id,
            "status": "approved",
            "business_name": "Rooftop Vendor",
            "categories": ["Restaurant", "Happy Hour"],
        }
    )
    database.users.insert_one(
        {
            "_id": customer_id,
            "latitude": 23.79,
            "longitude": 90.41,
        }
    )

    vendor_repository = VendorPortalRepository(database)
    created = vendor_repository.create_happy_hour(
        str(vendor_id),
        _happy_hour_payload(today),
    )

    assert database.vendor_happy_hours.count_documents({}) == 1
    assert database.vendor_events.count_documents({}) == 0
    assert created["offer_text"] == "Buy one, get one free"

    customer_repository = CustomerRepository(database)
    assert customer_repository.map_events(str(customer_id), limit=50) == []
    happy_hours = customer_repository.map_happy_hours(
        str(customer_id),
        limit=50,
    )
    assert len(happy_hours) == 1
    assert happy_hours[0]["id"] == created["id"]
    assert happy_hours[0]["entity_type"] == "happy_hour"
    assert happy_hours[0]["can_book_on_map"] is False


def test_legacy_happy_hour_event_is_migrated_and_hidden_from_events():
    database = mongomock.MongoClient().nuno
    vendor_id = ObjectId()
    event_id = ObjectId()
    today = datetime.now(UTC).date()
    database.vendors.insert_one(
        {
            "_id": vendor_id,
            "status": "approved",
            "business_name": "Legacy Vendor",
            "categories": ["Restaurant"],
        }
    )
    database.vendor_events.insert_one(
        {
            "_id": event_id,
            "vendor_id": vendor_id,
            "title": "Friday Happy Hour",
            "category": "Restaurant",
            "event_type": "Happy Hour",
            "event_date": (today + timedelta(days=1)).isoformat(),
            "start_time": "17:00",
            "end_time": "20:00",
            "timezone": "UTC",
            "venue": "Legacy Bar",
            "latitude": 23.78,
            "longitude": 90.4,
            "ticket_price": 12,
            "status": "published",
            "active": True,
            "created_at": datetime.now(UTC),
        }
    )

    repository = VendorPortalRepository(database)
    assert repository.list_events(str(vendor_id)) == []

    migrated = repository.list_happy_hours(str(vendor_id))
    assert len(migrated) == 1
    assert migrated[0]["id"] == str(event_id)
    assert migrated[0]["legacy_event_id"] == str(event_id)
    assert database.vendor_happy_hours.count_documents({"_id": event_id}) == 1
    assert "Happy Hour" in repository._allowed_vendor_categories(str(vendor_id))


def test_event_title_alone_does_not_reclassify_it_as_a_happy_hour():
    database = mongomock.MongoClient().nuno
    vendor_id = ObjectId()
    customer_id = ObjectId()
    event_id = ObjectId()
    today = datetime.now(UTC).date()
    database.vendors.insert_one(
        {
            "_id": vendor_id,
            "status": "approved",
            "business_name": "Festival Vendor",
            "categories": ["Event"],
        }
    )
    database.users.insert_one(
        {
            "_id": customer_id,
            "latitude": 23.79,
            "longitude": 90.41,
        }
    )
    database.vendor_events.insert_one(
        {
            "_id": event_id,
            "vendor_id": vendor_id,
            "title": "Happy Hour Music Festival",
            "category": "Event",
            "event_type": "Music Festival",
            "event_date": (today + timedelta(days=1)).isoformat(),
            "start_time": "17:00",
            "end_time": "20:00",
            "timezone": "UTC",
            "venue": "Festival Ground",
            "latitude": 23.78,
            "longitude": 90.4,
            "ticket_price": 12,
            "capacity": 100,
            "status": "published",
            "active": True,
            "created_at": datetime.now(UTC),
        }
    )
    database.vendor_happy_hours.insert_one(
        {
            "_id": event_id,
            "vendor_id": vendor_id,
            "title": "Happy Hour Music Festival",
            "offer_text": "Music Festival",
            "start_date": (today + timedelta(days=1)).isoformat(),
            "end_date": (today + timedelta(days=1)).isoformat(),
            "days_of_week": [],
            "start_time": "17:00",
            "end_time": "20:00",
            "timezone": "UTC",
            "venue": "Festival Ground",
            "latitude": 23.78,
            "longitude": 90.4,
            "status": "published",
            "active": True,
            "legacy_event_id": str(event_id),
            "created_at": datetime.now(UTC),
        }
    )

    customer_repository = CustomerRepository(database)
    events = customer_repository.list_events(
        str(customer_id),
        limit=50,
        skip=0,
    )
    assert [row["id"] for row in events["items"]] == [str(event_id)]
    assert customer_repository.list_happy_hours(
        str(customer_id),
        limit=50,
        skip=0,
    )["items"] == []
    assert database.vendor_happy_hours.count_documents({"_id": event_id}) == 1

    vendor_repository = VendorPortalRepository(database)
    assert [row["id"] for row in vendor_repository.list_events(str(vendor_id))] == [
        str(event_id)
    ]
    assert vendor_repository.list_happy_hours(str(vendor_id)) == []
    assert database.vendor_happy_hours.count_documents({"_id": event_id}) == 0
