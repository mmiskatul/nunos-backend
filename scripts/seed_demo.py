import asyncio
from datetime import UTC, datetime, timedelta

from motor.motor_asyncio import AsyncIOMotorClient

from app.core.config import get_settings
from app.db.mongo import ensure_indexes


async def seed() -> None:
    settings = get_settings()
    client = AsyncIOMotorClient(settings.mongodb_uri)
    db = client[settings.mongodb_db_name]

    await ensure_indexes(db)

    await db.listings.delete_many({})
    await db.offers.delete_many({})
    await db.reviews.delete_many({})

    now = datetime.now(UTC)

    listings = [
        {
            "name": "Metro Flame Grill",
            "type": "restaurant",
            "description": "Contemporary grill with rooftop seating.",
            "images": ["https://picsum.photos/seed/rest1/900/600"],
            "location": {"type": "Point", "coordinates": [90.4125, 23.8103]},
            "price_level": 3,
            "near_metro_station": "Agargaon",
            "has_offers": True,
            "rating_summary": {"average": 4.5, "count": 120},
            "created_at": now,
            "updated_at": now,
        },
        {
            "name": "Skyline Suites",
            "type": "hotel",
            "description": "Business hotel with fast metro access.",
            "images": ["https://picsum.photos/seed/hotel1/900/600"],
            "location": {"type": "Point", "coordinates": [90.4020, 23.7870]},
            "price_level": 4,
            "near_metro_station": "Farmgate",
            "has_offers": False,
            "rating_summary": {"average": 4.2, "count": 88},
            "created_at": now,
            "updated_at": now,
        },
        {
            "name": "Zen Spa Lounge",
            "type": "spa",
            "description": "Deep tissue and aromatherapy sessions.",
            "images": ["https://picsum.photos/seed/spa1/900/600"],
            "location": {"type": "Point", "coordinates": [90.4050, 23.7950]},
            "price_level": 3,
            "near_metro_station": "Karwan Bazar",
            "has_offers": True,
            "rating_summary": {"average": 4.7, "count": 61},
            "created_at": now,
            "updated_at": now,
        },
        {
            "name": "Live at Metro Arena",
            "type": "event",
            "description": "Weekend live music and food festival.",
            "images": ["https://picsum.photos/seed/event1/900/600"],
            "location": {"type": "Point", "coordinates": [90.3980, 23.7800]},
            "price_level": 2,
            "near_metro_station": "Motijheel",
            "has_offers": True,
            "event_datetime": now + timedelta(days=4),
            "rating_summary": {"average": 4.4, "count": 203},
            "created_at": now,
            "updated_at": now,
        },
    ]

    result = await db.listings.insert_many(listings)
    ids = result.inserted_ids

    await db.offers.insert_many(
        [
            {
                "listing_id": ids[0],
                "title": "Dinner 15% Off",
                "discount_percent": 15,
                "require_code": True,
                "promo_code": "NUNO15",
                "starts_at": now - timedelta(days=1),
                "ends_at": now + timedelta(days=30),
                "created_at": now,
                "updated_at": now,
            },
            {
                "listing_id": ids[2],
                "title": "Spa Week Offer",
                "discount_percent": 20,
                "require_code": False,
                "promo_code": None,
                "starts_at": now - timedelta(days=1),
                "ends_at": now + timedelta(days=14),
                "created_at": now,
                "updated_at": now,
            },
        ]
    )

    print("Seed completed.")
    print("Listing IDs:")
    for item in ids:
        print(str(item))

    client.close()


if __name__ == "__main__":
    asyncio.run(seed())
