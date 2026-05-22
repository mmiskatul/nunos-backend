from motor.motor_asyncio import AsyncIOMotorDatabase

from app.repositories.base import oid, utcnow


class UserRepository:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.collection = db.users

    async def create_user(self, payload: dict) -> dict:
        now = utcnow()
        payload.update({"created_at": now, "updated_at": now})
        result = await self.collection.insert_one(payload)
        return await self.find_by_id(str(result.inserted_id))

    async def find_by_id(self, user_id: str) -> dict | None:
        return await self.collection.find_one({"_id": oid(user_id)})

    async def find_by_email(self, email: str) -> dict | None:
        return await self.collection.find_one({"email": email})

    async def find_by_phone(self, phone: str) -> dict | None:
        return await self.collection.find_one({"phone": phone})

    async def find_by_email_or_phone(self, identifier: str) -> dict | None:
        return await self.collection.find_one({"$or": [{"email": identifier}, {"phone": identifier}]})

    async def update_profile(self, user_id: str, payload: dict) -> dict | None:
        await self.collection.update_one(
            {"_id": oid(user_id)},
            {"$set": {**payload, "updated_at": utcnow()}},
        )
        return await self.find_by_id(user_id)

    async def update_password_by_email(self, email: str, password_hash: str) -> bool:
        result = await self.collection.update_one(
            {"email": email},
            {"$set": {"password_hash": password_hash, "updated_at": utcnow()}},
        )
        return result.modified_count == 1

    async def add_points(self, user_id: str, points: int) -> None:
        await self.collection.update_one(
            {"_id": oid(user_id)},
            {"$inc": {"points_balance": points}, "$set": {"updated_at": utcnow()}},
        )
