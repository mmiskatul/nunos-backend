from fastapi import APIRouter, Depends, File, UploadFile, status

from app.modules.vendor.deps_auth import get_current_vendor, get_vendor_auth_service
from app.modules.vendor.schemas_auth import (
    VendorAuthResponse,
    VendorCodeRequestResponse,
    VendorDocumentUploadResponse,
    VendorForgotPasswordRequest,
    VendorKycStatusResponse,
    VendorKycSubmitRequest,
    VendorLoginRequest,
    VendorMessageResponse,
    VendorRefreshTokenRequest,
    VendorRegistrationFormConfigResponse,
    VendorRegistrationStatusResponse,
    VendorRegisterRequest,
    VendorResetPasswordRequest,
    VendorVerifyCodeResponse,
    VendorVerifyResetCodeRequest,
    VendorVerifySignupCodeRequest,
)
from app.modules.vendor.service_auth import VendorAuthService

router = APIRouter(prefix="/vendor/auth", tags=["Vendor Auth"])


@router.post("/register/request-code", response_model=VendorCodeRequestResponse)
def request_register_code(
    payload: VendorForgotPasswordRequest,
    auth_service: VendorAuthService = Depends(get_vendor_auth_service),
) -> VendorCodeRequestResponse:
    return auth_service.request_register_code(payload)


@router.post("/register/verify-code", response_model=VendorVerifyCodeResponse)
def verify_register_code(
    payload: VendorVerifySignupCodeRequest,
    auth_service: VendorAuthService = Depends(get_vendor_auth_service),
) -> VendorVerifyCodeResponse:
    return auth_service.verify_register_code(payload)


@router.post("/register", response_model=VendorAuthResponse, status_code=status.HTTP_201_CREATED)
def register_vendor(
    payload: VendorRegisterRequest,
    auth_service: VendorAuthService = Depends(get_vendor_auth_service),
) -> VendorAuthResponse:
    return auth_service.register(payload)


@router.get("/registration-form-config", response_model=VendorRegistrationFormConfigResponse)
def get_vendor_registration_form_config(
    auth_service: VendorAuthService = Depends(get_vendor_auth_service),
) -> VendorRegistrationFormConfigResponse:
    return auth_service.get_registration_form_config()


@router.post("/upload-document", response_model=VendorDocumentUploadResponse)
async def upload_vendor_registration_document(
    file: UploadFile = File(...),
    auth_service: VendorAuthService = Depends(get_vendor_auth_service),
) -> VendorDocumentUploadResponse:
    return await auth_service.upload_registration_document(file)


@router.get("/registration-status", response_model=VendorRegistrationStatusResponse)
def get_registration_status(
    email_or_phone: str,
    auth_service: VendorAuthService = Depends(get_vendor_auth_service),
) -> VendorRegistrationStatusResponse:
    return auth_service.get_registration_status(email_or_phone)


@router.post("/login", response_model=VendorAuthResponse)
def vendor_login(
    payload: VendorLoginRequest,
    auth_service: VendorAuthService = Depends(get_vendor_auth_service),
) -> VendorAuthResponse:
    return auth_service.login(payload)


@router.post("/refresh", response_model=VendorAuthResponse)
def vendor_refresh(
    payload: VendorRefreshTokenRequest,
    auth_service: VendorAuthService = Depends(get_vendor_auth_service),
) -> VendorAuthResponse:
    return auth_service.refresh(payload)


@router.post("/logout", response_model=VendorMessageResponse)
def vendor_logout(
    payload: VendorRefreshTokenRequest,
    auth_service: VendorAuthService = Depends(get_vendor_auth_service),
) -> VendorMessageResponse:
    return auth_service.logout(payload)


@router.post("/forgot-password/request", response_model=VendorCodeRequestResponse)
def request_forgot_password_code(
    payload: VendorForgotPasswordRequest,
    auth_service: VendorAuthService = Depends(get_vendor_auth_service),
) -> VendorCodeRequestResponse:
    return auth_service.request_forgot_password_code(payload)


@router.post("/forgot-password/verify-code", response_model=VendorVerifyCodeResponse)
def verify_forgot_password_code(
    payload: VendorVerifyResetCodeRequest,
    auth_service: VendorAuthService = Depends(get_vendor_auth_service),
) -> VendorVerifyCodeResponse:
    return auth_service.verify_forgot_password_code(payload)


@router.post("/forgot-password/reset", response_model=VendorMessageResponse)
def reset_forgot_password(
    payload: VendorResetPasswordRequest,
    auth_service: VendorAuthService = Depends(get_vendor_auth_service),
) -> VendorMessageResponse:
    return auth_service.reset_password(payload)


@router.post("/kyc/submit", response_model=VendorMessageResponse)
def submit_vendor_kyc(
    payload: VendorKycSubmitRequest,
    current_vendor: dict = Depends(get_current_vendor),
    auth_service: VendorAuthService = Depends(get_vendor_auth_service),
) -> VendorMessageResponse:
    return auth_service.submit_kyc(current_vendor["id"], payload)


@router.get("/kyc/status", response_model=VendorKycStatusResponse)
def get_vendor_kyc_status(
    current_vendor: dict = Depends(get_current_vendor),
    auth_service: VendorAuthService = Depends(get_vendor_auth_service),
) -> VendorKycStatusResponse:
    return auth_service.get_kyc_status(current_vendor["id"])
