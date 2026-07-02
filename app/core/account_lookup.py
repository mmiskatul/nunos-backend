from __future__ import annotations

from typing import Any

GLOBAL_ACCOUNT_COLLECTIONS = ("users", "vendors", "platform_admins")


def _normalize_email(email: str) -> str:
    return email.strip().lower()


def _normalize_contact_value(field: str, value: str) -> str:
    return _normalize_email(value) if field == "email" else value.strip()


def _build_result(collection_name: str, document: dict[str, Any]) -> dict[str, Any]:
    return {"collection": collection_name, "document": document}


async def find_existing_contact_async(
    db: Any,
    *,
    field: str,
    value: str,
    exclude_collection: str | None = None,
    exclude_id: str | None = None,
) -> dict[str, Any] | None:
    normalized_value = _normalize_contact_value(field, value)
    for collection_name in GLOBAL_ACCOUNT_COLLECTIONS:
        document = await db[collection_name].find_one({field: normalized_value})
        if not document:
            continue
        if exclude_collection == collection_name and exclude_id and str(document.get("_id")) == exclude_id:
            continue
        return _build_result(collection_name, document)
    return None


async def find_existing_email_async(
    db: Any,
    email: str,
    *,
    exclude_collection: str | None = None,
    exclude_id: str | None = None,
) -> dict[str, Any] | None:
    return await find_existing_contact_async(
        db,
        field="email",
        value=email,
        exclude_collection=exclude_collection,
        exclude_id=exclude_id,
    )


async def find_existing_phone_async(
    db: Any,
    phone: str,
    *,
    exclude_collection: str | None = None,
    exclude_id: str | None = None,
) -> dict[str, Any] | None:
    return await find_existing_contact_async(
        db,
        field="phone",
        value=phone,
        exclude_collection=exclude_collection,
        exclude_id=exclude_id,
    )


def find_existing_contact_sync(
    db: Any,
    *,
    field: str,
    value: str,
    exclude_collection: str | None = None,
    exclude_id: str | None = None,
) -> dict[str, Any] | None:
    normalized_value = _normalize_contact_value(field, value)
    for collection_name in GLOBAL_ACCOUNT_COLLECTIONS:
        document = db[collection_name].find_one({field: normalized_value})
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
    return find_existing_contact_sync(
        db,
        field="email",
        value=email,
        exclude_collection=exclude_collection,
        exclude_id=exclude_id,
    )


def find_existing_phone_sync(
    db: Any,
    phone: str,
    *,
    exclude_collection: str | None = None,
    exclude_id: str | None = None,
) -> dict[str, Any] | None:
    return find_existing_contact_sync(
        db,
        field="phone",
        value=phone,
        exclude_collection=exclude_collection,
        exclude_id=exclude_id,
    )
