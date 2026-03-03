from fastapi import APIRouter, Depends, status

from app.api.deps import get_auth_service, get_current_user
from app.schemas.auth import (
    AuthResponse,
    ForgotPasswordRequest,
    ForgotPasswordResponse,
    LoginRequest,
    MessageResponse,
    ResetPasswordRequest,
    SignupRequest,
    SocialLoginRequest,
    UserPublic,
)
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/signup", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
def signup(payload: SignupRequest, auth_service: AuthService = Depends(get_auth_service)) -> AuthResponse:
    return auth_service.signup(payload)


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
def register(payload: SignupRequest, auth_service: AuthService = Depends(get_auth_service)) -> AuthResponse:
    # Alias for clients still using `/register` from older UI contracts.
    return auth_service.signup(payload)


@router.post("/login", response_model=AuthResponse)
def login(payload: LoginRequest, auth_service: AuthService = Depends(get_auth_service)) -> AuthResponse:
    return auth_service.login(payload)


@router.post("/social-login", response_model=AuthResponse)
def social_login(
    payload: SocialLoginRequest,
    auth_service: AuthService = Depends(get_auth_service),
) -> AuthResponse:
    return auth_service.social_login(payload)


@router.post("/forgot-password/request", response_model=ForgotPasswordResponse)
def request_forgot_password(
    payload: ForgotPasswordRequest,
    auth_service: AuthService = Depends(get_auth_service),
) -> ForgotPasswordResponse:
    return auth_service.request_password_reset(payload)


@router.post("/forgot-password/reset", response_model=MessageResponse)
def reset_forgot_password(
    payload: ResetPasswordRequest,
    auth_service: AuthService = Depends(get_auth_service),
) -> MessageResponse:
    data = auth_service.reset_password(payload)
    return MessageResponse(**data)


@router.get("/me", response_model=UserPublic)
def get_me(current_user: dict = Depends(get_current_user)) -> UserPublic:
    return UserPublic.model_validate(current_user)
