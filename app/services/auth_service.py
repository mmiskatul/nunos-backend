import asyncio
import random
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, status
from pymongo.errors import DuplicateKeyError

from app.core.account_lookup import find_existing_email_async
from app.core.config import Settings
from app.core.mongo_errors import duplicate_contact_conflict_detail
from app.core.session_tokens import SESSION_COLLECTION, build_session_document, session_is_active
from app.core.security import (
    create_access_token,
    create_reset_token,
    hash_password,
    verify_password,
)
from app.models.user import (
    ForgotPasswordRequest,
    LoginRequest,
    RegistrationResponse,
    RefreshTokenRequest,
    ResetPasswordRequest,
    SocialLoginRequest,
    TokenPair,
    UserCreateRequest,
    VerifyEmailRequest,
)
from app.providers.email_sender import EmailSender
from app.providers.social_auth import SocialAuthStrategyFactory
from app.repositories.otp_repository import OTPRepository
from app.repositories.pending_signup_repository import PendingSignupRepository
from app.repositories.user_repository import UserRepository


class AuthService:
    def __init__(
        self,
        user_repo: UserRepository,
        otp_repo: OTPRepository,
        pending_signup_repo: PendingSignupRepository,
        email_sender: EmailSender,
        settings: Settings,
    ):
        self.user_repo = user_repo
        self.otp_repo = otp_repo
        self.pending_signup_repo = pending_signup_repo
        self.email_sender = email_sender
        self.settings = settings
        self.social_auth_factory = SocialAuthStrategyFactory(settings)
        self.session_collection = self.user_repo.collection.database[SESSION_COLLECTION]

    async def register(self, payload: UserCreateRequest) -> RegistrationResponse:
        if not payload.email:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email is required for registration")

        existing_account = await find_existing_email_async(self.user_repo.collection.database, payload.email)
        if existing_account:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This email is already in use by another account.",
            )

        if payload.phone:
            existing_phone = await self.user_repo.find_by_phone(payload.phone)
            if existing_phone:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Phone already exists")

        password_hash = hash_password(payload.password)
        await self.pending_signup_repo.upsert_signup(
            email=payload.email,
            full_name=payload.full_name,
            phone=payload.phone,
            password_hash=password_hash,
            location_enabled=payload.location_enabled,
            latitude=payload.latitude,
            longitude=payload.longitude,
            location_accuracy_meters=payload.location_accuracy_meters,
            expires_in_minutes=self.settings.signup_pending_expire_minutes,
        )

        otp = self._generate_otp()
        expires_at = datetime.now(UTC) + timedelta(minutes=self.settings.otp_expire_minutes)
        await self.otp_repo.upsert_code(
            email=payload.email,
            purpose="signup_verification",
            code=otp,
            expires_at=expires_at,
        )
        await asyncio.to_thread(
            self.email_sender.send_signup_verification_code,
            payload.email,
            payload.full_name,
            otp,
            self.settings.otp_expire_minutes,
        )
        return RegistrationResponse(message="Verification code sent to email.", email=payload.email)

    async def verify_email(self, payload: VerifyEmailRequest) -> TokenPair:
        signup_doc = await self.pending_signup_repo.get_valid_signup(email=payload.email)
        if not signup_doc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Registration request expired or missing")

        existing_account = await find_existing_email_async(self.user_repo.collection.database, payload.email)
        if existing_account:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This email is already in use by another account.",
            )

        is_valid = await self.otp_repo.verify_code(
            email=payload.email,
            purpose="signup_verification",
            code=payload.otp,
            now=datetime.now(UTC),
        )
        if not is_valid:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired verification code")

        user_doc = {
            "full_name": signup_doc["full_name"],
            "email": payload.email,
            "phone": signup_doc.get("phone"),
            "password_hash": signup_doc["password_hash"],
            "points_balance": 0,
            "is_active": True,
            "location_enabled": signup_doc.get("location_enabled", False),
            "latitude": signup_doc.get("latitude"),
            "longitude": signup_doc.get("longitude"),
            "location_accuracy_meters": signup_doc.get("location_accuracy_meters"),
        }
        try:
            user = await self.user_repo.create_user(user_doc)
        except DuplicateKeyError as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=duplicate_contact_conflict_detail(
                    exc,
                    email_detail="This email is already in use by another account.",
                    phone_detail="Phone already exists",
                    default_detail="Email or phone already exists",
                ),
            ) from exc

        await self.pending_signup_repo.delete_signup(email=payload.email)
        user_id = str(user["_id"])
        return await self._issue_token_pair(user_id)

    async def login(self, payload: LoginRequest) -> TokenPair:
        user = await self.user_repo.find_by_email_or_phone(payload.email_or_phone)
        password_hash = user.get("password_hash") if user else None
        if not user or not password_hash or not verify_password(payload.password, password_hash):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

        user_id = str(user["_id"])
        return await self._issue_token_pair(user_id)

    async def social_login(self, payload: SocialLoginRequest) -> TokenPair:
        try:
            strategy = self.social_auth_factory.get_strategy(payload.provider)
            social_user = await strategy.verify_token(payload.id_token)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc

        user = await self.user_repo.find_by_email(social_user.email)
        if user:
            updates: dict[str, str] = {}
            if social_user.full_name and social_user.full_name != user.get("full_name"):
                updates["full_name"] = social_user.full_name
            if social_user.profile_image_url and social_user.profile_image_url != user.get("profile_image_url"):
                updates["profile_image_url"] = social_user.profile_image_url
            if updates:
                user = await self.user_repo.update_profile(str(user["_id"]), updates)
        else:
            existing_account = await find_existing_email_async(self.user_repo.collection.database, social_user.email)
            if existing_account:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="This email is already in use by another account.",
                )

            try:
                user = await self.user_repo.create_user(
                    {
                        "full_name": social_user.full_name,
                        "email": social_user.email,
                        "phone": None,
                        "password_hash": "",
                        "auth_provider": social_user.provider,
                        "social_provider_user_id": social_user.provider_user_id,
                        "profile_image_url": social_user.profile_image_url,
                        "points_balance": 0,
                        "is_active": True,
                        "location_enabled": False,
                    }
                )
            except DuplicateKeyError as exc:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=duplicate_contact_conflict_detail(
                        exc,
                        email_detail="This email is already in use by another account.",
                        phone_detail="Phone already exists",
                        default_detail="Email or phone already exists",
                    ),
                ) from exc

        user_id = str(user["_id"])
        return await self._issue_token_pair(user_id)

    async def refresh(self, payload: RefreshTokenRequest) -> TokenPair:
        session = await self.session_collection.find_one({"token": payload.refresh_token})
        if not session_is_active(session, audience="customer"):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

        user_id = str(session.get("subject_id") or "")
        user = await self.user_repo.find_by_id(user_id)
        if not user:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
        await self.session_collection.update_one(
            {"_id": session["_id"]},
            {"$set": {"last_used_at": datetime.now(UTC)}},
        )

        return TokenPair(
            access_token=create_access_token(user_id, audience="customer"),
            refresh_token=payload.refresh_token,
            session_token=payload.refresh_token,
        )

    async def logout(self, payload: RefreshTokenRequest) -> dict[str, str]:
        await self.session_collection.update_one(
            {"token": payload.refresh_token, "audience": "customer", "revoked_at": None},
            {"$set": {"revoked_at": datetime.now(UTC), "last_used_at": datetime.now(UTC)}},
        )
        return {"message": "Logged out successfully"}

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

        full_name = user.get("full_name") or "there"
        await asyncio.to_thread(
            self.email_sender.send_password_reset_code,
            payload.email,
            full_name,
            otp,
            self.settings.otp_expire_minutes,
        )
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

    def _generate_otp(self) -> str:
        return "".join(str(random.randint(0, 9)) for _ in range(self.settings.otp_length))

    async def _issue_token_pair(self, user_id: str) -> TokenPair:
        session_doc = build_session_document(subject_id=user_id, audience="customer")
        await self.session_collection.insert_one(session_doc)
        session_token = str(session_doc["token"])
        return TokenPair(
            access_token=create_access_token(user_id, audience="customer"),
            refresh_token=session_token,
            session_token=session_token,
        )
