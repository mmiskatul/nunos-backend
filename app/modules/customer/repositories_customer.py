import hashlib
import math
from datetime import UTC, datetime
from typing import Any

from bson import ObjectId
from bson.errors import InvalidId
from pymongo import ASCENDING, DESCENDING
from pymongo.collection import Collection
from pymongo.database import Database


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
        self.vendor_reviews: Collection = db["vendor_reviews"]
        self.vendor_loyalty_settings: Collection = db["vendor_loyalty_settings"]
        self.vendor_bookings: Collection = db["vendor_bookings"]
        self.vendor_notifications: Collection = db["vendor_notifications"]
        self.vendor_notification_settings: Collection = db["vendor_notification_settings"]
        self.bookings: Collection = db["bookings"]
        self.customer_recent_searches: Collection = db["customer_recent_searches"]
        self.customer_saved_items: Collection = db["customer_saved_items"]

        self.vendor_bookings.create_index([("vendor_id", ASCENDING), ("scheduled_date", ASCENDING), ("scheduled_time", ASCENDING)])
        self.vendor_bookings.create_index([("customer_id", ASCENDING), ("created_at", DESCENDING)])
        self.vendor_notifications.create_index([("vendor_id", ASCENDING), ("created_at", DESCENDING)])
        self.vendor_notification_settings.create_index([("vendor_id", ASCENDING)], unique=True)
        self.customer_recent_searches.create_index([("customer_id", ASCENDING), ("created_at", DESCENDING)])
        self.customer_saved_items.create_index([("customer_id", ASCENDING), ("entity_type", ASCENDING), ("entity_id", ASCENDING)], unique=True)

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

    def _get_vendor_coords(self, bundle: dict[str, Any]) -> tuple[float | None, float | None]:
        profile_settings = bundle.get("profile_settings", {})
        general_settings = bundle.get("general", {})
        latitude = self._to_float(profile_settings.get("latitude"))
        longitude = self._to_float(profile_settings.get("longitude"))
        if latitude is None:
            latitude = self._to_float(general_settings.get("latitude"))
        if longitude is None:
            longitude = self._to_float(general_settings.get("longitude"))
        return latitude, longitude

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

    def _get_vendor_bundle(self, vendor_id: ObjectId) -> dict[str, Any]:
        vendor = self.vendors.find_one({"_id": vendor_id}) or {}
        profile = self.vendor_profiles.find_one({"vendor_id": vendor_id}) or {}
        business = self.vendor_business_details.find_one({"vendor_id": vendor_id}) or {}
        verification = self.vendor_verification_details.find_one({"vendor_id": vendor_id}) or {}
        settings_doc = self.vendor_portal_settings.find_one({"vendor_id": vendor_id}) or {}
        general_settings = settings_doc.get("general", {}) if isinstance(settings_doc.get("general"), dict) else {}
        profile_settings = settings_doc.get("profile", {}) if isinstance(settings_doc.get("profile"), dict) else {}
        first_gallery = self.vendor_assets.find_one(
            {"vendor_id": vendor_id, "asset_type": "gallery"},
            sort=[("created_at", DESCENDING)],
        )
        avg_row = list(
            self.vendor_reviews.aggregate(
                [
                    {"$match": {"vendor_id": vendor_id}},
                    {"$group": {"_id": "$vendor_id", "avg_rating": {"$avg": "$rating"}, "count": {"$sum": 1}}},
                ]
            )
        )
        active_offer = self.vendor_promotions.find_one({"vendor_id": vendor_id, "active": True})
        category = (
            verification.get("category")
            or profile.get("category")
            or "Restaurant"
        )
        return {
            "vendor": vendor,
            "profile": profile,
            "profile_settings": profile_settings,
            "business": business,
            "verification": verification,
            "general": general_settings,
            "cover_image": (first_gallery or {}).get("asset_url"),
            "rating": round(float(avg_row[0]["avg_rating"]), 1) if avg_row else 4.5,
            "reviews_count": int(avg_row[0]["count"]) if avg_row else 0,
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
    ) -> dict[str, Any]:
        query: dict[str, Any] = {"status": "approved"}
        if search:
            query["$or"] = [
                {"business_name": {"$regex": search, "$options": "i"}},
                {"owner_full_name": {"$regex": search, "$options": "i"}},
                {"email": {"$regex": search, "$options": "i"}},
            ]
        vendor_docs = list(self.vendors.find(query).sort("created_at", DESCENDING))
        cards: list[dict[str, Any]] = []
        customer_lat, customer_lng = self._get_customer_coords(customer_id)
        for vendor in vendor_docs:
            vendor_id = vendor["_id"]
            bundle = self._get_vendor_bundle(vendor_id)
            slots = bundle["general"].get("booking_availability_slots", [])
            if open_now is True and not slots:
                continue
            if with_offers is True and not bundle["active_offer"]:
                continue

            vendor_lat, vendor_lng = self._get_vendor_coords(bundle)
            location = (
                bundle["profile_settings"].get("location_label")
                or bundle["general"].get("business_address")
                or bundle["business"].get("address")
                or bundle["business"].get("city")
                or "Qatar"
            )
            cards.append(
                {
                    "id": str(vendor_id),
                    "name": bundle["vendor"].get("business_name") or bundle["profile"].get("business_name") or "Unnamed Restaurant",
                    "category": bundle["category"],
                    "rating": bundle["rating"],
                    "avg_rating": bundle["rating"],
                    "reviews_count": bundle["reviews_count"],
                    "distance_km": self._distance_between_km(customer_lat, customer_lng, vendor_lat, vendor_lng),
                    "location": location,
                    "address": bundle["general"].get("business_address") or bundle["business"].get("address"),
                    "city": bundle["business"].get("city"),
                    "latitude": vendor_lat,
                    "longitude": vendor_lng,
                    "is_open_now": bool(slots),
                    "cover_image_url": bundle["cover_image"] or "https://images.unsplash.com/photo-1517248135467-4c7edcad34c4?w=1200",
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
    ) -> dict[str, Any]:
        query: dict[str, Any] = {"status": "approved"}
        if search:
            query["$or"] = [
                {"business_name": {"$regex": search, "$options": "i"}},
            ]
        vendor_docs = list(self.vendors.find(query).sort("created_at", DESCENDING))
        cards: list[dict[str, Any]] = []
        for vendor in vendor_docs:
            vendor_id = vendor["_id"]
            bundle = self._get_vendor_bundle(vendor_id)
            if bundle["category"].lower() != "hotel":
                continue
            rooms = list(self.vendor_rooms.find({"vendor_id": vendor_id, "available": True}))
            min_price = 150.0
            if rooms:
                min_price = min(float(r.get("base_price", 150.0)) for r in rooms)
            has_rooms = len(rooms) > 0
            cards.append(
                {
                    "id": str(vendor_id),
                    "title": bundle["vendor"].get("business_name") or bundle["profile"].get("business_name") or "Unnamed Hotel",
                    "rating": str(bundle["rating"]),
                    "reviews": str(bundle["reviews_count"]),
                    "location": f"{bundle['general'].get('business_address') or bundle['business'].get('city') or 'Qatar'}",
                    "price": str(int(min_price)),
                    "status": "Available" if has_rooms else "Limited",
                    "badge": (bundle["active_offer"] or {}).get("promotion_name"),
                    "badgeColor": "#3b82f6",
                    "amenities": ["WiFi", "Pool", "Breakfast"] if has_rooms else ["WiFi"],
                    "image": bundle["cover_image"] or "https://images.unsplash.com/photo-1566073771259-6a8506099945?w=800",
                }
            )
        total = len(cards)
        return {"items": cards[skip : skip + limit], "total": total}

    def get_hotel_details(self, customer_id: str, hotel_id: str) -> dict[str, Any] | None:
        vendor = self.vendors.find_one({"_id": self._oid(hotel_id), "status": "approved"})
        if not vendor:
            return None
        vendor_id = vendor["_id"]
        bundle = self._get_vendor_bundle(vendor_id)
        if bundle["category"].lower() != "hotel":
            return None
        rooms_count = self.vendor_rooms.count_documents({"vendor_id": vendor_id, "available": True})
        gallery_count = self.vendor_assets.count_documents({"vendor_id": vendor_id, "asset_type": "gallery"})
        offers_count = self.vendor_promotions.count_documents({"vendor_id": vendor_id, "active": True})
        rooms = list(self.vendor_rooms.find({"vendor_id": vendor_id, "available": True}))
        min_price = 150.0
        if rooms:
            min_price = min(float(r.get("base_price", 150.0)) for r in rooms)
        return {
            "id": str(vendor_id),
            "title": bundle["vendor"].get("business_name") or bundle["profile"].get("business_name") or "Unnamed Hotel",
            "category": bundle["category"],
            "rating": str(bundle["rating"]),
            "reviews": str(bundle["reviews_count"]),
            "location": f"{bundle['general'].get('business_address') or bundle['business'].get('city') or 'Qatar'}",
            "address": bundle["general"].get("business_address") or bundle["business"].get("address") or "Qatar",
            "about": bundle["business"].get("business_description") or bundle["profile"].get("about_business") or "Welcome to our hotel.",
            "image": bundle["cover_image"] or "https://images.unsplash.com/photo-1566073771259-6a8506099945?w=800",
            "price": str(int(min_price)),
            "status": "Available",
            "amenities": ["Free WiFi", "Breakfast", "Pool", "Gym", "Parking", "Room Service"],
            "tabs": {
                "overview": True,
                "rooms_count": int(rooms_count),
                "gallery_count": int(gallery_count),
                "offers_count": int(offers_count),
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
                "image": images[0] if images else "https://images.unsplash.com/photo-1618773928121-c32242e63f39?w=800",
                "amenities": doc.get("amenities") or ["WiFi", "AC"],
            })
        return rooms

    def get_hotel_room_details(self, room_id: str) -> dict[str, Any] | None:
        doc = self.vendor_rooms.find_one({"_id": self._oid(room_id)})
        if not doc:
            return None
        base_price = float(doc.get("base_price", 298.0))
        raw_amenities = doc.get("amenities") or []
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
            "title": doc.get("name") or "Standard Room",
            "status": "Available" if doc.get("available", True) else "Unavailable",
            "size": f"{doc.get('size_sqm', 45)} m²",
            "guests": f"{doc.get('max_guests', 2)} Guests",
            "bed": doc.get("bed_type") or "King Bed",
            "view": "City View",
            "images": doc.get("images") or ["https://images.unsplash.com/photo-1618773928121-c32242e63f39?w=800"],
            "amenities": amenities_with_icons,
            "price": {
                "rate": str(int(base_price * 2)),
                "taxes": str(int(base_price * 0.2)),
                "total": str(int(base_price * 2.2)),
            }
        }

    def list_hotel_assets(self, hotel_id: str, asset_type: str) -> list[dict[str, Any]]:
        docs = self.vendor_assets.find(
            {"vendor_id": self._oid(hotel_id), "asset_type": asset_type}
        ).sort("created_at", DESCENDING)
        return [self._serialize(doc) for doc in docs]

    def get_hotel_reviews_payload(self, hotel_id: str) -> dict[str, Any]:
        vendor_id = self._oid(hotel_id)
        docs = list(self.vendor_reviews.find({"vendor_id": vendor_id}).sort("created_at", DESCENDING))
        total = len(docs)
        avg_rating = round(sum(float(doc.get("rating", 5)) for doc in docs) / total, 1) if total else 4.8
        
        reviews = []
        for doc in docs:
            created_at = doc.get("created_at")
            if isinstance(created_at, datetime):
                date_str = created_at.strftime("%b %d, %Y")
            elif isinstance(created_at, str):
                try:
                    date_str = datetime.fromisoformat(created_at).strftime("%b %d, %Y")
                except ValueError:
                    date_str = "Recently"
            else:
                date_str = "Recently"
            reviews.append({
                "id": str(doc["_id"]),
                "user": doc.get("customer_name") or "Anonymous",
                "date": date_str,
                "rating": int(doc.get("rating", 5)),
                "comment": doc.get("review_text") or doc.get("comment") or "",
            })
        return {
            "average_rating": str(avg_rating),
            "total_reviews": total,
            "items": reviews
        }

    def get_home_feed(self, customer_id: str) -> dict[str, Any]:
        restaurants = self.list_restaurants(customer_id=customer_id, limit=50, skip=0).get("items", [])
        trending: list[dict[str, Any]] = []
        for card in restaurants:
            vendor_id = self._oid(card["id"])
            category = str(card.get("category") or "restaurant").strip().lower()

            if category == "hotel":
                has_listing = self.vendor_rooms.count_documents(
                    {"vendor_id": vendor_id, "available": True},
                    limit=1,
                ) > 0
                route = f"/home/hotels/{card['id']}"
            elif category == "event":
                published_event = self.vendor_events.find_one(
                    {"vendor_id": vendor_id, "status": "published", "active": {"$ne": False}},
                    sort=[("created_at", DESCENDING)],
                )
                has_listing = published_event is not None
                route = f"/home/events/{published_event['_id']}" if published_event else ""
            else:
                has_active_service = self.vendor_services.count_documents(
                    {"vendor_id": vendor_id, "available": True},
                    limit=1,
                ) > 0
                has_menu = self.vendor_assets.count_documents(
                    {"vendor_id": vendor_id, "asset_type": "menu"},
                    limit=1,
                ) > 0
                portal_settings = self.vendor_portal_settings.find_one({"vendor_id": vendor_id}) or {}
                general_settings = portal_settings.get("general")
                has_booking_slots = bool(
                    general_settings.get("booking_availability_slots", [])
                    if isinstance(general_settings, dict)
                    else []
                )
                has_listing = has_active_service or has_menu or has_booking_slots
                route_prefix = "spa" if category == "spa" else "dining"
                route = f"/home/{route_prefix}/{card['id']}"

            if not has_listing:
                continue

            usage_count = self.vendor_bookings.count_documents(
                {
                    "vendor_id": vendor_id,
                    "status": {"$nin": ["cancelled", "rejected"]},
                }
            )
            if usage_count == 0:
                continue

            trending.append(
                {
                    **card,
                    "entity_type": category,
                    "detail_route": route,
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
        trending = trending[:6]
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
            "trending_now": trending,
            "featured_experiences": featured,
        }

    def get_restaurant_details(self, customer_id: str, restaurant_id: str) -> dict[str, Any] | None:
        vendor = self.vendors.find_one({"_id": self._oid(restaurant_id), "status": "approved"})
        if not vendor:
            return None
        vendor_id = vendor["_id"]
        bundle = self._get_vendor_bundle(vendor_id)
        menu_count = self.vendor_assets.count_documents({"vendor_id": vendor_id, "asset_type": "menu"})
        gallery_count = self.vendor_assets.count_documents({"vendor_id": vendor_id, "asset_type": "gallery"})
        offers_count = self.vendor_promotions.count_documents({"vendor_id": vendor_id, "active": True})
        opening_slots = bundle["general"].get("booking_availability_slots", [])
        customer_lat, customer_lng = self._get_customer_coords(customer_id)
        vendor_lat, vendor_lng = self._get_vendor_coords(bundle)
        location = (
            bundle["profile_settings"].get("location_label")
            or bundle["general"].get("business_address")
            or bundle["business"].get("address")
            or bundle["business"].get("city")
            or "Qatar"
        )
        return {
            "id": str(vendor_id),
            "name": bundle["vendor"].get("business_name") or bundle["profile"].get("business_name") or "Unnamed Restaurant",
            "category": bundle["category"],
            "rating": bundle["rating"],
            "reviews_count": bundle["reviews_count"],
            "distance_km": self._distance_between_km(customer_lat, customer_lng, vendor_lat, vendor_lng),
            "location": location,
            "address": bundle["general"].get("business_address") or bundle["business"].get("address"),
            "city": bundle["business"].get("city"),
            "latitude": vendor_lat,
            "longitude": vendor_lng,
            "about": bundle["business"].get("business_description")
            or bundle["profile"].get("about_business")
            or "Welcome to our venue.",
            "cover_image_url": bundle["cover_image"] or "https://images.unsplash.com/photo-1517248135467-4c7edcad34c4?w=1200",
            "opening_hours": {
                "monday_friday": "12:00 PM - 11:00 PM",
                "saturday_sunday": "11:00 AM - 12:00 AM",
                "is_open_now": bool(opening_slots),
            },
            "amenities": ["Free WiFi", "Parking", "Outdoor", "Cards", "Accessible", "Bar"],
            "tabs": {
                "overview": True,
                "menu_count": int(menu_count),
                "gallery_count": int(gallery_count),
                "offers_count": int(offers_count),
            },
            "contact": {
                "phone": bundle["general"].get("front_desk_phone"),
                "reservations_email": bundle["general"].get("reservations_email"),
            },
        }

    def list_restaurant_assets(self, restaurant_id: str, asset_type: str) -> list[dict[str, Any]]:
        docs = self.vendor_assets.find(
            {"vendor_id": self._oid(restaurant_id), "asset_type": asset_type}
        ).sort("created_at", DESCENDING)
        return [self._serialize(doc) for doc in docs]

    def list_restaurant_offers(self, restaurant_id: str) -> list[dict[str, Any]]:
        docs = self.vendor_promotions.find(
            {"vendor_id": self._oid(restaurant_id), "active": True}
        ).sort("created_at", DESCENDING)
        return [self._serialize(doc) for doc in docs]

    def list_events(
        self,
        customer_id: str,
        limit: int,
        skip: int,
        search: str | None = None,
    ) -> dict[str, Any]:
        query: dict[str, Any] = {"status": "published", "active": {"$ne": False}}
        if search:
            query["$or"] = [
                {"title": {"$regex": search, "$options": "i"}},
                {"venue": {"$regex": search, "$options": "i"}},
                {"event_type": {"$regex": search, "$options": "i"}},
                {"category": {"$regex": search, "$options": "i"}},
            ]

        docs = list(
            self.vendor_events.find(query).sort(
                [("event_date", ASCENDING), ("start_time", ASCENDING), ("created_at", DESCENDING)]
            )
        )
        cards: list[dict[str, Any]] = []
        customer_lat, customer_lng = self._get_customer_coords(customer_id)

        for event in docs:
            vendor_id = event.get("vendor_id")
            if not isinstance(vendor_id, ObjectId):
                continue

            vendor = self.vendors.find_one({"_id": vendor_id, "status": "approved"})
            if not vendor:
                continue

            bundle = self._get_vendor_bundle(vendor_id)
            vendor_lat, vendor_lng = self._get_vendor_coords(bundle)
            if vendor_lat is None or vendor_lng is None:
                continue

            active_offer = bundle.get("active_offer") or {}
            venue = str(event.get("venue") or "").strip()
            event_type = str(event.get("event_type") or "Event").strip()
            capacity = int(event.get("capacity") or 0)
            booking_mode = self._event_booking_mode(event)
            booking_summary = self._event_booking_summary(customer_id, event["_id"], capacity)

            cards.append(
                {
                    "id": str(event["_id"]),
                    "vendor_id": str(vendor_id),
                    "title": str(event.get("title") or "Untitled Event").strip(),
                    "name": str(event.get("title") or "Untitled Event").strip(),
                    "category": str(event.get("category") or "Event").strip(),
                    "entity_type": "event",
                    "event_type": event_type,
                    "event_date": event.get("event_date"),
                    "start_time": event.get("start_time"),
                    "end_time": event.get("end_time"),
                    "timezone": event.get("timezone"),
                    "venue": venue,
                    "location": venue
                    or bundle["general"].get("business_address")
                    or bundle["business"].get("address")
                    or bundle["business"].get("city")
                    or "Qatar",
                    "address": bundle["general"].get("business_address") or bundle["business"].get("address"),
                    "city": bundle["business"].get("city"),
                    "latitude": vendor_lat,
                    "longitude": vendor_lng,
                    "distance_km": self._distance_between_km(customer_lat, customer_lng, vendor_lat, vendor_lng),
                    "cover_image_url": event.get("banner_image_url")
                    or bundle["cover_image"]
                    or "https://images.unsplash.com/photo-1492684223066-81342ee5ff30?w=1200",
                    "banner_image_url": event.get("banner_image_url") or bundle["cover_image"],
                    "offer_text": active_offer.get("promotion_name") or event_type,
                    "description": event.get("description") or "",
                    "ticket_price": event.get("ticket_price"),
                    "capacity": event.get("capacity"),
                    "booking_mode": booking_mode,
                    "can_book_on_map": booking_mode == "simple" and not booking_summary["is_sold_out"],
                    **booking_summary,
                    "detail_route": f"/home/events/{event['_id']}",
                }
            )

        total = len(cards)
        return {"items": cards[skip : skip + limit], "total": total}

    def get_event_details(self, customer_id: str, event_id: str) -> dict[str, Any] | None:
        event = self.vendor_events.find_one(
            {"_id": self._oid(event_id), "status": "published", "active": {"$ne": False}}
        )
        if not event:
            return None

        vendor_id = event.get("vendor_id")
        if not isinstance(vendor_id, ObjectId):
            return None

        vendor = self.vendors.find_one({"_id": vendor_id, "status": "approved"})
        if not vendor:
            return None

        bundle = self._get_vendor_bundle(vendor_id)
        vendor_lat, vendor_lng = self._get_vendor_coords(bundle)
        customer_lat, customer_lng = self._get_customer_coords(customer_id)
        active_offer = bundle.get("active_offer") or {}
        event_type = str(event.get("event_type") or "Event").strip()
        venue = str(event.get("venue") or "").strip()
        capacity = int(event.get("capacity") or 0)
        booking_mode = self._event_booking_mode(event)
        booking_summary = self._event_booking_summary(customer_id, event["_id"], capacity)

        return {
            "id": str(event["_id"]),
            "vendor_id": str(vendor_id),
            "title": str(event.get("title") or "Untitled Event").strip(),
            "name": str(event.get("title") or "Untitled Event").strip(),
            "category": str(event.get("category") or "Event").strip(),
            "entity_type": "event",
            "event_type": event_type,
            "event_date": event.get("event_date"),
            "start_time": event.get("start_time"),
            "end_time": event.get("end_time"),
            "timezone": event.get("timezone"),
            "venue": venue,
            "location": venue
            or bundle["general"].get("business_address")
            or bundle["business"].get("address")
            or bundle["business"].get("city")
            or "Qatar",
            "address": bundle["general"].get("business_address") or bundle["business"].get("address"),
            "city": bundle["business"].get("city"),
            "latitude": vendor_lat,
            "longitude": vendor_lng,
            "distance_km": self._distance_between_km(customer_lat, customer_lng, vendor_lat, vendor_lng),
            "cover_image_url": event.get("banner_image_url")
            or bundle["cover_image"]
            or "https://images.unsplash.com/photo-1492684223066-81342ee5ff30?w=1200",
            "banner_image_url": event.get("banner_image_url") or bundle["cover_image"],
            "offer_text": active_offer.get("promotion_name") or event_type,
            "description": event.get("description") or "",
            "ticket_price": event.get("ticket_price"),
            "capacity": event.get("capacity"),
            "booking_mode": booking_mode,
            "can_book_on_map": booking_mode == "simple" and not booking_summary["is_sold_out"],
            **booking_summary,
            "detail_route": f"/home/events/{event['_id']}",
        }

    def create_event_ticket_booking(
        self,
        customer_id: str,
        event_id: str,
        quantity: int,
        notes: str | None,
        auto_confirm: bool,
    ) -> dict[str, Any]:
        customer = self.users.find_one({"_id": self._oid(customer_id)})
        if not customer:
            raise ValueError("Customer not found.")

        event = self.vendor_events.find_one(
            {"_id": self._oid(event_id), "status": "published", "active": {"$ne": False}}
        )
        if not event:
            raise ValueError("Event not found.")

        vendor_id = event.get("vendor_id")
        if not isinstance(vendor_id, ObjectId):
            raise ValueError("Event vendor is invalid.")

        vendor = self.vendors.find_one({"_id": vendor_id, "status": "approved"})
        if not vendor:
            raise ValueError("Provider not found.")

        capacity = int(event.get("capacity") or 0)
        sold = 0
        for row in self.vendor_bookings.find(
            {
                "event_id": self._oid(event_id),
                "status": {"$in": ["pending", "confirmed", "check_in"]},
            },
            {"quantity": 1},
        ):
            sold += int(row.get("quantity") or 0)

        if capacity > 0 and sold + quantity > capacity:
            remaining = max(capacity - sold, 0)
            raise ValueError(
                "Only "
                f"{remaining} ticket{'s' if remaining != 1 else ''} remaining for this event."
            )

        unit_price = round(float(event.get("ticket_price") or 0), 2)
        subtotal = round(unit_price * quantity, 2)
        service_fee = 0.0
        taxes = 0.0
        total = subtotal
        now = datetime.now(UTC)
        booking_code = f"#EV{now.strftime('%Y%m')}-{str(ObjectId())[-4:].upper()}"
        status = "confirmed" if auto_confirm else "pending"
        scheduled_date = str(event.get("event_date") or "")
        scheduled_time = str(event.get("start_time") or "")

        vendor_booking_payload = {
            "vendor_id": vendor["_id"],
            "customer_id": customer["_id"],
            "event_id": self._oid(event_id),
            "booking_code": booking_code,
            "customer_name": customer.get("full_name"),
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
            "total_amount": total,
            "subtotal": subtotal,
            "service_fee": service_fee,
            "taxes": taxes,
            "unit_price": unit_price,
            "source": "customer_app",
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
                "total_amount": total,
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

    def get_booking_availability(self, provider_id: str, date: str) -> dict[str, Any]:
        vendor_id = self._oid(provider_id)
        settings_doc = self.vendor_portal_settings.find_one({"vendor_id": vendor_id}) or {}
        general = settings_doc.get("general", {}) if isinstance(settings_doc.get("general"), dict) else {}
        slots = general.get(
            "booking_availability_slots",
            ["06:00 PM", "06:30 PM", "07:00 PM", "07:30 PM", "08:00 PM", "08:30 PM", "09:00 PM", "09:30 PM", "10:00 PM"],
        )
        capacity = sum(
            int(row.get("inventory_count", 0))
            for row in self.vendor_rooms.find({"vendor_id": vendor_id}, {"inventory_count": 1})
        )
        if capacity <= 0:
            capacity = 10
        booked_counts: dict[str, int] = {}
        for row in self.vendor_bookings.find(
            {
                "vendor_id": vendor_id,
                "scheduled_date": date,
                "status": {"$in": ["pending", "confirmed", "check_in"]},
            },
            {"scheduled_time": 1},
        ):
            key = str(row.get("scheduled_time"))
            booked_counts[key] = booked_counts.get(key, 0) + 1
        return {
            "provider_id": provider_id,
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
    ) -> dict[str, Any]:
        vendor = self.vendors.find_one({"_id": self._oid(provider_id), "status": "approved"})
        if not vendor:
            raise ValueError("Provider not found.")
        room = self.vendor_rooms.find_one({"vendor_id": vendor["_id"], "available": True}, sort=[("base_price", ASCENDING)])
        unit_price = float((room or {}).get("base_price", 60))
        subtotal = round(unit_price * guests, 2)
        service_fee = round(subtotal * 0.08, 2)
        taxes = round(subtotal * 0.05, 2)
        total = round(subtotal + service_fee + taxes, 2)
        loyalty = self.vendor_loyalty_settings.find_one({"vendor_id": vendor["_id"]}) or {}
        points_per_currency = float(loyalty.get("points_earned", 0))
        points = int(total * points_per_currency) if loyalty.get("enable_loyalty_program", False) else 0
        return {
            "provider_id": provider_id,
            "provider_name": vendor.get("business_name", "Provider"),
            "provider_type": provider_type,
            "date": date,
            "time": time,
            "guests": guests,
            "seating_preference": seating_preference,
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
    ) -> dict[str, Any]:
        customer = self.users.find_one({"_id": self._oid(customer_id)})
        if not customer:
            raise ValueError("Customer not found.")
        vendor = self.vendors.find_one({"_id": self._oid(provider_id), "status": "approved"})
        if not vendor:
            raise ValueError("Provider not found.")
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
        )
        now = datetime.now(UTC)
        booking_code = f"#BK{now.strftime('%Y%m')}-{str(ObjectId())[-4:].upper()}"
        status = "confirmed" if auto_confirm else "pending"
        vendor_booking_payload = {
            "vendor_id": vendor["_id"],
            "customer_id": customer["_id"],
            "booking_code": booking_code,
            "customer_name": customer.get("full_name"),
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
            "subtotal": quote["subtotal"],
            "service_fee": quote["service_fee"],
            "taxes": quote["taxes"],
            "source": "customer_app",
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

    def list_customer_bookings(self, customer_id: str, limit: int, skip: int) -> dict[str, Any]:
        query = {"customer_id": self._oid(customer_id)}
        total = int(self.vendor_bookings.count_documents(query))
        docs = self.vendor_bookings.find(query).sort("created_at", DESCENDING).skip(skip).limit(limit)
        return {"items": [self._serialize(row) for row in docs], "total": total}

    def get_customer_booking(self, customer_id: str, booking_id: str) -> dict[str, Any] | None:
        return self._serialize(
            self.vendor_bookings.find_one({"_id": self._oid(booking_id), "customer_id": self._oid(customer_id)})
        )

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
                    "offer_text": row.get("offer_text"),
                    "event_type": row.get("event_type"),
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

    def map_highlight(self, customer_id: str, restaurant_id: str | None = None) -> dict[str, Any] | None:
        if restaurant_id:
            details = self.get_restaurant_details(customer_id=customer_id, restaurant_id=restaurant_id)
            if not details:
                return None
            return {
                "id": details["id"],
                "name": details["name"],
                "rating": details["rating"],
                "distance_km": details["distance_km"],
                "category": details["category"],
                "cover_image_url": details["cover_image_url"],
                "offer_text": (self.list_restaurant_offers(details["id"])[:1] or [{}])[0].get("promotion_name"),
            }
        rows = self.list_restaurants(customer_id=customer_id, limit=1, skip=0).get("items", [])
        return rows[0] if rows else None

