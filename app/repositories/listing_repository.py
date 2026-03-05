from motor.motor_asyncio import AsyncIOMotorDatabase

from app.repositories.base import oid, utcnow


class ListingRepository:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.collection = db.listings

    async def insert_many(self, listings: list[dict]) -> None:
        if listings:
            now = utcnow()
            for item in listings:
                item.setdefault("created_at", now)
                item.setdefault("updated_at", now)
                item.setdefault("rating_summary", {"average": 0.0, "count": 0})
            await self.collection.insert_many(listings)

    async def search(self, query: dict, limit: int) -> list[dict]:
        cursor = self.collection.find(query).limit(limit)
        return await cursor.to_list(length=limit)

    async def get_by_id(self, listing_id: str) -> dict | None:
        return await self.collection.find_one({"_id": oid(listing_id)})

    async def update_rating_summary(self, listing_id: str, average: float, count: int) -> None:
        await self.collection.update_one(
            {"_id": oid(listing_id)},
            {
                "$set": {
                    "rating_summary": {"average": round(average, 2), "count": count},
                    "updated_at": utcnow(),
                }
            },
        )

    async def top_by_type(self, listing_type: str, limit: int, near_metro: bool | None, offers: bool | None) -> list[dict]:
        query: dict = {"type": listing_type}
        if near_metro:
            query["near_metro_station"] = {"$ne": None}
        if offers is not None:
            query["has_offers"] = offers

        cursor = self.collection.find(query).sort("rating_summary.average", -1).limit(limit)
        return await cursor.to_list(length=limit)
