from __future__ import annotations

from typing import Any

GLOBAL_EMAIL_COLLECTIONS = ("users", "vendors", "platform_admins")


def _normalize_email(email: str) -> str:
    return email.strip().lower()


def _build_result(collection_name: str, document: dict[str, Any]) -> dict[str, Any]:
    return {"collection": collection_name, "document": document}


async def find_existing_email_async(
    db: Any,
    email: str,
    *,
    exclude_collection: str | None = None,
    exclude_id: str | None = None,
) -> dict[str, Any] | None:
    normalized_email = _normalize_email(email)
    for collection_name in GLOBAL_EMAIL_COLLECTIONS:
        document = await db[collection_name].find_one({"email": normalized_email})
        if not document:
            continue
        if exclude_collection == collection_name and exclude_id and str(document.get("_id")) == exclude_id:
            continue
        return _build_result(collection_name, document)
    return None


def find_existing_email_sync(
    db: Any,
    email: str,
    *,
    exclude_collection: str | None = None,
    exclude_id: str | None = None,
) -> dict[str, Any] | None:
    normalized_email = _normalize_email(email)
    for collection_name in GLOBAL_EMAIL_COLLECTIONS:
        document = db[collection_name].find_one({"email": normalized_email})
        if not document:
            continue
        if exclude_collection == collection_name and exclude_id and str(document.get("_id")) == exclude_id:
            continue
        return _build_result(collection_name, document)
    return None
