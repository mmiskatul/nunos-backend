from datetime import UTC, datetime, timedelta

import mongomock
from bson import ObjectId

from app.modules.customer.repositories_customer import CustomerRepository


def test_map_events_only_returns_published_non_expired_events_with_coordinates():
    database = mongomock.MongoClient().nuno
    customer_id = ObjectId()
    vendor_id = ObjectId()
    repository = CustomerRepository(database)
    today = datetime.now(UTC).date()

    database.users.insert_one({"_id": customer_id, "latitude": 25.28, "longitude": 51.53})
    database.vendors.insert_one({"_id": vendor_id, "status": "approved", "business_name": "Live Events"})
    database.vendor_events.insert_many(
        [
            {
                "_id": ObjectId(),
                "vendor_id": vendor_id,
                "title": "Future event",
                "event_date": (today + timedelta(days=2)).isoformat(),
                "start_time": "18:00:00",
                "end_time": "22:00:00",
                "latitude": 25.29,
                "longitude": 51.54,
                "status": "published",
                "active": True,
            },
            {
                "_id": ObjectId(),
                "vendor_id": vendor_id,
                "title": "Ongoing multi-day event",
                "event_date": (today - timedelta(days=1)).isoformat(),
                "end_date": (today + timedelta(days=1)).isoformat(),
                "start_time": "18:00:00",
                "end_time": "10:00:00",
                "latitude": 25.29,
                "longitude": 51.54,
                "status": "published",
                "active": True,
            },
            {
                "_id": ObjectId(),
                "vendor_id": vendor_id,
                "title": "Expired event",
                "event_date": (today - timedelta(days=1)).isoformat(),
                "start_time": "18:00:00",
                "end_time": "22:00:00",
                "latitude": 25.29,
                "longitude": 51.54,
                "status": "published",
                "active": True,
            },
        ]
    )

    result = repository.map_events(str(customer_id), limit=50)

    assert [item["title"] for item in result] == [
        "Ongoing multi-day event",
        "Future event",
    ]
    assert result[0]["latitude"] == 25.29
    assert result[0]["longitude"] == 51.54
    assert result[0]["event_date"] == (today - timedelta(days=1)).isoformat()
    assert result[0]["end_date"] == (today + timedelta(days=1)).isoformat()
    assert result[0]["end_time"] == "10:00:00"


def test_event_list_keeps_published_events_without_coordinates():
    database = mongomock.MongoClient().nuno
    customer_id = ObjectId()
    vendor_id = ObjectId()
    today = datetime.now(UTC).date()

    database.vendors.insert_one({"_id": vendor_id, "status": "approved"})
    database.vendor_business_details.insert_one(
        {"vendor_id": vendor_id, "latitude": 23.78, "longitude": 90.40}
    )
    database.vendor_events.insert_one(
        {
            "_id": ObjectId(),
            "vendor_id": vendor_id,
            "title": "Venue-only event",
            "event_date": (today + timedelta(days=1)).isoformat(),
            "start_time": "18:00:00",
            "end_time": "22:00:00",
            "timezone": "UTC",
            "venue": "Community Hall",
            "status": "published",
            "active": True,
        }
    )

    result = CustomerRepository(database).list_events(str(customer_id), limit=50, skip=0)

    assert len(result["items"]) == 1
    assert result["items"][0]["title"] == "Venue-only event"
    assert result["items"][0]["latitude"] == 23.78
    assert result["items"][0]["longitude"] == 90.40


def test_registration_deadline_date_closes_after_the_selected_day():
    repository = CustomerRepository(mongomock.MongoClient().nuno)
    today = datetime.now(UTC).date()

    assert repository._event_registration_is_open(
        {"registration_deadline": today.isoformat(), "timezone": "UTC"}
    )
    assert not repository._event_registration_is_open(
        {
            "registration_deadline": (today - timedelta(days=1)).isoformat(),
            "timezone": "UTC",
        }
    )
