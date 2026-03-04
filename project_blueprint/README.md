# Nunos Full Project Blueprint

This folder contains the full API blueprint derived from the provided UI screens:
- Customer mobile app
- Vendor web dashboard
- Platform admin web panel

## Connection Map (Screen -> API -> Next Screen)

### Customer
1. `Home` -> `GET /api/v1/customer/home` -> `Details/List/Map`
2. `Restaurant/Spa/Event/Hotel list` -> `GET /api/v1/customer/{domain}` -> `Details`
3. `Details` -> `GET /api/v1/customer/{domain}/{id}` -> `Book`
4. `Book (date/time/guests)` -> `GET /api/v1/customer/bookings/availability` + `POST /api/v1/customer/bookings/quote` -> `Summary`
5. `Summary` -> `POST /api/v1/customer/bookings/{id}/confirm` -> `Booking Confirmed`
6. `Search` -> `GET /api/v1/customer/search` + `GET /api/v1/customer/search/recent`
7. `Map` -> `GET /api/v1/customer/map/pins` -> `Venue card` -> `Details`
8. `Plan for me` wizard -> `/api/v1/customer/plan-for-me/sessions/*` -> `Recommended feeds`
9. `Saved` -> `GET/POST/DELETE /api/v1/customer/saved/...`
10. `AI Chat` -> `/api/v1/customer/ai-concierge/sessions/*`
11. `Profile` -> `/api/v1/customer/profile*` + `/api/v1/customer/bookings`

### Vendor
0. `Vendor Onboarding/Auth` -> `/api/v1/vendor/auth/*` (registration code, verify, register, login, forgot password, KYC submit/status)
1. `Dashboard` -> `/api/v1/vendor/dashboard/*`
2. `Booking Management` -> `/api/v1/vendor/booking-management/bookings*`
3. `Menu/Services Upload` -> `/api/v1/vendor/menu-services/*`
4. `Rooms & Services` -> `/api/v1/vendor/rooms-services/rooms*`
5. `Promotions` -> `/api/v1/vendor/promotions*`
6. `Analytics` -> `/api/v1/vendor/analytics/*`
7. `Loyalty` -> `/api/v1/vendor/loyalty/settings`
8. `Reviews` -> `/api/v1/vendor/reviews*`
9. `Settings` -> `/api/v1/vendor/settings/*`

### Platform Admin
1. `Platform Dashboard` -> `/api/v1/platform-admin/dashboard/*`
2. `Users Management` -> `/api/v1/platform-admin/users*`
3. `Vendors Management` -> `/api/v1/platform-admin/vendors*`
4. `Content Moderation` -> `/api/v1/platform-admin/moderation/submissions*`
5. `Offers` -> `/api/v1/platform-admin/offers*`
6. `Billing` -> `/api/v1/platform-admin/billing/*`
7. `Support` -> `/api/v1/platform-admin/support/tickets*`
8. `Settings + Legal` -> `/api/v1/platform-admin/settings/*`

## Folder Mapping (Implemented)

- `app/modules/customer/router.py`
- `app/modules/vendor/router.py`
- `app/modules/platform_admin/router.py`
- `app/modules/schemas.py`

These routers are mounted by `app/api/router.py`.
