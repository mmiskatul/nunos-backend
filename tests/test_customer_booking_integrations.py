from datetime import UTC, datetime

import mongomock
from bson import ObjectId

from app.modules.customer.repositories_customer import CustomerRepository
from app.modules.customer.schemas_live import CustomerBookingQuoteRequest


def _base_customer_and_vendor(database):
    customer_id = ObjectId()
    vendor_id = ObjectId()
    database.users.insert_one(
        {
            "_id": customer_id,
            "full_name": "Booking Customer",
            "email": "customer@example.com",
            "points_balance": 0,
        }
    )
    database.vendors.insert_one(
        {
            "_id": vendor_id,
            "status": "approved",
            "business_name": "Integrated Provider",
        }
    )
    database.vendor_portal_settings.insert_one(
        {
            "vendor_id": vendor_id,
            "general": {"booking_availability_slots": ["10:00 AM"]},
        }
    )
    return customer_id, vendor_id


def test_restaurant_booking_uses_live_quote_and_records_request_timeline():
    database = mongomock.MongoClient().nuno
    customer_id, vendor_id = _base_customer_and_vendor(database)
    repository = CustomerRepository(database)
    request = CustomerBookingQuoteRequest(
        provider_id=str(vendor_id),
        provider_type="restaurant",
        date="2026-07-29",
        time="10:00 AM",
        guests=2,
        seating_preference="Indoor",
    )

    quote = repository.get_booking_quote(
        str(vendor_id),
        "restaurant",
        2,
        "2026-07-29",
        "10:00 AM",
        request.seating_preference,
        str(customer_id),
    )
    booking = repository.create_booking(
        str(customer_id),
        str(vendor_id),
        "restaurant",
        "2026-07-29",
        "10:00 AM",
        2,
        "Indoor",
        None,
        False,
    )

    assert booking["total_amount"] == quote["total"]
    assert booking["status_history"][0]["status"] == "pending"
    assert booking["requested_at"]


def test_spa_quote_and_booking_use_live_service_and_create_vendor_booking():
    database = mongomock.MongoClient().nuno
    customer_id, vendor_id = _base_customer_and_vendor(database)
    service_id = database.vendor_services.insert_one(
        {
            "vendor_id": vendor_id,
            "service_type": "spa",
            "name": "Deep Tissue Massage",
            "price": 80,
            "available": True,
            "active_status": True,
        }
    ).inserted_id
    repository = CustomerRepository(database)

    quote = repository.get_spa_booking_quote(
        str(customer_id),
        str(vendor_id),
        "2026-07-29",
        "10:00 AM",
        1,
        str(service_id),
    )
    booking = repository.create_spa_booking(
        str(customer_id),
        str(vendor_id),
        "2026-07-29",
        "10:00 AM",
        1,
        str(service_id),
        "Quiet room please.",
    )

    assert quote["service_name"] == "Deep Tissue Massage"
    assert quote["total"] == 90.4
    assert booking["provider_type"] == "spa"
    assert booking["service"] == "Deep Tissue Massage"
    assert booking["status"] == "pending"
    assert booking["requested_at"]
    assert booking["status_history"][0]["label"] == "Booking request sent by customer"
    assert database.bookings.count_documents({"booking_id": ObjectId(booking["id"])}) == 1


def test_hotel_quote_enforces_inventory_and_booking_uses_same_total():
    database = mongomock.MongoClient().nuno
    customer_id, vendor_id = _base_customer_and_vendor(database)
    room_id = database.vendor_rooms.insert_one(
        {
            "vendor_id": vendor_id,
            "name": "City Room",
            "base_price": 100,
            "weekend_price": 120,
            "available": True,
            "inventory_count": 1,
            "max_guests": 2,
            "min_stay_nights": 1,
            "max_stay_nights": 5,
            "tax_included": True,
        }
    ).inserted_id
    repository = CustomerRepository(database)

    quote = repository.get_hotel_booking_quote(
        str(customer_id),
        str(vendor_id),
        "2026-07-29",
        "2026-07-31",
        2,
        str(room_id),
    )
    booking = repository.create_hotel_booking(
        str(customer_id),
        str(vendor_id),
        "2026-07-29",
        "2026-07-31",
        2,
        None,
        False,
        room_id=str(room_id),
    )

    assert quote["nights"] == 2
    assert quote["original_subtotal"] == 200
    assert booking["total_amount"] == quote["total"]
    assert booking["room_id"] == str(room_id)
    assert booking["status_history"][0]["actor"] == "customer"

    try:
        repository.get_hotel_booking_quote(
            str(customer_id),
            str(vendor_id),
            "2026-07-30",
            "2026-08-01",
            2,
            str(room_id),
        )
    except ValueError as exc:
        assert str(exc) == "This room is not available for the selected dates."
    else:
        raise AssertionError("Overlapping room inventory was booked twice")


def test_event_quote_and_booking_return_matching_dynamic_amounts():
    database = mongomock.MongoClient().nuno
    customer_id, vendor_id = _base_customer_and_vendor(database)
    event_id = database.vendor_events.insert_one(
        {
            "vendor_id": vendor_id,
            "title": "Live Event",
            "event_date": "2026-08-01",
            "start_time": "18:00",
            "ticket_price": 25,
            "capacity": 10,
            "status": "published",
            "active": True,
            "created_at": datetime.now(UTC),
        }
    ).inserted_id
    repository = CustomerRepository(database)

    quote = repository.get_event_booking_quote(
        str(customer_id), str(event_id), 2
    )
    booking = repository.create_event_ticket_booking(
        str(customer_id), str(event_id), 2, None, False
    )

    assert quote["available_seats"] == 10
    assert quote["total"] == 50
    assert booking["total_amount"] == 50
    assert booking["quantity"] == 2
    assert booking["status_history"][0]["status"] == "pending"
