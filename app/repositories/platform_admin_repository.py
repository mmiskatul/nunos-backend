from motor.motor_asyncio import AsyncIOMotorDatabase
from bson import ObjectId
from datetime import UTC, datetime


class PlatformAdminRepository:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.collection = db.platform_admins

    def _serialize(self, document: dict | None) -> dict | None:
        if not document:
            return None
        serialized = {**document}
        serialized["id"] = str(serialized.pop("_id"))
        return serialized

    async def find_by_email(self, email: str) -> dict | None:
        return self._serialize(await self.collection.find_one({"email": email}))

    async def find_by_phone(self, phone: str) -> dict | None:
        return self._serialize(await self.collection.find_one({"phone": phone}))

    async def find_by_id(self, admin_id: str) -> dict | None:
        return self._serialize(await self.collection.find_one({"_id": ObjectId(admin_id)}))

    async def update_password_hash(self, admin_id: str, password_hash: str) -> None:
        await self.collection.update_one(
            {"_id": ObjectId(admin_id)},
            {"$set": {"password_hash": password_hash, "updated_at": datetime.now(UTC)}},
        )
