import hashlib
import math
from datetime import UTC, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from bson import ObjectId
from bson.errors import InvalidId
from pymongo import ASCENDING, DESCENDING
from pymongo.collection import Collection
from pymongo.database import Database

from app.domain.event_categories import normalize_event_category
from app.domain.service_listings import SERVICE_TYPES, collection_name_for, normalize_service_type


class CustomerRepository:
    def __init__(self, db: Database):
        self.users: Collection = db["users"]
        self.vendors: Collection = db["vendors"]
        self.vendor_profiles: Collection = db["vendor_profiles"]
        self.vendor_business_details: Collection = db["vendor_business_details"]
        self.vendor_verification_details: Collection = db["vendor_verification_details"]
        self.vendor_portal_settings: Collection = db["vendor_portal_settings"]
        self.vendor_assets: Collection = db["vendor_assets"]
        self.vendor_promotions: Collection = db["vendor_promotions"]
        self.vendor_rooms: Collection = db["vendor_rooms"]
        self.vendor_services: Collection = db["vendor_services"]
        self.vendor_events: Collection = db["vendor_events"]
        self.vendor_happy_hours: Collection = db["vendor_happy_hours"]
        self.vendor_reviews: Collection = db["vendor_reviews"]
        self.vendor_loyalty_settings: Collection = db["vendor_loyalty_settings"]
        self.vendor_bookings: Collection = db["vendor_bookings"]
        self.vendor_notifications: Collection = db["vendor_notifications"]
        self.vendor_notification_settings: Collection = db["vendor_notification_settings"]
        self.bookings: Collection = db["bookings"]
        self.customer_recent_searches: Collection = db["customer_recent_searches"]
        self.customer_saved_items: Collection = db["customer_saved_items"]
        self.notifications: Collection = db["notifications"]
        self.customer_plan_sessions: Collection = db["customer_plan_sessions"]
        self.public_service_collections: dict[str, Collection] = {
            service_type: db[collection_name_for(service_type)] for service_type in SERVICE_TYPES
        }

        self.vendor_bookings.create_index([("vendor_id", ASCENDING), ("scheduled_date", ASCENDING), ("scheduled_time", ASCENDING)])
        self.vendor_bookings.create_index([("customer_id", ASCENDING), ("created_at", DESCENDING)])
        self.vendor_notifications.create_index([("vendor_id", ASCENDING), ("created_at", DESCENDING)])
        self.vendor_notification_settings.create_index([("vendor_id", ASCENDING)], unique=True)
        self.customer_recent_searches.create_index([("customer_id", ASCENDING), ("created_at", DESCENDING)])
        self.customer_saved_items.create_index([("customer_id", ASCENDING), ("entity_type", ASCENDING), ("entity_id", ASCENDING)], unique=True)
        self.notifications.create_index([("user_id", ASCENDING), ("created_at", DESCENDING)])
        self.customer_plan_sessions.create_index([("customer_id", ASCENDING), ("updated_at", DESCENDING)])

    @staticmethod
    def _oid(value: str) -> ObjectId:
        return ObjectId(value)

    def _serialize(self, doc: dict[str, Any] | None) -> dict[str, Any] | None:
        if not doc:
            return None
        out = dict(doc)
        if out.get("_id") is not None:
            out["id"] = str(out.pop("_id"))
        for key, value in list(out.items()):
            if isinstance(value, ObjectId):
                out[key] = str(value)
            elif isinstance(value, datetime):
                out[key] = value.isoformat()
        return out

    @staticmethod
    def _distance_km(seed: str) -> float:
        digest = hashlib.md5(seed.encode("utf-8")).hexdigest()[:8]
        raw = int(digest, 16)
        return round(((raw % 90) + 10) / 10, 1)

    @staticmethod
    def _coords(seed: str) -> dict[str, float]:
        digest = hashlib.md5(seed.encode("utf-8")).hexdigest()
        lat_offset = (int(digest[:4], 16) % 2000) / 100000
        lng_offset = (int(digest[4:8], 16) % 2000) / 100000
        return {"lat": 25.2854 + lat_offset, "lng": 51.5310 + lng_offset}

    @staticmethod
    def _to_float(value: Any) -> float | None:
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def _get_customer_coords(self, customer_id: str) -> tuple[float | None, float | None]:
        user = self.users.find_one({"_id": self._oid(customer_id)}, {"latitude": 1, "longitude": 1}) or {}
        return self._to_float(user.get("latitude")), self._to_float(user.get("longitude"))

    def _published_vendor_docs(
        self,
        service_type: str,
        search: str | None = None,
    ) -> list[dict[str, Any]]:
        """Return approved vendors that explicitly published this service."""
        normalized = normalize_service_type(service_type)
        collection = self.public_service_collections[normalized]
        listing_docs = list(collection.find({}))
        listings_by_vendor = {
            row["vendor_id"]: row
            for row in listing_docs
            if isinstance(row.get("vendor_id"), ObjectId)
        }
        public_vendor_ids = {
            vendor_id
            for vendor_id, row in listings_by_vendor.items()
            if row.get("published") is True
        }

        settings_key = f"{normalized}_settings"
        settings_path = f"profile.{settings_key}"
        settings_docs = list(
            self.vendor_portal_settings.find(
                {f"{settings_path}.published": True},
                {"vendor_id": 1, settings_path: 1},
            )
        )
        settings_by_vendor = {
            row["vendor_id"]: (
                ((row.get("profile") or {}).get(settings_key) or {})
            )
            for row in settings_docs
            if isinstance(row.get("vendor_id"), ObjectId)
        }

        # During a partial projection migration, use explicitly published
        # profile settings only when this service has no dedicated listing yet.
        public_vendor_ids.update(
            vendor_id
            for vendor_id in settings_by_vendor
            if vendor_id not in listings_by_vendor
        )
        if not public_vendor_ids:
            return []

        vendors = list(
            self.vendors.find(
                {"_id": {"$in": list(public_vendor_ids)}, "status": "approved"}
            ).sort("created_at", DESCENDING)
        )
        needle = str(search or "").strip().casefold()
        if not needle:
            return vendors

        def matches_search(vendor: dict[str, Any]) -> bool:
            vendor_id = vendor["_id"]
            listing = listings_by_vendor.get(vendor_id, {})
            settings = settings_by_vendor.get(vendor_id, {})
            values = (
                listing.get("name"),
                listing.get("title"),
                listing.get("city"),
                listing.get("address"),
                settings.get("name"),
                settings.get("city"),
                settings.get("address"),
                vendor.get("business_name"),
                vendor.get("owner_full_name"),
                vendor.get("email"),
            )
            return any(needle in str(value or "").casefold() for value in values)

        return [vendor for vendor in vendors if matches_search(vendor)]

    def _is_public_service(self, vendor_id: ObjectId, service_type: str) -> bool:
        normalized = normalize_service_type(service_type)
        collection = self.public_service_collections[normalized]
        listing = collection.find_one({"vendor_id": vendor_id}, {"published": 1})
        if listing is not None:
            return listing.get("published") is True
        settings = self.vendor_portal_settings.find_one(
            {"vendor_id": vendor_id},
            {f"profile.{normalized}_settings.published": 1},
        ) or {}
        service_settings = (
            (settings.get("profile") or {}).get(f"{normalized}_settings") or {}
        )
        return service_settings.get("published") is True

    def _vendor_notification_settings(self, vendor_id: ObjectId) -> dict[str, bool]:
        setting = self.vendor_notification_settings.find_one({"vendor_id": vendor_id}) or {}
        return {
            "new_booking": bool(setting.get("new_booking", setting.get("booking_alerts", True))),
            "booking_cancellation": bool(setting.get("booking_cancellation", True)),
            "new_review": bool(setting.get("new_review", setting.get("review_alerts", True))),
            "platform_updates": bool(setting.get("platform_updates", False)),
        }

    def _create_vendor_notification(
        self,
        vendor_id: ObjectId,
        notification_type: str,
        title: str,
        message: str,
        *,
        action_type: str = "mark_read",
        action_label: str | None = None,
        metadata: dict[str, Any] | None = None,
        settings_key: str | None = None,
    ) -> None:
        if settings_key:
            settings = self._vendor_notification_settings(vendor_id)
            if not bool(settings.get(settings_key, False)):
                return
        now = datetime.now(UTC)
        self.vendor_notifications.insert_one(
            {
                "vendor_id": vendor_id,
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
        )

    def _get_vendor_coords(self, bundle: dict[str, Any], category: str | None = None) -> tuple[float | None, float | None]:
        profile_settings = bundle.get("profile_settings", {})
        general_settings = bundle.get("general", {})
        service_settings = profile_settings.get(f"{str(category or '').strip().lower()}_settings", {})
        if not isinstance(service_settings, dict):
            service_settings = {}
        latitude = self._to_float(service_settings.get("latitude"))
        longitude = self._to_float(service_settings.get("longitude"))
        if latitude is None:
            latitude = self._to_float(profile_settings.get("latitude"))
        if longitude is None:
            longitude = self._to_float(profile_settings.get("longitude"))
        if latitude is None:
            latitude = self._to_float(general_settings.get("latitude"))
        if longitude is None:
            longitude = self._to_float(general_settings.get("longitude"))
        return latitude, longitude

    @staticmethod
    def _service_settings(bundle: dict[str, Any], category: str | None = None) -> dict[str, Any]:
        key = f"{str(category or bundle.get('category') or '').strip().lower()}_settings"
        settings = bundle.get("profile_settings", {}).get(key, {})
        return settings if isinstance(settings, dict) else {}

    @staticmethod
    def _service_profile_image(
        bundle: dict[str, Any], service_settings: dict[str, Any]
    ) -> str:
        return str(
            service_settings.get("profile_image_url")
            or bundle.get("general", {}).get("logo_url")
            or bundle.get("profile_settings", {}).get("avatar_url")
            or ""
        ).strip()

    def _asset_query(
        self, vendor_id: ObjectId, asset_type: str, service_type: str
    ) -> dict[str, Any]:
        normalized = normalize_service_type(service_type)
        verification = self.vendor_verification_details.find_one(
            {"vendor_id": vendor_id}, {"category": 1}
        ) or {}
        profile = self.vendor_profiles.find_one(
            {"vendor_id": vendor_id}, {"category": 1}
        ) or {}
        try:
            legacy_service_type = normalize_service_type(
                verification.get("category") or profile.get("category") or "restaurant"
            )
        except ValueError:
            legacy_service_type = "restaurant"
        query: dict[str, Any] = {
            "vendor_id": vendor_id,
            "asset_type": asset_type,
        }
        if normalized == legacy_service_type:
            query["$or"] = [
                {"service_type": normalized},
                {"service_type": {"$exists": False}},
            ]
        else:
            query["service_type"] = normalized
        return query

    @staticmethod
    def _promotion_applies_to_service(
        promotion: dict[str, Any], service_type: str
    ) -> bool:
        applicable_to = str(promotion.get("applicable_to") or "All Services").strip().lower()
        if not applicable_to or applicable_to == "all services":
            return True
        normalized = str(service_type or "").strip().lower().replace("_room", "")
        if normalized not in {"restaurant", "hotel", "spa", "event"}:
            normalized = normalize_service_type(normalized)
        aliases = {
            "restaurant": ("restaurant", "dining", "food"),
            "hotel": ("hotel", "room", "stay"),
            "spa": ("spa", "wellness", "treatment"),
            "event": ("event", "ticket"),
        }
        return any(alias in applicable_to for alias in aliases[normalized])

    def _promotion_discount(
        self,
        vendor_id: ObjectId,
        service_type: str,
        subtotal: float,
        customer_id: ObjectId | None,
        scheduled_date: str,
        promo_code: str | None,
    ) -> dict[str, Any]:
        normalized_code = str(promo_code or "").strip().upper()
        candidates: list[tuple[float, dict[str, Any]]] = []
        try:
            booking_day = datetime.fromisoformat(scheduled_date[:10])
        except ValueError:
            booking_day = datetime.now(UTC)

        for promotion in self.vendor_promotions.find({"vendor_id": vendor_id, "active": True}):
            if not self._promotion_applies_to_service(promotion, service_type):
                continue
            start_date = str(promotion.get("start_date") or "")
            end_date = str(promotion.get("end_date") or "")
            day_value = booking_day.date().isoformat()
            if start_date and day_value < start_date[:10]:
                continue
            if end_date and day_value > end_date[:10]:
                continue
            recurring_days = [str(value) for value in promotion.get("recurring_days") or []]
            if recurring_days and str(booking_day.weekday()) not in recurring_days:
                continue

            required_code = bool(promotion.get("require_promo_code"))
            configured_code = str(promotion.get("promo_code") or "").strip().upper()
            if normalized_code:
                if not configured_code or configured_code != normalized_code:
                    continue
            elif required_code:
                continue
            minimum_spend = max(float(promotion.get("minimum_spend") or 0), 0)
            if subtotal < minimum_spend:
                continue
            if promotion.get("first_time_customers_only") and customer_id:
                previous = self.vendor_bookings.find_one(
                    {
                        "vendor_id": vendor_id,
                        "customer_id": customer_id,
                        "status": {"$nin": ["canceled", "cancelled"]},
                    },
                    {"_id": 1},
                )
                if previous:
                    continue

            value = max(float(promotion.get("discount_value") or 0), 0)
            offer_type = str(promotion.get("offer_type") or "percentage").lower()
            discount = subtotal * min(value, 100) / 100 if offer_type == "percentage" else value
            candidates.append((min(round(discount, 2), subtotal), promotion))

        if normalized_code and not candidates:
            raise ValueError("Promo code is invalid or not available for this booking.")
        if not candidates:
            return {"discount_amount": 0.0, "promotion_id": None, "promotion_name": None, "promo_code": None}

        discount, promotion = max(candidates, key=lambda item: item[0])
        return {
            "discount_amount": discount,
            "promotion_id": promotion["_id"],
            "promotion_name": promotion.get("promotion_name") or "Promotion",
            "promo_code": normalized_code or promotion.get("promo_code"),
        }

    def _estimate_loyalty_points(
        self,
        vendor_id: ObjectId,
        customer_id: ObjectId | None,
        total: float,
    ) -> int:
        loyalty = self.vendor_loyalty_settings.find_one({"vendor_id": vendor_id}) or {}
        if loyalty.get("enable_loyalty_program") is not True:
            return 0
        if loyalty.get("points_rule_type") == "percentage_based":
            points = int(total * float(loyalty.get("percentage_value") or 0) / 100)
        else:
            currency_unit = float(loyalty.get("currency_unit") or 1)
            points = int((total / currency_unit) * float(loyalty.get("points_earned") or 0))
        if customer_id and not self.vendor_bookings.find_one(
            {
                "vendor_id": vendor_id,
                "customer_id": customer_id,
                "status": {"$in": ["complete", "completed"]},
            },
            {"_id": 1},
        ):
            points += max(int(loyalty.get("first_booking_bonus") or 0), 0)
        return max(points, 0)

    def _list_service_offers(
        self,
        vendor_id: ObjectId,
        service_type: str,
        service_settings: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        normalized = normalize_service_type(service_type)
        if service_settings is None:
            service_settings = self._service_settings(
                self._get_vendor_bundle(vendor_id, normalized), normalized
            )
        settings_offers = [
            {
                "id": f"{normalized}-setting-offer-{index}",
                "title": str(offer.get("title") or "").strip(),
                "description": str(offer.get("description") or "").strip(),
                "active": True,
                "service_type": normalized,
                "source": f"{normalized}_settings",
            }
            for index, offer in enumerate(service_settings.get("special_offers") or [])
            if isinstance(offer, dict)
            and str(offer.get("title") or "").strip()
            and offer.get("active", True) is not False
        ]
        promotion_offers = []
        today = datetime.now(UTC).date().isoformat()
        for document in self.vendor_promotions.find(
            {"vendor_id": vendor_id, "active": True}
        ).sort("created_at", DESCENDING):
            offer = self._serialize(document)
            if not offer or not self._promotion_applies_to_service(offer, normalized):
                continue
            if offer.get("start_date") and str(offer["start_date"])[:10] > today:
                continue
            if offer.get("end_date") and str(offer["end_date"])[:10] < today:
                continue
            promotion_offers.append(
                {
                    **offer,
                    "title": offer.get("promotion_name")
                    or offer.get("title")
                    or "Special offer",
                    "description": offer.get("internal_description")
                    or offer.get("description")
                    or "",
                    "service_type": normalized,
                    "source": "promotion",
                }
            )
        return [*settings_offers, *promotion_offers]

    @staticmethod
    def _service_is_open(settings: dict[str, Any], fallback: bool) -> bool:
        opening = str(settings.get("opening_time") or "").strip()
        closing = str(settings.get("closing_time") or "").strip()
        if not opening or not closing:
            return fallback
        try:
            from datetime import datetime as _datetime
            current = _datetime.now().strftime("%H:%M")
            parse = lambda value: _datetime.strptime(value, "%I:%M %p").strftime("%H:%M")
            start, end = parse(opening), parse(closing)
            return start <= current < end if start <= end else current >= start or current < end
        except ValueError:
            return fallback

    def _get_event_coords(self, event: dict[str, Any], bundle: dict[str, Any]) -> tuple[float | None, float | None]:
        latitude = self._to_float(event.get("latitude"))
        longitude = self._to_float(event.get("longitude"))
        if latitude is None or longitude is None:
            return self._get_vendor_coords(bundle)
        return latitude, longitude

    @staticmethod
    def _event_is_not_expired(event: dict[str, Any]) -> bool:
        """Evaluate an event's end time in the event's own timezone."""
        event_date = str(
            event.get("end_date") or event.get("event_date") or ""
        ).strip()
        end_time = str(event.get("end_time") or "").strip()
        if not event_date or not end_time:
            return False
        try:
            timezone = ZoneInfo(str(event.get("timezone") or "UTC"))
            end_at = datetime.fromisoformat(f"{event_date}T{end_time}").replace(tzinfo=timezone)
        except (TypeError, ValueError):
            return False
        return end_at >= datetime.now(timezone)

    @staticmethod
    def _event_registration_is_open(event: dict[str, Any]) -> bool:
        """A date-only deadline remains open through 23:59:59 in event timezone."""
        deadline = str(event.get("registration_deadline") or "").strip()
        if not deadline:
            return True
        try:
            timezone = ZoneInfo(str(event.get("timezone") or "UTC"))
            if "T" in deadline:
                legacy_deadline = datetime.fromisoformat(
                    deadline.replace("Z", "+00:00")
                )
                deadline_at = (
                    legacy_deadline.astimezone(timezone)
                    if legacy_deadline.tzinfo
                    else legacy_deadline.replace(tzinfo=timezone)
                )
            else:
                deadline_at = datetime.fromisoformat(
                    f"{deadline}T23:59:59.999999"
                ).replace(tzinfo=timezone)
        except (TypeError, ValueError):
            return False
        return datetime.now(timezone) <= deadline_at

    @staticmethod
    def _legacy_happy_hour_match() -> dict[str, Any]:
        expression = {"$regex": r"^\s*happy[\s_-]*hour\s*$", "$options": "i"}
        return {
            "$or": [
                {"event_type": expression},
                {"category": expression},
                {"entity_type": expression},
                {"legacy_happy_hour": True},
            ]
        }

    @staticmethod
    def _happy_hour_schedule_state(happy_hour: dict[str, Any]) -> tuple[bool, bool]:
        start_date = str(happy_hour.get("start_date") or "").strip()
        end_date = str(happy_hour.get("end_date") or "").strip()
        start_time = str(happy_hour.get("start_time") or "").strip()
        end_time = str(happy_hour.get("end_time") or "").strip()
        try:
            timezone = ZoneInfo(str(happy_hour.get("timezone") or "UTC"))
            now = datetime.now(timezone)
            starts_on = datetime.fromisoformat(start_date).date()
            ends_on = datetime.fromisoformat(end_date).date()
            starts_at = datetime.fromisoformat(
                f"{now.date().isoformat()}T{start_time}"
            ).replace(tzinfo=timezone)
            ends_at = datetime.fromisoformat(
                f"{now.date().isoformat()}T{end_time}"
            ).replace(tzinfo=timezone)
        except (TypeError, ValueError):
            return False, False
        is_visible = ends_on >= now.date()
        configured_days = {
            str(day or "").strip().lower()
            for day in happy_hour.get("days_of_week") or []
        }
        day_matches = not configured_days or now.strftime("%A").lower() in configured_days
        is_active_now = (
            starts_on <= now.date() <= ends_on
            and day_matches
            and starts_at <= now <= ends_at
        )
        return is_visible, is_active_now

    @staticmethod
    def _legacy_event_as_happy_hour(event: dict[str, Any]) -> dict[str, Any]:
        event_date = str(event.get("event_date") or "").strip()
        try:
            day_name = datetime.fromisoformat(event_date).strftime("%A").lower()
        except ValueError:
            day_name = "monday"
        category = str(event.get("category") or "").strip().lower()
        return {
            **event,
            "venue_type": category if category in {"restaurant", "hotel", "spa"} else "other",
            "offer_text": event.get("event_type") or event.get("title") or "Happy Hour",
            "start_date": event_date,
            "end_date": event_date,
            "days_of_week": [day_name],
            "original_price": event.get("ticket_price"),
            "happy_hour_price": event.get("ticket_price"),
            "discount_percent": None,
            "terms_and_conditions": "",
            "legacy_event_id": str(event.get("_id") or ""),
        }

    @staticmethod
    def _distance_between_km(
        origin_lat: float | None,
        origin_lng: float | None,
        target_lat: float | None,
        target_lng: float | None,
    ) -> float | None:
        if None in (origin_lat, origin_lng, target_lat, target_lng):
            return None
        radius_km = 6371.0
        lat1 = math.radians(origin_lat)
        lng1 = math.radians(origin_lng)
        lat2 = math.radians(target_lat)
        lng2 = math.radians(target_lng)
        dlat = lat2 - lat1
        dlng = lng2 - lng1
        a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlng / 2) ** 2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        return round(radius_km * c, 1)

    def _event_booking_mode(self, event: dict[str, Any]) -> str:
        explicit_mode = str(event.get("booking_mode") or "").strip().lower()
        if explicit_mode in {"simple", "detailed"}:
            return explicit_mode
        if event.get("requires_seat_selection"):
            return "detailed"
        if event.get("requires_attendee_details"):
            return "detailed"
        if event.get("requires_timeslot_selection"):
            return "detailed"
        if event.get("requires_terms_confirmation"):
            return "detailed"
        if isinstance(event.get("ticket_types"), list) and len(event["ticket_types"]) > 1:
            return "detailed"
        if isinstance(event.get("addons"), list) and event["addons"]:
            return "detailed"
        if isinstance(event.get("packages"), list) and event["packages"]:
            return "detailed"
        return "simple"

    def _event_booking_summary(self, customer_id: str, event_id: ObjectId, capacity: int) -> dict[str, Any]:
        active_statuses = ["pending", "confirmed", "check_in"]
        sold = 0
        latest_booking: dict[str, Any] | None = None

        cursor = self.vendor_bookings.find(
            {"event_id": event_id, "status": {"$in": active_statuses}},
            {"customer_id": 1, "status": 1, "booking_code": 1, "quantity": 1, "created_at": 1},
        ).sort("created_at", DESCENDING)
        for booking in cursor:
            sold += int(booking.get("quantity") or 0)
            if latest_booking is None and str(booking.get("customer_id")) == customer_id:
                latest_booking = booking

        is_sold_out = capacity > 0 and sold >= capacity
        current_status = str(latest_booking.get("status") or "").lower() if latest_booking else ""
        current_code = str(latest_booking.get("booking_code") or "").strip() if latest_booking else ""

        return {
            "current_booking_status": current_status or None,
            "current_booking_code": current_code or None,
            "is_sold_out": is_sold_out,
            "remaining_capacity": max(capacity - sold, 0) if capacity > 0 else None,
        }

    @staticmethod
    def _normalize_review_provider_type(value: Any) -> str:
        normalized = str(value or "").strip().lower().replace("-", "_").replace(" ", "_")
        if normalized in {"hotel", "hotel_room", "room"}:
            return "hotel"
        if normalized in {"restaurant", "dining", "table", "table_booking"}:
            return "restaurant"
        if normalized in {"spa", "wellness"}:
            return "spa"
        if normalized in {"event", "ticket"}:
            return "event"
        return ""

    def _review_provider_type(self, review: dict[str, Any]) -> str:
        provider_type = self._normalize_review_provider_type(review.get("provider_type"))
        if provider_type:
            return provider_type

        booking_id = review.get("booking_id")
        if booking_id is not None:
            booking = self.vendor_bookings.find_one({"_id": booking_id}, {"provider_type": 1, "service": 1}) or {}
            provider_type = self._normalize_review_provider_type(booking.get("provider_type"))
            if provider_type:
                return provider_type
            service_name = str(booking.get("service") or "").lower()
        else:
            service_name = str(review.get("service") or "").lower()

        for keyword, resolved in (
            ("hotel", "hotel"),
            ("room", "hotel"),
            ("spa", "spa"),
            ("event", "event"),
            ("ticket", "event"),
            ("restaurant", "restaurant"),
            ("table", "restaurant"),
        ):
            if keyword in service_name:
                return resolved

        vendor_id = review.get("vendor_id")
        if isinstance(vendor_id, ObjectId):
            verification = self.vendor_verification_details.find_one({"vendor_id": vendor_id}, {"category": 1}) or {}
            profile = self.vendor_profiles.find_one({"vendor_id": vendor_id}, {"category": 1}) or {}
            return self._normalize_review_provider_type(verification.get("category") or profile.get("category"))
        return ""

    def _provider_review_documents(self, vendor_id: ObjectId, provider_type: str | None = None) -> list[dict[str, Any]]:
        docs = list(self.vendor_reviews.find({"vendor_id": vendor_id}).sort("created_at", DESCENDING))
        normalized_type = self._normalize_review_provider_type(provider_type)
        if not normalized_type:
            return docs
        return [doc for doc in docs if self._review_provider_type(doc) == normalized_type]

    def _get_vendor_bundle(self, vendor_id: ObjectId, review_provider_type: str | None = None) -> dict[str, Any]:
        vendor = self.vendors.find_one({"_id": vendor_id}) or {}
        profile = self.vendor_profiles.find_one({"vendor_id": vendor_id}) or {}
        business = self.vendor_business_details.find_one({"vendor_id": vendor_id}) or {}
        verification = self.vendor_verification_details.find_one({"vendor_id": vendor_id}) or {}
        settings_doc = self.vendor_portal_settings.find_one({"vendor_id": vendor_id}) or {}
        general_settings = settings_doc.get("general", {}) if isinstance(settings_doc.get("general"), dict) else {}
        profile_settings = settings_doc.get("profile", {}) if isinstance(settings_doc.get("profile"), dict) else {}
        category = (
            verification.get("category")
            or profile.get("category")
            or "Restaurant"
        )
        gallery_service_type = review_provider_type or category
        try:
            gallery_query = self._asset_query(
                vendor_id, "gallery", normalize_service_type(gallery_service_type)
            )
        except ValueError:
            gallery_query = {"vendor_id": vendor_id, "asset_type": "gallery"}
        first_gallery = self.vendor_assets.find_one(
            gallery_query,
            sort=[("created_at", DESCENDING)],
        )
        review_docs = self._provider_review_documents(vendor_id, review_provider_type)
        review_ratings = [float(doc.get("rating") or doc.get("star_rating") or 0) for doc in review_docs]
        offer_service_type = review_provider_type or category
        try:
            normalized_offer_service = normalize_service_type(offer_service_type)
        except ValueError:
            normalized_offer_service = "restaurant"
        offer_settings = profile_settings.get(
            f"{normalized_offer_service}_settings", {}
        )
        if not isinstance(offer_settings, dict):
            offer_settings = {}
        settings_offer = next(
            (
                offer
                for offer in offer_settings.get("special_offers") or []
                if isinstance(offer, dict)
                and str(offer.get("title") or "").strip()
                and offer.get("active", True) is not False
            ),
            None,
        )
        if settings_offer:
            active_offer = {
                "promotion_name": str(settings_offer.get("title") or "").strip(),
                "internal_description": str(
                    settings_offer.get("description") or ""
                ).strip(),
                "service_type": normalized_offer_service,
                "source": f"{normalized_offer_service}_settings",
            }
        else:
            active_offer = next(
                (
                    promotion
                    for promotion in self.vendor_promotions.find(
                        {"vendor_id": vendor_id, "active": True}
                    ).sort("created_at", DESCENDING)
                    if self._promotion_applies_to_service(
                        promotion, normalized_offer_service
                    )
                ),
                None,
            )
        return {
            "vendor": vendor,
            "profile": profile,
            "profile_settings": profile_settings,
            "business": business,
            "verification": verification,
            "general": general_settings,
            "cover_image": (first_gallery or {}).get("asset_url"),
            # Do not invent ratings for providers without reviews.
            "rating": round(sum(review_ratings) / len(review_ratings), 1) if review_ratings else 0.0,
            "reviews_count": len(review_ratings),
            "category": str(category),
            "active_offer": active_offer,
        }

    def list_restaurants(
        self,
        customer_id: str,
        limit: int,
        skip: int,
        search: str | None = None,
        open_now: bool | None = None,
        top_rated: bool | None = None,
        with_offers: bool | None = None,
        nearby: bool = False,
        max_distance_km: float = 50.0,
    ) -> dict[str, Any]:
        vendor_docs = self._published_vendor_docs("restaurant", search=search)
        cards: list[dict[str, Any]] = []
        customer_lat, customer_lng = self._get_customer_coords(customer_id)
        customer_lat, customer_lng = self._get_customer_coords(customer_id)
        for vendor in vendor_docs:
            vendor_id = vendor["_id"]
            bundle = self._get_vendor_bundle(vendor_id, "restaurant")
            primary_category = str(bundle.get("category") or "restaurant").strip().lower()
            restaurant_settings = self._service_settings(bundle, "restaurant")
            # A provider may offer both a hotel and a restaurant. Use the
            # restaurant-specific identity for restaurant listings instead of
            # leaking the hotel's name into this feed.
            listing_category = "restaurant" if restaurant_settings.get("name") and primary_category != "restaurant" else primary_category
            # The restaurant feed must not expose hotel-only records. A
            # provider offering both services is still included through its
            # explicitly configured restaurant identity.
            if listing_category != "restaurant":
                continue
            service_settings = self._service_settings(bundle, listing_category)
            if service_settings.get("published") is False:
                continue
            slots = bundle["general"].get("booking_availability_slots", [])
            if open_now is True and not slots:
                continue
            if with_offers is True and not bundle["active_offer"]:
                continue

            vendor_lat, vendor_lng = self._get_vendor_coords(bundle, listing_category)
            distance_km = self._distance_between_km(customer_lat, customer_lng, vendor_lat, vendor_lng)
            if nearby and (distance_km is None or distance_km > max_distance_km):
                continue
            room_image = None
            if listing_category == "hotel":
                room = self.vendor_rooms.find_one(
                    {"vendor_id": vendor_id, "available": True, "images": {"$exists": True, "$ne": []}},
                    {"images": 1},
                    sort=[("created_at", DESCENDING)],
                )
                room_image = next((image for image in (room or {}).get("images", []) if image), None)
            name = service_settings.get("name") or bundle["vendor"].get("business_name") or bundle["profile"].get("business_name")
            if not name:
                continue
            location = (
                service_settings.get("address")
                or service_settings.get("city")
                or bundle["profile_settings"].get("location_label")
                or bundle["general"].get("business_address")
                or bundle["business"].get("address")
                or bundle["business"].get("city")
            )
            cards.append(
                {
                    "id": str(vendor_id),
                    "name": name,
                    "category": listing_category,
                    "service_type": listing_category,
                    "entity_type": listing_category,
                    "rating": bundle["rating"],
                    "avg_rating": bundle["rating"],
                    "reviews_count": bundle["reviews_count"],
                    "distance_km": distance_km,
                    "location": location,
                    "address": service_settings.get("address") or bundle["general"].get("business_address") or bundle["business"].get("address"),
                    "city": service_settings.get("city") or bundle["business"].get("city"),
                    "latitude": vendor_lat,
                    "longitude": vendor_lng,
                    "is_open_now": self._service_is_open(service_settings, bool(slots)),
                    "opening_time": service_settings.get("opening_time"),
                    "closing_time": service_settings.get("closing_time"),
                    "profile_image_url": self._service_profile_image(bundle, service_settings),
                    "cover_image_url": room_image or bundle["cover_image"],
                    "offer_text": (bundle["active_offer"] or {}).get("promotion_name"),
                }
            )
        if top_rated:
            cards.sort(key=lambda row: row.get("rating", 0), reverse=True)
        total = len(cards)
        return {"items": cards[skip : skip + limit], "total": total}

    def list_hotels(
        self,
        customer_id: str,
        limit: int,
        skip: int,
        search: str | None = None,
        nearby: bool = False,
        max_distance_km: float = 50.0,
    ) -> dict[str, Any]:
        vendor_docs = self._published_vendor_docs("hotel", search=search)
        cards: list[dict[str, Any]] = []
        customer_lat, customer_lng = self._get_customer_coords(customer_id)
        for vendor in vendor_docs:
            vendor_id = vendor["_id"]
            bundle = self._get_vendor_bundle(vendor_id, "hotel")
            service_settings = self._service_settings(bundle, "hotel")
            if service_settings.get("published") is False:
                continue
            rooms = list(self.vendor_rooms.find({"vendor_id": vendor_id, "available": True}))
            # Room inventory is the source of truth for hotel visibility. A
            # provider may have an old/misclassified profile category while
            # actively publishing hotel rooms.
            if bundle["category"].lower() != "hotel" and not rooms:
                continue
            min_price = 150.0
            if rooms:
                min_price = min(float(r.get("base_price", 150.0)) for r in rooms)
            has_rooms = len(rooms) > 0
            property_amenities = [
                str(amenity).strip()
                for amenity in service_settings.get("amenities") or []
                if str(amenity).strip()
            ]
            room_amenities = [
                str(amenity).strip()
                for room in rooms
                for amenity in room.get("amenities") or []
                if str(amenity).strip()
            ]
            amenities = list(dict.fromkeys([*property_amenities, *room_amenities]))
            room_image = next((image for room in rooms for image in (room.get("images") or []) if image), None)
            vendor_lat, vendor_lng = self._get_vendor_coords(bundle, "hotel")
            distance_km = self._distance_between_km(customer_lat, customer_lng, vendor_lat, vendor_lng)
            if nearby and (distance_km is None or distance_km > max_distance_km):
                continue
            cards.append(
                {
                    "id": str(vendor_id),
                    "title": service_settings.get("name") or bundle["vendor"].get("business_name") or bundle["profile"].get("business_name") or "Unnamed Hotel",
                    "service_type": "hotel",
                    "entity_type": "hotel",
                    "rating": str(bundle["rating"]),
                    "reviews": str(bundle["reviews_count"]),
                    "location": f"{service_settings.get('address') or service_settings.get('city') or bundle['general'].get('business_address') or bundle['business'].get('city') or 'Location unavailable'}",
                    "distance_km": distance_km,
                    "price": str(int(min_price)),
                    "status": "Available" if has_rooms else "Limited",
                    "is_open_now": self._service_is_open(service_settings, has_rooms),
                    "opening_time": service_settings.get("opening_time"),
                    "closing_time": service_settings.get("closing_time"),
                    "badge": (bundle["active_offer"] or {}).get("promotion_name"),
                    "badgeColor": "#3b82f6",
                    "amenities": amenities,
                    "profile_image_url": self._service_profile_image(bundle, service_settings),
                    "image": room_image or bundle["cover_image"],
                }
            )
        total = len(cards)
        return {"items": cards[skip : skip + limit], "total": total}

    def get_hotel_details(self, customer_id: str, hotel_id: str) -> dict[str, Any] | None:
        vendor = self.vendors.find_one({"_id": self._oid(hotel_id), "status": "approved"})
        if not vendor:
            return None
        vendor_id = vendor["_id"]
        if not self._is_public_service(vendor_id, "hotel"):
            return None
        bundle = self._get_vendor_bundle(vendor_id, "hotel")
        service_settings = self._service_settings(bundle, "hotel")
        if service_settings.get("published") is False:
            return None
        customer_lat, customer_lng = self._get_customer_coords(customer_id)
        vendor_lat, vendor_lng = self._get_vendor_coords(bundle, bundle["category"])
        rooms = list(self.vendor_rooms.find({"vendor_id": vendor_id, "available": True}))
        if bundle["category"].lower() != "hotel" and not rooms:
            return None
        rooms_count = self.vendor_rooms.count_documents({"vendor_id": vendor_id, "available": True})
        gallery_count = self.vendor_assets.count_documents(
            self._asset_query(vendor_id, "gallery", "hotel")
        )
        offers = self._list_service_offers(vendor_id, "hotel", service_settings)
        room_amenities = []
        for room in rooms:
            for amenity in room.get("amenities") or []:
                normalized_amenity = str(amenity).strip()
                if normalized_amenity and normalized_amenity not in room_amenities:
                    room_amenities.append(normalized_amenity)
        property_amenities = [
            str(amenity).strip()
            for amenity in service_settings.get("amenities") or []
            if str(amenity).strip()
        ]
        amenities = list(dict.fromkeys([*property_amenities, *room_amenities]))
        min_price = 0.0
        if rooms:
            min_price = min(float(r.get("base_price", 150.0)) for r in rooms)
        return {
            "id": str(vendor_id),
            "title": service_settings.get("name") or bundle["vendor"].get("business_name") or bundle["profile"].get("business_name") or "Unnamed Hotel",
            "category": bundle["category"],
            "rating": str(bundle["rating"]),
            "reviews": str(bundle["reviews_count"]),
            "location": service_settings.get("address") or service_settings.get("city") or bundle["general"].get("business_address") or bundle["business"].get("city") or "",
            "distance_km": self._distance_between_km(customer_lat, customer_lng, vendor_lat, vendor_lng),
            "address": service_settings.get("address") or bundle["general"].get("business_address") or bundle["business"].get("address") or "",
            "about": service_settings.get("about") or bundle["business"].get("business_description") or bundle["profile"].get("about_business") or "",
            "profile_image_url": self._service_profile_image(bundle, service_settings),
            "image": next((image for room in rooms for image in (room.get("images") or []) if image), None)
            or bundle["cover_image"],
            "price": str(int(min_price)),
            "status": "Available",
            "is_open_now": self._service_is_open(service_settings, bool(rooms)),
            "opening_time": service_settings.get("opening_time"),
            "closing_time": service_settings.get("closing_time"),
            "amenities": amenities,
            "offers": offers,
            "tabs": {
                "overview": True,
                "rooms_count": int(rooms_count),
                "gallery_count": int(gallery_count),
                "offers_count": len(offers),
            },
            "contact": {
                "phone": bundle["general"].get("front_desk_phone"),
                "reservations_email": bundle["general"].get("reservations_email"),
            }
        }

    def list_hotel_rooms(self, hotel_id: str) -> list[dict[str, Any]]:
        docs = list(self.vendor_rooms.find({"vendor_id": self._oid(hotel_id), "available": True}).sort("created_at", DESCENDING))
        rooms = []
        for doc in docs:
            base_price = float(doc.get("base_price", 150.0))
            images = doc.get("images") or []
            rooms.append({
                "id": str(doc["_id"]),
                "title": doc.get("name") or "Standard Room",
                "bed": doc.get("bed_type") or "King Bed",
                "guests": f"Max {doc.get('max_guests', 2)} guests",
                "price": str(int(base_price)),
                "totalPrice": str(int(base_price * 2)),
                "nights": "2 nights",
                "image": images[0] if images else None,
                "amenities": doc.get("amenities") or ["WiFi", "AC"],
                "weekend_price": float(doc.get("weekend_price", base_price)),
                "default_discount_percent": float(
                    doc.get("default_discount_percent", 0)
                ),
                "tax_included": bool(doc.get("tax_included", True)),
                "inventory_count": int(doc.get("inventory_count", 1)),
                "min_stay_nights": int(doc.get("min_stay_nights", 1)),
                "max_stay_nights": int(doc.get("max_stay_nights", 30)),
            })
        return rooms

    def get_hotel_room_details(self, room_id: str) -> dict[str, Any] | None:
        doc = self.vendor_rooms.find_one({"_id": self._oid(room_id)})
        if not doc:
            return None
        base_price = float(doc.get("base_price", 298.0))
        nights = 2
        room_rate = base_price * nights
        tax_included = bool(doc.get("tax_included", True))
        taxes = 0.0 if tax_included else room_rate * 0.2
        raw_amenities = doc.get("amenities") if isinstance(doc.get("amenities"), list) else []
        amenities_with_icons = []
        for name in raw_amenities:
            lower_name = name.lower()
            icon = "wifi"
            if "air" in lower_name or "ac" in lower_name:
                icon = "snow"
            elif "tv" in lower_name:
                icon = "tv-outline"
            elif "coffee" in lower_name or "cafe" in lower_name:
                icon = "cafe-outline"
            elif "bath" in lower_name:
                icon = "water-outline"
            elif "balcony" in lower_name:
                icon = "business-outline"
            amenities_with_icons.append({"name": name, "icon": icon})
        return {
            "id": str(doc["_id"]),
            "hotel_id": str(doc.get("vendor_id")),
            "vendor_id": str(doc.get("vendor_id")),
            "title": doc.get("name") or "Room",
            "status": "Available" if doc.get("available", True) else "Unavailable",
            "size": f"{doc['size_sqm']} m²" if doc.get("size_sqm") is not None else "",
            "guests": f"{doc['max_guests']} Guests" if doc.get("max_guests") is not None else "",
            "bed": doc.get("bed_type") or "",
            "view": doc.get("view") or doc.get("room_view") or "",
            "images": doc.get("images") if isinstance(doc.get("images"), list) else [],
            "amenities": amenities_with_icons,
            "description": doc.get("description") or "",
            "number_of_beds": int(doc.get("number_of_beds", 1)),
            "weekend_price": float(doc.get("weekend_price", base_price)),
            "default_discount_percent": float(
                doc.get("default_discount_percent", 0)
            ),
            "tax_included": tax_included,
            "inventory_count": int(doc.get("inventory_count", 1)),
            "min_stay_nights": int(doc.get("min_stay_nights", 1)),
            "max_stay_nights": int(doc.get("max_stay_nights", 30)),
            "price": {
                "rate": str(int(room_rate)),
                "taxes": str(int(taxes)),
                "total": str(int(room_rate + taxes)),
                "tax_included": tax_included,
            }
        }

    def list_hotel_assets(self, hotel_id: str, asset_type: str) -> list[dict[str, Any]]:
        vendor_id = self._oid(hotel_id)
        docs = self.vendor_assets.find(
            self._asset_query(vendor_id, asset_type, "hotel")
        ).sort("created_at", DESCENDING)
        return [self._serialize(doc) for doc in docs]

    def get_hotel_reviews_payload(self, hotel_id: str) -> dict[str, Any]:
        return self.get_provider_reviews_payload(hotel_id, "hotel")

    def get_home_feed(self, customer_id: str) -> dict[str, Any]:
        restaurants = self.list_restaurants(customer_id=customer_id, limit=50, skip=0, nearby=True).get("items", [])
        featured = restaurants[:6]
        return {
            "greeting": "Good Morning",
            "plan_for_me": {"title": "Plan for me", "subtitle": "Tell us your mood, budget & time"},
            "quick_access": [
                {"key": "dining", "label": "Dining"},
                {"key": "events", "label": "Events"},
                {"key": "spa", "label": "Spa"},
                {"key": "hotels", "label": "Hotels"},
            ],
            "trending_now": self.get_trending_hotels(customer_id),
            "featured_experiences": featured,
        }

    def get_trending_hotels(self, customer_id: str, limit: int = 6) -> list[dict[str, Any]]:
        restaurants = self.list_hotels(customer_id=customer_id, limit=50, skip=0, nearby=True).get("items", [])
        trending: list[dict[str, Any]] = []
        for card in restaurants:
            vendor_id = self._oid(card["id"])
            category = "hotel"

            # Trending Now is intentionally hotel-only. A hotel is eligible
            # only while it has at least one available room right now.
            has_available_room = self.vendor_rooms.count_documents(
                {"vendor_id": vendor_id, "available": True},
                limit=1,
            ) > 0
            if not has_available_room:
                continue

            room_image = self.vendor_rooms.find_one(
                {"vendor_id": vendor_id, "available": True, "images": {"$exists": True, "$ne": []}},
                {"images": 1},
                sort=[("created_at", DESCENDING)],
            )
            uploaded_image = next(
                (image for image in (room_image or {}).get("images", []) if image),
                None,
            )

            usage_count = self.vendor_bookings.count_documents(
                {
                    "vendor_id": vendor_id,
                    "status": {"$nin": ["cancelled", "rejected"]},
                }
            )
            trending.append(
                {
                    **card,
                    "cover_image_url": uploaded_image or card.get("cover_image_url"),
                    "entity_type": category,
                    "detail_route": f"/home/hotels/{card['id']}",
                    "usage_count": usage_count,
                }
            )

        trending.sort(
            key=lambda row: (
                row["usage_count"],
                row.get("reviews_count", 0),
                row.get("rating", 0),
            ),
            reverse=True,
        )
        return trending[: max(1, min(limit, 50))]

    def list_spas(self, customer_id: str, limit: int, skip: int, search: str | None = None, nearby: bool = False, max_distance_km: float = 50.0) -> dict[str, Any]:
        public_spas = self._published_vendor_docs("spa", search=search)
        items = []
        customer_lat, customer_lng = self._get_customer_coords(customer_id)
        for vendor in public_spas:
            bundle = self._get_vendor_bundle(vendor["_id"], "spa")
            settings = self._service_settings(bundle, "spa")
            name = settings.get("name") or vendor.get("business_name") or "Unnamed Spa"
            lat, lng = self._get_vendor_coords(bundle, "spa")
            distance = self._distance_between_km(customer_lat, customer_lng, lat, lng)
            if nearby and (distance is None or distance > max_distance_km):
                continue
            items.append({"id": str(vendor["_id"]), "name": name, "title": name, "category": "spa", "service_type": "spa", "entity_type": "spa", "rating": bundle["rating"], "reviews_count": bundle["reviews_count"], "distance_km": distance, "location": settings.get("address") or settings.get("city"), "profile_image_url": self._service_profile_image(bundle, settings), "cover_image_url": bundle["cover_image"]})
        for item in items:
            item["title"] = item.get("name") or "Spa"
            item["type"] = item.get("category") or "Wellness"
            item["reviews"] = item.get("reviews_count", 0)
            item["image"] = item.get("cover_image_url")
        return {"items": items[skip : skip + limit], "total": len(items)}

    def get_spa_details(self, customer_id: str, spa_id: str) -> dict[str, Any] | None:
        row = self.get_restaurant_details(customer_id, spa_id, service_type="spa")
        if not row:
            return None
        row["title"] = row.get("name") or "Spa"
        row["type"] = row.get("category") or "Wellness"
        return row

    def list_spa_assets(self, spa_id: str, asset_type: str) -> list[dict[str, Any]]:
        return self.list_restaurant_assets(spa_id, asset_type, "spa")

    def list_spa_offers(self, spa_id: str) -> list[dict[str, Any]]:
        return self.list_restaurant_offers(spa_id, "spa")

    def list_provider_services(
        self, provider_id: str, service_type: str = "hotel"
    ) -> list[dict[str, Any]]:
        vendor_id = self._oid(provider_id)
        if not self.vendors.find_one({"_id": vendor_id, "status": "approved"}, {"_id": 1}):
            return []
        normalized = normalize_service_type(service_type)
        query: dict[str, Any] = {
            "vendor_id": vendor_id,
            "$and": [{"$or": [{"available": True}, {"active_status": True}]}],
        }
        if normalized == "hotel":
            query["$and"].append(
                {
                    "$or": [
                        {"service_type": "hotel"},
                        {"service_type": {"$exists": False}},
                    ]
                }
            )
        else:
            query["$and"].append({"service_type": normalized})
        docs = self.vendor_services.find(query).sort("created_at", DESCENDING)
        return [self._serialize(doc) for doc in docs]

    def list_categories(self) -> dict[str, Any]:
        # Count each customer-visible service independently. A single provider
        # may publish both a restaurant and a hotel, so its primary onboarding
        # category cannot be used as the category total.
        count_customer_id = str(ObjectId())
        counts = {
            "restaurant": int(
                self.list_restaurants(count_customer_id, limit=1, skip=0).get("total", 0)
            ),
            "hotel": int(
                self.list_hotels(count_customer_id, limit=1, skip=0).get("total", 0)
            ),
            "spa": int(
                self.list_spas(count_customer_id, limit=1, skip=0).get("total", 0)
            ),
            "event": 0,
            "happy_hour": 0,
        }
        counts["event"] = sum(
            1
            for event in self.vendor_events.find(
                {
                    "status": "published",
                    "active": {"$ne": False},
                    "$nor": [self._legacy_happy_hour_match()],
                }
            )
            if self._event_is_not_expired(event)
        )
        counts["happy_hour"] = int(
            self.list_happy_hours(
                count_customer_id,
                limit=1,
                skip=0,
            ).get("total", 0)
        )
        return {
            "items": [
                {
                    "key": key,
                    "label": key.replace("_", " ").title(),
                    "count": value,
                }
                for key, value in counts.items()
            ]
        }

    def get_customer_profile(self, customer_id: str) -> dict[str, Any]:
        profile = self._serialize(self.users.find_one({"_id": self._oid(customer_id)})) or {}
        for sensitive_key in ("password_hash", "hashed_password", "refresh_token"):
            profile.pop(sensitive_key, None)
        return profile

    def update_customer_profile(self, customer_id: str, data: dict[str, Any]) -> dict[str, Any]:
        allowed = {key: value for key, value in data.items() if key in {"full_name", "gender", "email", "phone", "date_of_birth", "location_enabled", "latitude", "longitude", "location_accuracy_meters"}}
        allowed["updated_at"] = datetime.now(UTC)
        self.users.update_one({"_id": self._oid(customer_id)}, {"$set": allowed})
        return self.get_customer_profile(customer_id)

    def get_customer_notifications(self, customer_id: str, limit: int = 50, skip: int = 0) -> dict[str, Any]:
        query = {"user_id": self._oid(customer_id)}
        total = int(self.notifications.count_documents(query))
        docs = self.notifications.find(query).sort("created_at", DESCENDING).skip(skip).limit(limit)
        return {"items": [self._serialize(doc) for doc in docs], "total": total, "unread_count": int(self.notifications.count_documents({**query, "read": {"$ne": True}}))}

    def _enrich_customer_booking(self, booking: dict[str, Any]) -> dict[str, Any]:
        """Attach current provider/event details to a customer booking."""
        result = self._serialize(booking) or {}
        history = list(result.get("status_history") or [])
        if not any(
            str(entry.get("status") or "").lower() in {"pending", "requested"}
            for entry in history
        ):
            history.insert(
                0,
                {
                    "status": "pending",
                    "at": result.get("requested_at") or result.get("created_at"),
                    "actor": "customer",
                    "label": "Booking request sent by customer",
                },
            )
        if result.get("accepted_at") and not any(
            str(entry.get("status") or "").lower() in {"confirmed", "accepted"}
            for entry in history
        ):
            history.append(
                {
                    "status": "confirmed",
                    "at": result["accepted_at"],
                    "actor": "service_provider",
                    "label": "Booking approved by service provider",
                }
            )
        result["status_history"] = history
        vendor_id = booking.get("vendor_id")
        if not isinstance(vendor_id, ObjectId):
            try:
                vendor_id = ObjectId(str(vendor_id))
            except (InvalidId, TypeError):
                return result

        review = self.vendor_reviews.find_one(
            {"booking_id": booking.get("_id"), "customer_id": booking.get("customer_id")}
        )
        if review:
            result["review"] = self._serialize(review)
            result["has_review"] = True
        else:
            result["has_review"] = False

        provider_type = str(booking.get("provider_type") or "restaurant").lower()
        bundle = self._get_vendor_bundle(vendor_id, provider_type)
        event_id = booking.get("event_id")
        if provider_type == "event" and not isinstance(event_id, ObjectId):
            try:
                event_id = ObjectId(str(event_id))
            except (InvalidId, TypeError):
                event_id = None
        if provider_type == "event" and isinstance(event_id, ObjectId):
            event = self.vendor_events.find_one({"_id": event_id}) or {}
            provider_name = event.get("title") or result.get("service") or "Event"
            provider_area = event.get("venue") or event.get("location") or "Location unavailable"
            result.update({
                "provider_name": provider_name,
                "provider_area": provider_area,
                "provider_address": provider_area,
                "provider_phone": bundle.get("general", {}).get("front_desk_phone"),
                "provider_image": event.get("banner_image_url") or bundle.get("cover_image"),
                "name": provider_name,
                "location": provider_area,
            })
            return result

        service_type = "hotel" if provider_type in {"hotel", "hotel_room"} else "spa" if provider_type == "spa" else "restaurant"
        settings = self._service_settings(bundle, service_type)
        address = (
            settings.get("address")
            or settings.get("city")
            or bundle.get("general", {}).get("business_address")
            or bundle.get("business", {}).get("address")
            or bundle.get("business", {}).get("city")
        )
        provider_name = settings.get("name") or bundle.get("vendor", {}).get("business_name") or result.get("service") or "Provider"
        provider_area = address or "Location unavailable"
        result.update({
            "provider_name": provider_name,
            "provider_area": provider_area,
            "provider_address": address,
            "provider_phone": settings.get("phone") or bundle.get("general", {}).get("front_desk_phone"),
            "provider_image": self._service_profile_image(bundle, settings)
            or bundle.get("cover_image"),
            "name": provider_name,
            "location": provider_area,
        })
        return result

    def update_customer_notification_preferences(self, customer_id: str, data: dict[str, Any]) -> dict[str, Any]:
        current = self.users.find_one({"_id": self._oid(customer_id)}, {"notification_preferences": 1}) or {}
        existing = current.get("notification_preferences") if isinstance(current.get("notification_preferences"), dict) else {}
        preferences = {
            "nearby_events": bool(data.get("nearby_events", existing.get("nearby_events", False))),
            "booking_reminders": bool(data.get("booking_reminders", existing.get("booking_reminders", True))),
        }
        self.users.update_one({"_id": self._oid(customer_id)}, {"$set": {"notification_preferences": preferences, "updated_at": datetime.now(UTC)}})
        return self.get_customer_profile(customer_id)

    def get_customer_points_summary(self, customer_id: str) -> dict[str, Any]:
        customer_obj_id = self._oid(customer_id)
        now = datetime.now(UTC)
        expired_points = 0
        for collection in (self.vendor_bookings, self.vendor_reviews):
            for row in collection.find(
                {
                    "customer_id": customer_obj_id,
                    "points_awarded": {"$gt": 0},
                    "points_expires_at": {"$lte": now},
                    "loyalty_points_expired_at": {"$exists": False},
                },
                {"points_awarded": 1},
            ):
                result = collection.update_one(
                    {"_id": row["_id"], "loyalty_points_expired_at": {"$exists": False}},
                    {"$set": {"loyalty_points_expired_at": now}},
                )
                if result.modified_count:
                    expired_points += int(row.get("points_awarded") or 0)
        profile = self.get_customer_profile(customer_id)
        points = max(int(profile.get("points_balance") or 0) - expired_points, 0)
        if expired_points:
            self.users.update_one(
                {"_id": customer_obj_id},
                {"$set": {"points_balance": points, "updated_at": now}},
            )
        tier = "gold" if points >= 500 else "silver" if points >= 200 else "bronze"
        return {"points_balance": points, "tier": tier, "expired_points": expired_points}

    def list_customer_reviews(self, customer_id: str, limit: int, skip: int) -> dict[str, Any]:
        customer_obj_id = self._oid(customer_id)
        query = {"customer_id": customer_obj_id}
        total = int(self.vendor_reviews.count_documents(query))
        docs = self.vendor_reviews.find(query).sort("created_at", DESCENDING).skip(skip).limit(limit)
        items: list[dict[str, Any]] = []

        for doc in docs:
            serialized = self._serialize(doc) or {}
            rating = int(doc.get("rating") or doc.get("star_rating") or 0)
            vendor_id = doc.get("vendor_id")
            if not isinstance(vendor_id, ObjectId):
                try:
                    vendor_id = ObjectId(str(vendor_id))
                except (InvalidId, TypeError):
                    vendor_id = None

            provider_name = str(doc.get("provider_name") or doc.get("service") or "Service provider")
            provider_image = ""
            if isinstance(vendor_id, ObjectId):
                bundle = self._get_vendor_bundle(vendor_id)
                service_type = str(doc.get("provider_type") or "restaurant").lower()
                if service_type in {"hotel", "hotel_room"}:
                    service_type = "hotel"
                settings = self._service_settings(bundle, service_type)
                provider_name = str(
                    settings.get("name")
                    or bundle.get("vendor", {}).get("business_name")
                    or bundle.get("business", {}).get("business_name")
                    or provider_name
                )
                provider_image = str(
                    self._service_profile_image(bundle, settings)
                    or bundle.get("cover_image")
                    or ""
                )

            booking = self.vendor_bookings.find_one(
                {"_id": doc.get("booking_id"), "customer_id": customer_obj_id},
                {"booking_code": 1},
            ) or {}
            items.append(
                {
                    **serialized,
                    "rating": rating,
                    "star_rating": rating,
                    "review_text": doc.get("review_text") or doc.get("comment") or "",
                    "provider_name": provider_name,
                    "provider_image": provider_image,
                    "booking_code": booking.get("booking_code"),
                    "vendor_reply": doc.get("vendor_reply") or doc.get("reply"),
                }
            )

        return {"items": items, "total": total}

    def list_saved_items(self, customer_id: str) -> dict[str, Any]:
        docs = self.customer_saved_items.find({"customer_id": self._oid(customer_id)}).sort("created_at", DESCENDING)
        items: list[dict[str, Any]] = []
        for saved in docs:
            entity_type = str(saved.get("entity_type") or "").lower()
            entity_id = str(saved.get("entity_id") or "")
            detail = None
            if entity_type in {"restaurant", "spa", "dining"}:
                detail = self.get_restaurant_details(customer_id, entity_id)
            elif entity_type == "hotel":
                detail = self.get_hotel_details(customer_id, entity_id)
            elif entity_type == "event":
                detail = self.get_event_details(customer_id, entity_id)
            if detail:
                items.append({"entity_type": entity_type, "entity_id": entity_id, **detail})
        return {"items": items, "total": len(items)}

    def add_saved_item(self, customer_id: str, entity_type: str, entity_id: str) -> dict[str, Any]:
        now = datetime.now(UTC)
        self.customer_saved_items.update_one(
            {"customer_id": self._oid(customer_id), "entity_type": entity_type.lower(), "entity_id": entity_id},
            {"$set": {"updated_at": now}, "$setOnInsert": {"created_at": now}},
            upsert=True,
        )
        return {"entity_type": entity_type.lower(), "entity_id": entity_id, "saved": True}

    def remove_saved_item(self, customer_id: str, entity_type: str, entity_id: str) -> dict[str, Any]:
        self.customer_saved_items.delete_one({"customer_id": self._oid(customer_id), "entity_type": entity_type.lower(), "entity_id": entity_id})
        return {"entity_type": entity_type.lower(), "entity_id": entity_id, "saved": False}

    def list_recent_searches(self, customer_id: str, limit: int = 20) -> dict[str, Any]:
        docs = self.customer_recent_searches.find({"customer_id": self._oid(customer_id)}).sort("created_at", DESCENDING).limit(limit)
        return {"items": [self._serialize(doc) for doc in docs]}

    def add_recent_search(self, customer_id: str, query: str) -> None:
        if query.strip():
            self.customer_recent_searches.insert_one({"customer_id": self._oid(customer_id), "query": query.strip(), "created_at": datetime.now(UTC)})

    def clear_recent_searches(self, customer_id: str) -> dict[str, Any]:
        result = self.customer_recent_searches.delete_many({"customer_id": self._oid(customer_id)})
        return {"deleted": int(result.deleted_count)}

    def global_search(self, customer_id: str, query: str, limit: int = 20) -> dict[str, Any]:
        self.add_recent_search(customer_id, query)
        search = query.strip()
        restaurants = self.list_restaurants(customer_id, limit=limit, skip=0, search=search).get("items", [])
        events = self.list_events(customer_id, limit=limit, skip=0, search=search).get("items", [])
        hotels = self.list_hotels(customer_id, limit=limit, skip=0, search=search).get("items", [])
        return {"items": [{**row, "entity_type": "restaurant"} for row in restaurants] + [{**row, "entity_type": "event"} for row in events] + [{**row, "entity_type": "hotel"} for row in hotels]}

    def create_plan_session(self, customer_id: str) -> dict[str, Any]:
        now = datetime.now(UTC)
        result = self.customer_plan_sessions.insert_one({"customer_id": self._oid(customer_id), "values": {}, "created_at": now, "updated_at": now})
        return self._serialize(self.customer_plan_sessions.find_one({"_id": result.inserted_id})) or {}

    def update_plan_session(self, customer_id: str, session_id: str, key: str, value: Any) -> dict[str, Any] | None:
        self.customer_plan_sessions.update_one({"_id": self._oid(session_id), "customer_id": self._oid(customer_id)}, {"$set": {f"values.{key}": value, "updated_at": datetime.now(UTC)}})
        return self._serialize(self.customer_plan_sessions.find_one({"_id": self._oid(session_id), "customer_id": self._oid(customer_id)}))

    def get_restaurant_details(self, customer_id: str, restaurant_id: str, service_type: str = "restaurant") -> dict[str, Any] | None:
        service_type = normalize_service_type(service_type)
        vendor = self.vendors.find_one({"_id": self._oid(restaurant_id), "status": "approved"})
        if not vendor:
            return None
        vendor_id = vendor["_id"]
        if not self._is_public_service(vendor_id, service_type):
            return None
        bundle = self._get_vendor_bundle(vendor_id, service_type)
        menu_count = self.vendor_assets.count_documents(
            self._asset_query(vendor_id, "menu", service_type)
        )
        gallery_count = self.vendor_assets.count_documents(
            self._asset_query(vendor_id, "gallery", service_type)
        )
        opening_slots = bundle["general"].get("booking_availability_slots", [])
        customer_lat, customer_lng = self._get_customer_coords(customer_id)
        service_settings = self._service_settings(bundle, service_type)
        if service_settings.get("published") is False:
            return None
        offers_count = len(
            self._list_service_offers(vendor_id, service_type, service_settings)
        )
        vendor_lat, vendor_lng = self._get_vendor_coords(bundle, service_type)
        display_label = service_type.title()
        location = (
            service_settings.get("address")
            or service_settings.get("city")
            or bundle["profile_settings"].get("location_label")
            or bundle["general"].get("business_address")
            or bundle["business"].get("address")
            or bundle["business"].get("city")
            or "Location unavailable"
        )
        return {
            "id": str(vendor_id),
            "name": service_settings.get("name") or bundle["vendor"].get("business_name") or bundle["profile"].get("business_name") or f"Unnamed {display_label}",
            "category": service_type,
            "rating": bundle["rating"],
            "reviews_count": bundle["reviews_count"],
            "distance_km": self._distance_between_km(customer_lat, customer_lng, vendor_lat, vendor_lng),
            "location": location,
            "address": service_settings.get("address") or bundle["general"].get("business_address") or bundle["business"].get("address"),
            "city": service_settings.get("city") or bundle["business"].get("city"),
            "latitude": vendor_lat,
            "longitude": vendor_lng,
            "about": service_settings.get("about")
            or bundle["business"].get("business_description")
            or bundle["profile"].get("about_business")
            or "Welcome to our venue.",
            "profile_image_url": self._service_profile_image(bundle, service_settings),
            "cover_image_url": bundle["cover_image"],
            "opening_hours": {
                "monday_friday": "12:00 PM - 11:00 PM",
                "saturday_sunday": "11:00 AM - 12:00 AM",
                "open_time": service_settings.get("opening_time"),
                "close_time": service_settings.get("closing_time"),
                "is_open_now": self._service_is_open(service_settings, bool(opening_slots)),
                "available_times": service_settings.get("available_booking_times") or opening_slots,
            },
            "seating_preferences": service_settings.get("seating_preferences") or ["Indoor", "Outdoor", "No preference"],
            "booking_policy": service_settings.get("policy") or "You can modify or cancel this booking later.",
            "amenities": service_settings.get("amenities") or [],
            "tabs": {
                "overview": True,
                "menu_count": int(menu_count),
                "gallery_count": int(gallery_count),
                "offers_count": int(offers_count),
            },
            "contact": {
                "phone": service_settings.get("phone") or bundle["general"].get("front_desk_phone"),
                "reservations_email": service_settings.get("email") or bundle["general"].get("reservations_email"),
            },
        }

    def list_restaurant_assets(
        self,
        restaurant_id: str,
        asset_type: str,
        service_type: str = "restaurant",
    ) -> list[dict[str, Any]]:
        vendor_id = self._oid(restaurant_id)
        docs = self.vendor_assets.find(
            self._asset_query(vendor_id, asset_type, service_type)
        ).sort("created_at", DESCENDING)
        return [self._serialize(doc) for doc in docs]

    def list_restaurant_offers(
        self, restaurant_id: str, service_type: str = "restaurant"
    ) -> list[dict[str, Any]]:
        return self._list_service_offers(self._oid(restaurant_id), service_type)

    def list_restaurant_services(self, restaurant_id: str) -> list[dict[str, Any]]:
        return self.list_provider_services(restaurant_id, "restaurant")

    def get_provider_reviews_payload(self, provider_id: str, provider_type: str = "restaurant") -> dict[str, Any]:
        docs = self._provider_review_documents(self._oid(provider_id), provider_type)
        total = len(docs)
        ratings = [float(doc.get("rating") or doc.get("star_rating") or 0) for doc in docs]
        average = round(sum(ratings) / total, 1) if total else 0
        breakdown = {str(star): sum(1 for rating in ratings if int(rating) == star) for star in range(1, 6)}
        items = []
        for doc in docs:
            created_at = doc.get("created_at")
            if isinstance(created_at, datetime):
                date_label = created_at.strftime("%b %d, %Y")
            else:
                date_label = str(created_at or "")
            items.append({
                "id": str(doc["_id"]),
                "user": doc.get("customer_name") or "Anonymous",
                "date": date_label,
                "rating": int(doc.get("rating") or doc.get("star_rating") or 0),
                "comment": doc.get("review_text") or doc.get("comment") or "",
                "avatar": doc.get("customer_avatar") or doc.get("avatar_url") or "",
                "vendor_reply": doc.get("vendor_reply") or doc.get("reply"),
            })
        return {"average_rating": average, "total_reviews": total, "breakdown": breakdown, "items": items}

    def list_events(
        self,
        customer_id: str,
        limit: int,
        skip: int,
        search: str | None = None,
    ) -> dict[str, Any]:
        query: dict[str, Any] = {
            "status": "published",
            "active": {"$ne": False},
            "$nor": [self._legacy_happy_hour_match()],
        }
        if search:
            query["$and"] = [
                {
                    "$or": [
                        {"title": {"$regex": search, "$options": "i"}},
                        {"venue": {"$regex": search, "$options": "i"}},
                        {"event_type": {"$regex": search, "$options": "i"}},
                        {"category": {"$regex": search, "$options": "i"}},
                    ]
                }
            ]

        docs = list(
            self.vendor_events.find(query).sort(
                [("event_date", ASCENDING), ("start_time", ASCENDING), ("created_at", DESCENDING)]
            )
        )
        cards: list[dict[str, Any]] = []
        customer_lat, customer_lng = self._get_customer_coords(customer_id)

        for event in docs:
            if not self._event_is_not_expired(event):
                continue
            vendor_id = event.get("vendor_id")
            if not isinstance(vendor_id, ObjectId):
                continue

            vendor = self.vendors.find_one({"_id": vendor_id, "status": "approved"})
            if not vendor:
                continue

            bundle = self._get_vendor_bundle(vendor_id)
            event_lat, event_lng = self._get_event_coords(event, bundle)
            if event_lat is None or event_lng is None:
                continue

            active_offer = bundle.get("active_offer") or {}
            venue = str(event.get("venue") or "").strip()
            display_address = (
                venue
                or str(bundle["general"].get("business_address") or "").strip()
                or str(bundle["business"].get("address") or "").strip()
                or str(bundle["business"].get("city") or "").strip()
                or "Location unavailable"
            )
            event_type = normalize_event_category(
                event.get("event_type"),
                fallback="Culture",
            )
            capacity = int(event.get("capacity") or 0)
            booking_mode = self._event_booking_mode(event)
            booking_summary = self._event_booking_summary(customer_id, event["_id"], capacity)
            registration_open = self._event_registration_is_open(event)

            cards.append(
                {
                    "id": str(event["_id"]),
                    "vendor_id": str(vendor_id),
                    "title": str(event.get("title") or "Untitled Event").strip(),
                    "name": str(event.get("title") or "Untitled Event").strip(),
                    "category": str(event.get("category") or "Event").strip(),
                    "entity_type": "event",
                    "event_type": event_type,
                    "event_category": event_type,
                    "event_date": event.get("event_date"),
                    "end_date": event.get("end_date") or event.get("event_date"),
                    "start_time": event.get("start_time"),
                    "end_time": event.get("end_time"),
                    "timezone": event.get("timezone"),
                    "venue": venue,
                    "location": display_address,
                    "address": display_address,
                    "city": bundle["business"].get("city"),
                    "latitude": event_lat,
                    "longitude": event_lng,
                    "distance_km": self._distance_between_km(customer_lat, customer_lng, event_lat, event_lng),
                    "cover_image_url": event.get("banner_image_url")
                    or bundle["cover_image"]
                    or "https://images.unsplash.com/photo-1492684223066-81342ee5ff30?w=1200",
                    "banner_image_url": event.get("banner_image_url") or bundle["cover_image"],
                    "offer_text": active_offer.get("promotion_name") or event_type,
                    "description": event.get("description") or "",
                    "ticket_price": event.get("ticket_price"),
                    "capacity": event.get("capacity"),
                    "registration_deadline": event.get("registration_deadline"),
                    "registration_open": registration_open,
                    "booking_mode": booking_mode,
                    "can_book_on_map": (
                        booking_mode == "simple"
                        and registration_open
                        and not booking_summary["is_sold_out"]
                    ),
                    **booking_summary,
                    "detail_route": f"/home/events/{event['_id']}",
                }
            )

        total = len(cards)
        return {"items": cards[skip : skip + limit], "total": total}

    def list_happy_hours(
        self,
        customer_id: str,
        limit: int,
        skip: int,
        search: str | None = None,
    ) -> dict[str, Any]:
        current_docs_unfiltered = list(
            self.vendor_happy_hours.find(
                {"status": "published", "active": {"$ne": False}}
            ).sort(
                [
                    ("start_date", ASCENDING),
                    ("start_time", ASCENDING),
                    ("created_at", DESCENDING),
                ]
            )
        )
        current_docs = []
        for happy_hour in current_docs_unfiltered:
            legacy_event_id = str(happy_hour.get("legacy_event_id") or "")
            if ObjectId.is_valid(legacy_event_id):
                source_id = ObjectId(legacy_event_id)
                source_event = self.vendor_events.find_one(
                    {"_id": source_id},
                    {"_id": 1},
                )
                explicitly_marked = self.vendor_events.find_one(
                    {"_id": source_id, **self._legacy_happy_hour_match()},
                    {"_id": 1},
                )
                if source_event and not explicitly_marked:
                    continue
            current_docs.append(happy_hour)

        current_ids = {row["_id"] for row in current_docs}
        legacy_docs = [
            self._legacy_event_as_happy_hour(row)
            for row in self.vendor_events.find(
                {
                    "status": "published",
                    "active": {"$ne": False},
                    **self._legacy_happy_hour_match(),
                }
            )
            if row["_id"] not in current_ids
        ]
        docs = [*current_docs, *legacy_docs]
        normalized_search = str(search or "").strip().casefold()
        customer_lat, customer_lng = self._get_customer_coords(customer_id)
        cards: list[dict[str, Any]] = []

        for happy_hour in docs:
            searchable_text = " ".join(
                str(happy_hour.get(field) or "")
                for field in ("title", "venue", "offer_text", "description")
            ).casefold()
            if normalized_search and normalized_search not in searchable_text:
                continue
            is_visible, is_active_now = self._happy_hour_schedule_state(happy_hour)
            if not is_visible:
                continue
            vendor_id = happy_hour.get("vendor_id")
            if not isinstance(vendor_id, ObjectId):
                continue
            vendor = self.vendors.find_one(
                {"_id": vendor_id, "status": "approved"}
            )
            if not vendor:
                continue

            venue_type = str(
                happy_hour.get("venue_type") or "restaurant"
            ).strip().lower()
            review_type = venue_type if venue_type in SERVICE_TYPES else None
            bundle = self._get_vendor_bundle(vendor_id, review_type)
            latitude, longitude = self._get_event_coords(happy_hour, bundle)
            if latitude is None or longitude is None:
                continue
            venue = str(happy_hour.get("venue") or "").strip()
            address = (
                venue
                or str(bundle["general"].get("business_address") or "").strip()
                or str(bundle["business"].get("address") or "").strip()
                or str(bundle["business"].get("city") or "").strip()
                or "Location unavailable"
            )
            detail_route = {
                "restaurant": f"/home/dining/{vendor_id}",
                "hotel": f"/home/hotels/{vendor_id}",
                "spa": f"/home/spa/{vendor_id}",
            }.get(venue_type)
            happy_hour_price = happy_hour.get("happy_hour_price")

            cards.append(
                {
                    "id": str(happy_hour["_id"]),
                    "vendor_id": str(vendor_id),
                    "title": str(happy_hour.get("title") or "Happy Hour").strip(),
                    "name": str(happy_hour.get("title") or "Happy Hour").strip(),
                    "category": "Happy Hour",
                    "entity_type": "happy_hour",
                    "event_type": "Happy Hour",
                    "venue_type": venue_type,
                    "event_date": happy_hour.get("start_date"),
                    "start_date": happy_hour.get("start_date"),
                    "end_date": happy_hour.get("end_date"),
                    "days_of_week": happy_hour.get("days_of_week") or [],
                    "start_time": happy_hour.get("start_time"),
                    "end_time": happy_hour.get("end_time"),
                    "timezone": happy_hour.get("timezone"),
                    "venue": venue,
                    "location": address,
                    "address": address,
                    "city": bundle["business"].get("city"),
                    "latitude": latitude,
                    "longitude": longitude,
                    "distance_km": self._distance_between_km(
                        customer_lat,
                        customer_lng,
                        latitude,
                        longitude,
                    ),
                    "cover_image_url": happy_hour.get("banner_image_url")
                    or bundle["cover_image"]
                    or "https://images.unsplash.com/photo-1515003197210-e0cd71810b5f?w=1200",
                    "banner_image_url": happy_hour.get("banner_image_url")
                    or bundle["cover_image"],
                    "offer_text": happy_hour.get("offer_text") or "Happy Hour",
                    "description": happy_hour.get("description") or "",
                    "terms_and_conditions": happy_hour.get("terms_and_conditions")
                    or "",
                    "original_price": happy_hour.get("original_price"),
                    "happy_hour_price": happy_hour_price,
                    "discount_percent": happy_hour.get("discount_percent"),
                    "ticket_price": happy_hour_price,
                    "rating": bundle["rating"],
                    "reviews_count": bundle["reviews_count"],
                    "is_open_now": is_active_now,
                    "booking_mode": "detailed",
                    "can_book_on_map": False,
                    "current_booking_status": None,
                    "current_booking_code": None,
                    "is_sold_out": False,
                    "remaining_capacity": None,
                    "detail_route": detail_route,
                }
            )

        cards.sort(
            key=lambda row: (
                row.get("distance_km") is None,
                row.get("distance_km") or float("inf"),
                row.get("start_date") or "",
            )
        )
        total = len(cards)
        return {"items": cards[skip : skip + limit], "total": total}

    def get_event_details(self, customer_id: str, event_id: str) -> dict[str, Any] | None:
        event = self.vendor_events.find_one(
            {
                "_id": self._oid(event_id),
                "status": "published",
                "active": {"$ne": False},
                "$nor": [self._legacy_happy_hour_match()],
            }
        )
        if not event:
            return None
        if not self._event_is_not_expired(event):
            return None

        vendor_id = event.get("vendor_id")
        if not isinstance(vendor_id, ObjectId):
            return None

        vendor = self.vendors.find_one({"_id": vendor_id, "status": "approved"})
        if not vendor:
            return None

        bundle = self._get_vendor_bundle(vendor_id)
        event_lat, event_lng = self._get_event_coords(event, bundle)
        customer_lat, customer_lng = self._get_customer_coords(customer_id)
        active_offer = bundle.get("active_offer") or {}
        event_type = normalize_event_category(
            event.get("event_type"),
            fallback="Culture",
        )
        venue = str(event.get("venue") or "").strip()
        display_address = (
            venue
            or str(bundle["general"].get("business_address") or "").strip()
            or str(bundle["business"].get("address") or "").strip()
            or str(bundle["business"].get("city") or "").strip()
                or "Location unavailable"
        )
        capacity = int(event.get("capacity") or 0)
        booking_mode = self._event_booking_mode(event)
        booking_summary = self._event_booking_summary(customer_id, event["_id"], capacity)
        registration_open = self._event_registration_is_open(event)

        return {
            "id": str(event["_id"]),
            "vendor_id": str(vendor_id),
            "title": str(event.get("title") or "Untitled Event").strip(),
            "name": str(event.get("title") or "Untitled Event").strip(),
            "category": str(event.get("category") or "Event").strip(),
            "entity_type": "event",
            "event_type": event_type,
            "event_category": event_type,
            "event_date": event.get("event_date"),
            "end_date": event.get("end_date") or event.get("event_date"),
            "start_time": event.get("start_time"),
            "end_time": event.get("end_time"),
            "timezone": event.get("timezone"),
            "venue": venue,
            "location": display_address,
            "address": display_address,
            "city": bundle["business"].get("city"),
            "latitude": event_lat,
            "longitude": event_lng,
            "distance_km": self._distance_between_km(customer_lat, customer_lng, event_lat, event_lng),
            "cover_image_url": event.get("banner_image_url")
            or bundle["cover_image"]
            or "https://images.unsplash.com/photo-1492684223066-81342ee5ff30?w=1200",
            "banner_image_url": event.get("banner_image_url") or bundle["cover_image"],
            "offer_text": active_offer.get("promotion_name") or event_type,
            "description": event.get("description") or "",
            "ticket_price": event.get("ticket_price"),
            "capacity": event.get("capacity"),
            "registration_deadline": event.get("registration_deadline"),
            "registration_open": registration_open,
            "booking_mode": booking_mode,
            "can_book_on_map": (
                booking_mode == "simple"
                and registration_open
                and not booking_summary["is_sold_out"]
            ),
            **booking_summary,
            "detail_route": f"/home/events/{event['_id']}",
        }

    def get_event_booking_quote(
        self,
        customer_id: str,
        event_id: str,
        quantity: int,
        promo_code: str | None = None,
    ) -> dict[str, Any]:
        event = self.vendor_events.find_one(
            {
                "_id": self._oid(event_id),
                "status": "published",
                "active": {"$ne": False},
                "$nor": [self._legacy_happy_hour_match()],
            }
        )
        if not event:
            raise ValueError("Event not found.")
        if not self._event_registration_is_open(event):
            raise ValueError("Registration for this event is closed.")
        vendor_id = event.get("vendor_id")
        if not isinstance(vendor_id, ObjectId):
            raise ValueError("Event vendor is invalid.")
        vendor = self.vendors.find_one({"_id": vendor_id, "status": "approved"})
        if not vendor:
            raise ValueError("Provider not found.")
        capacity = int(event.get("capacity") or 0)
        sold = sum(
            int(row.get("quantity") or 0)
            for row in self.vendor_bookings.find(
                {
                    "event_id": event["_id"],
                    "status": {"$in": ["pending", "confirmed", "check_in"]},
                },
                {"quantity": 1},
            )
        )
        if capacity > 0 and sold + quantity > capacity:
            remaining = max(capacity - sold, 0)
            raise ValueError(
                f"Only {remaining} ticket{'s' if remaining != 1 else ''} remaining for this event."
            )
        unit_price = round(float(event.get("ticket_price") or 0), 2)
        original_subtotal = round(unit_price * quantity, 2)
        promotion = self._promotion_discount(
            vendor_id,
            "event",
            original_subtotal,
            self._oid(customer_id),
            str(event.get("event_date") or ""),
            promo_code,
        )
        subtotal = round(original_subtotal - promotion["discount_amount"], 2)
        return {
            "provider_id": str(vendor_id),
            "provider_name": vendor.get("business_name") or "Event provider",
            "provider_type": "event",
            "event_id": str(event["_id"]),
            "event_name": event.get("title") or "Event",
            "quantity": quantity,
            "available_seats": max(capacity - sold, 0) if capacity > 0 else None,
            "unit_price": unit_price,
            "original_subtotal": original_subtotal,
            "discount_amount": promotion["discount_amount"],
            "promotion_id": str(promotion["promotion_id"]) if promotion["promotion_id"] else None,
            "promotion_name": promotion["promotion_name"],
            "promo_code": promotion["promo_code"],
            "subtotal": subtotal,
            "service_fee": 0.0,
            "taxes": 0.0,
            "total": subtotal,
            "estimated_points": self._estimate_loyalty_points(
                vendor_id, self._oid(customer_id), subtotal
            ),
        }

    def create_event_ticket_booking(
        self,
        customer_id: str,
        event_id: str,
        quantity: int,
        notes: str | None,
        auto_confirm: bool,
        promo_code: str | None = None,
    ) -> dict[str, Any]:
        customer = self.users.find_one({"_id": self._oid(customer_id)})
        if not customer:
            raise ValueError("Customer not found.")

        event = self.vendor_events.find_one(
            {
                "_id": self._oid(event_id),
                "status": "published",
                "active": {"$ne": False},
                "$nor": [self._legacy_happy_hour_match()],
            }
        )
        if not event:
            raise ValueError("Event not found.")

        vendor_id = event.get("vendor_id")
        if not isinstance(vendor_id, ObjectId):
            raise ValueError("Event vendor is invalid.")

        vendor = self.vendors.find_one({"_id": vendor_id, "status": "approved"})
        if not vendor:
            raise ValueError("Provider not found.")
        quote = self.get_event_booking_quote(customer_id, event_id, quantity, promo_code)
        promotion_id = self._oid(quote["promotion_id"]) if quote["promotion_id"] else None
        now = datetime.now(UTC)
        booking_code = f"#EV{now.strftime('%Y%m')}-{str(ObjectId())[-4:].upper()}"
        status = "pending"
        scheduled_date = str(event.get("event_date") or "")
        scheduled_time = str(event.get("start_time") or "")

        vendor_booking_payload = {
            "vendor_id": vendor["_id"],
            "customer_id": customer["_id"],
            "event_id": self._oid(event_id),
            "booking_code": booking_code,
            "customer_name": customer.get("full_name"),
            "customer_gender": customer.get("gender"),
            "customer_phone": customer.get("phone"),
            "customer_email": customer.get("email"),
            "scheduled_date": scheduled_date,
            "scheduled_time": scheduled_time,
            "service": str(event.get("title") or "Event Ticket"),
            "provider_type": "event",
            "guests": quantity,
            "quantity": quantity,
            "status": status,
            "payment_status": "unpaid",
            "special_requests": notes,
            "total_amount": quote["total"],
            "original_subtotal": quote["original_subtotal"],
            "discount_amount": quote["discount_amount"],
            "promotion_id": promotion_id,
            "promotion_name": quote["promotion_name"],
            "promo_code": quote["promo_code"],
            "subtotal": quote["subtotal"],
            "service_fee": quote["service_fee"],
            "taxes": quote["taxes"],
            "unit_price": quote["unit_price"],
            "estimated_points": quote["estimated_points"],
            "source": "customer_app",
            "requested_at": now,
            "status_history": [
                {
                    "status": "pending",
                    "at": now,
                    "actor": "customer",
                    "label": "Booking request sent by customer",
                }
            ],
            "created_at": now,
            "updated_at": now,
        }
        insert_result = self.vendor_bookings.insert_one(vendor_booking_payload)
        booking_id = insert_result.inserted_id
        self.bookings.insert_one(
            {
                "customer_id": customer["_id"],
                "vendor_id": vendor["_id"],
                "event_id": self._oid(event_id),
                "provider_type": "event",
                "booking_id": booking_id,
                "booking_code": booking_code,
                "date": scheduled_date,
                "time": scheduled_time,
                "guests": quantity,
                "quantity": quantity,
                "status": status,
                "total_amount": quote["total"],
                "promotion_id": promotion_id,
                "discount_amount": quote["discount_amount"],
                "created_at": now,
                "updated_at": now,
            }
        )
        created = self.vendor_bookings.find_one({"_id": booking_id})
        self._create_vendor_notification(
            vendor["_id"],
            "new_booking",
            "New Event Ticket Booking",
            (
                f"{customer.get('full_name') or 'A customer'} booked {quantity} ticket"
                f"{'s' if quantity != 1 else ''} for {event.get('title') or 'your event'}."
                f" Reference: {booking_code}."
            ),
            action_type="view_details",
            action_label="View Booking",
            metadata={
                "booking_id": str(booking_id),
                "booking_code": booking_code,
                "customer_id": str(customer["_id"]),
                "status": status,
                "provider_type": "event",
                "event_id": str(event["_id"]),
            },
            settings_key="new_booking",
        )
        return self._serialize(created) or {}

    def get_booking_availability(
        self, provider_id: str, date: str, provider_type: str = "restaurant"
    ) -> dict[str, Any]:
        vendor_id = self._oid(provider_id)
        settings_doc = self.vendor_portal_settings.find_one({"vendor_id": vendor_id}) or {}
        general = settings_doc.get("general", {}) if isinstance(settings_doc.get("general"), dict) else {}
        bundle = self._get_vendor_bundle(vendor_id)
        normalized_type = (
            provider_type if provider_type in {"restaurant", "hotel", "spa"} else "restaurant"
        )
        service_settings = self._service_settings(bundle, normalized_type)
        slots = service_settings.get("available_booking_times") or general.get(
            "booking_availability_slots",
            ["06:00 PM", "06:30 PM", "07:00 PM", "07:30 PM", "08:00 PM", "08:30 PM", "09:00 PM", "09:30 PM", "10:00 PM"],
        )
        if normalized_type == "hotel":
            capacity = sum(
                int(row.get("inventory_count", 0))
                for row in self.vendor_rooms.find(
                    {"vendor_id": vendor_id}, {"inventory_count": 1}
                )
            )
        else:
            capacity = int(
                service_settings.get("booking_capacity")
                or service_settings.get("capacity_per_slot")
                or 10
            )
        capacity = max(capacity, 1)
        booked_counts: dict[str, int] = {}
        booking_type_query: Any = (
            {"$in": ["hotel", "hotel_room"]}
            if normalized_type == "hotel"
            else normalized_type
        )
        for row in self.vendor_bookings.find(
            {
                "vendor_id": vendor_id,
                "provider_type": booking_type_query,
                "scheduled_date": date,
                "status": {"$in": ["pending", "confirmed", "check_in"]},
            },
            {"scheduled_time": 1},
        ):
            key = str(row.get("scheduled_time"))
            booked_counts[key] = booked_counts.get(key, 0) + 1
        return {
            "provider_id": provider_id,
            "provider_type": normalized_type,
            "date": date,
            "slots": [
                {"time": slot, "available": booked_counts.get(slot, 0) < capacity, "booked": booked_counts.get(slot, 0)}
                for slot in slots
            ],
        }

    def get_booking_quote(
        self,
        provider_id: str,
        provider_type: str,
        guests: int,
        date: str,
        time: str,
        seating_preference: str | None,
        customer_id: str | None = None,
        promo_code: str | None = None,
    ) -> dict[str, Any]:
        vendor = self.vendors.find_one({"_id": self._oid(provider_id), "status": "approved"})
        if not vendor:
            raise ValueError("Provider not found.")
        if provider_type == "spa":
            service = self.vendor_services.find_one(
                {
                    "vendor_id": vendor["_id"],
                    "service_type": "spa",
                    "$or": [{"available": True}, {"active_status": True}],
                },
                sort=[("price", ASCENDING)],
            )
            unit_price = float((service or {}).get("price", 0))
        else:
            room = self.vendor_rooms.find_one(
                {"vendor_id": vendor["_id"], "available": True},
                sort=[("base_price", ASCENDING)],
            )
            unit_price = float((room or {}).get("base_price", 60))
        original_subtotal = round(unit_price * guests, 2)
        promotion = self._promotion_discount(
            vendor["_id"],
            provider_type,
            original_subtotal,
            self._oid(customer_id) if customer_id else None,
            date,
            promo_code,
        )
        subtotal = round(original_subtotal - promotion["discount_amount"], 2)
        service_fee = round(subtotal * 0.08, 2)
        taxes = round(subtotal * 0.05, 2)
        total = round(subtotal + service_fee + taxes, 2)
        points = self._estimate_loyalty_points(
            vendor["_id"], self._oid(customer_id) if customer_id else None, total
        )
        return {
            "provider_id": provider_id,
            "provider_name": vendor.get("business_name", "Provider"),
            "provider_type": provider_type,
            "date": date,
            "time": time,
            "guests": guests,
            "seating_preference": seating_preference,
            "original_subtotal": original_subtotal,
            "discount_amount": promotion["discount_amount"],
            "promotion_id": str(promotion["promotion_id"]) if promotion["promotion_id"] else None,
            "promotion_name": promotion["promotion_name"],
            "promo_code": promotion["promo_code"],
            "subtotal": subtotal,
            "service_fee": service_fee,
            "taxes": taxes,
            "total": total,
            "estimated_points": points,
        }

    def create_booking(
        self,
        customer_id: str,
        provider_id: str,
        provider_type: str,
        date: str,
        time: str,
        guests: int,
        seating_preference: str | None,
        special_notes: str | None,
        auto_confirm: bool,
        promo_code: str | None = None,
    ) -> dict[str, Any]:
        customer = self.users.find_one({"_id": self._oid(customer_id)})
        if not customer:
            raise ValueError("Customer not found.")
        vendor = self.vendors.find_one({"_id": self._oid(provider_id), "status": "approved"})
        if not vendor:
            raise ValueError("Provider not found.")
        restaurant_settings = self._service_settings(self._get_vendor_bundle(vendor["_id"]), "restaurant")
        allowed_seating = restaurant_settings.get("seating_preferences") or ["Indoor", "Outdoor", "No preference"]
        if seating_preference and str(seating_preference).strip().lower() not in {str(item).strip().lower() for item in allowed_seating}:
            raise ValueError("Selected seating preference is not available at this restaurant.")
        availability = self.get_booking_availability(provider_id, date)
        slot = next((row for row in availability["slots"] if row["time"] == time), None)
        if not slot or not slot["available"]:
            raise ValueError("Selected slot is not available.")
        quote = self.get_booking_quote(
            provider_id=provider_id,
            provider_type=provider_type,
            guests=guests,
            date=date,
            time=time,
            seating_preference=seating_preference,
            customer_id=customer_id,
            promo_code=promo_code,
        )
        now = datetime.now(UTC)
        booking_code = f"#BK{now.strftime('%Y%m')}-{str(ObjectId())[-4:].upper()}"
        status = "pending"
        vendor_booking_payload = {
            "vendor_id": vendor["_id"],
            "customer_id": customer["_id"],
            "booking_code": booking_code,
            "customer_name": customer.get("full_name"),
            "customer_gender": customer.get("gender"),
            "customer_phone": customer.get("phone"),
            "customer_email": customer.get("email"),
            "scheduled_date": date,
            "scheduled_time": time,
            "service": "Table Booking",
            "provider_type": provider_type,
            "guests": guests,
            "status": status,
            "payment_status": "unpaid",
            "special_requests": special_notes,
            "seating_preference": seating_preference,
            "total_amount": quote["total"],
            "original_subtotal": quote["original_subtotal"],
            "discount_amount": quote["discount_amount"],
            "promotion_id": self._oid(quote["promotion_id"]) if quote["promotion_id"] else None,
            "promotion_name": quote["promotion_name"],
            "promo_code": quote["promo_code"],
            "subtotal": quote["subtotal"],
            "service_fee": quote["service_fee"],
            "taxes": quote["taxes"],
            "estimated_points": quote["estimated_points"],
            "source": "customer_app",
            "requested_at": now,
            "status_history": [
                {
                    "status": "pending",
                    "at": now,
                    "actor": "customer",
                    "label": "Booking request sent by customer",
                }
            ],
            "created_at": now,
            "updated_at": now,
        }
        insert_result = self.vendor_bookings.insert_one(vendor_booking_payload)
        booking_id = insert_result.inserted_id
        self.bookings.insert_one(
            {
                "customer_id": customer["_id"],
                "vendor_id": vendor["_id"],
                "provider_type": provider_type,
                "booking_id": booking_id,
                "booking_code": booking_code,
                "date": date,
                "time": time,
                "guests": guests,
                "status": status,
                "total_amount": quote["total"],
                "promotion_id": self._oid(quote["promotion_id"]) if quote["promotion_id"] else None,
                "discount_amount": quote["discount_amount"],
                "created_at": now,
                "updated_at": now,
            }
        )
        created = self.vendor_bookings.find_one({"_id": booking_id})
        self._create_vendor_notification(
            vendor["_id"],
            "new_booking",
            "New Booking Received",
            (
                f"{customer.get('full_name') or 'A customer'} created a new table booking."
                f" Scheduled for {date} {time}. Reference: {booking_code}."
            ),
            action_type="view_details",
            action_label="View Booking",
            metadata={
                "booking_id": str(booking_id),
                "booking_code": booking_code,
                "customer_id": str(customer["_id"]),
                "status": status,
                "provider_type": provider_type,
            },
            settings_key="new_booking",
        )
        return self._serialize(created) or {}

    def get_spa_booking_quote(
        self,
        customer_id: str,
        spa_id: str,
        date: str,
        time: str,
        guests: int,
        service_id: str | None = None,
        promo_code: str | None = None,
    ) -> dict[str, Any]:
        vendor = self.vendors.find_one({"_id": self._oid(spa_id), "status": "approved"})
        if not vendor:
            raise ValueError("Spa not found.")
        service_query: dict[str, Any] = {
            "vendor_id": vendor["_id"],
            "service_type": "spa",
            "$or": [{"available": True}, {"active_status": True}],
        }
        if service_id:
            service_query["_id"] = self._oid(service_id)
        service = self.vendor_services.find_one(service_query, sort=[("price", ASCENDING)])
        if not service:
            raise ValueError("No available spa service found.")
        availability = self.get_booking_availability(spa_id, date, "spa")
        slot = next((row for row in availability["slots"] if row["time"] == time), None)
        if not slot or not slot["available"]:
            raise ValueError("Selected slot is not available.")
        unit_price = round(float(service.get("price") or 0), 2)
        original_subtotal = round(unit_price * guests, 2)
        customer_obj_id = self._oid(customer_id)
        promotion = self._promotion_discount(
            vendor["_id"], "spa", original_subtotal, customer_obj_id, date, promo_code
        )
        subtotal = round(original_subtotal - promotion["discount_amount"], 2)
        service_fee = round(subtotal * 0.08, 2)
        taxes = round(subtotal * 0.05, 2)
        total = round(subtotal + service_fee + taxes, 2)
        return {
            "provider_id": spa_id,
            "provider_name": vendor.get("business_name") or "Spa",
            "provider_type": "spa",
            "service_id": str(service["_id"]),
            "service_name": service.get("name") or "Spa Service",
            "date": date,
            "time": time,
            "guests": guests,
            "unit_price": unit_price,
            "original_subtotal": original_subtotal,
            "discount_amount": promotion["discount_amount"],
            "promotion_id": str(promotion["promotion_id"]) if promotion["promotion_id"] else None,
            "promotion_name": promotion["promotion_name"],
            "promo_code": promotion["promo_code"],
            "subtotal": subtotal,
            "service_fee": service_fee,
            "taxes": taxes,
            "total": total,
            "estimated_points": self._estimate_loyalty_points(
                vendor["_id"], customer_obj_id, total
            ),
        }

    def create_spa_booking(
        self,
        customer_id: str,
        spa_id: str,
        date: str,
        time: str,
        guests: int,
        service_id: str | None,
        special_notes: str | None,
        promo_code: str | None = None,
    ) -> dict[str, Any]:
        customer = self.users.find_one({"_id": self._oid(customer_id)})
        if not customer:
            raise ValueError("Customer not found.")
        vendor = self.vendors.find_one({"_id": self._oid(spa_id), "status": "approved"})
        if not vendor:
            raise ValueError("Spa not found.")
        quote = self.get_spa_booking_quote(
            customer_id, spa_id, date, time, guests, service_id, promo_code
        )
        now = datetime.now(UTC)
        booking_code = f"#SP{now.strftime('%Y%m')}-{str(ObjectId())[-4:].upper()}"
        promotion_id = self._oid(quote["promotion_id"]) if quote["promotion_id"] else None
        payload = {
            "vendor_id": vendor["_id"],
            "customer_id": customer["_id"],
            "booking_code": booking_code,
            "customer_name": customer.get("full_name"),
            "customer_gender": customer.get("gender"),
            "customer_phone": customer.get("phone"),
            "customer_email": customer.get("email"),
            "scheduled_date": date,
            "scheduled_time": time,
            "service": quote["service_name"],
            "service_id": self._oid(quote["service_id"]),
            "provider_type": "spa",
            "guests": guests,
            "status": "pending",
            "payment_status": "unpaid",
            "special_requests": special_notes,
            "total_amount": quote["total"],
            "original_subtotal": quote["original_subtotal"],
            "discount_amount": quote["discount_amount"],
            "promotion_id": promotion_id,
            "promotion_name": quote["promotion_name"],
            "promo_code": quote["promo_code"],
            "subtotal": quote["subtotal"],
            "service_fee": quote["service_fee"],
            "taxes": quote["taxes"],
            "unit_price": quote["unit_price"],
            "estimated_points": quote["estimated_points"],
            "source": "customer_app",
            "requested_at": now,
            "status_history": [
                {
                    "status": "pending",
                    "at": now,
                    "actor": "customer",
                    "label": "Booking request sent by customer",
                }
            ],
            "created_at": now,
            "updated_at": now,
        }
        booking_id = self.vendor_bookings.insert_one(payload).inserted_id
        self.bookings.insert_one(
            {
                "customer_id": customer["_id"],
                "vendor_id": vendor["_id"],
                "provider_type": "spa",
                "booking_id": booking_id,
                "booking_code": booking_code,
                "date": date,
                "time": time,
                "guests": guests,
                "status": "pending",
                "service_id": payload["service_id"],
                "total_amount": quote["total"],
                "promotion_id": promotion_id,
                "discount_amount": quote["discount_amount"],
                "created_at": now,
                "updated_at": now,
            }
        )
        self._create_vendor_notification(
            vendor["_id"],
            "new_booking",
            "New Spa Booking Received",
            (
                f"{customer.get('full_name') or 'A customer'} requested {quote['service_name']} "
                f"for {date} {time}. Reference: {booking_code}."
            ),
            action_type="view_details",
            action_label="View Booking",
            metadata={
                "booking_id": str(booking_id),
                "booking_code": booking_code,
                "customer_id": str(customer["_id"]),
                "status": "pending",
                "provider_type": "spa",
                "service_id": quote["service_id"],
            },
            settings_key="new_booking",
        )
        return self._serialize(self.vendor_bookings.find_one({"_id": booking_id})) or {}

    def get_hotel_booking_quote(
        self,
        customer_id: str,
        hotel_id: str,
        check_in_date: str,
        check_out_date: str,
        guests: int,
        room_id: str | None = None,
        promo_code: str | None = None,
    ) -> dict[str, Any]:
        vendor = self.vendors.find_one({"_id": self._oid(hotel_id), "status": "approved"})
        if not vendor:
            raise ValueError("Provider not found.")
        room_query: dict[str, Any] = {"vendor_id": vendor["_id"], "available": True}
        if room_id:
            room_query["_id"] = self._oid(room_id)
        room = self.vendor_rooms.find_one(room_query, sort=[("base_price", ASCENDING)])
        if not room:
            raise ValueError("No available room found for this hotel.")
        try:
            check_in = datetime.fromisoformat(check_in_date).date()
            check_out = datetime.fromisoformat(check_out_date).date()
        except ValueError as exc:
            raise ValueError("Invalid check-in or check-out date.") from exc
        nights = (check_out - check_in).days
        if nights <= 0:
            raise ValueError("check_out_date must be after check_in_date.")
        if guests > int(room.get("max_guests") or 20):
            raise ValueError("Guest count exceeds this room's capacity.")
        if nights < int(room.get("min_stay_nights") or 1):
            raise ValueError("Stay is shorter than this room's minimum stay.")
        if nights > int(room.get("max_stay_nights") or 30):
            raise ValueError("Stay exceeds this room's maximum stay.")
        reserved = self.vendor_bookings.count_documents(
            {
                "vendor_id": vendor["_id"],
                "room_id": room["_id"],
                "status": {"$in": ["pending", "confirmed", "check_in"]},
                "check_in_date": {"$lt": check_out_date},
                "check_out_date": {"$gt": check_in_date},
            }
        )
        if reserved >= int(room.get("inventory_count") or 1):
            raise ValueError("This room is not available for the selected dates.")
        base_price = round(float(room.get("base_price") or 150), 2)
        weekend_price = round(float(room.get("weekend_price") or base_price), 2)
        original_subtotal = 0.0
        cursor = check_in
        while cursor < check_out:
            original_subtotal += weekend_price if cursor.weekday() >= 5 else base_price
            cursor += timedelta(days=1)
        original_subtotal = round(original_subtotal, 2)
        room_discount = round(
            original_subtotal * min(max(float(room.get("default_discount_percent") or 0), 0), 100) / 100,
            2,
        )
        discounted_room_subtotal = round(original_subtotal - room_discount, 2)
        promotion = self._promotion_discount(
            vendor["_id"],
            "hotel",
            discounted_room_subtotal,
            self._oid(customer_id),
            check_in_date,
            promo_code,
        )
        subtotal = round(discounted_room_subtotal - promotion["discount_amount"], 2)
        service_fee = round(subtotal * 0.08, 2)
        taxes = 0.0 if room.get("tax_included", True) else round(subtotal * 0.05, 2)
        total = round(subtotal + service_fee + taxes, 2)
        return {
            "provider_id": hotel_id,
            "provider_name": vendor.get("business_name") or "Hotel",
            "provider_type": "hotel_room" if room_id else "hotel",
            "room_id": str(room["_id"]),
            "room_name": room.get("name") or "Hotel Room",
            "check_in_date": check_in_date,
            "check_out_date": check_out_date,
            "nights": nights,
            "guests": guests,
            "rate_per_night": base_price,
            "weekend_rate": weekend_price,
            "original_subtotal": original_subtotal,
            "room_discount_amount": room_discount,
            "discount_amount": promotion["discount_amount"],
            "promotion_id": str(promotion["promotion_id"]) if promotion["promotion_id"] else None,
            "promotion_name": promotion["promotion_name"],
            "promo_code": promotion["promo_code"],
            "subtotal": subtotal,
            "service_fee": service_fee,
            "taxes": taxes,
            "tax_included": bool(room.get("tax_included", True)),
            "total": total,
            "estimated_points": self._estimate_loyalty_points(
                vendor["_id"], self._oid(customer_id), total
            ),
        }

    def create_hotel_booking(
        self,
        customer_id: str,
        hotel_id: str,
        check_in_date: str,
        check_out_date: str,
        guests: int,
        special_notes: str | None,
        auto_confirm: bool,
        room_id: str | None = None,
        guest_name: str | None = None,
        guest_email: str | None = None,
        guest_phone: str | None = None,
        promo_code: str | None = None,
    ) -> dict[str, Any]:
        customer = self.users.find_one({"_id": self._oid(customer_id)})
        if not customer:
            raise ValueError("Customer not found.")
        vendor = self.vendors.find_one({"_id": self._oid(hotel_id), "status": "approved"})
        if not vendor:
            raise ValueError("Provider not found.")

        quote = self.get_hotel_booking_quote(
            customer_id,
            hotel_id,
            check_in_date,
            check_out_date,
            guests,
            room_id,
            promo_code,
        )
        room = self.vendor_rooms.find_one({"_id": self._oid(quote["room_id"])})
        if not room:
            raise ValueError("No available room found for this hotel.")
        now = datetime.now(UTC)
        booking_code = f"#HT{now.strftime('%Y%m')}-{str(ObjectId())[-4:].upper()}"
        status = "pending"
        room_name = str(quote["room_name"])
        provider_type = str(quote["provider_type"])
        promotion_id = self._oid(quote["promotion_id"]) if quote["promotion_id"] else None

        vendor_booking_payload = {
            "vendor_id": vendor["_id"],
            "customer_id": customer["_id"],
            "booking_code": booking_code,
            "customer_name": guest_name or customer.get("full_name"),
            "customer_gender": customer.get("gender"),
            "customer_phone": guest_phone or customer.get("phone"),
            "customer_email": guest_email or customer.get("email"),
            "scheduled_date": check_in_date,
            "scheduled_time": "15:00",
            "check_in_date": check_in_date,
            "check_out_date": check_out_date,
            "nights": quote["nights"],
            "service": room_name,
            "room_id": room["_id"],
            "room_type": room_name,
            "provider_type": provider_type,
            "guests": guests,
            "status": status,
            "payment_status": "unpaid",
            "special_requests": special_notes,
            "total_amount": quote["total"],
            "original_subtotal": quote["original_subtotal"],
            "room_discount_amount": quote["room_discount_amount"],
            "discount_amount": quote["discount_amount"],
            "promotion_id": promotion_id,
            "promotion_name": quote["promotion_name"],
            "promo_code": quote["promo_code"],
            "subtotal": quote["subtotal"],
            "service_fee": quote["service_fee"],
            "taxes": quote["taxes"],
            "tax_included": quote["tax_included"],
            "rate_per_night": quote["rate_per_night"],
            "estimated_points": quote["estimated_points"],
            "source": "customer_app",
            "requested_at": now,
            "status_history": [
                {
                    "status": "pending",
                    "at": now,
                    "actor": "customer",
                    "label": "Booking request sent by customer",
                }
            ],
            "created_at": now,
            "updated_at": now,
        }
        insert_result = self.vendor_bookings.insert_one(vendor_booking_payload)
        booking_id = insert_result.inserted_id
        self.bookings.insert_one(
            {
                "customer_id": customer["_id"],
                "vendor_id": vendor["_id"],
                "provider_type": provider_type,
                "booking_id": booking_id,
                "booking_code": booking_code,
                "date": check_in_date,
                "time": "15:00",
                "guests": guests,
                "status": status,
                "room_id": room["_id"],
                "room_type": room_name,
                "check_in_date": check_in_date,
                "check_out_date": check_out_date,
                "nights": quote["nights"],
                "total_amount": quote["total"],
                "promotion_id": promotion_id,
                "discount_amount": quote["discount_amount"],
                "created_at": now,
                "updated_at": now,
            }
        )
        created = self.vendor_bookings.find_one({"_id": booking_id})
        self._create_vendor_notification(
            vendor["_id"],
            "new_booking",
            "New Hotel Booking Received",
            (
                f"{guest_name or customer.get('full_name') or 'A customer'} booked {room_name} "
                f"from {check_in_date} to {check_out_date}. Reference: {booking_code}."
            ),
            action_type="view_details",
            action_label="View Booking",
            metadata={
                "booking_id": str(booking_id),
                "booking_code": booking_code,
                "customer_id": str(customer["_id"]),
                "status": status,
                "provider_type": provider_type,
                "room_id": str(room["_id"]),
            },
            settings_key="new_booking",
        )
        return self._serialize(created) or {}

    def list_customer_bookings(self, customer_id: str, limit: int, skip: int, status: str | None = None) -> dict[str, Any]:
        query = {"customer_id": self._oid(customer_id)}
        normalized_status = str(status or "").strip().lower()
        if normalized_status in {"confirmed", "pending", "canceled", "cancelled", "complete", "completed"}:
            query["status"] = "canceled" if normalized_status == "cancelled" else "complete" if normalized_status == "completed" else normalized_status
        elif normalized_status == "upcoming":
            query["status"] = {"$in": ["pending", "confirmed", "check_in"]}
            query["scheduled_date"] = {"$gte": datetime.now(UTC).date().isoformat()}
        elif normalized_status == "past":
            query["$or"] = [
                {"scheduled_date": {"$lt": datetime.now(UTC).date().isoformat()}},
                {"status": {"$in": ["complete", "canceled"]}},
            ]
        total = int(self.vendor_bookings.count_documents(query))
        docs = self.vendor_bookings.find(query).sort("created_at", DESCENDING).skip(skip).limit(limit)
        return {"items": [self._enrich_customer_booking(row) for row in docs], "total": total}

    def get_customer_booking(self, customer_id: str, booking_id: str) -> dict[str, Any] | None:
        booking = self.vendor_bookings.find_one({"_id": self._oid(booking_id), "customer_id": self._oid(customer_id)})
        return self._enrich_customer_booking(booking) if booking else None

    def confirm_booking(self, customer_id: str, booking_id: str) -> dict[str, Any] | None:
        now = datetime.now(UTC)
        self.vendor_bookings.update_one(
            {"_id": self._oid(booking_id), "customer_id": self._oid(customer_id)},
            {"$set": {"status": "confirmed", "updated_at": now}},
        )
        self.bookings.update_many(
            {"booking_id": self._oid(booking_id), "customer_id": self._oid(customer_id)},
            {"$set": {"status": "confirmed", "updated_at": now}},
        )
        return self.get_customer_booking(customer_id, booking_id)

    def cancel_booking(self, customer_id: str, booking_id: str, reason: str | None) -> dict[str, Any] | None:
        now = datetime.now(UTC)
        self.vendor_bookings.update_one(
            {"_id": self._oid(booking_id), "customer_id": self._oid(customer_id)},
            {"$set": {"status": "canceled", "cancel_reason": reason, "updated_at": now}},
        )
        self.bookings.update_many(
            {"booking_id": self._oid(booking_id), "customer_id": self._oid(customer_id)},
            {"$set": {"status": "canceled", "updated_at": now}},
        )
        return self.get_customer_booking(customer_id, booking_id)

    def create_booking_review(
        self,
        customer_id: str,
        booking_id: str,
        rating: int,
        review_text: str,
    ) -> dict[str, Any]:
        customer_obj_id = self._oid(customer_id)
        booking_obj_id = self._oid(booking_id)
        booking = self.vendor_bookings.find_one(
            {"_id": booking_obj_id, "customer_id": customer_obj_id}
        )
        if not booking:
            raise ValueError("Booking not found.")
        if str(booking.get("status") or "").lower() not in {"complete", "completed"}:
            raise ValueError("You can review a booking after it is completed.")
        if self.vendor_reviews.find_one(
            {"booking_id": booking_obj_id, "customer_id": customer_obj_id}
        ):
            raise ValueError("You have already reviewed this booking.")

        vendor_obj_id = booking.get("vendor_id")
        if not isinstance(vendor_obj_id, ObjectId):
            vendor_obj_id = self._oid(str(vendor_obj_id))
        provider_type = self._normalize_review_provider_type(booking.get("provider_type")) or "restaurant"
        customer = self.users.find_one({"_id": customer_obj_id}) or {}
        now = datetime.now(UTC)
        review = {
            "vendor_id": vendor_obj_id,
            "booking_id": booking_obj_id,
            "customer_id": customer_obj_id,
            "customer_name": customer.get("full_name") or booking.get("customer_name") or "Customer",
            "customer_avatar": customer.get("profile_image_url") or customer.get("profile_image") or customer.get("avatar_url") or "",
            "rating": rating,
            "star_rating": rating,
            "review_text": review_text.strip(),
            "provider_type": provider_type,
            "service": booking.get("service"),
            "created_at": now,
            "updated_at": now,
        }
        review_id = self.vendor_reviews.insert_one(review).inserted_id
        loyalty = self.vendor_loyalty_settings.find_one({"vendor_id": vendor_obj_id}) or {}
        review_points = (
            max(int(loyalty.get("review_bonus_points") or 0), 0)
            if loyalty.get("enable_loyalty_program") is True
            else 0
        )
        if review_points:
            expiry_policy = str(loyalty.get("points_expiry_policy") or "1 Year")
            expires_at = None
            if expiry_policy != "No Expiry":
                years = 2 if expiry_policy == "2 Years" else 1
                try:
                    expires_at = now.replace(year=now.year + years)
                except ValueError:
                    expires_at = now.replace(month=2, day=28, year=now.year + years)
            self.users.update_one(
                {"_id": customer_obj_id},
                {"$inc": {"points_balance": review_points}, "$set": {"updated_at": now}},
            )
            self.vendor_reviews.update_one(
                {"_id": review_id},
                {"$set": {"points_awarded": review_points, "points_awarded_at": now, "points_expires_at": expires_at}},
            )
            self.vendor_bookings.update_one(
                {"_id": booking_obj_id},
                {"$set": {"review_points_awarded": review_points, "updated_at": now}},
            )
        self._create_vendor_notification(
            vendor_obj_id,
            "new_review",
            "New Customer Review",
            f"{review['customer_name']} left a {rating}-star review.",
            action_type="reply_review",
            action_label="View Review",
            metadata={"review_id": str(review_id), "booking_id": booking_id, "rating": rating},
            settings_key="new_review",
        )
        return self._serialize(self.vendor_reviews.find_one({"_id": review_id})) or {}

    def reschedule_booking(
        self,
        customer_id: str,
        booking_id: str,
        date: str,
        time: str,
        note: str | None,
    ) -> dict[str, Any] | None:
        booking = self.get_customer_booking(customer_id, booking_id)
        if not booking:
            return None
        availability = self.get_booking_availability(booking["vendor_id"], date)
        slot = next((row for row in availability["slots"] if row["time"] == time), None)
        if not slot or not slot["available"]:
            raise ValueError("Selected slot is not available.")
        now = datetime.now(UTC)
        self.vendor_bookings.update_one(
            {"_id": self._oid(booking_id), "customer_id": self._oid(customer_id)},
            {"$set": {"scheduled_date": date, "scheduled_time": time, "reschedule_note": note, "updated_at": now}},
        )
        self.bookings.update_many(
            {"booking_id": self._oid(booking_id), "customer_id": self._oid(customer_id)},
            {"$set": {"date": date, "time": time, "updated_at": now}},
        )
        return self.get_customer_booking(customer_id, booking_id)

    def map_pins(self, customer_id: str, limit: int) -> list[dict[str, Any]]:
        restaurants = self.list_restaurants(customer_id=customer_id, limit=limit, skip=0).get("items", [])
        pins = []
        for row in restaurants:
            lat = self._to_float(row.get("latitude"))
            lng = self._to_float(row.get("longitude"))
            if lat is None or lng is None:
                continue
            pins.append(
                {
                    "id": row["id"],
                    "name": row["name"],
                    "lat": lat,
                    "lng": lng,
                    "rating": row["rating"],
                    "distance_km": row["distance_km"],
                    "offer_text": row.get("offer_text"),
                }
            )
        events = self.list_events(customer_id=customer_id, limit=max(1, min(limit, 50)), skip=0).get("items", [])
        for row in events:
            lat = self._to_float(row.get("latitude"))
            lng = self._to_float(row.get("longitude"))
            if lat is None or lng is None:
                continue
            pins.append(
                {
                    "id": row["id"],
                    "name": row["title"],
                    "lat": lat,
                    "lng": lng,
                    "rating": None,
                    "distance_km": row["distance_km"],
                    "offer_text": row.get("offer_text"),
                    "entity_type": "event",
                }
            )
        return pins

    def map_events(self, customer_id: str, limit: int) -> list[dict[str, Any]]:
        events = self.list_events(customer_id=customer_id, limit=limit, skip=0).get("items", [])
        pins: list[dict[str, Any]] = []
        for row in events:
            lat = self._to_float(row.get("latitude"))
            lng = self._to_float(row.get("longitude"))
            if lat is None or lng is None:
                continue
            pins.append(
                {
                    "id": row["id"],
                    "title": row["title"],
                    "name": row["title"],
                    "lat": lat,
                    "lng": lng,
                    "latitude": lat,
                    "longitude": lng,
                    "distance_km": row.get("distance_km"),
                    # Keep the schedule on map pins so clients can apply the
                    # same non-expired-event rule when rendering markers.
                    "event_date": row.get("event_date"),
                    "end_date": row.get("end_date") or row.get("event_date"),
                    "start_time": row.get("start_time"),
                    "end_time": row.get("end_time"),
                    "timezone": row.get("timezone"),
                    "offer_text": row.get("offer_text"),
                    "event_type": row.get("event_type"),
                    "event_category": row.get("event_category")
                    or row.get("event_type"),
                    "venue": row.get("venue"),
                    "cover_image_url": row.get("cover_image_url"),
                    "banner_image_url": row.get("banner_image_url"),
                    "ticket_price": row.get("ticket_price"),
                    "capacity": row.get("capacity"),
                    "booking_mode": row.get("booking_mode"),
                    "can_book_on_map": row.get("can_book_on_map"),
                    "current_booking_status": row.get("current_booking_status"),
                    "current_booking_code": row.get("current_booking_code"),
                    "is_sold_out": row.get("is_sold_out"),
                    "remaining_capacity": row.get("remaining_capacity"),
                    "entity_type": "event",
                    "detail_route": row.get("detail_route"),
                }
            )
        return pins

    def map_happy_hours(self, customer_id: str, limit: int) -> list[dict[str, Any]]:
        happy_hours = self.list_happy_hours(
            customer_id=customer_id,
            limit=limit,
            skip=0,
        ).get("items", [])
        pins: list[dict[str, Any]] = []
        for row in happy_hours:
            latitude = self._to_float(row.get("latitude"))
            longitude = self._to_float(row.get("longitude"))
            if latitude is None or longitude is None:
                continue
            pins.append(
                {
                    **row,
                    "lat": latitude,
                    "lng": longitude,
                    "latitude": latitude,
                    "longitude": longitude,
                    "entity_type": "happy_hour",
                }
            )
        return pins

    def map_highlight(self, customer_id: str, restaurant_id: str | None = None) -> dict[str, Any] | None:
        if restaurant_id:
            details = self.get_restaurant_details(customer_id=customer_id, restaurant_id=restaurant_id)
            if not details:
                return None
            first_offer = (self.list_restaurant_offers(details["id"])[:1] or [{}])[0]
            return {
                "id": details["id"],
                "name": details["name"],
                "rating": details["rating"],
                "distance_km": details["distance_km"],
                "category": details["category"],
                "cover_image_url": details["cover_image_url"],
                "offer_text": first_offer.get("promotion_name")
                or first_offer.get("title"),
            }
        rows = self.list_restaurants(customer_id=customer_id, limit=1, skip=0).get("items", [])
        return rows[0] if rows else None

