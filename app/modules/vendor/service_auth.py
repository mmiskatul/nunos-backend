from datetime import UTC, datetime
from typing import Any

from bson.errors import InvalidId
from fastapi import HTTPException, UploadFile, status
from pymongo.errors import DuplicateKeyError

from app.core.account_lookup import find_existing_email_sync, find_existing_phone_sync
from app.core.config import get_settings
from app.core.contact import parse_email_or_phone
from app.core.mongo_errors import duplicate_contact_conflict_detail
from app.core.session_tokens import SESSION_COLLECTION, build_session_document, session_is_active
from app.core.security import create_access_token, decode_token, hash_password, verify_password
from app.modules.vendor.repositories_password_reset import VendorPasswordResetRepository
from app.modules.vendor.repositories_signup import VendorSignupVerificationRepository
from app.modules.vendor.repositories_vendor import VendorRepository
from app.modules.vendor.schemas_auth import (
    VendorAuthResponse,
    VendorCodeRequestResponse,
    VendorDocumentUploadResponse,
    VendorForgotPasswordRequest,
    VendorKycStatusResponse,
    VendorKycSubmitRequest,
    VendorLoginRequest,
    VendorMessageResponse,
    VendorPublic,
    VendorRefreshTokenRequest,
    VendorRegistrationStatusResponse,
    VendorRegisterRequest,
    VendorResetPasswordRequest,
    VendorVerifyCodeResponse,
    VendorVerifyResetCodeRequest,
    VendorVerifySignupCodeRequest,
)
from app.providers.cloudinary_uploader import CloudinaryUploader
from app.providers.email_sender import EmailSender


def _existing_vendor_conflict_detail(vendor: dict[str, Any]) -> str:
    status_value = str(vendor.get("status") or "").lower()

    if status_value == "pending_approval":
        return "A service provider account for this email already exists and is pending admin approval."
    if status_value == "approved":
        return "This email is already registered as a service provider."
    if status_value == "rejected":
        return "This service provider account was rejected. Contact support before registering again."
    if status_value == "blocked":
        return "This service provider account is blocked. Contact support."

    return "This email is already in use by another account."


