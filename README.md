# Nunos Backend (FastAPI + MongoDB)

Backend API scaffolding based on the provided **Login** and **Sign Up** UI screens.

## Tech
- FastAPI
- Pydantic
- MongoDB (PyMongo)

## Architecture
- Repository Pattern: `app/repositories/*`
- Service Layer: `app/services/auth_service.py`
- Strategy + Factory Pattern (social login providers): `app/providers/social_auth.py`
- Singleton Pattern (Mongo client): `app/db/mongodb.py`
- Full feature module routers:
  - `app/modules/customer/router.py`
  - `app/modules/vendor/router.py`
  - `app/modules/platform_admin/router.py`

## Run
```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
uvicorn app.main:app --reload
```

## UI-to-Endpoint Mapping
- Login form:
  - `POST /api/v1/auth/login`
  - `POST /api/v1/auth/forgot-password/request`
  - `POST /api/v1/auth/forgot-password/verify-code`
  - `POST /api/v1/auth/forgot-password/reset`
  - `POST /api/v1/auth/social-login` (Google / Apple)
- Sign up form:
  - `POST /api/v1/auth/signup/request-code`
  - `POST /api/v1/auth/signup/verify-code`
  - `POST /api/v1/auth/signup`
  - `PATCH /api/v1/users/me/location` (enable location toggle)
- Common authenticated user:
  - `GET /api/v1/auth/me`
  - `PATCH /api/v1/users/me/location`

## Vendor Auth Endpoints
- `POST /api/v1/vendor/auth/register/request-code`
- `POST /api/v1/vendor/auth/register/verify-code`
- `POST /api/v1/vendor/auth/register`
- `POST /api/v1/vendor/auth/login`
- `POST /api/v1/vendor/auth/forgot-password/request`
- `POST /api/v1/vendor/auth/forgot-password/verify-code`
- `POST /api/v1/vendor/auth/forgot-password/reset`
- `POST /api/v1/vendor/auth/kyc/submit`
- `GET /api/v1/vendor/auth/kyc/status`

`POST /api/v1/vendor/auth/register` now requires business registration + verification fields from vendor onboarding UI:
- `address`, `city`, `website`, `business_description`
- `trade_license_number`
- `trade_license_document_url`
- `owner_manager_id_document_url`
- `terms_accepted=true`

## Notes
- Social login strategy is wired for extension. Replace the development token parser in
  `app/providers/social_auth.py` with real Google/Apple token verification.
- Password reset flow now uses an email validation code:
  1. request code
  2. verify code (returns reset token)
  3. reset password using that token
- Signup now also requires email validation:
  1. request signup code
  2. verify signup code (returns signup token)
  3. call signup with `signup_token`
- Configure SMTP in `.env` (`SMTP_*` fields) so validation codes can be sent by email.
- If you add more UI screens, follow the same module split:
  - request/response models in `app/schemas`
  - business rules in `app/services`
  - DB access in `app/repositories`
  - expose routes in `app/api/routes`
- Full multi-app blueprint from provided UI images is in:
  - `project_blueprint/README.md`
  - `project_blueprint/ENDPOINT_INDEX.md`
