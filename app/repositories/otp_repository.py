from motor.motor_asyncio import AsyncIOMotorDatabase

from app.repositories.base import utcnow


class OTPRepository:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.collection = db.otp_codes

    async def upsert_code(self, *, email: str, purpose: str, code: str, expires_at) -> None:
        await self.collection.update_one(
            {"email": email, "purpose": purpose},
            {
                "$set": {
                    "code": code,
                    "expires_at": expires_at,
                    "verified": False,
                    "updated_at": utcnow(),
                },
                "$setOnInsert": {"created_at": utcnow()},
            },
            upsert=True,
        )

    async def verify_code(self, *, email: str, purpose: str, code: str, now) -> bool:
        result = await self.collection.find_one_and_update(
            {
                "email": email,
                "purpose": purpose,
                "code": code,
                "expires_at": {"$gt": now},
            },
            {"$set": {"verified": True, "updated_at": utcnow()}},
        )
        return bool(result)

    async def is_verified(self, *, email: str, purpose: str, now) -> bool:
        doc = await self.collection.find_one(
            {
                "email": email,
                "purpose": purpose,
                "verified": True,
                "expires_at": {"$gt": now},
            }
        )
        return bool(doc)