class VendorAuthService:
    """Service layer for vendor onboarding and authentication."""

    def __init__(
        self,
        vendor_repo: VendorRepository,
        signup_repo: VendorSignupVerificationRepository,
        password_reset_repo: VendorPasswordResetRepository,
        email_sender: EmailSender,
        cloudinary_uploader: CloudinaryUploader,
    ):
        self.vendor_repo = vendor_repo
        self.signup_repo = signup_repo
        self.password_reset_repo = password_reset_repo
        self.email_sender = email_sender
        self.settings = get_settings()
        self.cloudinary_uploader = cloudinary_uploader
        self.session_collection = self.vendor_repo.collection.database[SESSION_COLLECTION]

    def request_register_code(self, payload: VendorForgotPasswordRequest) -> VendorCodeRequestResponse:
        email, _ = parse_email_or_phone(payload.email_or_phone)
        if not email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Vendor registration requires email verification.",
            )

        existing = find_existing_email_sync(self.vendor_repo.collection.database, email)
        if existing:
            if existing.get("collection") == "vendors" and isinstance(existing.get("document"), dict):
                detail = _existing_vendor_conflict_detail(existing["document"])
            else:
                detail = "This email is already in use by another account."
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=detail,
            )

        code = self.signup_repo.create_validation_code(
            email=email,
            code_length=self.settings.signup_verification_code_length,
            expires_in_minutes=self.settings.signup_verification_code_expire_minutes,
        )
        self.email_sender.send_signup_verification_code(
            recipient_email=email,
            full_name="vendor",
            code=code,
            expires_in=self.settings.signup_verification_code_expire_minutes,
        )
        if self.settings.debug_return_signup_code:
            return VendorCodeRequestResponse(
                message="Verification code sent to email (debug mode includes code).",
                validation_code=code,
            )
        return VendorCodeRequestResponse(message="Verification code sent to email.")

    def verify_register_code(self, payload: VendorVerifySignupCodeRequest) -> VendorVerifyCodeResponse:
        email, _ = parse_email_or_phone(payload.email_or_phone)
        if not email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Vendor registration requires email verification.",
            )

        is_valid = self.signup_repo.validate_and_consume_code(email, payload.validation_code)
        if not is_valid:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired validation code.")

        signup_token = self.signup_repo.create_signup_token(
            email=email, expires_in_minutes=self.settings.signup_verification_token_expire_minutes
        )
        return VendorVerifyCodeResponse(message="Verification successful.", signup_token=signup_token)

    def register(self, payload: VendorRegisterRequest) -> VendorAuthResponse:
        email, phone_from_contact = parse_email_or_phone(payload.email_or_phone)
        if not email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Vendor registration requires verified email.",
            )

        explicit_phone = None
        if payload.phone:
            possible_email, parsed_phone = parse_email_or_phone(payload.phone)
            if possible_email:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="phone must be a phone number.")
            explicit_phone = parsed_phone

        valid_token = self.signup_repo.get_valid_signup_token(email=email, token=payload.signup_token)
        if not valid_token:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired signup token.")

        if find_existing_email_sync(self.vendor_repo.collection.database, email):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This email is already in use by another account.",
            )

        phone = explicit_phone or phone_from_contact
        if phone and find_existing_phone_sync(self.vendor_repo.collection.database, phone):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Phone already exists")

        categories = payload.categories or [payload.category]
        primary_category = categories[0]

        try:
            vendor = self.vendor_repo.create_vendor(
                {
                    "business_name": payload.business_name,
                    "owner_full_name": payload.owner_full_name,
                    "email": email,
                    "phone": phone,
                    "password_hash": hash_password(payload.password),
                    "role": "vendor",
                    "status": "pending_approval",
                    "terms_accepted": payload.terms_accepted,
                    "terms_accepted_at": datetime.now().isoformat(),
                    "kyc_status": "pending_review",
                    "kyc_submitted_at": datetime.now().isoformat(),
                    "category": primary_category,
                    "categories": categories,
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

        self.vendor_repo.create_vendor_sections(
            vendor_id=vendor["id"],
            profile_payload={
                "business_name": payload.business_name,
                "owner_full_name": payload.owner_full_name,
                "email": email,
                "phone": phone,
                "category": primary_category,
                "categories": categories,
            },
            business_payload={
                "address": payload.address,
                "city": payload.city,
                "website": payload.website,
                "business_description": payload.business_description,
                "categories": categories,
                "event_types": payload.event_types,
                "venue_capacity": payload.venue_capacity,
                "ticket_pricing_type": payload.ticket_pricing_type,
                "event_location_preference": payload.event_location_preference,
                "equipment_availability": payload.equipment_availability,
            },
            verification_payload={
                "category": primary_category,
                "categories": categories,
                "trade_license_number": payload.trade_license_number,
                "trade_license_document_url": payload.trade_license_document_url,
                "owner_manager_id_document_url": payload.owner_manager_id_document_url,
            },
        )

        self.signup_repo.mark_signup_token_used(payload.signup_token)
        return self._build_auth_response(vendor)

    async def upload_registration_document(
        self,
        file: UploadFile,
        *,
        folder_suffix: str = "vendor-documents",
    ) -> VendorDocumentUploadResponse:
        secure_url = await self.cloudinary_uploader.upload_vendor_document(
            file,
            folder_suffix=folder_suffix,
        )
        return VendorDocumentUploadResponse(
            message="Document uploaded successfully.",
            url=secure_url,
        )

    def login(self, payload: VendorLoginRequest) -> VendorAuthResponse:
        vendor = self._get_by_contact(payload.email_or_phone)
        if not vendor or not vendor.get("password_hash"):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials.")

        if not verify_password(payload.password, vendor["password_hash"]):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials.")
        if (vendor.get("role") or "") != "vendor":
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials.")

        account_status = (vendor.get("status") or "").lower()
        if account_status != "approved":
            if account_status == "blocked":
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Your vendor account was blocked. Contact support.",
                )
            if account_status == "rejected":
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Your vendor account was rejected. Contact support.",
                )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Your vendor account is pending admin approval.",
            )

        return self._build_auth_response(vendor)

    def refresh(self, payload: VendorRefreshTokenRequest) -> VendorAuthResponse:
        session = self.session_collection.find_one({"token": payload.refresh_token})
        if not session_is_active(session, audience="vendor"):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token.")

        vendor_id = str(session.get("subject_id") or "")
        if not vendor_id:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload.")

        try:
            vendor = self.vendor_repo.get_by_id(vendor_id)
        except InvalidId as exc:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token subject.") from exc
        if not vendor:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Vendor not found.")
        if (vendor.get("role") or "") != "vendor":
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token subject.")

        account_status = (vendor.get("status") or "").lower()
        if account_status != "approved":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Vendor account is not active.")

        self.session_collection.update_one(
            {"_id": session["_id"]},
            {"$set": {"last_used_at": datetime.now(UTC)}},
        )

        return VendorAuthResponse(
            access_token=create_access_token(vendor["id"], audience="vendor", role="vendor"),
            refresh_token=payload.refresh_token,
            session_token=payload.refresh_token,
            vendor=VendorPublic.model_validate(vendor),
        )

    def logout(self, payload: VendorRefreshTokenRequest) -> VendorMessageResponse:
        self.session_collection.update_one(
            {"token": payload.refresh_token, "audience": "vendor", "revoked_at": None},
            {"$set": {"revoked_at": datetime.now(UTC), "last_used_at": datetime.now(UTC)}},
        )
        return VendorMessageResponse(message="Logged out successfully.")

    def request_forgot_password_code(self, payload: VendorForgotPasswordRequest) -> VendorCodeRequestResponse:
        vendor = self._get_by_contact(payload.email_or_phone)
        if not vendor or not vendor.get("email"):
            return VendorCodeRequestResponse(message="If the account exists, a validation code has been sent.")

        code = self.password_reset_repo.create_validation_code(
            vendor_id=vendor["id"],
            code_length=self.settings.password_reset_code_length,
            expires_in_minutes=self.settings.password_reset_code_expire_minutes,
        )
        self.email_sender.send_password_reset_code(
            recipient_email=vendor["email"],
            full_name=vendor["owner_full_name"],
            code=code,
            expires_in=self.settings.password_reset_code_expire_minutes,
        )
        if self.settings.debug_return_reset_code:
            return VendorCodeRequestResponse(
                message="Validation code sent (debug mode includes code).",
                validation_code=code,
            )
        return VendorCodeRequestResponse(message="If the account exists, a validation code has been sent.")

    def verify_forgot_password_code(self, payload: VendorVerifyResetCodeRequest) -> VendorVerifyCodeResponse:
        vendor = self._get_by_contact(payload.email_or_phone)
        if not vendor:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired validation code.")

        is_valid = self.password_reset_repo.validate_and_consume_code(vendor["id"], payload.validation_code)
        if not is_valid:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired validation code.")

        reset_token = self.password_reset_repo.create_reset_token(
            vendor_id=vendor["id"], expires_in_minutes=self.settings.password_reset_token_expire_minutes
        )
        return VendorVerifyCodeResponse(message="Validation code verified.", reset_token=reset_token)

    def reset_password(self, payload: VendorResetPasswordRequest) -> VendorMessageResponse:
        token_doc = self.password_reset_repo.get_valid_reset_token(payload.reset_token)
        if not token_doc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired reset token.")

        vendor_id = str(token_doc["vendor_id"])
        self.vendor_repo.update_password_hash(vendor_id, hash_password(payload.new_password))
        self.password_reset_repo.mark_reset_token_used(payload.reset_token)
        return VendorMessageResponse(message="Password has been reset successfully.")

    def submit_kyc(self, vendor_id: str, payload: VendorKycSubmitRequest) -> VendorMessageResponse:
        self.vendor_repo.upsert_kyc(vendor_id, payload.model_dump())
        return VendorMessageResponse(message="KYC submitted successfully. Status is now pending_review.")

    def get_kyc_status(self, vendor_id: str) -> VendorKycStatusResponse:
        status_payload = self.vendor_repo.get_kyc_status(vendor_id)
        if not status_payload:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vendor not found.")

        return VendorKycStatusResponse(
            kyc_status=status_payload.get("kyc_status", "not_submitted"),
            submitted_at=self._to_iso(status_payload.get("submitted_at")),
            reviewed_at=self._to_iso(status_payload.get("reviewed_at")),
            rejection_reason=status_payload.get("rejection_reason"),
        )

    def get_current_vendor_from_token(self, token: str) -> dict[str, Any]:
        try:
            payload = decode_token(
                token,
                expected_type="access",
                expected_audience="vendor",
                expected_role="vendor",
            )
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid access token.") from exc
        vendor_id = payload.get("sub")
        if not vendor_id:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload.")

        try:
            vendor = self.vendor_repo.get_by_id(vendor_id)
        except InvalidId as exc:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token subject.") from exc
        if not vendor:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Vendor not found.")
        if (vendor.get("role") or "") != "vendor":
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token subject.")
        return vendor

    def get_registration_status(self, email_or_phone: str) -> VendorRegistrationStatusResponse:
        vendor = self._get_by_contact(email_or_phone)
        if not vendor:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vendor not found.")
        return VendorRegistrationStatusResponse(
            status=vendor.get("status", "pending_approval"),
            kyc_status=vendor.get("kyc_status", "not_submitted"),
            rejection_reason=vendor.get("kyc_rejection_reason"),
        )

    def _build_auth_response(self, vendor: dict[str, Any]) -> VendorAuthResponse:
        access_token = create_access_token(vendor["id"], audience="vendor", role="vendor")
        session_doc = build_session_document(subject_id=vendor["id"], audience="vendor", role="vendor")
        self.session_collection.insert_one(session_doc)
        refresh_token = str(session_doc["token"])
        return VendorAuthResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            session_token=refresh_token,
            vendor=VendorPublic.model_validate(vendor),
        )

    def _get_by_contact(self, email_or_phone: str) -> dict[str, Any] | None:
        email, phone = parse_email_or_phone(email_or_phone)
        if email:
            return self.vendor_repo.get_by_email(email)
        return self.vendor_repo.get_by_phone(phone or "")

    @staticmethod
    def _to_iso(value: Any) -> str | None:
        if isinstance(value, datetime):
            return value.isoformat()
        return None
