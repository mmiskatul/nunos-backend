import logging
import traceback
from contextlib import asynccontextmanager

from bson.errors import InvalidId
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.router import api_router
from app.core.config import Settings, get_settings
from app.db.mongo import MongoManager

logger = logging.getLogger("nunos.backend")


def create_app(*, settings: Settings | None = None, disable_startup_db: bool = False) -> FastAPI:
    app_settings = settings or get_settings()
    mongo_manager = MongoManager(app_settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if disable_startup_db:
            app.state.db = None
            yield
            return

        db = await mongo_manager.connect()
        app.state.db = db
        yield
        await mongo_manager.close()

    app = FastAPI(
        title=app_settings.app_name,
        version="1.0.0",
        lifespan=lifespan,
        openapi_url=f"{app_settings.api_v1_prefix}/openapi.json",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=app_settings.cors_origins,
        allow_origin_regex=app_settings.cors_origin_regex,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(api_router, prefix=app_settings.api_v1_prefix)

    # ── Global exception handlers ────────────────────────────────────────────

    @app.exception_handler(InvalidId)
    async def invalid_bson_id_handler(request: Request, exc: InvalidId):
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"detail": f"Invalid ID format: {exc}"},
        )

    @app.exception_handler(ValueError)
    async def value_error_handler(request: Request, exc: ValueError):
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"detail": str(exc)},
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        logger.error(
            "Unhandled exception on %s %s:\n%s",
            request.method,
            request.url.path,
            traceback.format_exc(),
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "An internal server error occurred. Please try again later."},
        )

    @app.get("/health", tags=["Health"])
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
