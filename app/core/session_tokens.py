from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

from app.core.config import get_settings
from app.core.security import TokenAudience

SESSION_COLLECTION = "auth_sessions"


def generate_session_token() -> str:
    return secrets.token_urlsafe(48)


def build_session_document(
    *,
    subject_id: str,
    audience: TokenAudience,
    role: str | None = None,
    token: str | None = None,
) -> dict[str, Any]:
    settings = get_settings()
    now = datetime.now(UTC)
    return {
        "token": token or generate_session_token(),
        "subject_id": subject_id,
        "audience": audience,
        "role": role,
        "created_at": now,
        "last_used_at": now,
        "expires_at": now + timedelta(minutes=settings.refresh_token_expire_minutes),
        "revoked_at": None,
    }


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def session_is_active(document: dict[str, Any] | None, *, audience: TokenAudience) -> bool:
    if not document:
        return False
    if document.get("audience") != audience:
        return False
    expected_role = "customer" if audience == "customer" else audience
    if document.get("role") != expected_role:
        return False
    if document.get("revoked_at") is not None:
        return False
    expires_at = document.get("expires_at")
    if not isinstance(expires_at, datetime):
        return False
    return _as_utc(expires_at) > datetime.now(UTC)
