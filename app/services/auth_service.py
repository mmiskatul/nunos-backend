import random
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, status
from pymongo.errors import DuplicateKeyError

from app.core.config import Settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    create_reset_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.models.user import (
    ForgotPasswordRequest,
    LoginRequest,
    RefreshTokenRequest,
    ResetPasswordRequest,
    TokenPair,
    UserCreateRequest,
)
from app.repositories.otp_repository import OTPRepository
from app.repositories.user_repository import UserRepository


class AuthService:
    def __init__(self, user_repo: UserRepository, otp_repo: OTPRepository, settings: Settings):
        self.user_repo = user_repo
        self.otp_repo = otp_repo
        self.settings = settings

    async def register(self, payload: UserCreateRequest) -> TokenPair:
        user_doc = {
            "full_name": payload.full_name,
            "email": payload.email,
            "phone": payload.phone,
            "password_hash": hash_password(payload.password),
            "points_balance": 0,
            "is_active": True,
        }
        try:
            user = await self.user_repo.create_user(user_doc)
        except DuplicateKeyError as exc:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email or phone already exists") from exc

        user_id = str(user["_id"])
        return TokenPair(access_token=create_access_token(user_id), refresh_token=create_refresh_token(user_id))

    async def login(self, payload: LoginRequest) -> TokenPair:
        user = await self.user_repo.find_by_email_or_phone(payload.email_or_phone)
        if not user or not verify_password(payload.password, user["password_hash"]):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

        user_id = str(user["_id"])
        return TokenPair(access_token=create_access_token(user_id), refresh_token=create_refresh_token(user_id))

    async def refresh(self, payload: RefreshTokenRequest) -> TokenPair:
        try:
            token_data = decode_token(payload.refresh_token, expected_type="refresh")
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token") from exc

        user_id = token_data.get("sub")
        user = await self.user_repo.find_by_id(user_id)
        if not user:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

        return TokenPair(access_token=create_access_token(user_id), refresh_token=create_refresh_token(user_id))

    async def forgot_password(self, payload: ForgotPasswordRequest) -> dict:
        user = await self.user_repo.find_by_email(payload.email)
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

        otp = self._generate_otp()
        expires_at = datetime.now(UTC) + timedelta(minutes=self.settings.otp_expire_minutes)
        await self.otp_repo.upsert_code(
            email=payload.email,
            purpose="forgot_password",
            code=otp,
            expires_at=expires_at,
        )

        await self._send_email_stub(payload.email, otp)
        return {"message": "OTP sent"}

    async def verify_otp(self, email: str, otp: str) -> dict:
        is_valid = await self.otp_repo.verify_code(
            email=email,
            purpose="forgot_password",
            code=otp,
            now=datetime.now(UTC),
        )
        if not is_valid:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired OTP")

        return {"reset_token": create_reset_token(email)}

    async def reset_password(self, payload: ResetPasswordRequest) -> dict:
        try:
            token_data = decode_token(payload.reset_token, expected_type="reset")
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid reset token") from exc

        email = token_data.get("sub")
        if not email:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid reset token payload")

        updated = await self.user_repo.update_password_by_email(email, hash_password(payload.new_password))
        if not updated:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

        return {"message": "Password reset successful"}

    async def _send_email_stub(self, email: str, otp: str) -> None:
        print(f"[stub-email] sending OTP {otp} to {email}")

    def _generate_otp(self) -> str:
        return "".join(str(random.randint(0, 9)) for _ in range(self.settings.otp_length))
