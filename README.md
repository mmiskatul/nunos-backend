# Nuno Backend (FastAPI + MongoDB + AI Concierge)

Production-ready async backend for Nuno mobile app: discover + book + AI concierge for Restaurants, Events, Spas, and Hotels near metro stations.

## Stack
- Python 3.11+
- FastAPI
- Pydantic v2 + pydantic-settings
- MongoDB + Motor (async)
- JWT (access + refresh)
- Passlib + bcrypt
- Pytest + HTTPX (async)

## Project Structure
- `app/main.py` - FastAPI app + lifespan
- `app/core/config.py` - env settings
- `app/core/security.py` - JWT + hashing
- `app/db/mongo.py` - Motor manager + indexes + DB dependency
- `app/models/` - request/response schemas
- `app/domain/` - enums/value objects
- `app/repositories/` - Mongo repositories
- `app/services/` - business logic
- `app/services/bookings/` - Strategy + Factory for booking polymorphism
- `app/api/v1/routers/` - API routes
- `app/ai/` - prompt templates + LLM client + output schema
- `scripts/seed_demo.py` - demo data seed
- `tests/` - async endpoint tests

## Setup
```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

## Required Env Variables
```env
MONGODB_URI=mongodb://localhost:27017
MONGODB_DB_NAME=nuno
JWT_SECRET_KEY=replace-with-a-strong-secret
PLATFORM_ADMIN_EMAIL=admin@example.com
PLATFORM_ADMIN_PASSWORD=replace-with-a-strong-admin-password
OPENAI_API_KEY=
OPENAI_MODEL=gpt-4.1-mini
```

If `OPENAI_API_KEY` is empty, `/ai/plan` automatically uses a local stub LLM client.
If `PLATFORM_ADMIN_EMAIL` and `PLATFORM_ADMIN_PASSWORD` are set, the backend bootstraps the platform admin account from `.env` on startup.

## Run
```bash
uvicorn app.main:app --reload
```

OpenAPI docs:
- `http://localhost:8000/docs`
- `http://localhost:8000/redoc`

## Docker
```bash
docker-compose up --build
```

## Seed Demo Data
```bash
python scripts/seed_demo.py
```

## Key API Endpoints
### Auth
- `POST /api/v1/auth/register`
- `POST /api/v1/auth/login`
- `POST /api/v1/auth/refresh`
- `POST /api/v1/auth/forgot-password`
- `POST /api/v1/auth/verify-otp`
- `POST /api/v1/auth/reset-password`

### Listings + Reviews + Favorites
- `GET /api/v1/listings`
- `GET /api/v1/listings/{listing_id}`
- `POST /api/v1/listings/{listing_id}/reviews`
- `POST /api/v1/listings/{listing_id}/favorite`
- `DELETE /api/v1/listings/{listing_id}/favorite`
- `GET /api/v1/listings/me/favorites`

### Published service feeds

Vendor service identities are projected into separate MongoDB collections when
the vendor updates a service listing: `restaurants`, `hotels`, and `spas`.
Only records with `published: true` are returned by the corresponding customer
endpoints:

- `GET /api/v1/customer/restaurants`
- `GET /api/v1/customer/hotels`
- `GET /api/v1/customer/spas`

The mobile app also has dedicated top-level aliases for the same service
resources, including details, menus/services, galleries, offers, reviews, and
bookings:

- `GET /api/v1/restaurants`
- `GET /api/v1/hotels`
- `GET /api/v1/spas`

Service names are saved independently through
`PATCH /api/v1/vendor/settings/services/{restaurant|hotel|spa}` with a payload
such as `{"data": {"name": "Nuno Garden", "published": true}}`.

### Bookings
- `POST /api/v1/bookings`
- `GET /api/v1/bookings/{id}`
- `PATCH /api/v1/bookings/{id}/cancel`
- `PATCH /api/v1/bookings/{id}/reschedule`
- `GET /api/v1/users/me/bookings?status=upcoming|past`

### Loyalty + Offers
- `GET /api/v1/users/me/loyalty`
- `POST /api/v1/offers/validate`

### AI Concierge
- `POST /api/v1/ai/plan`

## Booking Strategy/Factory
`BookingService` uses `BookingStrategyFactory` to route booking validation and normalization by `booking_type`:
- `table` -> `TableBookingStrategy`
- `room` -> `RoomBookingStrategy`
- `spa` -> `SpaBookingStrategy`
- `ticket` -> `TicketBookingStrategy`

Each strategy validates required fields and returns a normalized `details` payload + `scheduled_at` for Mongo storage.

## Tests
```bash
pytest -q
```
# Vendor index migration

Vendor indexes are intentionally not managed inside request-scoped repositories. Run the idempotent migration once during every deployment before serving traffic:

```bash
python scripts/ensure_vendor_indexes.py
```

This keeps normal API reads free of index-management round trips while ensuring the dashboard, analytics, booking, review, promotion, and notification query paths are indexed.
