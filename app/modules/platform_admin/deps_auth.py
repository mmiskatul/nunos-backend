from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import get_settings
from app.db.mongodb import MongoDatabase
from app.modules.platform_admin.repositories_admin import PlatformAdminRepository
from app.modules.platform_admin.repositories_password_reset import AdminPasswordResetRepository
from app.modules.platform_admin.repositories_signup import AdminSignupVerificationRepository
from app.modules.platform_admin.service_auth import PlatformAdminAuthService
from app.providers.email_sender import SMTPEmailSender

admin_bearer_scheme = HTTPBearer(auto_error=False)


def get_db(request: Request) -> MongoDatabase:
    return request.app.state.db  # type: ignore[return-value]


def get_admin_repository(db: MongoDatabase = Depends(get_db)) -> PlatformAdminRepository:
    return PlatformAdminRepository(db.db)


def get_admin_signup_repository(db: MongoDatabase = Depends(get_db)) -> AdminSignupVerificationRepository:
    return AdminSignupVerificationRepository(db.db)


def get_admin_password_reset_repository(db: MongoDatabase = Depends(get_db)) -> AdminPasswordResetRepository:
    return AdminPasswordResetRepository(db.db)


def get_platform_admin_auth_service(
    admin_repo: PlatformAdminRepository = Depends(get_admin_repository),
    signup_repo: AdminSignupVerificationRepository = Depends(get_admin_signup_repository),
    password_reset_repo: AdminPasswordResetRepository = Depends(get_admin_password_reset_repository),
) -> PlatformAdminAuthService:
    return PlatformAdminAuthService(
        admin_repo=admin_repo,
        signup_repo=signup_repo,
        password_reset_repo=password_reset_repo,
        email_sender=SMTPEmailSender(get_settings()),
    )


def get_current_platform_admin(
    credentials: HTTPAuthorizationCredentials | None = Depends(admin_bearer_scheme),
    auth_service: PlatformAdminAuthService = Depends(get_platform_admin_auth_service),
) -> dict:
    if not credentials or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated.")
    return auth_service.get_current_admin_from_token(credentials.credentials)

