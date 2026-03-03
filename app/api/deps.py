from fastapi import Depends, Request
from fastapi.security import OAuth2PasswordBearer

from app.db.mongodb import MongoDatabase
from app.providers.social_auth import SocialAuthStrategyFactory
from app.repositories.password_reset_repository import PasswordResetRepository
from app.repositories.user_repository import UserRepository
from app.services.auth_service import AuthService

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


def get_db(request: Request) -> MongoDatabase:
    return request.app.state.db  # type: ignore[return-value]


def get_user_repository(db: MongoDatabase = Depends(get_db)) -> UserRepository:
    return UserRepository(db.db)


def get_password_reset_repository(
    db: MongoDatabase = Depends(get_db),
) -> PasswordResetRepository:
    return PasswordResetRepository(db.db)


def get_auth_service(
    user_repo: UserRepository = Depends(get_user_repository),
    password_reset_repo: PasswordResetRepository = Depends(get_password_reset_repository),
) -> AuthService:
    return AuthService(user_repo, password_reset_repo, SocialAuthStrategyFactory())


def get_current_user(
    token: str = Depends(oauth2_scheme),
    auth_service: AuthService = Depends(get_auth_service),
) -> dict:
    return auth_service.get_current_user_from_token(token)

