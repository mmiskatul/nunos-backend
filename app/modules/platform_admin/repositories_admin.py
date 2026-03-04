from datetime import UTC, datetime
from typing import Any

from bson import ObjectId
from pymongo.collection import Collection
from pymongo.database import Database


class PlatformAdminRepository:
    def __init__(self, db: Database):
        self.collection: Collection = db["platform_admins"]
        self.collection.create_index("email", unique=True, sparse=True)
        self.collection.create_index("phone", unique=True, sparse=True)

    def _serialize(self, document: dict[str, Any] | None) -> dict[str, Any] | None:
        if not document:
            return None
        document["id"] = str(document.pop("_id"))
        return document

    def create_admin(self, payload: dict[str, Any]) -> dict[str, Any]:
        now = datetime.now(UTC)
        insert_payload = {key: value for key, value in payload.items() if value is not None}
        insert_payload["created_at"] = now
        insert_payload["updated_at"] = now
        inserted = self.collection.insert_one(insert_payload)
        created = self.collection.find_one({"_id": inserted.inserted_id})
        return self._serialize(created)  # type: ignore[return-value]

    def get_by_email(self, email: str) -> dict[str, Any] | None:
        return self._serialize(self.collection.find_one({"email": email}))

    def get_by_phone(self, phone: str) -> dict[str, Any] | None:
        return self._serialize(self.collection.find_one({"phone": phone}))

    def get_by_id(self, admin_id: str) -> dict[str, Any] | None:
        return self._serialize(self.collection.find_one({"_id": ObjectId(admin_id)}))

    def update_password_hash(self, admin_id: str, password_hash: str) -> None:
        self.collection.update_one(
            {"_id": ObjectId(admin_id)},
            {"$set": {"password_hash": password_hash, "updated_at": datetime.now(UTC)}},
        )

