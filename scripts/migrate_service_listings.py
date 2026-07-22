"""Project existing vendor service settings into public service collections."""

from app.core.config import get_settings
from app.db.mongodb import MongoDatabase
from app.modules.vendor.repositories_portal import VendorPortalRepository


def main() -> None:
    settings = get_settings()
    mongo = MongoDatabase(settings.mongodb_uri, settings.mongodb_db_name)
    try:
        repository = VendorPortalRepository(mongo.db)
        migrated = 0
        for document in mongo.db["vendor_portal_settings"].find({}, {"vendor_id": 1, "profile": 1}):
            vendor_id = document.get("vendor_id")
            profile = document.get("profile") if isinstance(document.get("profile"), dict) else {}
            if vendor_id is None:
                continue
            for service_type in ("restaurant", "hotel", "spa"):
                service_settings = profile.get(f"{service_type}_settings")
                if isinstance(service_settings, dict):
                    repository.sync_service_listing(str(vendor_id), service_type, service_settings)
                    migrated += 1
        print(f"Projected {migrated} service listings into restaurants/hotels/spas.")
    finally:
        mongo.close()


if __name__ == "__main__":
    main()
