"""Shared rules for public Restaurant, Hotel, and Spa listings."""

from typing import Final

SERVICE_TYPES: Final[tuple[str, ...]] = ("restaurant", "hotel", "spa")
SERVICE_COLLECTIONS: Final[dict[str, str]] = {
    "restaurant": "restaurants",
    "hotel": "hotels",
    "spa": "spas",
}


def normalize_service_type(value: str) -> str:
    normalized = str(value or "").strip().lower()
    if normalized not in SERVICE_TYPES:
        raise ValueError(f"Unsupported service type: {value}")
    return normalized


def collection_name_for(service_type: str) -> str:
    return SERVICE_COLLECTIONS[normalize_service_type(service_type)]
