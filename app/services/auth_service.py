from typing import Any

from bson.errors import InvalidId
from fastapi import HTTPException, status

from app.core.config import get_settings
from app.core.contact import parse_email_or_phone
from app.core.security import create_access_token, decode_access_token, hash_password, verify_password
from app.providers.social_auth import SocialAuthStrategyFactory
from app.repositories.password_reset_repository import PasswordResetRepository
from app.repositories.user_repository import UserRepository
from app.schemas.auth import (
    AuthResponse,
    ForgotPasswordRequest,
    ForgotPasswordResponse,
    LoginRequest,
    ResetPasswordRequest,
    SignupRequest,
    SocialLoginRequest,
    UserPublic,
)


class AuthService:
    """Service layer for authentication and account lifecycle."""

    def __init__(
        self,
        user_repo: UserRepository,
        password_reset_repo: PasswordResetRepository,
        social_factory: SocialAuthStrategyFactory,
    ):
        self.user_repo = user_repo
        self.password_reset_repo = password_reset_repo
        self.social_factory = social_factory
        self.settings = get_settings()

    def signup(self, payload: SignupRequest) -> AuthResponse:
        email, phone = parse_email_or_phone(payload.email_or_phone)
        existing = self.user_repo.get_by_email(email) if email else self.user_repo.get_by_phone(phone or "")
        if existing:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User already exists.")

        user = self.user_repo.create_user(
            {
                "full_name": payload.full_name,
                "email": email,
                "phone": phone,
                "password_hash": hash_password(payload.password),
                "enable_location": payload.enable_location,
                "auth_provider": "local",
            }
        )
        return self._build_auth_response(user)

    def login(self, payload: LoginRequest) -> AuthResponse:
        user = self._get_user_by_contact(payload.email_or_phone)
        if not user or not user.get("password_hash"):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials.")

        if not verify_password(payload.password, user["password_hash"]):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials.")

        return self._build_auth_response(user)

    def social_login(self, payload: SocialLoginRequest) -> AuthResponse:
        strategy = self.social_factory.get_strategy(payload.provider)
        social_user = strategy.verify_token(payload.provider_token)

        user = self.user_repo.get_by_provider_user_id(social_user.provider_user_id)
        if not user:
            user = self.user_repo.get_by_email(social_user.email)

        if not user:
            user = self.user_repo.create_user(
                {
                    "full_name": social_user.full_name,
                    "email": social_user.email,
                    "phone": None,
                    "password_hash": None,
                    "enable_location": False,
                    "auth_provider": payload.provider,
                    "provider_user_id": social_user.provider_user_id,
                }
            )
        return self._build_auth_response(user)

    def request_password_reset(self, payload: ForgotPasswordRequest) -> ForgotPasswordResponse:
        user = self._get_user_by_contact(payload.email_or_phone)
        if not user:
            return ForgotPasswordResponse(
                message="If the account exists, a password reset link has been generated."
            )

        token = self.password_reset_repo.create_token(
            user_id=user["id"], expires_in_minutes=self.settings.password_reset_token_expire_minutes
        )
        if self.settings.debug_return_reset_token:
            return ForgotPasswordResponse(
                message="Password reset token created (debug mode).",
                reset_token=token,
            )
        return ForgotPasswordResponse(
            message="If the account exists, a password reset link has been generated."
        )

    def reset_password(self, payload: ResetPasswordRequest) -> dict[str, str]:
        token_doc = self.password_reset_repo.get_valid_token(payload.reset_token)
        if not token_doc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired reset token.")

        user_id = str(token_doc["user_id"])
        self.user_repo.update_password_hash(user_id, hash_password(payload.new_password))
        self.password_reset_repo.mark_used(payload.reset_token)
        return {"message": "Password has been reset successfully."}

    def get_current_user_from_token(self, token: str) -> dict[str, Any]:
        payload = decode_access_token(token)
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload.")
        try:
            user = self.user_repo.get_by_id(user_id)
        except InvalidId as exc:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token subject.") from exc
        if not user:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found.")
        return user

    def update_location_preference(self, user_id: str, enable_location: bool) -> UserPublic:
        updated_user = self.user_repo.update_location_preference(user_id, enable_location)
        if not updated_user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
        return UserPublic.model_validate(updated_user)

    def _build_auth_response(self, user: dict[str, Any]) -> AuthResponse:
        token = create_access_token(user["id"])
        return AuthResponse(access_token=token, user=UserPublic.model_validate(user))

    def _get_user_by_contact(self, email_or_phone: str) -> dict[str, Any] | None:
        email, phone = parse_email_or_phone(email_or_phone)
        if email:
            return self.user_repo.get_by_email(email)
        return self.user_repo.get_by_phone(phone or "")

