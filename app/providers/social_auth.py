from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class SocialUserInfo:
    provider_user_id: str
    email: str
    full_name: str


class SocialAuthStrategy(ABC):
    provider: str

    @abstractmethod
    def verify_token(self, provider_token: str) -> SocialUserInfo:
        raise NotImplementedError


class GoogleAuthStrategy(SocialAuthStrategy):
    provider = "google"

    def verify_token(self, provider_token: str) -> SocialUserInfo:
        return _parse_fake_token(provider_token, self.provider)


class AppleAuthStrategy(SocialAuthStrategy):
    provider = "apple"

    def verify_token(self, provider_token: str) -> SocialUserInfo:
        return _parse_fake_token(provider_token, self.provider)


class SocialAuthStrategyFactory:
    """Factory pattern for choosing the social auth strategy."""

    def __init__(self):
        self._strategies: dict[str, SocialAuthStrategy] = {
            "google": GoogleAuthStrategy(),
            "apple": AppleAuthStrategy(),
        }

    def get_strategy(self, provider: str) -> SocialAuthStrategy:
        strategy = self._strategies.get(provider.lower())
        if not strategy:
            raise ValueError(f"Unsupported provider: {provider}")
        return strategy


def _parse_fake_token(provider_token: str, provider: str) -> SocialUserInfo:
    """
    Development-only parser.
    Expected token format: provider|provider_user_id|email|full_name
    Example: google|g-123|dev@example.com|John Doe
    """
    parts = provider_token.split("|")
    if len(parts) != 4 or parts[0].lower() != provider:
        raise ValueError("Invalid provider token format.")
    _, provider_user_id, email, full_name = parts
    return SocialUserInfo(provider_user_id=provider_user_id, email=email.lower(), full_name=full_name)

