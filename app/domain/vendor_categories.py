from collections.abc import Iterable
from typing import Any


LEGACY_EVENT_VENUE_CATEGORY = "event venue"
DEFAULT_VENDOR_CATEGORY = "Restaurant"


def normalize_account_categories(
    values: Iterable[Any] | Any,
    *,
    fallback: str = DEFAULT_VENDOR_CATEGORY,
) -> list[str]:
    source = values if isinstance(values, (list, tuple, set)) else [values]
    normalized: list[str] = []
    for item in source:
        label = str(item or "").strip()
        if not label or label.casefold() == LEGACY_EVENT_VENUE_CATEGORY:
            continue
        if label not in normalized:
            normalized.append(label)
    if normalized:
        return normalized
    safe_fallback = str(fallback or "").strip()
    if (
        not safe_fallback
        or safe_fallback.casefold() == LEGACY_EVENT_VENUE_CATEGORY
    ):
        safe_fallback = DEFAULT_VENDOR_CATEGORY
    return [safe_fallback]
