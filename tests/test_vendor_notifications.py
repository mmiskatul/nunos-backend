from bson import ObjectId
import mongomock

from app.modules.vendor.repositories_portal import VendorPortalRepository


def test_notification_list_reports_unread_count_across_all_pages():
    database = mongomock.MongoClient().nuno
    vendor_id = ObjectId()
    database.vendor_notifications.insert_many(
        [
            {"vendor_id": vendor_id, "title": "Unread one", "read": False},
            {"vendor_id": vendor_id, "title": "Unread two"},
            {"vendor_id": vendor_id, "title": "Already read", "read": True},
            {"vendor_id": vendor_id, "title": "Legacy read", "is_read": True},
        ]
    )

    result = VendorPortalRepository(database).list_notifications(
        str(vendor_id),
        limit=1,
        skip=0,
    )

    assert result["total"] == 4
    assert len(result["items"]) == 1
    assert result["unread_count"] == 2
