"""Install the vendor indexes once as a deployment/release step."""

from app.core.config import get_settings
from app.db.mongodb import MongoDatabase
from app.db.vendor_indexes import ensure_vendor_indexes


def main() -> None:
    settings = get_settings()
    mongo = MongoDatabase(settings.mongodb_uri, settings.mongodb_db_name)
    try:
        created = ensure_vendor_indexes(mongo.db)
        total = sum(len(names) for names in created.values())
        print(f"Ensured {total} indexes across {len(created)} collections.")
    finally:
        mongo.close()


if __name__ == "__main__":
    main()
