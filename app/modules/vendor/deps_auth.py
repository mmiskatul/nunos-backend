from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pymongo.database import Database

from app.api.deps import get_cloudinary_uploader, get_email_sender
from app.core.config import Settings, get_settings
from app.db.mongodb import MongoDatabaseSingleton
from app.modules.vendor.repositories_password_reset import VendorPasswordResetRepository
from app.modules.vendor.repositories_portal import VendorPortalRepository
from app.modules.vendor.repositories_signup import VendorSignupVerificationRepository
from app.modules.vendor.repositories_vendor import VendorRepository
from app.modules.vendor.service_auth import VendorAuthService
from app.modules.vendor.service_portal import VendorPortalService
from app.providers.email_sender import EmailSender

vendor_bearer_scheme = HTTPBearer(auto_error=False)


def get_vendor_db(settings: Settings = Depends(get_settings)) -> Database:
    return MongoDatabaseSingleton.get_instance(settings).db


def get_vendor_repository(db: Database = Depends(get_vendor_db)) -> VendorRepository:
    return VendorRepository(db)


def get_vendor_signup_repository(
    db: Database = Depends(get_vendor_db),
) -> VendorSignupVerificationRepository:
    return VendorSignupVerificationRepository(db)


def get_vendor_password_reset_repository(
    db: Database = Depends(get_vendor_db),
) -> VendorPasswordResetRepository:
    return VendorPasswordResetRepository(db)


def get_vendor_portal_repository(db: Database = Depends(get_vendor_db)) -> VendorPortalRepository:
    return VendorPortalRepository(db)


def get_vendor_auth_service(
    vendor_repo: VendorRepository = Depends(get_vendor_repository),
    signup_repo: VendorSignupVerificationRepository = Depends(get_vendor_signup_repository),
    password_reset_repo: VendorPasswordResetRepository = Depends(get_vendor_password_reset_repository),
    email_sender: EmailSender = Depends(get_email_sender),
    cloudinary_uploader=Depends(get_cloudinary_uploader),
    settings: Settings = Depends(get_settings),
) -> VendorAuthService:
    return VendorAuthService(
        vendor_repo=vendor_repo,
        signup_repo=signup_repo,
        password_reset_repo=password_reset_repo,
        email_sender=email_sender,
        cloudinary_uploader=cloudinary_uploader,
        settings=settings,
    )


def get_vendor_portal_service(
    repo: VendorPortalRepository = Depends(get_vendor_portal_repository),
) -> VendorPortalService:
    return VendorPortalService(repo)


def get_current_vendor(
    credentials: HTTPAuthorizationCredentials | None = Depends(vendor_bearer_scheme),
    auth_service: VendorAuthService = Depends(get_vendor_auth_service),
) -> dict:
    if not credentials or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated.")
    return auth_service.get_current_vendor_from_token(credentials.credentials)
