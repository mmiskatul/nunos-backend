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
  - `POST /api/v1/auth/social-login` (Google / Apple)
- Sign up form:
  - `POST /api/v1/auth/signup`
  - `PATCH /api/v1/users/me/location` (enable location toggle)
- Common authenticated user:
  - `GET /api/v1/auth/me`
  - `POST /api/v1/auth/forgot-password/reset`

## Notes
- Social login strategy is wired for extension. Replace the development token parser in
  `app/providers/social_auth.py` with real Google/Apple token verification.
- If you add more UI screens, follow the same module split:
  - request/response models in `app/schemas`
  - business rules in `app/services`
  - DB access in `app/repositories`
  - expose routes in `app/api/routes`

