from pymongo import ASCENDING, DESCENDING
from pymongo.database import Database


def ensure_mongodb_indexes(db: Database) -> None:
    """Create indexes for all major collections (idempotent)."""
    db["users"].create_index("email", unique=True, sparse=True)
    db["users"].create_index("phone", unique=True, sparse=True)
    db["users"].create_index([("created_at", DESCENDING)])

    db["vendors"].create_index("email", unique=True, sparse=True)
    db["vendors"].create_index("phone", unique=True, sparse=True)
    db["vendors"].create_index("status")
    db["vendors"].create_index([("created_at", DESCENDING)])

    db["platform_admins"].create_index("email", unique=True, sparse=True)
    db["platform_admins"].create_index("phone", unique=True, sparse=True)
    db["platform_admins"].create_index("status")

    db["vendor_profiles"].create_index("vendor_id", unique=True)
    db["vendor_business_details"].create_index("vendor_id", unique=True)
    db["vendor_verification_details"].create_index("vendor_id", unique=True)
    db["vendor_verification_details"].create_index("status")
    db["vendor_admin_reviews"].create_index("vendor_id", unique=True)
    db["vendor_admin_reviews"].create_index("review_status")

    db["password_reset_tokens"].create_index("token", unique=True)
    db["password_reset_tokens"].create_index("expires_at", expireAfterSeconds=0)
    db["password_reset_codes"].create_index("user_id", unique=True)
    db["password_reset_codes"].create_index("expires_at", expireAfterSeconds=0)

    db["vendor_password_reset_tokens"].create_index("token", unique=True)
    db["vendor_password_reset_tokens"].create_index("expires_at", expireAfterSeconds=0)
    db["vendor_password_reset_codes"].create_index("vendor_id", unique=True)
    db["vendor_password_reset_codes"].create_index("expires_at", expireAfterSeconds=0)

    db["signup_verification_codes"].create_index("email", unique=True)
    db["signup_verification_codes"].create_index("expires_at", expireAfterSeconds=0)
    db["signup_verification_tokens"].create_index("token", unique=True)
    db["signup_verification_tokens"].create_index("expires_at", expireAfterSeconds=0)

    db["vendor_signup_codes"].create_index("email", unique=True)
    db["vendor_signup_codes"].create_index("expires_at", expireAfterSeconds=0)
    db["vendor_signup_tokens"].create_index("token", unique=True)
    db["vendor_signup_tokens"].create_index("expires_at", expireAfterSeconds=0)

    db["platform_admin_signup_codes"].create_index("email", unique=True)
    db["platform_admin_signup_codes"].create_index("expires_at", expireAfterSeconds=0)
    db["platform_admin_signup_tokens"].create_index("token", unique=True)
    db["platform_admin_signup_tokens"].create_index("expires_at", expireAfterSeconds=0)

    db["platform_admin_password_reset_tokens"].create_index("token", unique=True)
    db["platform_admin_password_reset_tokens"].create_index("expires_at", expireAfterSeconds=0)
    db["platform_admin_password_reset_codes"].create_index("admin_id", unique=True)
    db["platform_admin_password_reset_codes"].create_index("expires_at", expireAfterSeconds=0)

    db["notifications"].create_index([("user_id", ASCENDING), ("created_at", DESCENDING)])
    db["bookings"].create_index([("customer_id", ASCENDING), ("created_at", DESCENDING)])
    db["bookings"].create_index([("vendor_id", ASCENDING), ("date", ASCENDING), ("time", ASCENDING)])
