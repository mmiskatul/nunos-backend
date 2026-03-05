from motor.motor_asyncio import AsyncIOMotorDatabase

from app.repositories.base import oid, utcnow


class ReviewRepository:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.collection = db.reviews

    async def create(self, payload: dict) -> dict:
        now = utcnow()
        payload.update({"created_at": now, "updated_at": now})
        result = await self.collection.insert_one(payload)
        return await self.collection.find_one({"_id": result.inserted_id})

    async def list_for_listing(self, listing_id: str, limit: int = 50) -> list[dict]:
        cursor = self.collection.find({"listing_id": oid(listing_id)}).sort("created_at", -1).limit(limit)
        return await cursor.to_list(length=limit)

    async def rating_aggregate(self, listing_id: str) -> tuple[float, int]:
        pipeline = [
            {"$match": {"listing_id": oid(listing_id)}},
            {
                "$group": {
                    "_id": "$listing_id",
                    "avg": {"$avg": "$rating"},
                    "count": {"$sum": 1},
                }
            },
        ]
        result = await self.collection.aggregate(pipeline).to_list(length=1)
        if not result:
            return 0.0, 0
        return float(result[0]["avg"]), int(result[0]["count"])
