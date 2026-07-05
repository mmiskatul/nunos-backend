from datetime import UTC, datetime
from typing import Any

from bson import ObjectId
from pymongo.collection import Collection
from pymongo.database import Database


class VendorRepository:
    def __init__(self, db: Database):
        self.collection: Collection = db["vendors"]
        self.profile_collection: Collection = db["vendor_profiles"]
        self.business_collection: Collection = db["vendor_business_details"]
        self.verification_collection: Collection = db["vendor_verification_details"]
        self.admin_review_collection: Collection = db["vendor_admin_reviews"]

        self.collection.create_index("email", unique=True, sparse=True)
        try:
            self.collection.drop_index("phone_1")
        except Exception:
            pass
        self.collection.create_index("phone", sparse=True)
        self.collection.create_index("status")

        self.profile_collection.create_index("vendor_id", unique=True)
        self.business_collection.create_index("vendor_id", unique=True)
        self.verification_collection.create_index("vendor_id", unique=True)
        self.admin_review_collection.create_index("vendor_id", unique=True)
        self.admin_review_collection.create_index("review_status")

    def _serialize(self, document: dict[str, Any] | None) -> dict[str, Any] | None:
        if not document:
            return None
        document["id"] = str(document.pop("_id"))
        return document

    def create_vendor(self, payload: dict[str, Any]) -> dict[str, Any]:
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

    def get_by_id(self, vendor_id: str) -> dict[str, Any] | None:
        return self._serialize(self.collection.find_one({"_id": ObjectId(vendor_id)}))

    def list_vendors(
        self,
        limit: int = 50,
        skip: int = 0,
        search: str | None = None,
        status: str | None = None,
    ) -> list[dict[str, Any]]:
        query = self._build_vendor_query(search=search, status=status)
        cursor = self.collection.find(query).sort("created_at", -1).skip(skip).limit(limit)
        rows = [self._serialize(doc) for doc in cursor if doc]  # type: ignore[list-item]
        for row in rows:
            row["sections"] = self.get_vendor_sections(row["id"])
        return rows

    def count_vendors(self, search: str | None = None, status: str | None = None) -> int:
        query = self._build_vendor_query(search=search, status=status)
        return int(self.collection.count_documents(query))

    def list_by_status(self, status: str, limit: int = 50, skip: int = 0) -> list[dict[str, Any]]:
        return self.list_vendors(limit=limit, skip=skip, status=status)

    def update_password_hash(self, vendor_id: str, password_hash: str) -> None:
        self.collection.update_one(
            {"_id": ObjectId(vendor_id)},
            {"$set": {"password_hash": password_hash, "updated_at": datetime.now(UTC)}},
        )

    def upsert_kyc(self, vendor_id: str, payload: dict[str, Any]) -> None:
        now = datetime.now(UTC)
        vendor_obj_id = ObjectId(vendor_id)
        self.collection.update_one(
            {"_id": vendor_obj_id},
            {
                "$set": {
                    "kyc_status": "pending_review",
                    "kyc_submitted_at": now,
                    "updated_at": now,
                }
            },
        )
        self.verification_collection.update_one(
            {"vendor_id": vendor_obj_id},
            {
                "$set": {
                    "category": payload.get("category"),
                    "trade_license_number": payload.get("trade_license_number"),
                    "document_urls": payload.get("document_urls", []),
                    "status": "pending_review",
                    "submitted_at": now,
                    "reviewed_at": None,
                    "rejection_reason": None,
                    "updated_at": now,
                }
            },
            upsert=True,
        )
        self.admin_review_collection.update_one(
            {"vendor_id": vendor_obj_id},
            {
                "$set": {
                    "review_status": "pending_review",
                    "reviewed_at": None,
                    "rejection_reason": None,
                    "updated_at": now,
                },
                "$setOnInsert": {"created_at": now},
            },
            upsert=True,
        )

    def get_kyc_status(self, vendor_id: str) -> dict[str, Any] | None:
        vendor_obj_id = ObjectId(vendor_id)
        vendor = self.collection.find_one({"_id": vendor_obj_id})
        if not vendor:
            return None
        verification = self.verification_collection.find_one({"vendor_id": vendor_obj_id}) or {}
        return {
            "kyc_status": verification.get("status", vendor.get("kyc_status", "not_submitted")),
            "submitted_at": verification.get("submitted_at", vendor.get("kyc_submitted_at")),
            "reviewed_at": verification.get("reviewed_at", vendor.get("kyc_reviewed_at")),
            "rejection_reason": verification.get("rejection_reason", vendor.get("kyc_rejection_reason")),
        }

    def set_verification_decision(self, vendor_id: str, decision: str, reason: str | None = None) -> dict[str, Any] | None:
        now = datetime.now(UTC)
        vendor_obj_id = ObjectId(vendor_id)
        decision_normalized = decision.lower()
        if decision_normalized == "approved":
            set_payload: dict[str, Any] = {
                "status": "approved",
                "kyc_status": "approved",
                "kyc_reviewed_at": now,
                "kyc_rejection_reason": None,
                "updated_at": now,
            }
            verification_status = "approved"
            rejection_reason = None
        elif decision_normalized == "blocked":
            set_payload = {
                "status": "blocked",
                "kyc_status": "blocked",
                "kyc_reviewed_at": now,
                "kyc_rejection_reason": reason or "Blocked by admin.",
                "updated_at": now,
            }
            verification_status = "blocked"
            rejection_reason = reason or "Blocked by admin."
        elif decision_normalized in {"cancel", "cancelled", "canceled"}:
            set_payload = {
                "status": "pending_approval",
                "kyc_status": "pending_review",
                "kyc_reviewed_at": None,
                "kyc_rejection_reason": None,
                "updated_at": now,
            }
            verification_status = "pending_review"
            rejection_reason = None
        else:
            set_payload = {
                "status": "rejected",
                "kyc_status": "rejected",
                "kyc_reviewed_at": now,
                "kyc_rejection_reason": reason or "Rejected by admin.",
                "updated_at": now,
            }
            verification_status = "rejected"
            rejection_reason = reason or "Rejected by admin."
        self.collection.update_one({"_id": vendor_obj_id}, {"$set": set_payload})
        self.verification_collection.update_one(
            {"vendor_id": vendor_obj_id},
            {
                "$set": {
                    "status": verification_status,
                    "reviewed_at": None if decision_normalized in {"cancel", "cancelled", "canceled"} else now,
                    "rejection_reason": rejection_reason,
                    "updated_at": now,
                }
            },
            upsert=True,
        )
        self.admin_review_collection.update_one(
            {"vendor_id": vendor_obj_id},
            {
                "$set": {
                    "review_status": verification_status,
                    "reviewed_at": None if decision_normalized in {"cancel", "cancelled", "canceled"} else now,
                    "rejection_reason": rejection_reason,
                    "updated_at": now,
                },
                "$setOnInsert": {"created_at": now},
            },
            upsert=True,
        )
        return self.get_by_id(vendor_id)

    def update_status(self, vendor_id: str, status: str, reason: str | None = None) -> dict[str, Any] | None:
        return self.set_verification_decision(vendor_id=vendor_id, decision=status, reason=reason)

    def create_vendor_sections(
        self,
        vendor_id: str,
        profile_payload: dict[str, Any],
        business_payload: dict[str, Any],
        verification_payload: dict[str, Any],
    ) -> None:
        now = datetime.now(UTC)
        vendor_obj_id = ObjectId(vendor_id)
        self.profile_collection.update_one(
            {"vendor_id": vendor_obj_id},
            {"$set": {"vendor_id": vendor_obj_id, **profile_payload, "updated_at": now}, "$setOnInsert": {"created_at": now}},
            upsert=True,
        )
        self.business_collection.update_one(
            {"vendor_id": vendor_obj_id},
            {"$set": {"vendor_id": vendor_obj_id, **business_payload, "updated_at": now}, "$setOnInsert": {"created_at": now}},
            upsert=True,
        )
        self.verification_collection.update_one(
            {"vendor_id": vendor_obj_id},
            {
                "$set": {
                    "vendor_id": vendor_obj_id,
                    **verification_payload,
                    "status": "pending_review",
                    "submitted_at": now,
                    "reviewed_at": None,
                    "rejection_reason": None,
                    "updated_at": now,
                },
                "$setOnInsert": {"created_at": now},
            },
            upsert=True,
        )
        self.admin_review_collection.update_one(
            {"vendor_id": vendor_obj_id},
            {
                "$set": {
                    "vendor_id": vendor_obj_id,
                    "review_status": "pending_review",
                    "reviewed_at": None,
                    "rejection_reason": None,
                    "updated_at": now,
                },
                "$setOnInsert": {"created_at": now},
            },
            upsert=True,
        )

    def get_vendor_sections(self, vendor_id: str) -> dict[str, Any]:
        vendor_obj_id = ObjectId(vendor_id)
        profile = self.profile_collection.find_one({"vendor_id": vendor_obj_id}) or {}
        business = self.business_collection.find_one({"vendor_id": vendor_obj_id}) or {}
        verification = self.verification_collection.find_one({"vendor_id": vendor_obj_id}) or {}
        admin_review = self.admin_review_collection.find_one({"vendor_id": vendor_obj_id}) or {}
        for section in (profile, business, verification, admin_review):
            section.pop("_id", None)
            section.pop("vendor_id", None)
        return {
            "profile": profile,
            "business": business,
            "verification": verification,
            "admin_review": admin_review,
        }

    def get_vendor_application(self, vendor_id: str) -> dict[str, Any] | None:
        vendor = self.get_by_id(vendor_id)
        if not vendor:
            return None
        return {
            "vendor": vendor,
            "sections": self.get_vendor_sections(vendor_id),
        }

    @staticmethod
    def _build_vendor_query(search: str | None = None, status: str | None = None) -> dict[str, Any]:
        query: dict[str, Any] = {}
        if search:
            escaped = search.strip()
            if escaped:
                query["$or"] = [
                    {"business_name": {"$regex": escaped, "$options": "i"}},
                    {"owner_full_name": {"$regex": escaped, "$options": "i"}},
                    {"email": {"$regex": escaped, "$options": "i"}},
                    {"phone": {"$regex": escaped, "$options": "i"}},
                ]
        if status:
            query["status"] = status
        return query
