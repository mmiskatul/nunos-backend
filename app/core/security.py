from datetime import UTC, datetime, timedelta
from typing import Literal

# ── Compatibility shim ──────────────────────────────────────────────────────
# passlib 1.7.4 reads bcrypt.__about__.__version__ which was removed in
# bcrypt >= 4.0. Inject a fake __about__ so passlib's internal check is
# silent. This does NOT affect password hashing — purely cosmetic.
import bcrypt as _bcrypt_mod

if not hasattr(_bcrypt_mod, "__about__"):
    import types as _types

    _about = _types.SimpleNamespace(__version__=_bcrypt_mod.__version__)
    _bcrypt_mod.__about__ = _about
# ────────────────────────────────────────────────────────────────────────────

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import get_settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

TokenType = Literal["access", "refresh", "reset"]
TokenAudience = Literal["customer", "vendor", "platform_admin"]


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def _create_token(
    subject: str,
    token_type: TokenType,
    expires_delta: timedelta,
    *,
    audience: TokenAudience | None = None,
    role: str | None = None,
) -> str:
    settings = get_settings()
    now = datetime.now(UTC)
    payload = {
        "sub": subject,
        "type": token_type,
        "iat": int(now.timestamp()),
        "exp": int((now + expires_delta).timestamp()),
    }
    if audience:
        payload["aud"] = audience
    if role:
        payload["role"] = role
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def create_access_token(subject: str, *, audience: TokenAudience | None = None, role: str | None = None) -> str:
    settings = get_settings()
    return _create_token(
        subject,
        "access",
        timedelta(minutes=settings.access_token_expire_minutes),
        audience=audience,
        role=role,
    )


def create_refresh_token(subject: str) -> str:
    settings = get_settings()
    return _create_token(subject, "refresh", timedelta(minutes=settings.refresh_token_expire_minutes))


def create_reset_token(subject: str) -> str:
    settings = get_settings()
    return _create_token(subject, "reset", timedelta(minutes=settings.reset_token_expire_minutes))


def decode_token(
    token: str,
    expected_type: TokenType | None = None,
    *,
    expected_audience: TokenAudience | None = None,
) -> dict:
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    except JWTError as exc:
        raise ValueError("Invalid token") from exc

    if expected_type and payload.get("type") != expected_type:
        raise ValueError("Invalid token type")
    if expected_audience and payload.get("aud") != expected_audience:
        raise ValueError("Invalid token audience")

    return payload
