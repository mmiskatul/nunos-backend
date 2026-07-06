from datetime import UTC, datetime, timedelta
from typing import Any

from bson import ObjectId
from pymongo import DESCENDING
from pymongo.collection import Collection
from pymongo.database import Database


class VendorPortalRepository:
    def __init__(self, db: Database):
        self.bookings: Collection = db["vendor_bookings"]
        self.assets: Collection = db["vendor_assets"]
        self.rooms: Collection = db["vendor_rooms"]
        self.services: Collection = db["vendor_services"]
        self.events: Collection = db["vendor_events"]
        self.promotions: Collection = db["vendor_promotions"]
        self.platform_campaigns: Collection = db["platform_campaigns"]
        self.loyalty_settings: Collection = db["vendor_loyalty_settings"]
        self.reviews: Collection = db["vendor_reviews"]
        self.settings: Collection = db["vendor_portal_settings"]
        self.support_tickets: Collection = db["vendor_support_tickets"]
        self.notifications: Collection = db["vendor_notifications"]
        self.notification_settings: Collection = db["vendor_notification_settings"]

        self.bookings.create_index([("vendor_id", 1), ("scheduled_date", 1), ("status", 1)])
        self.bookings.create_index([("vendor_id", 1), ("customer_email", 1)])
        self.bookings.create_index([("vendor_id", 1), ("customer_phone", 1)])
        self.assets.create_index([("vendor_id", 1), ("asset_type", 1), ("created_at", -1)])
        self.rooms.create_index([("vendor_id", 1), ("created_at", -1)])
        self.services.create_index([("vendor_id", 1), ("created_at", -1)])
        self.events.create_index([("vendor_id", 1), ("event_date", 1), ("start_time", 1)])
        self.events.create_index([("vendor_id", 1), ("status", 1), ("created_at", -1)])
        self.events.create_index([("vendor_id", 1), ("category", 1), ("created_at", -1)])
        self.promotions.create_index([("vendor_id", 1), ("created_at", -1)])
        self.promotions.create_index([("vendor_id", 1), ("active", 1)])
        self.platform_campaigns.create_index([("active", 1), ("created_at", -1)])
        self.reviews.create_index([("vendor_id", 1), ("created_at", -1)])
        self.reviews.create_index([("vendor_id", 1), ("rating", -1)])
        self.support_tickets.create_index([("vendor_id", 1), ("created_at", -1)])
        self.notifications.create_index([("vendor_id", 1), ("created_at", -1)])
        self.settings.create_index("vendor_id", unique=True)
        self.notification_settings.create_index("vendor_id", unique=True)

    @staticmethod
    def _sanitize_payload(payload: dict[str, Any]) -> dict[str, Any]:
        blocked_keys = {"_id", "id", "vendor_id", "created_at", "updated_at"}
        return {key: value for key, value in payload.items() if key not in blocked_keys}

    @staticmethod
    def _to_float(value: Any, default: float = 0.0) -> float:
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            cleaned = "".join(char for char in value if char.isdigit() or char in ".-")
            if cleaned:
                try:
                    return float(cleaned)
                except ValueError:
                    return default
        return default

    @classmethod
    def _to_int(cls, value: Any, default: int = 0) -> int:
        return int(round(cls._to_float(value, float(default))))

    @staticmethod
    def _promotion_type_label(offer_type: str) -> str:
        normalized = offer_type.strip().lower()
        if normalized == "fixed_amount":
            return "FIXED"
        if normalized == "happy_hour":
            return "HAPPY HOUR"
        if normalized == "custom_deal":
            return "CUSTOM DEAL"
        return normalized.replace("_", " ").upper() or "PERCENTAGE"

    def _allowed_vendor_categories(self, vendor_id: str) -> list[str]:
        vendor, profile, business, verification = self._get_vendor_records(vendor_id)
        for source in (profile, verification, vendor, business):
            categories = source.get("categories")
            if isinstance(categories, list):
                normalized = [str(item).strip() for item in categories if str(item).strip()]
                if normalized:
                    return list(dict.fromkeys(normalized))
        for source in (profile, verification, vendor, business):
            category = str(source.get("category") or "").strip()
            if category:
                return [category]
        return ["Restaurant"]

    def _validate_vendor_category_access(self, vendor_id: str, category: str) -> None:
        allowed_categories = self._allowed_vendor_categories(vendor_id)
        if category not in allowed_categories:
            raise ValueError(
                f"Category '{category}' is not enabled for this vendor. Allowed categories: {', '.join(allowed_categories)}."
            )

    @staticmethod
    def _build_location_label(category: str) -> str:
        normalized_category = str(category or "").strip().lower()
        if not normalized_category:
            return "Your location"
        return f"Your {normalized_category} location"

    @classmethod
    def _normalize_location_label(cls, label: Any, category: str) -> str:
        normalized_label = str(label or "").strip()
        if not normalized_label:
            return cls._build_location_label(category)
        if normalized_label.lower() in {"test", "testing", "sample", "demo"}:
            return cls._build_location_label(category)
        return normalized_label

    @classmethod
    def _promotion_value_label(cls, row: dict[str, Any]) -> str:
        offer_type = str(row.get("offer_type", "")).strip().lower()
        discount_value = cls._to_float(row.get("discount_value"))
        if offer_type == "percentage":
            return f"{discount_value:g}% Off"
        if offer_type == "fixed_amount":
            return f"${discount_value:,.2f} Off"
        if offer_type == "happy_hour":
            return f"${discount_value:,.2f} Happy Hour"
        if discount_value > 0:
            return f"${discount_value:,.2f}"
        return str(row.get("value") or "").strip()

    @staticmethod
    def _promotion_schedule_label(row: dict[str, Any]) -> str:
        recurring_days = row.get("recurring_days")
        if isinstance(recurring_days, list):
            days = [str(day).strip() for day in recurring_days if str(day).strip()]
            if days:
                return " - ".join(days)
        start_date = str(row.get("start_date") or "").strip()
        end_date = str(row.get("end_date") or "").strip()
        if start_date and end_date:
            return f"{start_date} - {end_date}"
        return start_date or end_date or "No schedule"

    @classmethod
    def _normalize_promotion_row(cls, row: dict[str, Any]) -> dict[str, Any]:
        normalized = dict(row)
        usage_count = cls._to_int(
            row.get("usage_count", row.get("usageCount", row.get("redemptions", 0))),
        )
        usage_max = cls._to_int(
            row.get("usage_max", row.get("usageMax", row.get("campaign_reach", 0))),
        )
        normalized["name"] = row.get("name") or row.get("promotion_name") or ""
        normalized["description"] = row.get("description") or row.get("internal_description") or ""
        normalized["type"] = row.get("type") or cls._promotion_type_label(str(row.get("offer_type", "percentage")))
        normalized["value"] = row.get("value") or cls._promotion_value_label(row)
        normalized["schedule"] = row.get("schedule") or cls._promotion_schedule_label(row)
        normalized["usage_count"] = usage_count
        normalized["usage_max"] = max(usage_max, usage_count)
        normalized["is_active"] = bool(row.get("is_active", row.get("active", False)))
        return normalized

    @classmethod
    def summarize_promotions(cls, promotions: list[dict[str, Any]]) -> dict[str, Any]:
        active_promotions = 0
        campaign_reach = 0
        total_conversion = 0.0
        conversion_bases = 0
        total_promo_revenue = 0.0

        for row in promotions:
            if bool(row.get("active")):
                active_promotions += 1

            usage_count = cls._to_int(row.get("usage_count", row.get("usageCount", row.get("redemptions", 0))))
            usage_max = cls._to_int(row.get("usage_max", row.get("usageMax", row.get("campaign_reach", 0))))
            campaign_reach += max(usage_max, usage_count)

            if usage_max > 0:
                total_conversion += (usage_count / usage_max) * 100
                conversion_bases += 1

            explicit_revenue = row.get("total_promo_revenue", row.get("promo_revenue", row.get("revenue_generated")))
            if explicit_revenue not in (None, ""):
                total_promo_revenue += cls._to_float(explicit_revenue)
                continue

            discount_value = cls._to_float(row.get("discount_value"))
            minimum_spend = cls._to_float(row.get("minimum_spend"))
            offer_type = str(row.get("offer_type", "")).strip().lower()
            if offer_type == "percentage" and minimum_spend > 0:
                total_promo_revenue += usage_count * ((minimum_spend * discount_value) / 100)
            elif offer_type == "fixed_amount":
                total_promo_revenue += usage_count * discount_value

        avg_conversion_percent = round(total_conversion / conversion_bases, 1) if conversion_bases else 0.0
        return {
            "total_promotions": len(promotions),
            "active_promotions": active_promotions,
            "campaign_reach": campaign_reach,
            "avg_conversion_percent": avg_conversion_percent,
            "total_promo_revenue": round(total_promo_revenue, 2),
        }

    def ensure_seed_data(self, vendor_id: str) -> None:
        _ = vendor_id
        # Demo/static seeding is intentionally disabled.
        return None

    def _get_vendor_records(self, vendor_id: str) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
        vendor_obj_id = ObjectId(vendor_id)
        vendor = self.settings.database["vendors"].find_one({"_id": vendor_obj_id}) or {}
        profile = self.settings.database["vendor_profiles"].find_one({"vendor_id": vendor_obj_id}) or {}
        business = self.settings.database["vendor_business_details"].find_one({"vendor_id": vendor_obj_id}) or {}
        verification = self.settings.database["vendor_verification_details"].find_one({"vendor_id": vendor_obj_id}) or {}
        for record in (vendor, profile, business, verification):
            record.pop("_id", None)
            record.pop("vendor_id", None)
            record.pop("password_hash", None)
        return vendor, profile, business, verification

    def _serialize(self, doc: dict[str, Any] | None) -> dict[str, Any] | None:
        if not doc:
            return None
        out = dict(doc)
        if out.get("_id") is not None:
            out["id"] = str(out.pop("_id"))
        if isinstance(out.get("vendor_id"), ObjectId):
            out["vendor_id"] = str(out["vendor_id"])
        for key, value in list(out.items()):
            if isinstance(value, datetime):
                out[key] = value.isoformat()
            if isinstance(value, ObjectId):
                out[key] = str(value)
        return out

    def list_bookings(
        self,
        vendor_id: str,
        limit: int,
        skip: int,
        search: str | None = None,
        status: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
    ) -> dict[str, Any]:
        query: dict[str, Any] = {"vendor_id": ObjectId(vendor_id)}
        if search:
            query["$or"] = [
                {"booking_code": {"$regex": search, "$options": "i"}},
                {"customer_name": {"$regex": search, "$options": "i"}},
            ]
        if status and status.lower() not in {"all", ""}:
            status_norm = status.strip().lower()
            if status_norm in {"cancelled", "canceled"}:
                query["status"] = "canceled"
            elif status_norm == "completed":
                query["status"] = "complete"
            elif status_norm == "upcoming":
                query["status"] = {"$in": ["confirmed", "pending", "check_in"]}
            else:
                query["status"] = status_norm
        if date_from or date_to:
            range_q: dict[str, Any] = {}
            if date_from:
                range_q["$gte"] = date_from
            if date_to:
                range_q["$lte"] = date_to
            query["scheduled_date"] = range_q
        total = int(self.bookings.count_documents(query))
        docs = self.bookings.find(query).sort("created_at", DESCENDING).skip(skip).limit(limit)
        return {"items": [self._serialize(doc) for doc in docs], "total": total}

    def get_booking(self, vendor_id: str, booking_id: str) -> dict[str, Any] | None:
        return self._serialize(
            self.bookings.find_one({"_id": ObjectId(booking_id), "vendor_id": ObjectId(vendor_id)})
        )

    def update_booking_status(self, vendor_id: str, booking_id: str, status: str, note: str | None = None) -> dict[str, Any] | None:
        status_normalized = status.lower().strip()
        if status_normalized == "cancelled":
            status_normalized = "canceled"
        payload: dict[str, Any] = {"status": status_normalized, "updated_at": datetime.now(UTC)}
        if note:
            payload["status_note"] = note
        self.bookings.update_one(
            {"_id": ObjectId(booking_id), "vendor_id": ObjectId(vendor_id)},
            {"$set": payload},
        )
        return self.get_booking(vendor_id, booking_id)

    def reschedule_booking(self, vendor_id: str, booking_id: str, date: str, time: str, note: str | None = None) -> dict[str, Any] | None:
        payload: dict[str, Any] = {"scheduled_date": date, "scheduled_time": time, "updated_at": datetime.now(UTC)}
        if note:
            payload["reschedule_note"] = note
        self.bookings.update_one(
            {"_id": ObjectId(booking_id), "vendor_id": ObjectId(vendor_id)},
            {"$set": payload},
        )
        return self.get_booking(vendor_id, booking_id)

    def generate_receipt(self, vendor_id: str, booking_id: str) -> dict[str, Any] | None:
        booking = self.get_booking(vendor_id, booking_id)
        if not booking:
            return None
        subtotal = float(booking.get("total_amount", 0))
        taxes = round(subtotal * 0.05, 2)
        return {
            "booking_id": booking.get("id"),
            "booking_code": booking.get("booking_code"),
            "customer_name": booking.get("customer_name"),
            "service": booking.get("service"),
            "subtotal": subtotal,
            "taxes": taxes,
            "total": round(subtotal + taxes, 2),
            "generated_at": datetime.now(UTC).isoformat(),
        }

    def get_dashboard_overview(self, vendor_id: str) -> dict[str, Any]:
        today = datetime.now(UTC).date().isoformat()
        month_key = datetime.now(UTC).strftime("%Y-%m")
        bookings = list(self.bookings.find({"vendor_id": ObjectId(vendor_id)}))
        reviews = list(self.reviews.find({"vendor_id": ObjectId(vendor_id)}))
        kpis = {
            "total_bookings_month": sum(1 for b in bookings if str(b.get("scheduled_date", "")).startswith(month_key)),
            "todays_bookings": sum(1 for b in bookings if b.get("scheduled_date") == today),
            "monthly_revenue": round(
                sum(float(b.get("total_amount", 0)) for b in bookings if str(b.get("scheduled_date", "")).startswith(month_key)),
                2,
            ),
            "occupancy_rate": self.get_occupancy_metrics(vendor_id).get("occupancy_rate", 0),
            "average_rating": round(
                (sum(float(r.get("rating", 0)) for r in reviews) / len(reviews)) if reviews else 0.0,
                1,
            ),
        }
        return {
            "kpis": kpis,
            "booking_trends": self.get_booking_trends(vendor_id),
            "calendar_preview": self.get_calendar_preview(vendor_id),
            "upcoming_bookings": self.list_bookings(vendor_id, limit=10, skip=0, status="confirmed").get("items", []),
            "recent_reviews": self.list_reviews(vendor_id, limit=5, skip=0).get("items", []),
        }

    def get_booking_trends(self, vendor_id: str) -> list[dict[str, Any]]:
        buckets: dict[str, int] = {}
        for b in self.bookings.find({"vendor_id": ObjectId(vendor_id)}, {"scheduled_date": 1}):
            month = str(b.get("scheduled_date", ""))[:7]
            if month:
                buckets[month] = buckets.get(month, 0) + 1
        now = datetime.now(UTC)
        points: list[dict[str, Any]] = []
        for i in range(11, -1, -1):
            dt = (now.replace(day=1) - timedelta(days=32 * i)).replace(day=1)
            key = dt.strftime("%Y-%m")
            points.append({"month": dt.strftime("%b"), "bookings": buckets.get(key, 0)})
        return points

    def get_calendar_preview(self, vendor_id: str) -> dict[str, Any]:
        month_key = datetime.now(UTC).strftime("%Y-%m")
        counts: dict[int, int] = {}
        for b in self.bookings.find(
            {"vendor_id": ObjectId(vendor_id), "scheduled_date": {"$regex": f"^{month_key}"}},
            {"scheduled_date": 1},
        ):
            day = int(str(b["scheduled_date"]).split("-")[-1])
            counts[day] = counts.get(day, 0) + 1
        return {"month": month_key, "busy_days": [{"day": d, "count": c} for d, c in sorted(counts.items())]}

    def list_assets(self, vendor_id: str, asset_type: str | None = None) -> list[dict[str, Any]]:
        query: dict[str, Any] = {"vendor_id": ObjectId(vendor_id)}
        if asset_type:
            query["asset_type"] = asset_type
        docs = self.assets.find(query).sort("created_at", DESCENDING)
        return [self._serialize(doc) for doc in docs]

    def add_asset(self, vendor_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        sanitized = self._sanitize_payload(payload)
        inserted = self.assets.insert_one(
            {"vendor_id": ObjectId(vendor_id), **sanitized, "created_at": datetime.now(UTC)}
        )
        created = self.assets.find_one({"_id": inserted.inserted_id})
        return self._serialize(created)  # type: ignore[return-value]

    def delete_asset(self, vendor_id: str, asset_id: str) -> bool:
        result = self.assets.delete_one({"_id": ObjectId(asset_id), "vendor_id": ObjectId(vendor_id)})
        return result.deleted_count > 0

    def list_rooms(self, vendor_id: str) -> list[dict[str, Any]]:
        docs = self.rooms.find({"vendor_id": ObjectId(vendor_id)}).sort("created_at", DESCENDING)
        return [self._serialize(doc) for doc in docs]

    def create_room(self, vendor_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        now = datetime.now(UTC)
        sanitized = self._sanitize_payload(payload)
        inserted = self.rooms.insert_one(
            {
                "vendor_id": ObjectId(vendor_id),
                **sanitized,
                "available": sanitized.get("active_status", True),
                "created_at": now,
                "updated_at": now,
            }
        )
        created = self.rooms.find_one({"_id": inserted.inserted_id})
        return self._serialize(created)  # type: ignore[return-value]

    def get_room(self, vendor_id: str, room_id: str) -> dict[str, Any] | None:
        return self._serialize(
            self.rooms.find_one({"_id": ObjectId(room_id), "vendor_id": ObjectId(vendor_id)})
        )

    def update_room(self, vendor_id: str, room_id: str, payload: dict[str, Any]) -> dict[str, Any] | None:
        sanitized = self._sanitize_payload(payload)
        self.rooms.update_one(
            {"_id": ObjectId(room_id), "vendor_id": ObjectId(vendor_id)},
            {"$set": {**sanitized, "updated_at": datetime.now(UTC)}},
        )
        return self.get_room(vendor_id, room_id)

    def update_room_availability(
        self,
        vendor_id: str,
        room_id: str,
        available: bool,
        maintenance_note: str | None = None,
    ) -> dict[str, Any] | None:
        self.rooms.update_one(
            {"_id": ObjectId(room_id), "vendor_id": ObjectId(vendor_id)},
            {"$set": {"available": available, "maintenance_note": maintenance_note, "updated_at": datetime.now(UTC)}},
        )
        return self.get_room(vendor_id, room_id)

    def delete_room(self, vendor_id: str, room_id: str) -> bool:
        result = self.rooms.delete_one({"_id": ObjectId(room_id), "vendor_id": ObjectId(vendor_id)})
        return result.deleted_count > 0

    def list_services(self, vendor_id: str) -> list[dict[str, Any]]:
        docs = self.services.find({"vendor_id": ObjectId(vendor_id)}).sort("created_at", DESCENDING)
        return [self._serialize(doc) for doc in docs]

    def create_service(self, vendor_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        now = datetime.now(UTC)
        sanitized = self._sanitize_payload(payload)
        inserted = self.services.insert_one(
            {
                "vendor_id": ObjectId(vendor_id),
                **sanitized,
                "available": sanitized.get("active_status", True),
                "created_at": now,
                "updated_at": now,
            }
        )
        created = self.services.find_one({"_id": inserted.inserted_id})
        return self._serialize(created)  # type: ignore[return-value]

    def list_events(
        self,
        vendor_id: str,
        search: str | None = None,
        status: str | None = None,
        category: str | None = None,
    ) -> list[dict[str, Any]]:
        query: dict[str, Any] = {"vendor_id": ObjectId(vendor_id)}
        if search:
            query["$or"] = [
                {"title": {"$regex": search, "$options": "i"}},
                {"venue": {"$regex": search, "$options": "i"}},
                {"event_type": {"$regex": search, "$options": "i"}},
            ]
        if status and status.lower() not in {"all", ""}:
            query["status"] = status.strip().lower()
        if category and category.lower() not in {"all", ""}:
            query["category"] = category.strip()
        docs = self.events.find(query).sort([("event_date", 1), ("start_time", 1), ("created_at", DESCENDING)])
        return [self._serialize(doc) for doc in docs]

    def create_event(self, vendor_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        now = datetime.now(UTC)
        sanitized = self._sanitize_payload(payload)
        category = str(sanitized.get("category") or "").strip()
        self._validate_vendor_category_access(vendor_id, category)
        inserted = self.events.insert_one(
            {
                "vendor_id": ObjectId(vendor_id),
                **sanitized,
                "status": str(sanitized.get("status") or "draft").lower(),
                "active": bool(sanitized.get("active_status", True)),
                "created_at": now,
                "updated_at": now,
            }
        )
        created = self.events.find_one({"_id": inserted.inserted_id})
        return self._serialize(created)  # type: ignore[return-value]

    def get_event(self, vendor_id: str, event_id: str) -> dict[str, Any] | None:
        return self._serialize(
            self.events.find_one({"_id": ObjectId(event_id), "vendor_id": ObjectId(vendor_id)})
        )

    def update_event(self, vendor_id: str, event_id: str, payload: dict[str, Any]) -> dict[str, Any] | None:
        sanitized = self._sanitize_payload(payload)
        category = str(sanitized.get("category") or "").strip()
        if category:
            self._validate_vendor_category_access(vendor_id, category)
        if "status" in sanitized:
            sanitized["status"] = str(sanitized["status"]).lower()
        if "active_status" in sanitized:
            sanitized["active"] = bool(sanitized["active_status"])
        self.events.update_one(
            {"_id": ObjectId(event_id), "vendor_id": ObjectId(vendor_id)},
            {"$set": {**sanitized, "updated_at": datetime.now(UTC)}},
        )
        return self.get_event(vendor_id, event_id)

    def update_event_status(self, vendor_id: str, event_id: str, status: str) -> dict[str, Any] | None:
        normalized = status.strip().lower()
        self.events.update_one(
            {"_id": ObjectId(event_id), "vendor_id": ObjectId(vendor_id)},
            {"$set": {"status": normalized, "updated_at": datetime.now(UTC)}},
        )
        return self.get_event(vendor_id, event_id)

    def delete_event(self, vendor_id: str, event_id: str) -> bool:
        result = self.events.delete_one({"_id": ObjectId(event_id), "vendor_id": ObjectId(vendor_id)})
        return result.deleted_count > 0

    def get_service(self, vendor_id: str, service_id: str) -> dict[str, Any] | None:
        return self._serialize(
            self.services.find_one({"_id": ObjectId(service_id), "vendor_id": ObjectId(vendor_id)})
        )

    def update_service(self, vendor_id: str, service_id: str, payload: dict[str, Any]) -> dict[str, Any] | None:
        sanitized = self._sanitize_payload(payload)
        self.services.update_one(
            {"_id": ObjectId(service_id), "vendor_id": ObjectId(vendor_id)},
            {"$set": {**sanitized, "updated_at": datetime.now(UTC)}},
        )
        return self.get_service(vendor_id, service_id)

    def update_service_status(self, vendor_id: str, service_id: str, active: bool) -> dict[str, Any] | None:
        self.services.update_one(
            {"_id": ObjectId(service_id), "vendor_id": ObjectId(vendor_id)},
            {"$set": {"available": active, "updated_at": datetime.now(UTC)}},
        )
        return self.get_service(vendor_id, service_id)

    def delete_service(self, vendor_id: str, service_id: str) -> bool:
        result = self.services.delete_one({"_id": ObjectId(service_id), "vendor_id": ObjectId(vendor_id)})
        return result.deleted_count > 0

    def list_promotions(
        self, vendor_id: str, search: str | None = None, active: bool | None = None
    ) -> list[dict[str, Any]]:
        query: dict[str, Any] = {"vendor_id": ObjectId(vendor_id)}
        if search:
            query["promotion_name"] = {"$regex": search, "$options": "i"}
        if active is not None:
            query["active"] = active
        docs = self.promotions.find(query).sort("created_at", DESCENDING)
        return [self._normalize_promotion_row(self._serialize(doc) or {}) for doc in docs]

    def create_promotion(self, vendor_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        now = datetime.now(UTC)
        sanitized = self._sanitize_payload(payload)
        inserted = self.promotions.insert_one(
            {"vendor_id": ObjectId(vendor_id), **sanitized, "created_at": now, "updated_at": now}
        )
        created = self.promotions.find_one({"_id": inserted.inserted_id})
        return self._serialize(created)  # type: ignore[return-value]

    def get_promotion(self, vendor_id: str, promotion_id: str) -> dict[str, Any] | None:
        return self._serialize(
            self.promotions.find_one({"_id": ObjectId(promotion_id), "vendor_id": ObjectId(vendor_id)})
        )

    def update_promotion(self, vendor_id: str, promotion_id: str, payload: dict[str, Any]) -> dict[str, Any] | None:
        sanitized = self._sanitize_payload(payload)
        self.promotions.update_one(
            {"_id": ObjectId(promotion_id), "vendor_id": ObjectId(vendor_id)},
            {"$set": {**sanitized, "updated_at": datetime.now(UTC)}},
        )
        return self.get_promotion(vendor_id, promotion_id)

    def update_promotion_status(self, vendor_id: str, promotion_id: str, active: bool) -> dict[str, Any] | None:
        return self.update_promotion(vendor_id, promotion_id, {"active": active})

    def delete_promotion(self, vendor_id: str, promotion_id: str) -> bool:
        result = self.promotions.delete_one({"_id": ObjectId(promotion_id), "vendor_id": ObjectId(vendor_id)})
        return result.deleted_count > 0

    def list_platform_campaigns(self, vendor_id: str) -> list[dict[str, Any]]:
        campaigns = [self._serialize(doc) for doc in self.platform_campaigns.find({"active": True})]
        joined_ids = {
            str(row.get("source_campaign_id"))
            for row in self.promotions.find(
                {"vendor_id": ObjectId(vendor_id), "source": "platform", "active": True},
                {"source_campaign_id": 1},
            )
            if row.get("source_campaign_id")
        }
        for campaign in campaigns:
            campaign["joined"] = campaign.get("id") in joined_ids
            campaign["title"] = campaign.get("title") or campaign.get("campaign_name") or campaign.get("name") or ""
            campaign["is_active"] = bool(campaign.get("joined"))
        return campaigns

    def set_platform_campaign_join(self, vendor_id: str, campaign_id: str, join: bool) -> dict[str, Any]:
        campaign = self.platform_campaigns.find_one({"_id": ObjectId(campaign_id)})
        if not campaign:
            raise ValueError("Campaign not found.")
        if join:
            self.promotions.update_one(
                {
                    "vendor_id": ObjectId(vendor_id),
                    "source": "platform",
                    "source_campaign_id": ObjectId(campaign_id),
                },
                {
                    "$set": {
                        "active": True,
                        "updated_at": datetime.now(UTC),
                        "promotion_name": campaign.get("campaign_name"),
                    },
                    "$setOnInsert": {
                        "vendor_id": ObjectId(vendor_id),
                        "source": "platform",
                        "source_campaign_id": ObjectId(campaign_id),
                        "created_at": datetime.now(UTC),
                    },
                },
                upsert=True,
            )
        else:
            self.promotions.update_many(
                {
                    "vendor_id": ObjectId(vendor_id),
                    "source": "platform",
                    "source_campaign_id": ObjectId(campaign_id),
                },
                {"$set": {"active": False, "updated_at": datetime.now(UTC)}},
            )
        return {"campaign_id": campaign_id, "joined": join}

    def get_occupancy_metrics(self, vendor_id: str) -> dict[str, Any]:
        total_rooms = sum(
            int(row.get("inventory_count", 0))
            for row in self.rooms.find({"vendor_id": ObjectId(vendor_id)}, {"inventory_count": 1})
        )
        active_bookings = self.bookings.count_documents(
            {"vendor_id": ObjectId(vendor_id), "status": {"$in": ["confirmed", "check_in"]}}
        )
        occupancy_rate = round((active_bookings / total_rooms) * 100, 1) if total_rooms else 0
        return {
            "occupancy_rate": occupancy_rate,
            "rooms_available": max(total_rooms - active_bookings, 0),
            "rooms_total": total_rooms,
            "active_bookings": active_bookings,
        }

    def get_reviews_summary(self, vendor_id: str) -> dict[str, Any]:
        rows = list(self.reviews.find({"vendor_id": ObjectId(vendor_id)}, {"rating": 1}))
        total = len(rows)
        average = round(sum(float(r.get("rating", 0)) for r in rows) / total, 1) if total else 0.0
        breakdown = {str(star): 0 for star in [5, 4, 3, 2, 1]}
        for row in rows:
            star = str(int(row.get("rating", 0)))
            if star in breakdown:
                breakdown[star] += 1
        return {"average_rating": average, "total_reviews": total, "breakdown": breakdown}

    def get_analytics_overview(self, vendor_id: str) -> dict[str, Any]:
        dashboard = self.get_dashboard_overview(vendor_id)
        return {
            **dashboard["kpis"],
            "demographics": self.get_demographics(vendor_id),
            "occupancy_tracking": self.get_occupancy_metrics(vendor_id),
            "reviews_summary": self.get_reviews_summary(vendor_id),
        }

    def get_demographics(self, vendor_id: str) -> dict[str, Any]:
        _ = vendor_id
        return {
            "gender_distribution": {"female": 62, "male": 38},
            "age_groups": {"18-25": 15, "26-40": 48, "41-60": 24, "60+": 13},
        }

    def export_analytics(self, vendor_id: str) -> dict[str, Any]:
        _ = vendor_id
        return {
            "message": "Analytics export prepared.",
            "download_url": "https://files.example.com/exports/vendor-analytics-report.csv",
        }

    def get_loyalty_settings(self, vendor_id: str) -> dict[str, Any]:
        return self._serialize(self.loyalty_settings.find_one({"vendor_id": ObjectId(vendor_id)})) or {}

    def update_loyalty_settings(self, vendor_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        sanitized = self._sanitize_payload(payload)
        self.loyalty_settings.update_one(
            {"vendor_id": ObjectId(vendor_id)},
            {"$set": {**sanitized, "updated_at": datetime.now(UTC)}},
            upsert=True,
        )
        return self.get_loyalty_settings(vendor_id)

    def list_reviews(
        self,
        vendor_id: str,
        limit: int,
        skip: int,
        search: str | None = None,
        star_rating: int | None = None,
        replied: bool | None = None,
    ) -> dict[str, Any]:
        query: dict[str, Any] = {"vendor_id": ObjectId(vendor_id)}
        filters: list[dict[str, Any]] = []
        if search:
            filters.append(
                {
                    "$or": [
                        {"customer_name": {"$regex": search, "$options": "i"}},
                        {"review_text": {"$regex": search, "$options": "i"}},
                    ]
                }
            )
        if star_rating:
            filters.append({"rating": star_rating})
        if replied is True:
            filters.append({"vendor_reply": {"$exists": True, "$ne": ""}})
        if replied is False:
            filters.append({"$or": [{"vendor_reply": {"$exists": False}}, {"vendor_reply": ""}]})
        if filters:
            query["$and"] = filters
        total = int(self.reviews.count_documents(query))
        docs = self.reviews.find(query).sort("created_at", DESCENDING).skip(skip).limit(limit)
        return {"items": [self._serialize(doc) for doc in docs], "total": total}

    def reply_review(self, vendor_id: str, review_id: str, reply_text: str) -> dict[str, Any] | None:
        self.reviews.update_one(
            {"_id": ObjectId(review_id), "vendor_id": ObjectId(vendor_id)},
            {"$set": {"vendor_reply": reply_text, "replied_at": datetime.now(UTC), "updated_at": datetime.now(UTC)}},
        )
        return self._serialize(
            self.reviews.find_one({"_id": ObjectId(review_id), "vendor_id": ObjectId(vendor_id)})
        )

    def get_settings(self, vendor_id: str) -> dict[str, Any]:
        doc = self.settings.find_one({"vendor_id": ObjectId(vendor_id)}) or {}
        doc.pop("_id", None)
        doc.pop("vendor_id", None)
        return doc

    def get_settings_general(self, vendor_id: str) -> dict[str, Any]:
        settings_general = self.get_settings(vendor_id).get("general", {})
        vendor, profile, business, _ = self._get_vendor_records(vendor_id)
        return {
            "business_name": settings_general.get("business_name")
            or vendor.get("business_name")
            or profile.get("business_name")
            or "",
            "legal_entity_name": settings_general.get("legal_entity_name") or business.get("legal_entity_name") or "",
            "business_address": settings_general.get("business_address") or business.get("address") or "",
            "logo_url": settings_general.get("logo_url") or "",
            "cover_image_url": settings_general.get("cover_image_url") or "",
            "booking_availability_slots": settings_general.get("booking_availability_slots") or [],
            "buffer_time_minutes": settings_general.get("buffer_time_minutes") or 15,
            "front_desk_phone": settings_general.get("front_desk_phone") or vendor.get("phone") or profile.get("phone") or "",
            "reservations_email": settings_general.get("reservations_email") or vendor.get("email") or profile.get("email") or "",
            "emergency_contact": settings_general.get("emergency_contact") or vendor.get("phone") or "",
        }

    def update_settings_general(self, vendor_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        sanitized = self._sanitize_payload(payload)
        self.settings.update_one(
            {"vendor_id": ObjectId(vendor_id)},
            {"$set": {"general": sanitized, "updated_at": datetime.now(UTC)}},
            upsert=True,
        )
        vendor_updates = {
            "business_name": sanitized.get("business_name"),
            "updated_at": datetime.now(UTC),
        }
        self.settings.database["vendors"].update_one(
            {"_id": ObjectId(vendor_id)},
            {"$set": {key: value for key, value in vendor_updates.items() if value not in (None, "")}},
        )
        business_updates = {
            "address": sanitized.get("business_address"),
            "updated_at": datetime.now(UTC),
        }
        self.settings.database["vendor_business_details"].update_one(
            {"vendor_id": ObjectId(vendor_id)},
            {
                "$set": {key: value for key, value in business_updates.items() if value not in (None, "")},
                "$setOnInsert": {"created_at": datetime.now(UTC)},
            },
            upsert=True,
        )
        return self.get_settings_general(vendor_id)

    def update_settings_commission(self, vendor_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        sanitized = self._sanitize_payload(payload)
        self.settings.update_one(
            {"vendor_id": ObjectId(vendor_id)},
            {"$set": {"commission": sanitized, "updated_at": datetime.now(UTC)}},
            upsert=True,
        )
        return self.get_settings_commission(vendor_id)

    def get_settings_commission(self, vendor_id: str) -> dict[str, Any]:
        settings_doc = self.get_settings(vendor_id)
        commission = settings_doc.get("commission", {}) if isinstance(settings_doc.get("commission"), dict) else {}
        return {
            "globalRate": str(commission.get("globalRate") or commission.get("global_rate") or ""),
            "categoryRate": str(commission.get("categoryRate") or commission.get("category_rate") or ""),
            "categoryLabel": str(commission.get("categoryLabel") or commission.get("category_label") or ""),
        }

    def _default_legal_docs(self) -> dict[str, Any]:
        return {
            "documents": {
                "terms": "Terms of Service",
                "privacy": "Privacy Policy",
            },
            "content": {
                "terms": {
                    "business": "# Business Terms of Service\n\n### 1. Commercial Eligibility\nBusiness accounts must provide accurate company information and maintain an active point of contact for compliance updates.",
                },
                "privacy": {
                    "business": "# Business Privacy Policy\n\n### 1. Business Contact Data\nWe collect administrator details, team member information, and account-level configuration data required to deliver business services.",
                },
            },
            "lastUpdated": "January 15, 2025 at 2:30 PM",
        }

    def _platform_legal_content(self) -> dict[str, Any]:
        settings_doc = self.settings.database["platform_admin_settings"].find_one({"_id": "platform_admin_settings"}) or {}
        legal_content = settings_doc.get("legalContent")
        if isinstance(legal_content, dict):
            return legal_content
        return self._default_legal_docs()

    def get_legal_doc(self, vendor_id: str, doc_type: str) -> dict[str, Any]:
        _ = vendor_id
        legal_content = self._platform_legal_content()
        content_map = legal_content.get("content", {}).get(doc_type, {})
        return {
            "doc_type": doc_type,
            "title": legal_content.get("documents", {}).get(doc_type, doc_type.title()),
            "content": str(content_map.get("business") or ""),
            "audience": "business",
            "last_updated": legal_content.get("lastUpdated", ""),
        }

    def update_legal_doc(self, vendor_id: str, doc_type: str, content: str, audience: str) -> dict[str, Any]:
        _ = vendor_id
        normalized_doc_type = str(doc_type).strip().lower()
        normalized_audience = str(audience).strip().lower() or "business"
        settings_collection = self.settings.database["platform_admin_settings"]
        settings_doc = settings_collection.find_one({"_id": "platform_admin_settings"}) or {"_id": "platform_admin_settings"}
        legal_content = settings_doc.get("legalContent")
        if not isinstance(legal_content, dict):
            legal_content = self._default_legal_docs()
        legal_content.setdefault("content", {}).setdefault(normalized_doc_type, {})[normalized_audience] = content
        legal_content["lastUpdated"] = datetime.now(UTC).strftime("%B %d, %Y at %I:%M %p").replace(" 0", " ")
        settings_doc["legalContent"] = legal_content
        settings_doc["updated_at"] = datetime.now(UTC)
        settings_collection.update_one(
            {"_id": "platform_admin_settings"},
            {
                "$set": {key: value for key, value in settings_doc.items() if key not in {"_id", "created_at"}},
                "$setOnInsert": {"created_at": datetime.now(UTC)},
            },
            upsert=True,
        )
        return self.get_legal_doc(vendor_id, doc_type)

    def get_settings_profile(self, vendor_id: str) -> dict[str, Any]:
        settings_doc = self.get_settings(vendor_id)
        profile_settings = settings_doc.get("profile", {})
        general_settings = settings_doc.get("general", {})
        vendor, profile, business, verification = self._get_vendor_records(vendor_id)
        category = (
            profile_settings.get("category")
            or verification.get("category")
            or vendor.get("category")
            or "Restaurant"
        )

        business_name = (
            profile_settings.get("business_name")
            or general_settings.get("business_name")
            or vendor.get("business_name")
            or profile.get("business_name")
            or ""
        )
        email = profile_settings.get("email_address") or vendor.get("email") or profile.get("email") or ""
        phone = profile_settings.get("phone_number") or vendor.get("phone") or profile.get("phone") or ""
        address = (
            profile_settings.get("office_address")
            or general_settings.get("business_address")
            or business.get("address")
            or ""
        )
        description = profile_settings.get("about_business") or business.get("business_description") or ""
        website = profile_settings.get("website") or business.get("website") or ""
        location_value = (
            profile_settings.get("office_address")
            or general_settings.get("business_address")
            or business.get("address")
            or ""
        )
        location_label = self._normalize_location_label(
            profile_settings.get("location_label")
            or verification.get("location_label")
            or business.get("location_label"),
            category,
        )

        return {
            **profile_settings,
            "business_name": business_name,
            "category": category,
            "categories": (
                profile_settings.get("categories")
                or verification.get("categories")
                or vendor.get("categories")
                or ([profile_settings.get("category")] if profile_settings.get("category") else None)
                or ([verification.get("category")] if verification.get("category") else None)
                or ([vendor.get("category")] if vendor.get("category") else ["Restaurant"])
            ),
            "email_address": email,
            "phone_number": phone,
            "about_business": description,
            "office_address": location_value,
            "website": website,
            "avatar_url": profile_settings.get("avatar_url") or "",
            "owner_full_name": profile_settings.get("owner_full_name") or vendor.get("owner_full_name") or "",
            "email": email,
            "phone": phone,
            "address": location_value,
            "location_label": location_label,
            "location_value": location_value,
            "description": description,
            "name": business_name,
        }

    def update_settings_profile(self, vendor_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        sanitized = self._sanitize_payload(payload)
        current = self.settings.find_one({"vendor_id": ObjectId(vendor_id)}) or {}
        current_profile = current.get("profile", {}) if isinstance(current.get("profile"), dict) else {}
        current_general = current.get("general", {}) if isinstance(current.get("general"), dict) else {}
        vendor, _, _, verification = self._get_vendor_records(vendor_id)

        next_profile = {**current_profile, **sanitized}
        next_category = (
            sanitized.get("category")
            or current_profile.get("category")
            or verification.get("category")
            or vendor.get("category")
            or "Restaurant"
        )
        next_profile["location_label"] = self._normalize_location_label(
            next_profile.get("location_label"),
            str(next_category),
        )
        update_doc: dict[str, Any] = {
            "profile": next_profile,
            "updated_at": datetime.now(UTC),
        }

        office_address = sanitized.get("office_address")
        if office_address:
            update_doc["general"] = {
                **current_general,
                "business_address": office_address,
            }

        self.settings.update_one(
            {"vendor_id": ObjectId(vendor_id)},
            {"$set": update_doc},
            upsert=True,
        )
        vendor_updates = {
            "business_name": sanitized.get("business_name"),
            "updated_at": datetime.now(UTC),
        }
        self.settings.database["vendors"].update_one(
            {"_id": ObjectId(vendor_id)},
            {"$set": {key: value for key, value in vendor_updates.items() if value not in (None, "")}},
        )
        business_updates = {
            "address": sanitized.get("office_address"),
            "website": sanitized.get("website"),
            "business_description": sanitized.get("about_business"),
            "updated_at": datetime.now(UTC),
        }
        self.settings.database["vendor_business_details"].update_one(
            {"vendor_id": ObjectId(vendor_id)},
            {
                "$set": {key: value for key, value in business_updates.items() if value not in (None, "")},
                "$setOnInsert": {"created_at": datetime.now(UTC)},
            },
            upsert=True,
        )
        profile_updates = {
            "business_name": sanitized.get("business_name"),
            "owner_full_name": sanitized.get("owner_full_name"),
            "email": sanitized.get("email_address"),
            "phone": sanitized.get("phone_number"),
            "updated_at": datetime.now(UTC),
        }
        self.settings.database["vendor_profiles"].update_one(
            {"vendor_id": ObjectId(vendor_id)},
            {
                "$set": {key: value for key, value in profile_updates.items() if value not in (None, "")},
                "$setOnInsert": {"created_at": datetime.now(UTC)},
            },
            upsert=True,
        )
        return self.get_settings_profile(vendor_id)

    # ------------------------------------------------------------------
    # Targeted image URL helpers — update only a single image field so
    # the rest of the vendor settings document is never overwritten.
    # ------------------------------------------------------------------

    def update_logo_url(self, vendor_id: str, url: str) -> dict[str, Any]:
        """Persist a Cloudinary secure_url as the vendor's logo."""
        self.settings.update_one(
            {"vendor_id": ObjectId(vendor_id)},
            {"$set": {"general.logo_url": url, "updated_at": datetime.now(UTC)}},
            upsert=True,
        )
        return self.get_settings_general(vendor_id)

    def update_cover_image_url(self, vendor_id: str, url: str) -> dict[str, Any]:
        """Persist a Cloudinary secure_url as the vendor's cover image."""
        self.settings.update_one(
            {"vendor_id": ObjectId(vendor_id)},
            {"$set": {"general.cover_image_url": url, "updated_at": datetime.now(UTC)}},
            upsert=True,
        )
        return self.get_settings_general(vendor_id)

    def update_avatar_url(self, vendor_id: str, url: str) -> dict[str, Any]:
        """Persist a Cloudinary secure_url as the vendor's profile avatar."""
        self.settings.update_one(
            {"vendor_id": ObjectId(vendor_id)},
            {"$set": {"profile.avatar_url": url, "updated_at": datetime.now(UTC)}},
            upsert=True,
        )
        return self.get_settings_profile(vendor_id)


    def create_support_ticket(self, vendor_id: str, subject: str, description: str) -> dict[str, Any]:
        ticket_code = f"#SP-{datetime.now(UTC).year}-{str(ObjectId())[-3:]}"
        inserted = self.support_tickets.insert_one(
            {
                "vendor_id": ObjectId(vendor_id),
                "ticket_code": ticket_code,
                "subject": subject,
                "description": description,
                "status": "open",
                "messages": [],
                "created_at": datetime.now(UTC),
                "updated_at": datetime.now(UTC),
            }
        )
        created = self.support_tickets.find_one({"_id": inserted.inserted_id})
        return self._serialize(created)  # type: ignore[return-value]

    def list_support_tickets(self, vendor_id: str, limit: int, skip: int) -> dict[str, Any]:
        query = {"vendor_id": ObjectId(vendor_id)}
        total = int(self.support_tickets.count_documents(query))
        docs = self.support_tickets.find(query).sort("created_at", DESCENDING).skip(skip).limit(limit)
        return {"items": [self._serialize(doc) for doc in docs], "total": total}

    def get_support_ticket(self, vendor_id: str, ticket_id: str) -> dict[str, Any] | None:
        return self._serialize(
            self.support_tickets.find_one({"_id": ObjectId(ticket_id), "vendor_id": ObjectId(vendor_id)})
        )

    def add_support_ticket_message(
        self, vendor_id: str, ticket_id: str, message: str, metadata: dict | None = None
    ) -> dict[str, Any] | None:
        msg_entry = {"sender": "vendor", "message": message, "metadata": metadata or {}, "sent_at": datetime.now(UTC)}
        result = self.support_tickets.find_one_and_update(
            {"_id": ObjectId(ticket_id), "vendor_id": ObjectId(vendor_id)},
            {"$push": {"messages": msg_entry}, "$set": {"updated_at": datetime.now(UTC)}},
            return_document=True,
        )
        return self._serialize(result)

    def list_notifications(self, vendor_id: str, limit: int, skip: int) -> dict[str, Any]:
        query = {"vendor_id": ObjectId(vendor_id)}
        total = int(self.notifications.count_documents(query))
        docs = self.notifications.find(query).sort("created_at", DESCENDING).skip(skip).limit(limit)
        return {
            "items": [self._serialize(doc) for doc in docs],
            "total": total,
            "settings": self.get_notification_settings(vendor_id),
        }

    def clear_notifications(self, vendor_id: str) -> int:
        result = self.notifications.delete_many({"vendor_id": ObjectId(vendor_id)})
        return int(result.deleted_count)

    def create_notification(
        self,
        vendor_id: str,
        notification_type: str,
        title: str,
        message: str,
        *,
        action_type: str = "mark_read",
        action_label: str | None = None,
        metadata: dict[str, Any] | None = None,
        respect_settings_key: str | None = None,
    ) -> dict[str, Any] | None:
        if respect_settings_key:
            settings = self.get_notification_settings(vendor_id)
            if not bool(settings.get(respect_settings_key, False)):
                return None

        now = datetime.now(UTC)
        payload = {
            "vendor_id": ObjectId(vendor_id),
            "type": notification_type,
            "title": title.strip(),
            "message": message.strip(),
            "read": False,
            "action_type": action_type,
            "action_label": action_label or "Mark as Read",
            "metadata": metadata or {},
            "created_at": now,
            "updated_at": now,
        }
        inserted = self.notifications.insert_one(payload)
        created = self.notifications.find_one({"_id": inserted.inserted_id})
        return self._serialize(created)

    def create_booking_notification(self, vendor_id: str, booking: dict[str, Any]) -> dict[str, Any] | None:
        customer_name = str(booking.get("customer_name") or "A customer").strip()
        booking_code = str(booking.get("booking_code") or "").strip()
        scheduled_date = str(booking.get("scheduled_date") or "").strip()
        scheduled_time = str(booking.get("scheduled_time") or "").strip()
        service = str(booking.get("service") or "booking").strip()
        schedule_label = " ".join(part for part in [scheduled_date, scheduled_time] if part).strip()
        message = f"{customer_name} created a new {service.lower()}."
        if schedule_label:
            message = f"{message} Scheduled for {schedule_label}."
        if booking_code:
            message = f"{message} Reference: {booking_code}."

        return self.create_notification(
            vendor_id,
            "new_booking",
            "New Booking Received",
            message,
            action_type="view_details",
            action_label="View Booking",
            metadata={
                "booking_id": str(booking.get("id") or booking.get("_id") or ""),
                "booking_code": booking_code,
                "status": booking.get("status"),
            },
            respect_settings_key="new_booking",
        )

    def broadcast_platform_update(
        self,
        title: str,
        message: str,
        *,
        action_label: str | None = None,
        metadata: dict[str, Any] | None = None,
        vendor_ids: list[str] | None = None,
    ) -> int:
        vendor_filter: dict[str, Any] = {}
        if vendor_ids:
            vendor_filter = {"vendor_id": {"$in": [ObjectId(vendor_id) for vendor_id in vendor_ids]}}

        opted_in_rows = list(
            self.notification_settings.find(
                {
                    "platform_updates": True,
                    **vendor_filter,
                },
                {"vendor_id": 1},
            )
        )
        if not opted_in_rows:
            return 0

        vendor_id_values = [row.get("vendor_id") for row in opted_in_rows if row.get("vendor_id")]
        if not vendor_id_values:
            return 0

        now = datetime.now(UTC)
        docs = [
            {
                "vendor_id": vendor_oid,
                "type": "platform_update",
                "title": title.strip(),
                "message": message.strip(),
                "read": False,
                "action_type": "view_details",
                "action_label": action_label or "View Update",
                "metadata": metadata or {},
                "created_at": now,
                "updated_at": now,
            }
            for vendor_oid in vendor_id_values
        ]
        result = self.notifications.insert_many(docs)
        return len(result.inserted_ids)

    def get_notification_settings(self, vendor_id: str) -> dict[str, Any]:
        setting = self.notification_settings.find_one({"vendor_id": ObjectId(vendor_id)}) or {}
        setting.pop("_id", None)
        setting.pop("vendor_id", None)
        return {
            "new_booking": bool(setting.get("new_booking", setting.get("booking_alerts", True))),
            "booking_cancellation": bool(setting.get("booking_cancellation", True)),
            "new_review": bool(setting.get("new_review", setting.get("review_alerts", True))),
            "platform_updates": bool(setting.get("platform_updates", False)),
        }

    def update_notification_settings(self, vendor_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        sanitized = self._sanitize_payload(payload)
        normalized = {
            "new_booking": bool(sanitized.get("new_booking", sanitized.get("booking_alerts", True))),
            "booking_cancellation": bool(sanitized.get("booking_cancellation", True)),
            "new_review": bool(sanitized.get("new_review", sanitized.get("review_alerts", True))),
            "platform_updates": bool(sanitized.get("platform_updates", False)),
        }
        self.notification_settings.update_one(
            {"vendor_id": ObjectId(vendor_id)},
            {
                "$set": {**normalized, "updated_at": datetime.now(UTC)},
                "$unset": {"booking_alerts": "", "review_alerts": ""},
            },
            upsert=True,
        )
        return self.get_notification_settings(vendor_id)

    def apply_notification_action(self, vendor_id: str, notification_id: str, action: str) -> dict[str, Any] | None:
        row = self.notifications.find_one({"_id": ObjectId(notification_id), "vendor_id": ObjectId(vendor_id)})
        if not row:
            return None
        self.notifications.update_one(
            {"_id": row["_id"]},
            {"$set": {"read": True, "last_action": action, "updated_at": datetime.now(UTC)}},
        )
        return self._serialize(self.notifications.find_one({"_id": row["_id"]}))
