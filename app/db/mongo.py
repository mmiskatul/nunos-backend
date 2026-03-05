from collections.abc import AsyncIterator

from fastapi import Request
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo import ASCENDING, GEOSPHERE, TEXT

from app.core.config import Settings


class MongoManager:
    def __init__(self, settings: Settings):
        self._settings = settings
        self._client: AsyncIOMotorClient | None = None

    async def connect(self) -> AsyncIOMotorDatabase:
        self._client = AsyncIOMotorClient(self._settings.mongodb_uri)
        db = self._client[self._settings.mongodb_db_name]
        await ensure_indexes(db)
        return db

    async def close(self) -> None:
        if self._client is not None:
            self._client.close()


async def ensure_indexes(db: AsyncIOMotorDatabase) -> None:
    await db.users.create_index("email", unique=True, sparse=True)
    await db.users.create_index("phone", unique=True, sparse=True)

    await db.otp_codes.create_index([("expires_at", ASCENDING)], expireAfterSeconds=0)
    await db.otp_codes.create_index([("email", ASCENDING), ("purpose", ASCENDING)])

    await db.listings.create_index([("location", GEOSPHERE)])
    await db.listings.create_index([("name", TEXT), ("description", TEXT)])
    await db.listings.create_index("type")
    await db.listings.create_index("near_metro_station")

    await db.reviews.create_index([("listing_id", ASCENDING), ("created_at", ASCENDING)])

    await db.favorites.create_index([("user_id", ASCENDING), ("listing_id", ASCENDING)], unique=True)

    await db.bookings.create_index([("user_id", ASCENDING), ("created_at", ASCENDING)])
    await db.bookings.create_index([("status", ASCENDING), ("scheduled_at", ASCENDING)])

    await db.offers.create_index([("listing_id", ASCENDING), ("promo_code", ASCENDING)])


async def get_database(request: Request) -> AsyncIOMotorDatabase:
    return request.app.state.db


async def database_lifespan(db: AsyncIOMotorDatabase) -> AsyncIterator[AsyncIOMotorDatabase]:
    yield db
