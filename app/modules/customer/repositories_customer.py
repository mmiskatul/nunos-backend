import hashlib
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
        self.vendor_reviews: Collection = db["vendor_reviews"]
        self.vendor_loyalty_settings: Collection = db["vendor_loyalty_settings"]
        self.vendor_bookings: Collection = db["vendor_bookings"]
        self.bookings: Collection = db["bookings"]
        self.customer_recent_searches: Collection = db["customer_recent_searches"]
        self.customer_saved_items: Collection = db["customer_saved_items"]

        self.vendor_bookings.create_index([("vendor_id", ASCENDING), ("scheduled_date", ASCENDING), ("scheduled_time", ASCENDING)])
        self.vendor_bookings.create_index([("customer_id", ASCENDING), ("created_at", DESCENDING)])
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

    def _get_vendor_bundle(self, vendor_id: ObjectId) -> dict[str, Any]:
        vendor = self.vendors.find_one({"_id": vendor_id}) or {}
        profile = self.vendor_profiles.find_one({"vendor_id": vendor_id}) or {}
        business = self.vendor_business_details.find_one({"vendor_id": vendor_id}) or {}
        verification = self.vendor_verification_details.find_one({"vendor_id": vendor_id}) or {}
        settings_doc = self.vendor_portal_settings.find_one({"vendor_id": vendor_id}) or {}
        general_settings = settings_doc.get("general", {}) if isinstance(settings_doc.get("general"), dict) else {}
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
        for vendor in vendor_docs:
            vendor_id = vendor["_id"]
            bundle = self._get_vendor_bundle(vendor_id)
            slots = bundle["general"].get("booking_availability_slots", [])
            if open_now is True and not slots:
                continue
            if with_offers is True and not bundle["active_offer"]:
                continue

            seed = f"{customer_id}:{vendor_id}"
            cards.append(
                {
                    "id": str(vendor_id),
                    "name": bundle["vendor"].get("business_name") or bundle["profile"].get("business_name") or "Unnamed Restaurant",
                    "category": bundle["category"],
                    "rating": bundle["rating"],
                    "reviews_count": bundle["reviews_count"],
                    "distance_km": self._distance_km(seed),
                    "address": bundle["general"].get("business_address") or bundle["business"].get("address"),
                    "city": bundle["business"].get("city"),
                    "is_open_now": bool(slots),
                    "cover_image_url": bundle["cover_image"] or "https://images.unsplash.com/photo-1517248135467-4c7edcad34c4?w=1200",
                    "offer_text": (bundle["active_offer"] or {}).get("promotion_name"),
                }
            )
        if top_rated:
            cards.sort(key=lambda row: row.get("rating", 0), reverse=True)
        total = len(cards)
        return {"items": cards[skip : skip + limit], "total": total}

    def get_home_feed(self, customer_id: str) -> dict[str, Any]:
        restaurants = self.list_restaurants(customer_id=customer_id, limit=50, skip=0).get("items", [])
        trending = sorted(restaurants, key=lambda row: row.get("rating", 0), reverse=True)[:6]
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
        _ = customer_id
        vendor = self.vendors.find_one({"_id": self._oid(restaurant_id), "status": "approved"})
        if not vendor:
            return None
        vendor_id = vendor["_id"]
        bundle = self._get_vendor_bundle(vendor_id)
        menu_count = self.vendor_assets.count_documents({"vendor_id": vendor_id, "asset_type": "menu"})
        gallery_count = self.vendor_assets.count_documents({"vendor_id": vendor_id, "asset_type": "gallery"})
        offers_count = self.vendor_promotions.count_documents({"vendor_id": vendor_id, "active": True})
        opening_slots = bundle["general"].get("booking_availability_slots", [])
        return {
            "id": str(vendor_id),
            "name": bundle["vendor"].get("business_name") or bundle["profile"].get("business_name") or "Unnamed Restaurant",
            "category": bundle["category"],
            "rating": bundle["rating"],
            "reviews_count": bundle["reviews_count"],
            "distance_km": self._distance_km(str(vendor_id)),
            "address": bundle["general"].get("business_address") or bundle["business"].get("address"),
            "city": bundle["business"].get("city"),
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
            coords = self._coords(f"{customer_id}:{row['id']}")
            pins.append(
                {
                    "id": row["id"],
                    "name": row["name"],
                    "lat": coords["lat"],
                    "lng": coords["lng"],
                    "rating": row["rating"],
                    "distance_km": row["distance_km"],
                    "offer_text": row.get("offer_text"),
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

