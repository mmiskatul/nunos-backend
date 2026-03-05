from fastapi import APIRouter

from app.api.v1.routers.ai import router as ai_router
from app.api.v1.routers.auth import router as auth_router
from app.api.v1.routers.bookings import router as bookings_router
from app.api.v1.routers.listings import router as listings_router
from app.api.v1.routers.offers import router as offers_router
from app.api.v1.routers.users import router as users_router

api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(users_router)
api_router.include_router(listings_router)
api_router.include_router(bookings_router)
api_router.include_router(offers_router)
api_router.include_router(ai_router)
