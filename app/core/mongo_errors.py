from pymongo.errors import DuplicateKeyError


def duplicate_contact_conflict_detail(
    exc: DuplicateKeyError,
    *,
    email_detail: str,
    phone_detail: str,
    default_detail: str,
) -> str:
    details = getattr(exc, "details", {}) or {}
    key_pattern = details.get("keyPattern") or {}
    key_value = details.get("keyValue") or {}
    error_parts = [str(key_pattern), str(key_value), details.get("errmsg") or "", str(exc)]
    error_text = " ".join(part for part in error_parts if part).lower()

    if "phone" in key_pattern or "phone" in key_value or "phone" in error_text:
        return phone_detail
    if "email" in key_pattern or "email" in key_value or "email" in error_text:
        return email_detail
    return default_detail
