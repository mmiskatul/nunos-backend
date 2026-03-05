from datetime import datetime

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.repositories.base import oid, utcnow


class BookingRepository:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.collection = db.bookings

    async def create(self, payload: dict) -> dict:
        now = utcnow()
        payload.update({"created_at": now, "updated_at": now})
        result = await self.collection.insert_one(payload)
        return await self.get_by_id(str(result.inserted_id))

    async def get_by_id(self, booking_id: str) -> dict | None:
        return await self.collection.find_one({"_id": oid(booking_id)})

    async def update_status(self, booking_id: str, status: str) -> dict | None:
        await self.collection.update_one(
            {"_id": oid(booking_id)},
            {"$set": {"status": status, "updated_at": utcnow()}},
        )
        return await self.get_by_id(booking_id)

    async def reschedule(self, booking_id: str, details: dict, scheduled_at: datetime) -> dict | None:
        await self.collection.update_one(
            {"_id": oid(booking_id)},
            {
                "$set": {
                    "status": "rescheduled",
                    "details": details,
                    "scheduled_at": scheduled_at,
                    "updated_at": utcnow(),
                }
            },
        )
        return await self.get_by_id(booking_id)

    async def list_for_user(self, user_id: str, *, upcoming: bool | None = None) -> list[dict]:
        query: dict = {"user_id": oid(user_id)}
        now = utcnow()
        if upcoming is True:
            query["scheduled_at"] = {"$gte": now}
        elif upcoming is False:
            query["scheduled_at"] = {"$lt": now}

        cursor = self.collection.find(query).sort("scheduled_at", 1)
        return await cursor.to_list(length=300)
