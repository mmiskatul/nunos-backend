from datetime import UTC, datetime

from collections.abc import AsyncIterator

from fastapi import Request
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo import ASCENDING, GEOSPHERE, TEXT

from app.core.config import Settings
from app.core.security import hash_password


class MongoManager:
    def __init__(self, settings: Settings):
        self._settings = settings
        self._client: AsyncIOMotorClient | None = None

    async def connect(self) -> AsyncIOMotorDatabase:
        self._client = AsyncIOMotorClient(self._settings.mongodb_uri)
        db = self._client[self._settings.mongodb_db_name]
        await ensure_indexes(db)
        await ensure_platform_admin(db, self._settings)
        return db

    async def close(self) -> None:
        if self._client is not None:
            self._client.close()


async def ensure_indexes(db: AsyncIOMotorDatabase) -> None:
    await db.users.create_index("email", unique=True, sparse=True)
    await db.users.create_index("phone", unique=True, sparse=True)
    await db.platform_admins.create_index("email", unique=True, sparse=True)
    await db.platform_admins.create_index("phone", unique=True, sparse=True)
    await db.platform_admins.create_index("status")

    await db.otp_codes.create_index([("expires_at", ASCENDING)], expireAfterSeconds=0)
    await db.otp_codes.create_index([("email", ASCENDING), ("purpose", ASCENDING)])
    await db.pending_signups.create_index("email", unique=True)
    await db.pending_signups.create_index([("expires_at", ASCENDING)], expireAfterSeconds=0)
    await db.auth_sessions.create_index("token", unique=True)
    await db.auth_sessions.create_index([("expires_at", ASCENDING)], expireAfterSeconds=0)
    await db.auth_sessions.create_index([("subject_id", ASCENDING), ("audience", ASCENDING), ("created_at", ASCENDING)])

    await db.listings.create_index([("location", GEOSPHERE)])
    await db.listings.create_index([("name", TEXT), ("description", TEXT)])
    await db.listings.create_index("type")
    await db.listings.create_index("near_metro_station")

    await db.reviews.create_index([("listing_id", ASCENDING), ("created_at", ASCENDING)])

    await db.favorites.create_index([("user_id", ASCENDING), ("listing_id", ASCENDING)], unique=True)

    await db.bookings.create_index([("user_id", ASCENDING), ("created_at", ASCENDING)])
    await db.bookings.create_index([("status", ASCENDING), ("scheduled_at", ASCENDING)])

    await db.offers.create_index([("listing_id", ASCENDING), ("promo_code", ASCENDING)])

    # Public service listings are separated so each app feed can only query
    # its own published entity type.
    for collection_name in ("restaurants", "hotels", "spas"):
        await db[collection_name].create_index("vendor_id", unique=True)
        await db[collection_name].create_index("published")
        await db[collection_name].create_index("updated_at")


async def ensure_platform_admin(db: AsyncIOMotorDatabase, settings: Settings) -> None:
    if not settings.platform_admin_email or not settings.platform_admin_password:
        return

    now = datetime.now(UTC)
    email = settings.platform_admin_email.strip().lower()
    phone = settings.platform_admin_phone.strip() if settings.platform_admin_phone else None

    await db.platform_admins.update_one(
        {"email": email},
        {
            "$set": {
                "full_name": settings.platform_admin_full_name.strip() or "Platform Admin",
                "email": email,
                "phone": phone,
                "password_hash": hash_password(settings.platform_admin_password),
                "role": "platform_admin",
                "status": "active",
                "updated_at": now,
            },
            "$setOnInsert": {"created_at": now},
        },
        upsert=True,
    )


async def get_database(request: Request) -> AsyncIOMotorDatabase:
    return request.app.state.db


async def database_lifespan(db: AsyncIOMotorDatabase) -> AsyncIterator[AsyncIOMotorDatabase]:
    yield db
