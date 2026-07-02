from datetime import UTC, datetime
from typing import Any

from bson.errors import InvalidId
from fastapi import HTTPException, status
from pymongo.errors import DuplicateKeyError

from app.core.account_lookup import find_existing_email_sync, find_existing_phone_sync
from app.core.config import get_settings
from app.core.contact import parse_email_or_phone
from app.core.mongo_errors import duplicate_contact_conflict_detail
from app.core.session_tokens import SESSION_COLLECTION, build_session_document, session_is_active
from app.core.security import create_access_token, decode_token, hash_password, verify_password
from app.modules.platform_admin.repositories_admin import PlatformAdminRepository
from app.modules.platform_admin.repositories_password_reset import AdminPasswordResetRepository
from app.modules.platform_admin.repositories_signup import AdminSignupVerificationRepository
from app.modules.platform_admin.schemas_auth import (
    AdminAuthResponse,
    AdminCodeResponse,
    AdminForgotPasswordRequest,
    AdminLoginRequest,
    AdminMessageResponse,
    AdminPublic,
    AdminRefreshTokenRequest,
    AdminRegisterCodeRequest,
    AdminRegisterRequest,
    AdminResetPasswordRequest,
    AdminVerifyCodeResponse,
    AdminVerifyRegisterCodeRequest,
    AdminVerifyResetCodeRequest,
)
from app.providers.email_sender import EmailSender


