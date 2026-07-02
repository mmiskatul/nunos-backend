from fastapi import APIRouter, Depends

from app.api.deps import get_auth_service
from app.core.responses import envelope
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
    VerifyOtpRequest,
)
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/register")
async def register(payload: UserCreateRequest, service: AuthService = Depends(get_auth_service)):
    result: RegistrationResponse = await service.register(payload)
    return envelope(result.model_dump())


@router.post("/verify-email")
async def verify_email(payload: VerifyEmailRequest, service: AuthService = Depends(get_auth_service)):
    token_pair: TokenPair = await service.verify_email(payload)
    return envelope(token_pair.model_dump())


@router.post("/login")
async def login(payload: LoginRequest, service: AuthService = Depends(get_auth_service)):
    token_pair: TokenPair = await service.login(payload)
    return envelope(token_pair.model_dump())


@router.post("/social-login")
async def social_login(payload: SocialLoginRequest, service: AuthService = Depends(get_auth_service)):
    token_pair: TokenPair = await service.social_login(payload)
    return envelope(token_pair.model_dump())


@router.post("/refresh")
async def refresh(payload: RefreshTokenRequest, service: AuthService = Depends(get_auth_service)):
    token_pair = await service.refresh(payload)
    return envelope(token_pair.model_dump())


@router.post("/logout")
async def logout(payload: RefreshTokenRequest, service: AuthService = Depends(get_auth_service)):
    result = await service.logout(payload)
    return envelope(result)


@router.post("/forgot-password")
async def forgot_password(payload: ForgotPasswordRequest, service: AuthService = Depends(get_auth_service)):
    result = await service.forgot_password(payload)
    return envelope(result)


@router.post("/verify-otp")
async def verify_otp(payload: VerifyOtpRequest, service: AuthService = Depends(get_auth_service)):
    result = await service.verify_otp(payload.email, payload.otp)
    return envelope(result)


@router.post("/reset-password")
async def reset_password(payload: ResetPasswordRequest, service: AuthService = Depends(get_auth_service)):
    result = await service.reset_password(payload)
    return envelope(result)
