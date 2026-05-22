from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from app.ai.client import OpenAILLMClient, StubLLMClient
from app.core.config import Settings, get_settings
from app.core.security import decode_token
from app.db.mongo import get_database
from app.providers.cloudinary_uploader import CloudinaryUploader
from app.providers.email_sender import EmailSender, SMTPEmailSender
from app.repositories.booking_repository import BookingRepository
from app.repositories.favorite_repository import FavoriteRepository
from app.repositories.listing_repository import ListingRepository
from app.repositories.offer_repository import OfferRepository
from app.repositories.otp_repository import OTPRepository
from app.repositories.pending_signup_repository import PendingSignupRepository
from app.repositories.platform_admin_repository import PlatformAdminRepository
from app.repositories.review_repository import ReviewRepository
from app.repositories.user_repository import UserRepository
from app.services.ai_service import AIPlannerService
from app.services.auth_service import AuthService
from app.services.booking_service import BookingService
from app.services.bookings.factory import BookingStrategyFactory
from app.services.dashboard_auth_service import DashboardAuthService
from app.services.listing_service import ListingService
from app.services.loyalty_service import LoyaltyService
from app.services.offer_service import OfferService


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


def get_user_repo(db=Depends(get_database)) -> UserRepository:
    return UserRepository(db)


def get_otp_repo(db=Depends(get_database)) -> OTPRepository:
    return OTPRepository(db)


def get_pending_signup_repo(db=Depends(get_database)) -> PendingSignupRepository:
    return PendingSignupRepository(db)


def get_email_sender(settings: Settings = Depends(get_settings)) -> EmailSender:
    return SMTPEmailSender(settings)


def get_cloudinary_uploader(settings: Settings = Depends(get_settings)) -> CloudinaryUploader:
    return CloudinaryUploader(settings)


def get_platform_admin_repo(db=Depends(get_database)) -> PlatformAdminRepository:
    return PlatformAdminRepository(db)


def get_auth_service(
    user_repo: UserRepository = Depends(get_user_repo),
    otp_repo: OTPRepository = Depends(get_otp_repo),
    pending_signup_repo: PendingSignupRepository = Depends(get_pending_signup_repo),
    email_sender: EmailSender = Depends(get_email_sender),
    settings: Settings = Depends(get_settings),
) -> AuthService:
    return AuthService(user_repo, otp_repo, pending_signup_repo, email_sender, settings)


def get_dashboard_auth_service(
    admin_repo: PlatformAdminRepository = Depends(get_platform_admin_repo),
    otp_repo: OTPRepository = Depends(get_otp_repo),
    email_sender: EmailSender = Depends(get_email_sender),
) -> DashboardAuthService:
    return DashboardAuthService(admin_repo, otp_repo, email_sender)


def get_listing_repo(db=Depends(get_database)) -> ListingRepository:
    return ListingRepository(db)


def get_review_repo(db=Depends(get_database)) -> ReviewRepository:
    return ReviewRepository(db)


def get_favorite_repo(db=Depends(get_database)) -> FavoriteRepository:
    return FavoriteRepository(db)


def get_offer_repo(db=Depends(get_database)) -> OfferRepository:
    return OfferRepository(db)


def get_booking_repo(db=Depends(get_database)) -> BookingRepository:
    return BookingRepository(db)


def get_listing_service(
    listing_repo: ListingRepository = Depends(get_listing_repo),
    review_repo: ReviewRepository = Depends(get_review_repo),
    favorite_repo: FavoriteRepository = Depends(get_favorite_repo),
) -> ListingService:
    return ListingService(listing_repo, review_repo, favorite_repo)


def get_offer_service(offer_repo: OfferRepository = Depends(get_offer_repo)) -> OfferService:
    return OfferService(offer_repo)


def get_loyalty_service(user_repo: UserRepository = Depends(get_user_repo)) -> LoyaltyService:
    return LoyaltyService(user_repo)


def get_booking_service(
    booking_repo: BookingRepository = Depends(get_booking_repo),
    listing_repo: ListingRepository = Depends(get_listing_repo),
    user_repo: UserRepository = Depends(get_user_repo),
    settings: Settings = Depends(get_settings),
) -> BookingService:
    return BookingService(booking_repo, listing_repo, user_repo, BookingStrategyFactory(), settings)


def get_ai_service(
    listing_repo: ListingRepository = Depends(get_listing_repo),
    settings: Settings = Depends(get_settings),
) -> AIPlannerService:
    llm_client = OpenAILLMClient(settings) if settings.openai_api_key else StubLLMClient()
    return AIPlannerService(listing_repo, llm_client)


async def get_current_user_id(
    token: str = Depends(oauth2_scheme),
    user_repo: UserRepository = Depends(get_user_repo),
) -> str:
    try:
        payload = decode_token(token, expected_type="access")
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid access token") from exc

    user_id = payload.get("sub")
    user = await user_repo.find_by_id(user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return str(user["_id"])


# Alias used by customer module router — returns {"id": user_id} dict
async def get_current_user(user_id: str = Depends(get_current_user_id)) -> dict:
    return {"id": user_id}

# Alias for direct DB access (raw AsyncIOMotorDatabase)
get_db = get_database
