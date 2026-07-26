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
            "service_type": "hotel",
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


def test_assets_and_services_are_isolated_by_service_type():
    database = mongomock.MongoClient().nuno
    vendor_id = ObjectId()
    database.vendors.insert_one(
        {"_id": vendor_id, "status": "approved", "business_name": "Multi Venue"}
    )
    database.vendor_profiles.insert_one(
        {"vendor_id": vendor_id, "category": "Restaurant"}
    )
    database.vendor_assets.insert_many(
        [
            {
                "vendor_id": vendor_id,
                "asset_type": "gallery",
                "asset_url": "https://example.com/legacy-restaurant.jpg",
            },
            {
                "vendor_id": vendor_id,
                "asset_type": "gallery",
                "service_type": "restaurant",
                "asset_url": "https://example.com/restaurant.jpg",
            },
            {
                "vendor_id": vendor_id,
                "asset_type": "gallery",
                "service_type": "spa",
                "asset_url": "https://example.com/spa.jpg",
            },
        ]
    )
    database.vendor_services.insert_many(
        [
            {
                "vendor_id": vendor_id,
                "name": "Legacy room service",
                "available": True,
            },
            {
                "vendor_id": vendor_id,
                "name": "Breakfast delivery",
                "service_type": "hotel",
                "available": True,
            },
            {
                "vendor_id": vendor_id,
                "name": "Massage",
                "service_type": "spa",
                "available": True,
            },
        ]
    )

    portal = VendorPortalRepository(database)
    restaurant_assets = portal.list_assets(
        str(vendor_id), "gallery", "restaurant"
    )
    spa_assets = portal.list_assets(str(vendor_id), "gallery", "spa")
    customer = CustomerRepository(database)

    assert {asset["asset_url"] for asset in restaurant_assets} == {
        "https://example.com/legacy-restaurant.jpg",
        "https://example.com/restaurant.jpg",
    }
    assert [asset["asset_url"] for asset in spa_assets] == [
        "https://example.com/spa.jpg"
    ]
    assert {
        service["name"]
        for service in customer.list_provider_services(str(vendor_id), "hotel")
    } == {"Legacy room service", "Breakfast delivery"}
    assert [
        service["name"]
        for service in customer.list_provider_services(str(vendor_id), "spa")
    ] == ["Massage"]


def test_hotel_service_uses_hotel_settings_for_inherited_location():
    database = mongomock.MongoClient().nuno
    vendor_id = ObjectId()
    database.vendors.insert_one(
        {"_id": vendor_id, "status": "approved", "business_name": "Multi Venue"}
    )
    database.vendor_profiles.insert_one(
        {"vendor_id": vendor_id, "category": "Restaurant"}
    )
    database.vendor_portal_settings.insert_one(
        {
            "vendor_id": vendor_id,
            "profile": {
                "restaurant_settings": {"address": "Restaurant Floor"},
                "hotel_settings": {
                    "address": "Hotel Tower",
                    "latitude": 23.8,
                    "longitude": 90.4,
                },
            },
            "general": {},
        }
    )

    service = VendorPortalRepository(database).create_service(
        str(vendor_id),
        {
            "name": "Breakfast delivery",
            "service_type": "hotel",
            "category": "Food",
            "price": 20,
            "active_status": True,
        },
    )

    assert service["service_type"] == "hotel"
    assert service["location_label"] == "Hotel Tower"
    assert service["latitude"] == 23.8
    assert service["longitude"] == 90.4


def test_room_tax_setting_changes_customer_price_breakdown():
    database = mongomock.MongoClient().nuno
    vendor_id = ObjectId()
    included_room_id = database.vendor_rooms.insert_one(
        {
            "vendor_id": vendor_id,
            "name": "Tax Included",
            "base_price": 100,
            "tax_included": True,
        }
    ).inserted_id
    excluded_room_id = database.vendor_rooms.insert_one(
        {
            "vendor_id": vendor_id,
            "name": "Tax Extra",
            "base_price": 100,
            "tax_included": False,
        }
    ).inserted_id
    repository = CustomerRepository(database)

    included = repository.get_hotel_room_details(str(included_room_id))
    excluded = repository.get_hotel_room_details(str(excluded_room_id))

    assert included is not None
    assert included["price"] == {
        "rate": "200",
        "taxes": "0",
        "total": "200",
        "tax_included": True,
    }
    assert excluded is not None
    assert excluded["price"] == {
        "rate": "200",
        "taxes": "40",
        "total": "240",
        "tax_included": False,
    }


def test_restaurant_and_spa_settings_drive_their_own_amenities_and_offers():
    database = mongomock.MongoClient().nuno
    vendor_id = ObjectId()
    customer_id = ObjectId()
    database.vendors.insert_one(
        {"_id": vendor_id, "status": "approved", "business_name": "Multi Venue"}
    )
    database.vendor_profiles.insert_one(
        {"vendor_id": vendor_id, "category": "Restaurant"}
    )
    database.vendor_portal_settings.insert_one(
        {
            "vendor_id": vendor_id,
            "profile": {
                "restaurant_settings": {
                    "name": "Garden Dining",
                    "amenities": ["Outdoor seating"],
                    "special_offers": [
                        {
                            "title": "Lunch deal",
                            "description": "Lunch menu discount",
                            "active": True,
                        }
                    ],
                    "published": True,
                },
                "spa_settings": {
                    "name": "Garden Spa",
                    "amenities": ["Sauna"],
                    "special_offers": [
                        {
                            "title": "Wellness day",
                            "description": "Full-day spa access",
                            "active": True,
                        }
                    ],
                    "published": True,
                },
            },
            "general": {},
        }
    )
    database.vendor_promotions.insert_many(
        [
            {
                "vendor_id": vendor_id,
                "promotion_name": "Dining promotion",
                "applicable_to": "Dining Only",
                "active": True,
            },
            {
                "vendor_id": vendor_id,
                "promotion_name": "Spa promotion",
                "applicable_to": "Spa Only",
                "active": True,
            },
        ]
    )
    portal = VendorPortalRepository(database)
    portal.sync_service_listing(
        str(vendor_id),
        "restaurant",
        {"name": "Garden Dining", "published": True},
    )
    portal.sync_service_listing(
        str(vendor_id), "spa", {"name": "Garden Spa", "published": True}
    )
    repository = CustomerRepository(database)

    restaurant = repository.get_restaurant_details(
        str(customer_id), str(vendor_id), "restaurant"
    )
    spa = repository.get_spa_details(str(customer_id), str(vendor_id))
    restaurant_offers = repository.list_restaurant_offers(
        str(vendor_id), "restaurant"
    )
    spa_offers = repository.list_spa_offers(str(vendor_id))

    assert restaurant is not None
    assert restaurant["amenities"] == ["Outdoor seating"]
    assert spa is not None
    assert spa["amenities"] == ["Sauna"]
    assert {offer["title"] for offer in restaurant_offers} == {
        "Lunch deal",
        "Dining promotion",
    }
    assert {offer["title"] for offer in spa_offers} == {
        "Wellness day",
        "Spa promotion",
    }
