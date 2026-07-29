from typing import Any


EVENT_CATEGORY_OPTIONS = (
    "Music",
    "Nightlife",
    "Comedy",
    "Family",
    "Culture",
    "Sports",
)

_EVENT_CATEGORY_KEYWORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("Comedy", ("comedy", "comedian", "stand-up", "standup")),
    (
        "Family",
        ("family", "kids", "children", "child", "birthday", "wedding"),
    ),
    (
        "Sports",
        (
            "sport",
            "football",
            "soccer",
            "cricket",
            "basketball",
            "tennis",
            "fitness",
            "wellness",
            "race",
            "marathon",
            "tournament",
        ),
    ),
    (
        "Music",
        (
            "music",
            "concert",
            "festival",
            "band",
            "singer",
            "live performance",
            "dj",
        ),
    ),
    (
        "Nightlife",
        (
            "nightlife",
            "night club",
            "nightclub",
            "club",
            "party",
            "lounge",
            "bar",
            "gala",
            "dinner",
            "late session",
        ),
    ),
    (
        "Culture",
        (
            "culture",
            "cultural",
            "art",
            "exhibition",
            "museum",
            "theatre",
            "theater",
            "heritage",
            "workshop",
            "conference",
            "tasting",
        ),
    ),
)


def normalize_event_category(
    value: Any,
    *,
    fallback: str | None = None,
) -> str:
    label = str(value or "").strip()
    normalized = label.casefold()

    for category in EVENT_CATEGORY_OPTIONS:
        if normalized == category.casefold():
            return category

    for category, keywords in _EVENT_CATEGORY_KEYWORDS:
        if any(keyword in normalized for keyword in keywords):
            return category

    if fallback in EVENT_CATEGORY_OPTIONS:
        return fallback

    allowed = ", ".join(EVENT_CATEGORY_OPTIONS)
    raise ValueError(f"Event category must be one of: {allowed}.")
