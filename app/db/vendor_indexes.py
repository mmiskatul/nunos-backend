"""MongoDB indexes used by the service-provider API.

Run this module through ``scripts/ensure_vendor_indexes.py`` during deployment.
Keeping index management out of request-scoped repositories removes dozens of
database round trips from every vendor request.
"""

from pymongo import ASCENDING, DESCENDING, IndexModel
from pymongo.database import Database


VENDOR_INDEXES: dict[str, list[IndexModel]] = {
    "vendors": [
        IndexModel([("email", ASCENDING)], unique=True, sparse=True, name="vendor_email_unique"),
        IndexModel([("phone", ASCENDING)], sparse=True, name="vendor_phone"),
        IndexModel([("status", ASCENDING)], name="vendor_status"),
    ],
    "vendor_profiles": [IndexModel([("vendor_id", ASCENDING)], unique=True, name="vendor_profile_unique")],
    "vendor_business_details": [IndexModel([("vendor_id", ASCENDING)], unique=True, name="vendor_business_unique")],
    "vendor_verification_details": [IndexModel([("vendor_id", ASCENDING)], unique=True, name="vendor_verification_unique")],
    "vendor_admin_reviews": [
        IndexModel([("vendor_id", ASCENDING)], unique=True, name="vendor_admin_review_unique"),
        IndexModel([("review_status", ASCENDING)], name="vendor_admin_review_status"),
    ],
    "vendor_signup_codes": [
        IndexModel([("email", ASCENDING)], unique=True, name="vendor_signup_email_unique"),
        IndexModel([("expires_at", ASCENDING)], expireAfterSeconds=0, name="vendor_signup_code_ttl"),
    ],
    "vendor_signup_tokens": [
        IndexModel([("token", ASCENDING)], unique=True, name="vendor_signup_token_unique"),
        IndexModel([("expires_at", ASCENDING)], expireAfterSeconds=0, name="vendor_signup_token_ttl"),
    ],
    "vendor_password_reset_tokens": [
        IndexModel([("token", ASCENDING)], unique=True, name="vendor_reset_token_unique"),
        IndexModel([("expires_at", ASCENDING)], expireAfterSeconds=0, name="vendor_reset_token_ttl"),
    ],
    "vendor_password_reset_codes": [
        IndexModel([("vendor_id", ASCENDING)], unique=True, name="vendor_reset_code_unique"),
        IndexModel([("expires_at", ASCENDING)], expireAfterSeconds=0, name="vendor_reset_code_ttl"),
    ],
    "vendor_bookings": [
        IndexModel([("vendor_id", ASCENDING), ("scheduled_date", ASCENDING), ("status", ASCENDING)], name="vendor_booking_schedule"),
        IndexModel([("vendor_id", ASCENDING), ("created_at", DESCENDING)], name="vendor_booking_created"),
        IndexModel([("vendor_id", ASCENDING), ("customer_email", ASCENDING)], name="vendor_booking_email"),
        IndexModel([("vendor_id", ASCENDING), ("customer_phone", ASCENDING)], name="vendor_booking_phone"),
    ],
    "vendor_assets": [IndexModel([("vendor_id", ASCENDING), ("asset_type", ASCENDING), ("created_at", DESCENDING)], name="vendor_asset_type")],
    "vendor_rooms": [IndexModel([("vendor_id", ASCENDING), ("created_at", DESCENDING)], name="vendor_room_created")],
    "vendor_services": [IndexModel([("vendor_id", ASCENDING), ("created_at", DESCENDING)], name="vendor_service_created")],
    "vendor_events": [
        IndexModel([("vendor_id", ASCENDING), ("event_date", ASCENDING), ("start_time", ASCENDING)], name="vendor_event_schedule"),
        IndexModel([("vendor_id", ASCENDING), ("status", ASCENDING), ("created_at", DESCENDING)], name="vendor_event_status"),
        IndexModel([("vendor_id", ASCENDING), ("category", ASCENDING), ("created_at", DESCENDING)], name="vendor_event_category"),
    ],
    "vendor_promotions": [
        IndexModel([("vendor_id", ASCENDING), ("created_at", DESCENDING)], name="vendor_promotion_created"),
        IndexModel([("vendor_id", ASCENDING), ("active", ASCENDING)], name="vendor_promotion_active"),
    ],
    "platform_campaigns": [IndexModel([("active", ASCENDING), ("created_at", DESCENDING)], name="platform_campaign_active")],
    "vendor_reviews": [
        IndexModel([("vendor_id", ASCENDING), ("created_at", DESCENDING)], name="vendor_review_created"),
        IndexModel([("vendor_id", ASCENDING), ("rating", DESCENDING)], name="vendor_review_rating"),
    ],
    "vendor_support_tickets": [IndexModel([("vendor_id", ASCENDING), ("created_at", DESCENDING)], name="vendor_ticket_created")],
    "vendor_notifications": [IndexModel([("vendor_id", ASCENDING), ("created_at", DESCENDING)], name="vendor_notification_created")],
    "vendor_portal_settings": [IndexModel([("vendor_id", ASCENDING)], unique=True, name="vendor_settings_unique")],
    "vendor_notification_settings": [IndexModel([("vendor_id", ASCENDING)], unique=True, name="vendor_notification_settings_unique")],
    "vendor_loyalty_settings": [IndexModel([("vendor_id", ASCENDING)], unique=True, name="vendor_loyalty_settings_unique")],
}


def ensure_vendor_indexes(db: Database) -> dict[str, list[str]]:
    """Create missing vendor indexes and return their resulting names.

    Older releases created the same key patterns with MongoDB's default names.
    We retain compatible existing indexes instead of failing on a name-only
    conflict, while refusing to silently accept incompatible unique/TTL rules.
    """
    result: dict[str, list[str]] = {}
    for collection_name, indexes in VENDOR_INDEXES.items():
        collection = db[collection_name]
        existing = collection.index_information()
        names: list[str] = []
        pending: list[IndexModel] = []
        for index in indexes:
            document = index.document
            requested_keys = list(document["key"].items())
            match = next(
                ((name, info) for name, info in existing.items() if info.get("key") == requested_keys),
                None,
            )
            if match:
                name, info = match
                for option in ("unique", "sparse", "expireAfterSeconds"):
                    requested = document.get(option)
                    installed = info.get(option)
                    if requested is not None and requested != installed:
                        raise RuntimeError(
                            f"Index {collection_name}.{name} has incompatible {option}: "
                            f"installed={installed!r}, required={requested!r}."
                        )
                names.append(name)
            else:
                pending.append(index)
        if pending:
            names.extend(collection.create_indexes(pending))
        result[collection_name] = names
    return result
