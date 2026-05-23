from abc import ABC, abstractmethod
from dataclasses import dataclass

import httpx

from app.core.config import Settings


@dataclass
class SocialUserInfo:
    provider: str
    provider_user_id: str
    email: str
    full_name: str
    profile_image_url: str | None = None


class SocialAuthStrategy(ABC):
    provider: str

    @abstractmethod
    async def verify_token(self, id_token: str) -> SocialUserInfo:
        raise NotImplementedError


class GoogleAuthStrategy(SocialAuthStrategy):
    provider = "google"
    _token_info_url = "https://oauth2.googleapis.com/tokeninfo"

    def __init__(self, settings: Settings):
        self.settings = settings

    async def verify_token(self, id_token: str) -> SocialUserInfo:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.get(self._token_info_url, params={"id_token": id_token})

        if response.status_code != 200:
            raise ValueError("Google token verification failed.")

        payload = response.json()
        issuer = str(payload.get("iss") or "")
        audience = str(payload.get("aud") or "")
        subject = str(payload.get("sub") or "")
        email = str(payload.get("email") or "").strip().lower()
        full_name = str(payload.get("name") or "").strip()
        email_verified = str(payload.get("email_verified") or "").lower() == "true"

        if issuer not in {"accounts.google.com", "https://accounts.google.com"}:
            raise ValueError("Google token issuer is invalid.")
        if self.settings.google_oauth_client_ids and audience not in self.settings.google_oauth_client_ids:
            raise ValueError("Google token audience is not allowed.")
        if not subject:
            raise ValueError("Google account id is missing.")
        if not email or not email_verified:
            raise ValueError("Google account email is missing or not verified.")

        return SocialUserInfo(
            provider=self.provider,
            provider_user_id=subject,
            email=email,
            full_name=full_name or email.split("@")[0],
            profile_image_url=str(payload.get("picture") or "").strip() or None,
        )


class SocialAuthStrategyFactory:
    def __init__(self, settings: Settings):
        self._strategies: dict[str, SocialAuthStrategy] = {
            "google": GoogleAuthStrategy(settings),
        }

    def get_strategy(self, provider: str) -> SocialAuthStrategy:
        strategy = self._strategies.get(provider.lower())
        if not strategy:
            raise ValueError(f"Unsupported provider: {provider}")
        return strategy
