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
