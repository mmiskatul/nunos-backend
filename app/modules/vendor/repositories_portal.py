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

    def ensure_seed_data(self, vendor_id: str) -> None:
        vid = ObjectId(vendor_id)
        now = datetime.now(UTC)
        today = now.date().isoformat()
        existing_booking_count = self.bookings.count_documents({"vendor_id": vid})
        target_seed_bookings = 30
        if existing_booking_count < target_seed_bookings:
            first_names = [
                "Eleanor",
                "Julian",
                "Michael",
                "Sarah",
                "Robert",
                "Lisa",
                "David",
                "Marcus",
                "Nina",
                "Owen",
                "Priya",
                "Khaled",
                "Amira",
                "Sofia",
                "Noah",
                "Ava",
                "Liam",
                "Emma",
                "Mason",
                "Mia",
                "Lucas",
                "Zoe",
                "Ethan",
                "Olivia",
                "Henry",
                "Ella",
                "Jack",
                "Chloe",
                "Leo",
                "Layla",
            ]
            last_names = [
                "Shellstrop",
                "Casablancas",
                "Scott",
                "Jenkins",
                "Vance",
                "Anderson",
                "Martinez",
                "Taylor",
                "Patel",
                "Rahman",
            ]
            statuses = ["confirmed", "pending", "confirmed", "canceled", "complete", "check_in"]
            payment_statuses = ["unpaid", "unpaid", "paid", "paid"]
            services = ["Dinner Table", "Lunch Table", "Spa Session", "Family Table"]
            time_slots = ["06:00 PM", "06:30 PM", "07:00 PM", "07:30 PM", "08:00 PM", "08:30 PM", "09:00 PM", "09:30 PM"]

            booking_docs: list[dict[str, Any]] = []
            start_index = int(existing_booking_count)
            for i in range(start_index, target_seed_bookings):
                fn = first_names[i % len(first_names)]
                ln = last_names[i % len(last_names)]
                full_name = f"{fn} {ln}"
                day_offset = (i % 12) - 3
                booking_date = (now + timedelta(days=day_offset)).date().isoformat()
                status_value = statuses[i % len(statuses)]
                total_amount = round(70 + ((i % 7) * 22.5) + ((i % 4) * 11), 2)
                booking_docs.append(
                    {
                        "vendor_id": vid,
                        "booking_code": f"#BK-{1000 + i}",
                        "customer_name": full_name,
                        "customer_phone": f"+1 (555) 12{i % 10}{(i + 3) % 10}-{34 + i:02d}{56 + i:02d}",
                        "customer_email": f"{fn.lower()}.{ln.lower()}{i}@example.com",
                        "scheduled_date": booking_date,
                        "scheduled_time": time_slots[i % len(time_slots)],
                        "service": services[i % len(services)],
                        "room_type": "Deluxe King Room",
                        "guests": (i % 6) + 1,
                        "status": status_value,
                        "payment_status": payment_statuses[i % len(payment_statuses)],
                        "special_requests": "Allergy: peanuts; quiet corner if available." if i % 5 == 0 else "",
                        "total_amount": total_amount,
                        "created_at": now - timedelta(days=max(0, 10 - i), hours=i % 6),
                        "updated_at": now,
                    }
                )
            if booking_docs:
                self.bookings.insert_many(booking_docs)
        if self.rooms.count_documents({"vendor_id": vid}) == 0:
            self.rooms.insert_one(
                {
                    "vendor_id": vid,
                    "name": "Deluxe King Room",
                    "size_sqm": 32,
                    "max_guests": 2,
                    "bed_type": "King Bed",
                    "number_of_beds": 1,
                    "base_price": 180.0,
                    "weekend_price": 230.0,
                    "default_discount_percent": 0.0,
                    "amenities": ["Wi-Fi", "Smart TV", "Balcony", "AC"],
                    "images": ["https://files.example.com/rooms/deluxe-king.jpg"],
                    "inventory_count": 12,
                    "min_stay_nights": 1,
                    "max_stay_nights": 30,
                    "available": True,
                    "created_at": now,
                    "updated_at": now,
                }
            )
        if self.promotions.count_documents({"vendor_id": vid}) == 0:
            self.promotions.insert_one(
                {
                    "vendor_id": vid,
                    "promotion_name": "Weekend Brunch Special",
                    "offer_type": "percentage",
                    "discount_value": 20,
                    "applicable_to": "All Services",
                    "start_date": today,
                    "end_date": today,
                    "recurring_days": ["Sat", "Sun"],
                    "active": True,
                    "created_at": now,
                    "updated_at": now,
                }
            )
        if self.platform_campaigns.count_documents({"active": True}) == 0:
            self.platform_campaigns.insert_one(
                {
                    "campaign_name": "Flash Sale Friday",
                    "requirement": "30% Min Discount",
                    "duration": "24 Hours",
                    "platform_commission_delta": "+2%",
                    "active": True,
                    "created_at": now,
                }
            )
        if self.loyalty_settings.count_documents({"vendor_id": vid}) == 0:
            self.loyalty_settings.insert_one(
                {
                    "vendor_id": vid,
                    "enable_loyalty_program": True,
                    "points_rule_type": "points_per_currency",
                    "points_earned": 5,
                    "currency_unit": 1,
                    "percentage_value": 10,
                    "first_booking_bonus": 100,
                    "review_bonus_points": 25,
                    "points_expiry_policy": "1 Year",
                    "updated_at": now,
                }
            )
        if self.reviews.count_documents({"vendor_id": vid}) == 0:
            self.reviews.insert_one(
                {
                    "vendor_id": vid,
                    "customer_name": "James L.",
                    "rating": 5,
                    "review_text": "Excellent service and room was spotless.",
                    "booking_verified": True,
                    "created_at": now,
                    "updated_at": now,
                }
            )
        if self.settings.count_documents({"vendor_id": vid}) == 0:
            self.settings.insert_one(
                {
                    "vendor_id": vid,
                    "general": {
                        "business_name": "Grand Plaza & Spa",
                        "legal_entity_name": "Grand Plaza Hospitality Group LLC",
                        "business_address": "789 Luxury Avenue, Central District",
                        "booking_availability_slots": [
                            "09:00 AM",
                            "10:30 AM",
                            "11:30 AM",
                            "12:00 PM",
                            "01:00 PM",
                        ],
                        "buffer_time_minutes": 15,
                        "front_desk_phone": "+1 (555) 0123-4567",
                        "reservations_email": "reservations@grandplaza.com",
                        "emergency_contact": "+1 (555) 0123-9999",
                    },
                    "profile": {
                        "business_name": "TechFlow Solutions",
                        "category": "Retail",
                        "email_address": "business@example.com",
                        "phone_number": "+1 (555) 000-0000",
                        "about_business": "Growing businesses leverage technology for growth.",
                        "office_address": "123 Innovation Drive, San Francisco, CA",
                        "website": "https://techflow.com",
                    },
                    "commission": {"commission_percent": 12.5},
                    "legal_docs": {},
                    "updated_at": now,
                }
            )
        if self.support_tickets.count_documents({"vendor_id": vid}) == 0:
            self.support_tickets.insert_one(
                {
                    "vendor_id": vid,
                    "ticket_code": "#SP-2024-001",
                    "subject": "Payment not processed",
                    "description": "Payment was deducted but invoice still unpaid.",
                    "status": "resolved",
                    "messages": [],
                    "created_at": now,
                    "updated_at": now,
                }
            )
        if self.notification_settings.count_documents({"vendor_id": vid}) == 0:
            self.notification_settings.insert_one(
                {"vendor_id": vid, "booking_alerts": True, "review_alerts": True, "updated_at": now}
            )
        if self.notifications.count_documents({"vendor_id": vid}) == 0:
            self.notifications.insert_one(
                {
                    "vendor_id": vid,
                    "type": "booking",
                    "title": "New Booking Received",
                    "message": "Customer requested a booking for tomorrow.",
                    "read": False,
                    "actions": ["accept_request", "view_details"],
                    "created_at": now,
                }
            )

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

    def list_promotions(
        self, vendor_id: str, search: str | None = None, active: bool | None = None
    ) -> list[dict[str, Any]]:
        query: dict[str, Any] = {"vendor_id": ObjectId(vendor_id)}
        if search:
            query["promotion_name"] = {"$regex": search, "$options": "i"}
        if active is not None:
            query["active"] = active
        docs = self.promotions.find(query).sort("created_at", DESCENDING)
        return [self._serialize(doc) for doc in docs]

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
        return self.get_settings(vendor_id).get("general", {})

    def update_settings_general(self, vendor_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        sanitized = self._sanitize_payload(payload)
        self.settings.update_one(
            {"vendor_id": ObjectId(vendor_id)},
            {"$set": {"general": sanitized, "updated_at": datetime.now(UTC)}},
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
        return self.get_settings(vendor_id).get("commission", {})

    def get_legal_doc(self, vendor_id: str, doc_type: str) -> dict[str, Any]:
        legal_docs = self.get_settings(vendor_id).get("legal_docs", {})
        raw_doc = legal_docs.get(doc_type, {})
        if isinstance(raw_doc, dict):
            return {
                "doc_type": doc_type,
                "content": raw_doc.get("content", ""),
                "audience": raw_doc.get("audience", "apps"),
            }
        return {"doc_type": doc_type, "content": str(raw_doc), "audience": "apps"}

    def update_legal_doc(self, vendor_id: str, doc_type: str, content: str, audience: str) -> dict[str, Any]:
        self.settings.update_one(
            {"vendor_id": ObjectId(vendor_id)},
            {"$set": {f"legal_docs.{doc_type}": {"content": content, "audience": audience}, "updated_at": datetime.now(UTC)}},
            upsert=True,
        )
        return self.get_legal_doc(vendor_id, doc_type)

    def get_settings_profile(self, vendor_id: str) -> dict[str, Any]:
        return self.get_settings(vendor_id).get("profile", {})

    def update_settings_profile(self, vendor_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        sanitized = self._sanitize_payload(payload)
        self.settings.update_one(
            {"vendor_id": ObjectId(vendor_id)},
            {"$set": {"profile": sanitized, "updated_at": datetime.now(UTC)}},
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

    def list_notifications(self, vendor_id: str, limit: int, skip: int) -> dict[str, Any]:
        query = {"vendor_id": ObjectId(vendor_id)}
        total = int(self.notifications.count_documents(query))
        docs = self.notifications.find(query).sort("created_at", DESCENDING).skip(skip).limit(limit)
        setting = self.notification_settings.find_one({"vendor_id": ObjectId(vendor_id)}) or {}
        setting.pop("_id", None)
        setting.pop("vendor_id", None)
        return {"items": [self._serialize(doc) for doc in docs], "total": total, "settings": setting}

    def clear_notifications(self, vendor_id: str) -> int:
        result = self.notifications.delete_many({"vendor_id": ObjectId(vendor_id)})
        return int(result.deleted_count)

    def update_notification_settings(self, vendor_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        sanitized = self._sanitize_payload(payload)
        self.notification_settings.update_one(
            {"vendor_id": ObjectId(vendor_id)},
            {"$set": {**sanitized, "updated_at": datetime.now(UTC)}},
            upsert=True,
        )
        setting = self.notification_settings.find_one({"vendor_id": ObjectId(vendor_id)}) or {}
        setting.pop("_id", None)
        setting.pop("vendor_id", None)
        return setting

    def apply_notification_action(self, vendor_id: str, notification_id: str, action: str) -> dict[str, Any] | None:
        row = self.notifications.find_one({"_id": ObjectId(notification_id), "vendor_id": ObjectId(vendor_id)})
        if not row:
            return None
        self.notifications.update_one(
            {"_id": row["_id"]},
            {"$set": {"read": True, "last_action": action, "updated_at": datetime.now(UTC)}},
        )
        return self._serialize(self.notifications.find_one({"_id": row["_id"]}))
