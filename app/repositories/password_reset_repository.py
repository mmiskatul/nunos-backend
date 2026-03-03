import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

from bson import ObjectId
from pymongo.collection import Collection
from pymongo.database import Database


class PasswordResetRepository:
    def __init__(self, db: Database):
        self.collection: Collection = db["password_reset_tokens"]
        self.collection.create_index("token", unique=True)
        self.collection.create_index("expires_at", expireAfterSeconds=0)

    def create_token(self, user_id: str, expires_in_minutes: int) -> str:
        token = secrets.token_urlsafe(32)
        expires_at = datetime.now(UTC) + timedelta(minutes=expires_in_minutes)
        self.collection.insert_one(
            {
                "token": token,
                "user_id": ObjectId(user_id),
                "expires_at": expires_at,
                "used": False,
                "created_at": datetime.now(UTC),
            }
        )
        return token

    def get_valid_token(self, token: str) -> dict[str, Any] | None:
        document = self.collection.find_one(
            {"token": token, "used": False, "expires_at": {"$gt": datetime.now(UTC)}}
        )
        return document

    def mark_used(self, token: str) -> None:
        self.collection.update_one({"token": token}, {"$set": {"used": True}})

