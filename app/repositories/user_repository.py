from datetime import UTC, datetime
from typing import Any

from bson import ObjectId
from pymongo.collection import Collection
from pymongo.database import Database


class UserRepository:
    """Repository pattern for user persistence."""

    def __init__(self, db: Database):
        self.collection: Collection = db["users"]
        self.collection.create_index("email", unique=True, sparse=True)
        self.collection.create_index("phone", unique=True, sparse=True)
        self.collection.create_index("provider_user_id", unique=True, sparse=True)

    def _serialize(self, document: dict[str, Any] | None) -> dict[str, Any] | None:
        if not document:
            return None
        document["id"] = str(document.pop("_id"))
        return document

    def create_user(self, payload: dict[str, Any]) -> dict[str, Any]:
        now = datetime.now(UTC)
        payload["created_at"] = now
        payload["updated_at"] = now
        inserted = self.collection.insert_one(payload)
        created = self.collection.find_one({"_id": inserted.inserted_id})
        return self._serialize(created)  # type: ignore[return-value]

    def get_by_email(self, email: str) -> dict[str, Any] | None:
        return self._serialize(self.collection.find_one({"email": email}))

    def get_by_phone(self, phone: str) -> dict[str, Any] | None:
        return self._serialize(self.collection.find_one({"phone": phone}))

    def get_by_provider_user_id(self, provider_user_id: str) -> dict[str, Any] | None:
        return self._serialize(self.collection.find_one({"provider_user_id": provider_user_id}))

    def get_by_id(self, user_id: str) -> dict[str, Any] | None:
        return self._serialize(self.collection.find_one({"_id": ObjectId(user_id)}))

    def update_password_hash(self, user_id: str, password_hash: str) -> None:
        self.collection.update_one(
            {"_id": ObjectId(user_id)},
            {"$set": {"password_hash": password_hash, "updated_at": datetime.now(UTC)}},
        )

    def update_location_preference(self, user_id: str, enable_location: bool) -> dict[str, Any] | None:
        self.collection.update_one(
            {"_id": ObjectId(user_id)},
            {"$set": {"enable_location": enable_location, "updated_at": datetime.now(UTC)}},
        )
        return self.get_by_id(user_id)

