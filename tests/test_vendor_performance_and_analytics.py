from datetime import UTC, datetime, timedelta

import mongomock
from bson import ObjectId

from app.db.vendor_indexes import ensure_vendor_indexes
from app.modules.vendor.repositories_password_reset import VendorPasswordResetRepository
from app.modules.vendor.repositories_portal import VendorPortalRepository
from app.modules.vendor.repositories_signup import VendorSignupVerificationRepository
from app.modules.vendor.repositories_vendor import VendorRepository


class _NoIndexCollection:
    def create_index(self, *args, **kwargs):  # pragma: no cover - failure path
        raise AssertionError("repositories must not create indexes during requests")

    def create_indexes(self, *args, **kwargs):  # pragma: no cover - failure path
        raise AssertionError("repositories must not create indexes during requests")

    def drop_index(self, *args, **kwargs):  # pragma: no cover - failure path
        raise AssertionError("repositories must not mutate indexes during requests")


class _NoIndexDatabase:
    def __getitem__(self, name):
        return _NoIndexCollection()


def test_vendor_repository_constructors_do_not_touch_indexes():
    database = _NoIndexDatabase()
    VendorRepository(database)
    VendorPortalRepository(database)
    VendorSignupVerificationRepository(database)
    VendorPasswordResetRepository(database)


def test_vendor_index_migration_is_idempotent():
    database = mongomock.MongoClient().nuno
    first = ensure_vendor_indexes(database)
    second = ensure_vendor_indexes(database)

    assert first == second
    assert "vendor_booking_schedule" in second["vendor_bookings"]


def test_occupancy_only_counts_bookings_for_requested_date():
    database = mongomock.MongoClient().nuno
    vendor_id = ObjectId()
    repository = VendorPortalRepository(database)
    today = datetime.now(UTC).date().isoformat()
    yesterday = (datetime.now(UTC).date() - timedelta(days=1)).isoformat()
    database.vendor_rooms.insert_one({"vendor_id": vendor_id, "total_inventory": 10})
    database.vendor_bookings.insert_many(
        [
            {"vendor_id": vendor_id, "scheduled_date": today, "status": "confirmed"},
            {"vendor_id": vendor_id, "scheduled_date": yesterday, "status": "confirmed"},
        ]
    )

    metrics = repository.get_occupancy_metrics(str(vendor_id), today)

    assert metrics["active_bookings"] == 1
    assert metrics["rooms_total"] == 10
    assert metrics["occupancy_rate"] == 10.0


def test_analytics_uses_selected_range_and_returns_real_csv():
    database = mongomock.MongoClient().nuno
    vendor_id = ObjectId()
    repository = VendorPortalRepository(database)
    database.vendor_rooms.insert_one({"vendor_id": vendor_id, "inventory_count": 4})
    database.vendor_bookings.insert_many(
        [
            {
                "vendor_id": vendor_id,
                "scheduled_date": "2026-07-10",
                "status": "confirmed",
                "total_amount": "120.50",
                "customer_gender": "female",
                "customer_age": 31,
            },
            {
                "vendor_id": vendor_id,
                "scheduled_date": "2026-06-10",
                "status": "complete",
                "total_amount": 999,
            },
        ]
    )

    overview = repository.get_analytics_overview(str(vendor_id), "2026-07-01", "2026-07-31")
    export = repository.export_analytics(str(vendor_id), "2026-07-01", "2026-07-31")

    assert overview["total_bookings"] == 1
    assert overview["monthly_revenue"] == 120.5
    assert overview["demographics"]["gender_distribution"]["female"] == 100
    assert "Total bookings,1" in export["content"]
    assert "files.example.com" not in str(export)


def test_vendor_legal_edits_do_not_modify_platform_legal_content():
    database = mongomock.MongoClient().nuno
    vendor_id = ObjectId()
    repository = VendorPortalRepository(database)
    database.platform_admin_settings.insert_one(
        {
            "_id": "platform_admin_settings",
            "legalContent": {
                "documents": {"terms": "Terms of Service"},
                "content": {"terms": {"business": "Platform terms"}},
                "lastUpdated": "Platform date",
            },
        }
    )

    updated = repository.update_legal_doc(str(vendor_id), "terms", "Vendor terms", "business")

    platform = database.platform_admin_settings.find_one({"_id": "platform_admin_settings"})
    vendor_settings = database.vendor_portal_settings.find_one({"vendor_id": vendor_id})
    assert platform["legalContent"]["content"]["terms"]["business"] == "Platform terms"
    assert vendor_settings["legal_content"]["content"]["terms"]["business"] == "Vendor terms"
    assert repository.get_public_legal_doc("terms")["content"] == "Platform terms"
    assert updated["content"] == "Vendor terms"


def test_vendor_commission_is_read_from_platform_settings():
    database = mongomock.MongoClient().nuno
    vendor_id = ObjectId()
    repository = VendorPortalRepository(database)
    database.platform_admin_settings.insert_one(
        {
            "_id": "platform_admin_settings",
            "commission": {"globalRate": "12.50", "categoryRate": "18.00", "categoryLabel": "Luxury"},
        }
    )
    database.vendor_business_details.insert_one({"vendor_id": vendor_id, "categories": ["Luxury"]})

    commission = repository.get_settings_commission(str(vendor_id))

    assert commission["commission_percent"] == 18.0
    assert commission["category_applies"] is True
    assert commission["source"] == "platform_admin_settings"


def test_generated_receipt_is_downloadable_and_escapes_customer_data():
    database = mongomock.MongoClient().nuno
    vendor_id = ObjectId()
    booking_id = ObjectId()
    repository = VendorPortalRepository(database)
    database.vendor_bookings.insert_one(
        {
            "_id": booking_id,
            "vendor_id": vendor_id,
            "booking_code": "../../unsafe code",
            "customer_name": "<script>alert(1)</script>",
            "service": "Dinner & stay",
            "total_amount": 100,
        }
    )

    receipt = repository.generate_receipt(str(vendor_id), str(booking_id))

    assert receipt is not None
    assert receipt["content_type"] == "text/html;charset=utf-8"
    assert receipt["filename"].startswith("receipt-")
    assert "/" not in receipt["filename"]
    assert "<script>" not in receipt["content"]
    assert "&lt;script&gt;" in receipt["content"]
