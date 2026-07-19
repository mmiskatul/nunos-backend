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

    assert [item["title"] for item in result] == ["Future event"]
    assert result[0]["latitude"] == 25.29
    assert result[0]["longitude"] == 51.54
    assert result[0]["event_date"] == (today + timedelta(days=2)).isoformat()
    assert result[0]["end_time"] == "22:00:00"
