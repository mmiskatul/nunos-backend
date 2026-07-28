"""Install core and vendor MongoDB indexes as a deployment step."""

import asyncio

from motor.motor_asyncio import AsyncIOMotorClient

from app.core.config import get_settings
from app.db.mongo import ensure_indexes
from app.db.mongodb import MongoDatabase
from app.db.vendor_indexes import ensure_vendor_indexes


async def ensure_core_indexes() -> None:
    settings = get_settings()
    client = AsyncIOMotorClient(
        settings.mongodb_uri,
        connectTimeoutMS=settings.mongodb_connect_timeout_ms,
        serverSelectionTimeoutMS=settings.mongodb_server_selection_timeout_ms,
        socketTimeoutMS=settings.mongodb_socket_timeout_ms,
    )
    try:
        await ensure_indexes(client[settings.mongodb_db_name])
    finally:
        client.close()


def main() -> None:
    settings = get_settings()
    asyncio.run(ensure_core_indexes())

    mongo = MongoDatabase(
        settings.mongodb_uri,
        settings.mongodb_db_name,
        connect_timeout_ms=settings.mongodb_connect_timeout_ms,
        server_selection_timeout_ms=settings.mongodb_server_selection_timeout_ms,
        socket_timeout_ms=settings.mongodb_socket_timeout_ms,
    )
    try:
        vendor_indexes = ensure_vendor_indexes(mongo.db)
    finally:
        mongo.close()

    total = sum(len(names) for names in vendor_indexes.values())
    print(f"Core indexes and {total} vendor indexes are ready.")


if __name__ == "__main__":
    main()
