from datetime import UTC, datetime

from bson import ObjectId


def oid(value: str) -> ObjectId:
    if not ObjectId.is_valid(value):
        raise ValueError("Invalid ObjectId")
    return ObjectId(value)


def utcnow() -> datetime:
    return datetime.now(UTC)
