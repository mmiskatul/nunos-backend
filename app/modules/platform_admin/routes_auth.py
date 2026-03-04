from fastapi import APIRouter, Depends, status

from app.modules.platform_admin.deps_auth import get_current_platform_admin, get_platform_admin_auth_service
from app.modules.platform_admin.schemas_auth import (
    AdminAuthResponse,
    AdminCodeResponse,
    AdminForgotPasswordRequest,
    AdminLoginRequest,
    AdminMessageResponse,
    AdminPublic,
    AdminRegisterCodeRequest,
    AdminRegisterRequest,
    AdminResetPasswordRequest,
    AdminVerifyCodeResponse,
    AdminVerifyRegisterCodeRequest,
    AdminVerifyResetCodeRequest,
)
from app.modules.platform_admin.service_auth import PlatformAdminAuthService

router = APIRouter(prefix="/platform-admin/auth", tags=["Platform Admin Auth"])


@router.post("/register/request-code", response_model=AdminCodeResponse)
def request_register_code(
    payload: AdminRegisterCodeRequest,
    auth_service: PlatformAdminAuthService = Depends(get_platform_admin_auth_service),
) -> AdminCodeResponse:
    return auth_service.request_register_code(payload)


@router.post("/register/verify-code", response_model=AdminVerifyCodeResponse)
def verify_register_code(
    payload: AdminVerifyRegisterCodeRequest,
    auth_service: PlatformAdminAuthService = Depends(get_platform_admin_auth_service),
) -> AdminVerifyCodeResponse:
    return auth_service.verify_register_code(payload)


@router.post("/register", response_model=AdminAuthResponse, status_code=status.HTTP_201_CREATED)
def register_admin(
    payload: AdminRegisterRequest,
    auth_service: PlatformAdminAuthService = Depends(get_platform_admin_auth_service),
) -> AdminAuthResponse:
    return auth_service.register(payload)


@router.post("/login", response_model=AdminAuthResponse)
def login_admin(
    payload: AdminLoginRequest,
    auth_service: PlatformAdminAuthService = Depends(get_platform_admin_auth_service),
) -> AdminAuthResponse:
    return auth_service.login(payload)


@router.post("/forgot-password/request", response_model=AdminCodeResponse)
def request_forgot_password_code(
    payload: AdminForgotPasswordRequest,
    auth_service: PlatformAdminAuthService = Depends(get_platform_admin_auth_service),
) -> AdminCodeResponse:
    return auth_service.request_forgot_password_code(payload)


@router.post("/forgot-password/verify-code", response_model=AdminVerifyCodeResponse)
def verify_forgot_password_code(
    payload: AdminVerifyResetCodeRequest,
    auth_service: PlatformAdminAuthService = Depends(get_platform_admin_auth_service),
) -> AdminVerifyCodeResponse:
    return auth_service.verify_forgot_password_code(payload)


@router.post("/forgot-password/reset", response_model=AdminMessageResponse)
def reset_password(
    payload: AdminResetPasswordRequest,
    auth_service: PlatformAdminAuthService = Depends(get_platform_admin_auth_service),
) -> AdminMessageResponse:
    return auth_service.reset_password(payload)


@router.get("/me", response_model=AdminPublic)
def get_me(current_admin: dict = Depends(get_current_platform_admin)) -> AdminPublic:
    return AdminPublic.model_validate(current_admin)

