from datetime import UTC, datetime

from bson import ObjectId
import mongomock
import pytest
from pydantic import ValidationError

from app.modules.customer.repositories_customer import CustomerRepository
from app.modules.vendor.repositories_portal import VendorPortalRepository
from app.modules.vendor.schemas_portal import (
    VendorAmenityCreateRequest,
    VendorSettingsProfileRequest,
    VendorServiceSettings,
)


class _StrictMongoUpdateCollection:
    """Make mongomock reject update-path conflicts like production MongoDB."""

    def __init__(self, collection):
        self.collection = collection

    def update_one(self, query, update, **kwargs):
        set_fields = set(update.get("$set", {}))
        insert_fields = set(update.get("$setOnInsert", {}))
        assert not set_fields.intersection(insert_fields)
        return self.collection.update_one(query, update, **kwargs)

    def find_one(self, *args, **kwargs):
        return self.collection.find_one(*args, **kwargs)


def test_custom_amenity_schema_normalizes_and_limits_input():
    assert VendorAmenityCreateRequest(name="  Rooftop Lounge  ").name == "Rooftop Lounge"

    with pytest.raises(ValidationError):
        VendorAmenityCreateRequest(name="   ")
    with pytest.raises(ValidationError):
        VendorAmenityCreateRequest(name="x" * 81)
    with pytest.raises(ValidationError):
        VendorServiceSettings(amenities=[f"Amenity {index}" for index in range(51)])


def test_partial_profile_patch_contains_only_explicit_fields():
    payload = VendorSettingsProfileRequest(
        owner_full_name="Updated Owner",
    ).model_dump(exclude_unset=True)

    assert payload == {"owner_full_name": "Updated Owner"}


def test_profile_categories_remove_legacy_event_venue_module():
    payload = VendorSettingsProfileRequest(
        category="Event Venue",
        categories=["Event Venue", "Hotel"],
    )

    assert payload.category == "Hotel"
    assert payload.categories == ["Hotel"]


def test_profile_response_hides_legacy_event_venue_module():
    database = mongomock.MongoClient().nuno
    vendor_id = ObjectId()
    database.vendors.insert_one(
        {
            "_id": vendor_id,
            "status": "approved",
            "business_name": "Legacy Event Account",
            "category": "Event Venue",
            "categories": ["Event Venue"],
        }
    )
    database.vendor_portal_settings.insert_one(
        {
            "vendor_id": vendor_id,
            "profile": {
                "category": "Event Venue",
                "categories": ["Event Venue"],
            },
        }
    )

    profile = VendorPortalRepository(database).get_settings_profile(str(vendor_id))

    assert profile["category"] == "Restaurant"
    assert profile["categories"] == ["Restaurant", "Happy Hour"]


def test_partial_profile_update_preserves_service_settings_without_resync():
    database = mongomock.MongoClient().nuno
    vendor_id = ObjectId()
    database.vendors.insert_one(
        {
            "_id": vendor_id,
            "status": "approved",
            "business_name": "Garden Venue",
            "owner_full_name": "Original Owner",
        }
    )
    database.vendor_portal_settings.insert_one(
        {
            "vendor_id": vendor_id,
            "profile": {
                "business_name": "Garden Venue",
                "restaurant_settings": {
                    "name": "Garden Restaurant",
                    "amenities": ["Free WiFi"],
                    "published": True,
                },
            },
        }
    )
    portal = VendorPortalRepository(database)
    synchronized: list[str] = []
    portal.sync_service_listing = lambda _vendor_id, service_type, _settings: synchronized.append(service_type)  # type: ignore[method-assign]

    profile = portal.update_settings_profile(
        str(vendor_id),
        {"owner_full_name": "Updated Owner"},
    )

    assert profile["owner_full_name"] == "Updated Owner"
    assert profile["restaurant_settings"]["amenities"] == ["Free WiFi"]
    assert synchronized == []


def test_profile_amenities_save_does_not_write_created_at_twice():
    database = mongomock.MongoClient().nuno
    vendor_id = ObjectId()
    database.vendors.insert_one(
        {"_id": vendor_id, "status": "approved", "business_name": "Garden Venue"}
    )
    portal = VendorPortalRepository(database)
    portal.service_collections["restaurant"] = _StrictMongoUpdateCollection(
        database.vendor_restaurants
    )

    profile = portal.update_settings_profile(
        str(vendor_id),
        {
            "restaurant_settings": {
                "name": "Garden Restaurant",
                "amenities": ["Free WiFi"],
                "published": True,
            }
        },
    )

    listing = portal.service_collections["restaurant"].find_one(
        {"vendor_id": vendor_id}
    )
    assert profile["restaurant_settings"]["amenities"] == ["Free WiFi"]
    assert listing is not None
    assert listing["amenities"] == ["Free WiFi"]
    assert listing["created_at"]


