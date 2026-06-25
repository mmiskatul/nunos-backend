from fastapi import APIRouter

from app.api.v1.routers.ai import router as ai_router
from app.api.v1.routers.auth import router as auth_router
from app.api.v1.routers.bookings import router as bookings_router
from app.api.v1.routers.dashboard_auth import router as dashboard_auth_router
from app.api.v1.routers.legal import router as legal_router
from app.api.v1.routers.listings import router as listings_router
from app.api.v1.routers.offers import router as offers_router
from app.api.v1.routers.users import router as users_router

# Module routers — vendor
from app.modules.vendor.router import router as vendor_router
from app.modules.vendor.routes_auth import router as vendor_auth_router
from app.modules.vendor.routes_users import router as vendor_users_router

# Module routers — customer
from app.modules.customer.router import router as customer_router
from app.modules.customer.routes_ai_concierge import router as customer_ai_concierge_router

# Module routers — platform admin
from app.modules.platform_admin.router import router as platform_admin_router
from app.modules.platform_admin.routes_auth import router as platform_admin_auth_router
from app.modules.platform_admin.routes_offers import router as platform_admin_offers_router
from app.modules.platform_admin.routes_settings import router as platform_admin_settings_router
from app.modules.platform_admin.routes_support import router as platform_admin_support_router
from app.modules.platform_admin.routes_users import router as platform_admin_users_router
from app.modules.platform_admin.routes_vendors import router as platform_admin_vendors_router

api_router = APIRouter()

# ── Customer auth (register, login, etc.) ──────────────────────────────────
api_router.include_router(auth_router)

# ── Legacy dashboard auth (kept for backwards compat) ──────────────────────
api_router.include_router(dashboard_auth_router)

# ── Customer user profile ──────────────────────────────────────────────────
api_router.include_router(users_router)
api_router.include_router(legal_router)

# ── Customer module (home, restaurants, spas, events, hotels, bookings…) ──
api_router.include_router(customer_ai_concierge_router)
api_router.include_router(customer_router)

# ── Vendor auth ────────────────────────────────────────────────────────────
api_router.include_router(vendor_auth_router)

# ── Vendor portal (dashboard, bookings, menu, rooms, promotions…) ──────────
api_router.include_router(vendor_router)

# ── Vendor users (customers who have booked with this vendor) ──────────────
api_router.include_router(vendor_users_router)

# ── Platform admin auth ────────────────────────────────────────────────────
api_router.include_router(platform_admin_auth_router)

# ── Platform admin live routes ─────────────────────────────────────────────
api_router.include_router(platform_admin_users_router)
api_router.include_router(platform_admin_vendors_router)
api_router.include_router(platform_admin_offers_router)
api_router.include_router(platform_admin_settings_router)
api_router.include_router(platform_admin_support_router)

# ── Platform admin planned stubs (dashboard, offers, billing, support…) ───
api_router.include_router(platform_admin_router)

# ── Listings, bookings, offers (legacy helpers) ────────────────────────────
api_router.include_router(listings_router)
api_router.include_router(bookings_router)
api_router.include_router(offers_router)

# ── AI service ────────────────────────────────────────────────────────────
api_router.include_router(ai_router)
