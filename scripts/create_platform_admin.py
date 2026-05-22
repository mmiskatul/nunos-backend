import argparse

from pymongo import MongoClient

from app.core.config import get_settings
from app.core.security import hash_password


def main() -> None:
    parser = argparse.ArgumentParser(description="Create or update a platform admin account.")
    parser.add_argument("--email", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--full-name", required=True)
    parser.add_argument("--phone", default=None)
    args = parser.parse_args()

    settings = get_settings()
    client = MongoClient(settings.mongodb_uri)
    db = client[settings.mongodb_db_name]

    payload = {
        "full_name": args.full_name,
        "email": args.email.strip().lower(),
        "phone": args.phone.strip() if args.phone else None,
        "password_hash": hash_password(args.password),
        "role": "platform_admin",
        "status": "active",
    }

    db.platform_admins.update_one(
        {"email": payload["email"]},
        {"$set": {k: v for k, v in payload.items() if v is not None}},
        upsert=True,
    )
    print(f"Platform admin ready: {payload['email']}")


if __name__ == "__main__":
    main()
