from fastapi import APIRouter

from app.api.routes import auth, users
from app.modules.customer import router as customer_router
from app.modules.platform_admin import routes_auth as platform_admin_auth_router
from app.modules.platform_admin import router as platform_admin_router
from app.modules.platform_admin import routes_users as platform_admin_users_live_router
from app.modules.platform_admin import routes_vendors as platform_admin_vendors_live_router
from app.modules.vendor import routes_auth as vendor_auth_router
from app.modules.vendor import router as vendor_router

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(vendor_auth_router.router)
api_router.include_router(platform_admin_auth_router.router)
api_router.include_router(customer_router.router)
api_router.include_router(vendor_router.router)
api_router.include_router(platform_admin_users_live_router.router)
api_router.include_router(platform_admin_vendors_live_router.router)
api_router.include_router(platform_admin_router.router)
