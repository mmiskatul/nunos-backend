from datetime import datetime

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.repositories.base import oid, utcnow


class OfferRepository:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.collection = db.offers

    async def create(self, payload: dict) -> dict:
        now = utcnow()
        payload.update({"created_at": now, "updated_at": now})
        result = await self.collection.insert_one(payload)
        return await self.collection.find_one({"_id": result.inserted_id})

    async def validate_promo(self, listing_id: str, promo_code: str | None, now: datetime) -> dict | None:
        query: dict = {"listing_id": oid(listing_id)}
        query["$or"] = [
            {"starts_at": None},
            {"starts_at": {"$lte": now}},
        ]
        query["$and"] = [
            {"$or": [{"ends_at": None}, {"ends_at": {"$gte": now}}]},
        ]

        offers = await self.collection.find(query).to_list(length=30)
        for offer in offers:
            if offer.get("require_code"):
                if promo_code and offer.get("promo_code") == promo_code:
                    return offer
                continue
            return offer

        if promo_code:
            return await self.collection.find_one({"listing_id": oid(listing_id), "promo_code": promo_code})
        return None
