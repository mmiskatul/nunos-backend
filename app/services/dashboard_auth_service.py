import asyncio
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, status

from app.core.contact import parse_email_or_phone
from app.core.config import get_settings
from app.core.security import create_access_token, create_reset_token, decode_token, hash_password, verify_password
from app.models.dashboard_auth import (
    DashboardAdminPublic,
    DashboardAuthResponse,
    DashboardForgotPasswordRequest,
    DashboardLoginRequest,
    DashboardResetPasswordRequest,
    DashboardVerifyResetCodeRequest,
)
from app.providers.email_sender import EmailSender
from app.repositories.otp_repository import OTPRepository
from app.repositories.platform_admin_repository import PlatformAdminRepository


class DashboardAuthService:
    def __init__(self, admin_repo: PlatformAdminRepository, otp_repo: OTPRepository, email_sender: EmailSender):
        self.admin_repo = admin_repo
        self.otp_repo = otp_repo
        self.email_sender = email_sender
        self.settings = get_settings()

    async def login(self, payload: DashboardLoginRequest) -> DashboardAuthResponse:
        email, phone = parse_email_or_phone(payload.email_or_phone)
        admin = await (self.admin_repo.find_by_email(email) if email else self.admin_repo.find_by_phone(phone or ""))
        if not admin or not admin.get("password_hash"):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

        if not verify_password(payload.password, admin["password_hash"]):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

        if (admin.get("role") or "") != "platform_admin":
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
        if (admin.get("status") or "").lower() != "active":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin account is not active")

        return DashboardAuthResponse(
            access_token=create_access_token(admin["id"], audience="platform_admin", role="platform_admin"),
            admin=DashboardAdminPublic.model_validate(admin),
        )

    async def request_forgot_password(self, payload: DashboardForgotPasswordRequest) -> dict:
        email, phone = parse_email_or_phone(payload.email_or_phone)
        admin = await (self.admin_repo.find_by_email(email) if email else self.admin_repo.find_by_phone(phone or ""))
        if not admin or not admin.get("email"):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")

        otp = self._generate_otp()
        expires_at = datetime.now(UTC) + timedelta(minutes=self.settings.otp_expire_minutes)
        await self.otp_repo.upsert_code(
            email=admin["email"],
            purpose="dashboard_forgot_password",
            code=otp,
            expires_at=expires_at,
        )
        await asyncio.to_thread(
            self.email_sender.send_password_reset_code,
            admin["email"],
            admin.get("full_name") or "admin",
            otp,
            self.settings.otp_expire_minutes,
        )
        return {"message": "OTP sent"}

    async def verify_reset_code(self, payload: DashboardVerifyResetCodeRequest) -> dict:
        email, phone = parse_email_or_phone(payload.email_or_phone)
        admin = await (self.admin_repo.find_by_email(email) if email else self.admin_repo.find_by_phone(phone or ""))
        if not admin or not admin.get("email"):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid verification code")

        is_valid = await self.otp_repo.verify_code(
            email=admin["email"],
            purpose="dashboard_forgot_password",
            code=payload.code,
            now=datetime.now(UTC),
        )
        if not is_valid:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired verification code")

        return {"reset_token": create_reset_token(admin["id"])}

    async def reset_password(self, payload: DashboardResetPasswordRequest) -> dict:
        try:
            token_data = decode_token(payload.reset_token, expected_type="reset")
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid reset token") from exc

        admin_id = token_data.get("sub")
        if not admin_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid reset token payload")

        admin = await self.admin_repo.find_by_id(admin_id)
        if not admin:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Admin not found")

        await self.admin_repo.update_password_hash(admin_id, hash_password(payload.new_password))
        return {"message": "Password reset successful"}

    def _generate_otp(self) -> str:
        from random import randint

        return "".join(str(randint(0, 9)) for _ in range(self.settings.otp_length))
