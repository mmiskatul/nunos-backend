from datetime import UTC, datetime, timedelta

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.repositories.base import utcnow


class PendingSignupRepository:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.collection = db.pending_signups

    async def upsert_signup(
        self,
        *,
        email: str,
        full_name: str,
        phone: str | None,
        password_hash: str,
        location_enabled: bool,
        latitude: float | None,
        longitude: float | None,
        location_accuracy_meters: float | None,
        expires_in_minutes: int,
    ) -> None:
        now = utcnow()
        await self.collection.update_one(
            {"email": email},
            {
                "$set": {
                    "full_name": full_name,
                    "phone": phone,
                    "password_hash": password_hash,
                    "location_enabled": location_enabled,
                    "latitude": latitude,
                    "longitude": longitude,
                    "location_accuracy_meters": location_accuracy_meters,
                    "expires_at": now + timedelta(minutes=expires_in_minutes),
                    "updated_at": now,
                },
                "$setOnInsert": {"created_at": now},
            },
            upsert=True,
        )

    async def get_valid_signup(self, *, email: str, now: datetime | None = None) -> dict | None:
        current_time = now or datetime.now(UTC)
        return await self.collection.find_one({"email": email, "expires_at": {"$gt": current_time}})

    async def delete_signup(self, *, email: str) -> None:
        await self.collection.delete_one({"email": email})
