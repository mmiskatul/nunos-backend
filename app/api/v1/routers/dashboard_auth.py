from fastapi import APIRouter, Depends

from app.api.deps import get_dashboard_auth_service
from app.core.responses import envelope
from app.models.dashboard_auth import (
    DashboardAuthResponse,
    DashboardForgotPasswordRequest,
    DashboardLoginRequest,
    DashboardResetPasswordRequest,
    DashboardVerifyResetCodeRequest,
)
from app.services.dashboard_auth_service import DashboardAuthService

router = APIRouter(prefix="/dashboard/auth", tags=["Dashboard Auth"])


@router.post("/login")
async def login(payload: DashboardLoginRequest, service: DashboardAuthService = Depends(get_dashboard_auth_service)):
    result: DashboardAuthResponse = await service.login(payload)
    return envelope(result.model_dump())


@router.post("/forgot-password/request")
async def forgot_password_request(
    payload: DashboardForgotPasswordRequest, service: DashboardAuthService = Depends(get_dashboard_auth_service)
):
    result = await service.request_forgot_password(payload)
    return envelope(result)


@router.post("/forgot-password/verify-code")
async def forgot_password_verify(
    payload: DashboardVerifyResetCodeRequest, service: DashboardAuthService = Depends(get_dashboard_auth_service)
):
    result = await service.verify_reset_code(payload)
    return envelope(result)


@router.post("/forgot-password/reset")
async def forgot_password_reset(
    payload: DashboardResetPasswordRequest, service: DashboardAuthService = Depends(get_dashboard_auth_service)
):
    result = await service.reset_password(payload)
    return envelope(result)
