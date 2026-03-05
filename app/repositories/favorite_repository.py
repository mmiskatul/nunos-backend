from motor.motor_asyncio import AsyncIOMotorDatabase

from app.repositories.base import oid, utcnow


class FavoriteRepository:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.collection = db.favorites

    async def add(self, user_id: str, listing_id: str) -> None:
        await self.collection.update_one(
            {"user_id": oid(user_id), "listing_id": oid(listing_id)},
            {
                "$setOnInsert": {
                    "created_at": utcnow(),
                    "updated_at": utcnow(),
                }
            },
            upsert=True,
        )

    async def remove(self, user_id: str, listing_id: str) -> None:
        await self.collection.delete_one({"user_id": oid(user_id), "listing_id": oid(listing_id)})

    async def list_listing_ids(self, user_id: str) -> list[str]:
        cursor = self.collection.find({"user_id": oid(user_id)})
        docs = await cursor.to_list(length=1000)
        return [str(doc["listing_id"]) for doc in docs]