class PlatformAdminAuthService:
    """Service layer for platform admin authentication and validation flows."""

    def __init__(
        self,
        admin_repo: PlatformAdminRepository,
        signup_repo: AdminSignupVerificationRepository,
        password_reset_repo: AdminPasswordResetRepository,
        email_sender: EmailSender,
    ):
        self.admin_repo = admin_repo
        self.signup_repo = signup_repo
        self.password_reset_repo = password_reset_repo
        self.email_sender = email_sender
        self.settings = get_settings()
        self.session_collection = self.admin_repo.collection.database[SESSION_COLLECTION]

    def request_register_code(self, payload: AdminRegisterCodeRequest) -> AdminCodeResponse:
        email, _ = parse_email_or_phone(payload.email_or_phone)
        if not email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Admin registration requires email verification.",
            )
        if find_existing_email_sync(self.admin_repo.collection.database, email):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This email is already in use by another account.",
            )

        code = self.signup_repo.create_validation_code(
            email=email,
            code_length=self.settings.signup_verification_code_length,
            expires_in_minutes=self.settings.signup_verification_code_expire_minutes,
        )
        self.email_sender.send_validation_code(
            recipient_email=email,
            full_name="admin",
            code=code,
            expires_in=self.settings.signup_verification_code_expire_minutes,
        )
        if self.settings.debug_return_signup_code:
            return AdminCodeResponse(
                message="Validation code sent to email (debug mode includes code).",
                validation_code=code,
            )
        return AdminCodeResponse(message="Validation code sent to email.")

    def verify_register_code(self, payload: AdminVerifyRegisterCodeRequest) -> AdminVerifyCodeResponse:
        email, _ = parse_email_or_phone(payload.email_or_phone)
        if not email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Admin registration requires email verification.",
            )

        is_valid = self.signup_repo.validate_and_consume_code(email, payload.validation_code)
        if not is_valid:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired validation code.")

        signup_token = self.signup_repo.create_signup_token(
            email=email, expires_in_minutes=self.settings.signup_verification_token_expire_minutes
        )
        return AdminVerifyCodeResponse(message="Validation successful.", signup_token=signup_token)

    def register(self, payload: AdminRegisterRequest) -> AdminAuthResponse:
        email, phone = parse_email_or_phone(payload.email_or_phone)
        if not email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Admin registration requires verified email.",
            )

        valid_token = self.signup_repo.get_valid_signup_token(email=email, token=payload.signup_token)
        if not valid_token:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired signup token.")

        if find_existing_email_sync(self.admin_repo.collection.database, email):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This email is already in use by another account.",
            )
        if phone and find_existing_phone_sync(self.admin_repo.collection.database, phone):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This phone number is already used by another account.",
            )

        try:
            admin = self.admin_repo.create_admin(
                {
                    "full_name": payload.full_name,
                    "email": email,
                    "phone": phone,
                    "password_hash": hash_password(payload.password),
                    "role": "platform_admin",
                    "status": "active",
                }
            )
        except DuplicateKeyError as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=duplicate_contact_conflict_detail(
                    exc,
                    email_detail="This email is already in use by another account.",
                    phone_detail="This phone number is already used by another account.",
                    default_detail="Email or phone already exists",
                ),
            ) from exc

        self.signup_repo.mark_signup_token_used(payload.signup_token)
        return self._build_auth_response(admin)

    def login(self, payload: AdminLoginRequest) -> AdminAuthResponse:
        admin = self._get_by_contact(payload.email_or_phone)
        if not admin or not admin.get("password_hash"):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials.")

        if not verify_password(payload.password, admin["password_hash"]):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials.")
        if (admin.get("role") or "") != "platform_admin":
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials.")

        if (admin.get("status") or "").lower() != "active":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin account is not active.")

        return self._build_auth_response(admin)

    def refresh(self, payload: AdminRefreshTokenRequest) -> AdminAuthResponse:
        session = self.session_collection.find_one({"token": payload.refresh_token})
        if not session_is_active(session, audience="platform_admin"):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token.")

        admin_id = str(session.get("subject_id") or "")
        if not admin_id:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload.")
        try:
            admin = self.admin_repo.get_by_id(admin_id)
        except InvalidId as exc:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token subject.") from exc
        if not admin:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Admin not found.")
        if (admin.get("role") or "") != "platform_admin":
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token subject.")
        if (admin.get("status") or "").lower() != "active":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin account is not active.")

        self.session_collection.update_one(
            {"_id": session["_id"]},
            {"$set": {"last_used_at": datetime.now(UTC)}},
        )

        return AdminAuthResponse(
            access_token=create_access_token(admin["id"], audience="platform_admin", role="platform_admin"),
            refresh_token=payload.refresh_token,
            session_token=payload.refresh_token,
            admin=AdminPublic.model_validate(admin),
        )

    def logout(self, payload: AdminRefreshTokenRequest) -> AdminMessageResponse:
        self.session_collection.update_one(
            {"token": payload.refresh_token, "audience": "platform_admin", "revoked_at": None},
            {"$set": {"revoked_at": datetime.now(UTC), "last_used_at": datetime.now(UTC)}},
        )
        return AdminMessageResponse(message="Logged out successfully.")

    def request_forgot_password_code(self, payload: AdminForgotPasswordRequest) -> AdminCodeResponse:
        admin = self._get_by_contact(payload.email_or_phone)
        if not admin or not admin.get("email"):
            return AdminCodeResponse(message="If the account exists, a validation code has been sent.")

        code = self.password_reset_repo.create_validation_code(
            admin_id=admin["id"],
            code_length=self.settings.password_reset_code_length,
            expires_in_minutes=self.settings.password_reset_code_expire_minutes,
        )
        self.email_sender.send_validation_code(
            recipient_email=admin["email"],
            full_name=admin.get("full_name", "admin"),
            code=code,
            expires_in=self.settings.password_reset_code_expire_minutes,
        )
        if self.settings.debug_return_reset_code:
            return AdminCodeResponse(message="Validation code sent (debug mode includes code).", validation_code=code)
        return AdminCodeResponse(message="If the account exists, a validation code has been sent.")

    def verify_forgot_password_code(self, payload: AdminVerifyResetCodeRequest) -> AdminVerifyCodeResponse:
        admin = self._get_by_contact(payload.email_or_phone)
        if not admin:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired validation code.")

        is_valid = self.password_reset_repo.validate_and_consume_code(admin["id"], payload.validation_code)
        if not is_valid:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired validation code.")

        reset_token = self.password_reset_repo.create_reset_token(
            admin_id=admin["id"], expires_in_minutes=self.settings.password_reset_token_expire_minutes
        )
        return AdminVerifyCodeResponse(message="Validation code verified.", reset_token=reset_token)

    def reset_password(self, payload: AdminResetPasswordRequest) -> AdminMessageResponse:
        token_doc = self.password_reset_repo.get_valid_reset_token(payload.reset_token)
        if not token_doc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired reset token.")

        admin_id = str(token_doc["admin_id"])
        self.admin_repo.update_password_hash(admin_id, hash_password(payload.new_password))
        self.password_reset_repo.mark_reset_token_used(payload.reset_token)
        return AdminMessageResponse(message="Password has been reset successfully.")

    def get_current_admin_from_token(self, token: str) -> dict[str, Any]:
        try:
            payload = decode_token(
                token,
                expected_type="access",
                expected_audience="platform_admin",
                expected_role="platform_admin",
            )
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid access token.") from exc
        admin_id = payload.get("sub")
        if not admin_id:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload.")
        try:
            admin = self.admin_repo.get_by_id(admin_id)
        except InvalidId as exc:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token subject.") from exc
        if not admin:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Admin not found.")
        if (admin.get("role") or "") != "platform_admin":
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token subject.")
        return admin

    def _build_auth_response(self, admin: dict[str, Any]) -> AdminAuthResponse:
        access_token = create_access_token(admin["id"], audience="platform_admin", role="platform_admin")
        session_doc = build_session_document(
            subject_id=admin["id"],
            audience="platform_admin",
            role="platform_admin",
        )
        self.session_collection.insert_one(session_doc)
        refresh_token = str(session_doc["token"])
        return AdminAuthResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            session_token=refresh_token,
            admin=AdminPublic.model_validate(admin),
        )

    def _get_by_contact(self, email_or_phone: str) -> dict[str, Any] | None:
        email, phone = parse_email_or_phone(email_or_phone)
        if email:
            return self.admin_repo.get_by_email(email)
        return self.admin_repo.get_by_phone(phone or "")

