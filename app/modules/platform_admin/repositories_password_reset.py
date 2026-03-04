import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

from bson import ObjectId
from pymongo.collection import Collection
from pymongo.database import Database


class AdminPasswordResetRepository:
    def __init__(self, db: Database):
        self.code_collection: Collection = db["platform_admin_password_reset_codes"]
        self.token_collection: Collection = db["platform_admin_password_reset_tokens"]
        self.code_collection.create_index("admin_id", unique=True)
        self.code_collection.create_index("expires_at", expireAfterSeconds=0)
        self.token_collection.create_index("token", unique=True)
        self.token_collection.create_index("expires_at", expireAfterSeconds=0)

    def create_validation_code(self, admin_id: str, code_length: int, expires_in_minutes: int) -> str:
        max_code = 10**code_length
        code = f"{secrets.randbelow(max_code):0{code_length}d}"
        now = datetime.now(UTC)
        self.code_collection.update_one(
            {"admin_id": ObjectId(admin_id)},
            {
                "$set": {
                    "code_hash": self._hash_code(admin_id, code),
                    "expires_at": now + timedelta(minutes=expires_in_minutes),
                    "used": False,
                    "attempts": 0,
                    "updated_at": now,
                },
                "$setOnInsert": {"created_at": now},
            },
            upsert=True,
        )
        return code

    def validate_and_consume_code(self, admin_id: str, code: str, max_attempts: int = 5) -> bool:
        record = self.code_collection.find_one(
            {"admin_id": ObjectId(admin_id), "used": False, "expires_at": {"$gt": datetime.now(UTC)}}
        )
        if not record:
            return False

        if record.get("attempts", 0) >= max_attempts:
            self.code_collection.update_one(
                {"_id": record["_id"]},
                {"$set": {"used": True, "updated_at": datetime.now(UTC)}},
            )
            return False

        if record.get("code_hash") != self._hash_code(admin_id, code):
            self.code_collection.update_one(
                {"_id": record["_id"]},
                {"$inc": {"attempts": 1}, "$set": {"updated_at": datetime.now(UTC)}},
            )
            return False

        self.code_collection.update_one(
            {"_id": record["_id"]},
            {"$set": {"used": True, "updated_at": datetime.now(UTC)}},
        )
        return True

    def create_reset_token(self, admin_id: str, expires_in_minutes: int) -> str:
        token = secrets.token_urlsafe(32)
        self.token_collection.insert_one(
            {
                "token": token,
                "admin_id": ObjectId(admin_id),
                "used": False,
                "expires_at": datetime.now(UTC) + timedelta(minutes=expires_in_minutes),
                "created_at": datetime.now(UTC),
            }
        )
        return token

    def get_valid_reset_token(self, token: str) -> dict[str, Any] | None:
        return self.token_collection.find_one(
            {"token": token, "used": False, "expires_at": {"$gt": datetime.now(UTC)}}
        )

    def mark_reset_token_used(self, token: str) -> None:
        self.token_collection.update_one({"token": token}, {"$set": {"used": True}})

    @staticmethod
    def _hash_code(admin_id: str, code: str) -> str:
        return hashlib.sha256(f"{admin_id}:{code}".encode("utf-8")).hexdigest()

