from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.router import api_router
from app.core.config import get_settings
from app.db.mongodb import MongoDatabaseSingleton

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    db = MongoDatabaseSingleton.get_instance(settings)
    app.state.db = db
    yield
    db.close()


def create_app() -> FastAPI:
    application = FastAPI(title=settings.app_name, lifespan=lifespan)
    application.include_router(api_router, prefix=settings.api_v1_prefix)

    @application.get("/health", tags=["Health"])
    def health_check() -> dict[str, str]:
        return {"status": "ok"}

    return application


app = create_app()

