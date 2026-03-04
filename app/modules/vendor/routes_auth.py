from fastapi import APIRouter, Depends, status

from app.modules.vendor.deps_auth import get_current_vendor, get_vendor_auth_service
from app.modules.vendor.schemas_auth import (
    VendorAuthResponse,
    VendorCodeRequestResponse,
    VendorForgotPasswordRequest,
    VendorKycStatusResponse,
    VendorKycSubmitRequest,
    VendorLoginRequest,
    VendorMessageResponse,
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


@router.post("/login", response_model=VendorAuthResponse)
def vendor_login(
    payload: VendorLoginRequest,
    auth_service: VendorAuthService = Depends(get_vendor_auth_service),
) -> VendorAuthResponse:
    return auth_service.login(payload)


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

