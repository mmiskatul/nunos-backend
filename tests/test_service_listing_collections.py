from bson import ObjectId
import mongomock

from app.modules.customer.repositories_customer import CustomerRepository
from app.modules.vendor.repositories_portal import VendorPortalRepository


def test_published_service_types_use_independent_collections():
    database = mongomock.MongoClient().nuno
    vendor_id = ObjectId()
    database.vendors.insert_one({"_id": vendor_id, "status": "approved", "business_name": "Shared Venue"})

    portal = VendorPortalRepository(database)
    portal.sync_service_listing(str(vendor_id), "restaurant", {"name": "Garden Restaurant", "published": True})
    portal.sync_service_listing(str(vendor_id), "hotel", {"name": "Garden Hotel", "published": False})
    portal.sync_service_listing(str(vendor_id), "spa", {"name": "Garden Spa", "published": True})

    customer = CustomerRepository(database)
    assert [row["_id"] for row in customer._published_vendor_docs("restaurant")] == [vendor_id]
    assert customer._published_vendor_docs("hotel") == []
    assert [row["_id"] for row in customer._published_vendor_docs("spa")] == [vendor_id]


def test_spa_detail_checks_spa_publication_instead_of_restaurant_publication():
    database = mongomock.MongoClient().nuno
    vendor_id = ObjectId()
    database.vendors.insert_one({"_id": vendor_id, "status": "approved", "business_name": "Wellness Venue"})
    database.vendor_profiles.insert_one({"vendor_id": vendor_id, "category": "Spa"})
    database.vendor_portal_settings.insert_one(
        {
            "vendor_id": vendor_id,
            "profile": {"spa_settings": {"name": "Wellness Spa", "published": True}},
            "general": {},
        }
    )
    VendorPortalRepository(database).sync_service_listing(
        str(vendor_id), "spa", {"name": "Wellness Spa", "published": True}
    )

    detail = CustomerRepository(database).get_spa_details(str(ObjectId()), str(vendor_id))

    assert detail is not None
    assert detail["category"] == "spa"
    assert detail["name"] == "Wellness Spa"


def test_hotel_detail_uses_saved_overview_settings_and_merges_room_amenities():
    database = mongomock.MongoClient().nuno
    vendor_id = ObjectId()
    customer_id = ObjectId()
    database.vendors.insert_one(
        {"_id": vendor_id, "status": "approved", "business_name": "Harbour Hotel"}
    )
    database.vendor_profiles.insert_one({"vendor_id": vendor_id, "category": "Hotel"})
    database.vendor_rooms.insert_one(
        {
            "vendor_id": vendor_id,
            "name": "Deluxe Room",
            "available": True,
            "base_price": 220,
            "amenities": ["Air Conditioning", "Smart TV"],
        }
    )

    settings = {
        "name": "Harbour Hotel",
        "address": "12 Lake Road, Dhaka",
        "about": "A quiet city stay close to the lake.",
        "amenities": ["Free WiFi", "Air Conditioning"],
        "special_offers": [
            {
                "title": "Weekend escape",
                "description": "Stay two nights and save 15%.",
                "active": True,
            },
            {
                "title": "Expired internal offer",
                "description": "Not visible",
                "active": False,
            },
        ],
        "published": True,
    }
    database.vendor_portal_settings.insert_one(
        {
            "vendor_id": vendor_id,
            "profile": {"hotel_settings": settings},
            "general": {},
        }
    )
    VendorPortalRepository(database).sync_service_listing(str(vendor_id), "hotel", settings)

    detail = CustomerRepository(database).get_hotel_details(
        str(customer_id), str(vendor_id)
    )

    assert detail is not None
    assert detail["about"] == "A quiet city stay close to the lake."
    assert detail["address"] == "12 Lake Road, Dhaka"
    assert detail["amenities"] == ["Free WiFi", "Air Conditioning", "Smart TV"]
    assert detail["offers"] == [
        {
            "id": "hotel-setting-offer-0",
            "title": "Weekend escape",
            "description": "Stay two nights and save 15%.",
            "active": True,
            "source": "hotel_settings",
        }
    ]
    assert detail["tabs"]["offers_count"] == 1


def test_hotel_cards_do_not_invent_static_amenities():
    database = mongomock.MongoClient().nuno
    vendor_id = ObjectId()
    customer_id = ObjectId()
    database.vendors.insert_one(
        {"_id": vendor_id, "status": "approved", "business_name": "Harbour Hotel"}
    )
    database.vendor_profiles.insert_one({"vendor_id": vendor_id, "category": "Hotel"})
    database.vendor_rooms.insert_one(
        {
            "vendor_id": vendor_id,
            "name": "Standard Room",
            "available": True,
            "base_price": 150,
            "amenities": ["Coffee Maker"],
        }
    )
    settings = {
        "name": "Harbour Hotel",
        "amenities": ["Free WiFi"],
        "published": True,
    }
    database.vendor_portal_settings.insert_one(
        {
            "vendor_id": vendor_id,
            "profile": {"hotel_settings": settings},
            "general": {},
        }
    )
    VendorPortalRepository(database).sync_service_listing(str(vendor_id), "hotel", settings)

    result = CustomerRepository(database).list_hotels(
        str(customer_id), limit=10, skip=0
    )

    assert result["items"][0]["amenities"] == ["Free WiFi", "Coffee Maker"]


def test_category_counts_include_each_published_service_for_multi_service_provider():
    database = mongomock.MongoClient().nuno
    vendor_id = ObjectId()
    database.vendors.insert_one(
        {"_id": vendor_id, "status": "approved", "business_name": "Harbour Group"}
    )
    database.vendor_profiles.insert_one(
        {"vendor_id": vendor_id, "category": "Restaurant"}
    )
    database.vendor_portal_settings.insert_one(
        {
            "vendor_id": vendor_id,
            "profile": {
                "restaurant_settings": {
                    "name": "Harbour Restaurant",
                    "published": True,
                },
                "hotel_settings": {
                    "name": "Harbour Hotel",
                    "published": True,
                },
            },
            "general": {},
        }
    )
    database.vendor_rooms.insert_one(
        {
            "vendor_id": vendor_id,
            "name": "Standard Room",
            "available": True,
            "base_price": 150,
        }
    )
    portal = VendorPortalRepository(database)
    portal.sync_service_listing(
        str(vendor_id),
        "restaurant",
        {"name": "Harbour Restaurant", "published": True},
    )
    portal.sync_service_listing(
        str(vendor_id),
        "hotel",
        {"name": "Harbour Hotel", "published": True},
    )

    categories = CustomerRepository(database).list_categories()["items"]
    counts = {item["key"]: item["count"] for item in categories}

    assert counts["restaurant"] == 1
    assert counts["hotel"] == 1
    assert counts["spa"] == 0
