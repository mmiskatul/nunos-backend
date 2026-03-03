from app.core.config import get_settings
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.db.mongodb import MongoDatabase
from app.providers.email_sender import SMTPEmailSender
from app.providers.social_auth import SocialAuthStrategyFactory
from app.repositories.password_reset_repository import PasswordResetRepository
from app.repositories.signup_verification_repository import SignupVerificationRepository
from app.repositories.user_repository import UserRepository
from app.services.auth_service import AuthService

bearer_scheme = HTTPBearer(auto_error=False)


def get_db(request: Request) -> MongoDatabase:
    return request.app.state.db  # type: ignore[return-value]


def get_user_repository(db: MongoDatabase = Depends(get_db)) -> UserRepository:
    return UserRepository(db.db)


def get_password_reset_repository(
    db: MongoDatabase = Depends(get_db),
) -> PasswordResetRepository:
    return PasswordResetRepository(db.db)


def get_signup_verification_repository(
    db: MongoDatabase = Depends(get_db),
) -> SignupVerificationRepository:
    return SignupVerificationRepository(db.db)


def get_auth_service(
    user_repo: UserRepository = Depends(get_user_repository),
    password_reset_repo: PasswordResetRepository = Depends(get_password_reset_repository),
    signup_verification_repo: SignupVerificationRepository = Depends(get_signup_verification_repository),
) -> AuthService:
    return AuthService(
        user_repo,
        password_reset_repo,
        signup_verification_repo,
        SocialAuthStrategyFactory(),
        SMTPEmailSender(get_settings()),
    )


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    auth_service: AuthService = Depends(get_auth_service),
) -> dict:
    if not credentials or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated.")
    return auth_service.get_current_user_from_token(credentials.credentials)