def test_add_service_amenity_preserves_settings_and_avoids_case_duplicates():
    database = mongomock.MongoClient().nuno
    vendor_id = ObjectId()
    database.vendors.insert_one(
        {"_id": vendor_id, "status": "approved", "business_name": "Garden Venue"}
    )
    database.vendor_portal_settings.insert_one(
        {
            "vendor_id": vendor_id,
            "profile": {
                "restaurant_settings": {
                    "name": "Garden Restaurant",
                    "policy": "Cancel two hours before arrival.",
                    "amenities": ["Free WiFi"],
                    "published": True,
                }
            },
        }
    )
    portal = VendorPortalRepository(database)

    added = portal.add_service_amenity(
        str(vendor_id), "restaurant", "Private Dining"
    )
    duplicate = portal.add_service_amenity(
        str(vendor_id), "restaurant", "private dining"
    )

    assert added["created"] is True
    assert duplicate["created"] is False
    assert duplicate["amenity"] == "Private Dining"
    assert duplicate["amenities"] == ["Free WiFi", "Private Dining"]
    assert duplicate["settings"]["policy"] == "Cancel two hours before arrival."
    listing = portal.service_collections["restaurant"].find_one(
        {"vendor_id": vendor_id}
    )
    assert listing is not None
    assert listing["amenities"] == ["Free WiFi", "Private Dining"]


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


def test_unpublished_spa_is_not_counted_before_projection_sync():
    database = mongomock.MongoClient().nuno
    published_vendor_id = ObjectId()
    unpublished_vendor_id = ObjectId()
    database.vendors.insert_many(
        [
            {
                "_id": published_vendor_id,
                "status": "approved",
                "business_name": "Published Wellness",
            },
            {
                "_id": unpublished_vendor_id,
                "status": "approved",
                "business_name": "Private Wellness",
            },
        ]
    )
    database.vendor_profiles.insert_many(
        [
            {"vendor_id": published_vendor_id, "category": "Spa"},
            {"vendor_id": unpublished_vendor_id, "category": "Spa"},
        ]
    )
    database.vendor_portal_settings.insert_many(
        [
            {
                "vendor_id": published_vendor_id,
                "profile": {
                    "spa_settings": {
                        "name": "Published Wellness",
                        "published": True,
                    }
                },
            },
            {
                "vendor_id": unpublished_vendor_id,
                "profile": {
                    "spa_settings": {
                        "name": "Private Wellness",
                        "published": False,
                    }
                },
            },
        ]
    )

    repository = CustomerRepository(database)
    categories = repository.list_categories()["items"]
    counts = {item["key"]: item["count"] for item in categories}
    spas = repository.list_spas(str(ObjectId()), limit=20, skip=0)

    assert counts["spa"] == 1
    assert spas["total"] == 1
    assert spas["items"][0]["name"] == "Published Wellness"
    assert repository.list_spas(
        str(ObjectId()),
        limit=20,
        skip=0,
        search="Private Wellness",
    )["total"] == 0
    assert repository._is_public_service(unpublished_vendor_id, "spa") is False


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


def test_customer_service_payloads_expose_each_service_profile_image():
    database = mongomock.MongoClient().nuno
    vendor_id = ObjectId()
    customer_id = ObjectId()
    database.vendors.insert_one(
        {"_id": vendor_id, "status": "approved", "business_name": "Harbour Group"}
    )
    database.vendor_profiles.insert_one(
        {"vendor_id": vendor_id, "category": "Restaurant"}
    )
    service_settings = {
        "restaurant": {
            "name": "Harbour Dining",
            "profile_image_url": "https://example.com/restaurant-profile.jpg",
            "published": True,
        },
        "hotel": {
            "name": "Harbour Hotel",
            "profile_image_url": "https://example.com/hotel-profile.jpg",
            "published": True,
        },
        "spa": {
            "name": "Harbour Spa",
            "profile_image_url": "https://example.com/spa-profile.jpg",
            "published": True,
        },
    }
    database.vendor_portal_settings.insert_one(
        {
            "vendor_id": vendor_id,
            "profile": {
                f"{service_type}_settings": settings
                for service_type, settings in service_settings.items()
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
    for service_type, settings in service_settings.items():
        portal.sync_service_listing(str(vendor_id), service_type, settings)
        database.vendor_bookings.insert_one(
            {
                "vendor_id": vendor_id,
                "customer_id": customer_id,
                "provider_type": service_type,
                "service": f"{service_type.title()} Booking",
                "status": "confirmed",
                "created_at": datetime.now(UTC),
            }
        )

    repository = CustomerRepository(database)
    restaurants = repository.list_restaurants(str(customer_id), limit=10, skip=0)
    hotels = repository.list_hotels(str(customer_id), limit=10, skip=0)
    spas = repository.list_spas(str(customer_id), limit=10, skip=0)

    assert restaurants["items"][0]["profile_image_url"].endswith(
        "restaurant-profile.jpg"
    )
    assert hotels["items"][0]["profile_image_url"].endswith("hotel-profile.jpg")
    assert spas["items"][0]["profile_image_url"].endswith("spa-profile.jpg")
    assert repository.get_restaurant_details(
        str(customer_id), str(vendor_id)
    )["profile_image_url"].endswith("restaurant-profile.jpg")
    assert repository.get_hotel_details(
        str(customer_id), str(vendor_id)
    )["profile_image_url"].endswith("hotel-profile.jpg")
    assert repository.get_spa_details(
        str(customer_id), str(vendor_id)
    )["profile_image_url"].endswith("spa-profile.jpg")
    bookings = repository.list_customer_bookings(
        str(customer_id), limit=10, skip=0
    )["items"]
    booking_images = {
        booking["provider_type"]: booking["provider_image"] for booking in bookings
    }
    assert booking_images["restaurant"].endswith("restaurant-profile.jpg")
    assert booking_images["hotel"].endswith("hotel-profile.jpg")
    assert booking_images["spa"].endswith("spa-profile.jpg")


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
