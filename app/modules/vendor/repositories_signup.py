import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

from pymongo.collection import Collection
from pymongo.database import Database


class VendorSignupVerificationRepository:
    def __init__(self, db: Database):
        self.code_collection: Collection = db["vendor_signup_codes"]
        self.token_collection: Collection = db["vendor_signup_tokens"]

    def create_validation_code(self, email: str, code_length: int, expires_in_minutes: int) -> str:
        max_code = 10**code_length
        code = f"{secrets.randbelow(max_code):0{code_length}d}"
        now = datetime.now(UTC)
        self.code_collection.update_one(
            {"email": email},
            {
                "$set": {
                    "code_hash": self._hash_code(email, code),
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

    def validate_and_consume_code(self, email: str, code: str, max_attempts: int = 5) -> bool:
        record = self.code_collection.find_one(
            {"email": email, "used": False, "expires_at": {"$gt": datetime.now(UTC)}}
        )
        if not record:
            return False

        if record.get("attempts", 0) >= max_attempts:
            self.code_collection.update_one(
                {"_id": record["_id"]},
                {"$set": {"used": True, "updated_at": datetime.now(UTC)}},
            )
            return False

        if record.get("code_hash") != self._hash_code(email, code):
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

    def create_signup_token(self, email: str, expires_in_minutes: int) -> str:
        token = secrets.token_urlsafe(32)
        self.token_collection.insert_one(
            {
                "token": token,
                "email": email,
                "used": False,
                "expires_at": datetime.now(UTC) + timedelta(minutes=expires_in_minutes),
                "created_at": datetime.now(UTC),
            }
        )
        return token

    def get_valid_signup_token(self, email: str, token: str) -> dict[str, Any] | None:
        return self.token_collection.find_one(
            {
                "token": token,
                "email": email,
                "used": False,
                "expires_at": {"$gt": datetime.now(UTC)},
            }
        )

    def mark_signup_token_used(self, token: str) -> None:
        self.token_collection.update_one({"token": token}, {"$set": {"used": True}})

    @staticmethod
    def _hash_code(email: str, code: str) -> str:
        return hashlib.sha256(f"{email}:{code}".encode("utf-8")).hexdigest()

