from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import get_settings
from app.db.mongodb import MongoDatabase
from app.modules.vendor.repositories_password_reset import VendorPasswordResetRepository
from app.modules.vendor.repositories_signup import VendorSignupVerificationRepository
from app.modules.vendor.repositories_vendor import VendorRepository
from app.modules.vendor.service_auth import VendorAuthService
from app.providers.email_sender import SMTPEmailSender

vendor_bearer_scheme = HTTPBearer(auto_error=False)


def get_db(request: Request) -> MongoDatabase:
    return request.app.state.db  # type: ignore[return-value]


def get_vendor_repository(db: MongoDatabase = Depends(get_db)) -> VendorRepository:
    return VendorRepository(db.db)


def get_vendor_signup_repository(
    db: MongoDatabase = Depends(get_db),
) -> VendorSignupVerificationRepository:
    return VendorSignupVerificationRepository(db.db)


def get_vendor_password_reset_repository(
    db: MongoDatabase = Depends(get_db),
) -> VendorPasswordResetRepository:
    return VendorPasswordResetRepository(db.db)


def get_vendor_auth_service(
    vendor_repo: VendorRepository = Depends(get_vendor_repository),
    signup_repo: VendorSignupVerificationRepository = Depends(get_vendor_signup_repository),
    password_reset_repo: VendorPasswordResetRepository = Depends(get_vendor_password_reset_repository),
) -> VendorAuthService:
    return VendorAuthService(
        vendor_repo=vendor_repo,
        signup_repo=signup_repo,
        password_reset_repo=password_reset_repo,
        email_sender=SMTPEmailSender(get_settings()),
    )


def get_current_vendor(
    credentials: HTTPAuthorizationCredentials | None = Depends(vendor_bearer_scheme),
    auth_service: VendorAuthService = Depends(get_vendor_auth_service),
) -> dict:
    if not credentials or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated.")
    return auth_service.get_current_vendor_from_token(credentials.credentials)

