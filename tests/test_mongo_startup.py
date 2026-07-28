import pytest

from app.core.config import Settings
from app.db import mongo as mongo_module


class _FakeClient:
    def __init__(self, uri: str, **options):
        self.uri = uri
        self.options = options
        self.database = object()

    def __getitem__(self, name: str):
        self.database_name = name
        return self.database

    def close(self) -> None:
        return None


@pytest.mark.asyncio
async def test_mongo_startup_skips_database_setup_by_default(monkeypatch):
    fake_client = _FakeClient("mongodb://unused")
    setup_calls: list[str] = []

    monkeypatch.setattr(
        mongo_module,
        "AsyncIOMotorClient",
        lambda uri, **options: (
            setattr(fake_client, "uri", uri)
            or setattr(fake_client, "options", options)
            or fake_client
        ),
    )

    async def record_indexes(db):
        setup_calls.append("indexes")

    async def record_admin(db, settings):
        setup_calls.append("admin")

    monkeypatch.setattr(mongo_module, "ensure_indexes", record_indexes)
    monkeypatch.setattr(mongo_module, "ensure_platform_admin", record_admin)

    settings = Settings(
        mongodb_uri="mongodb://example",
        mongodb_db_name="test-db",
        jwt_secret_key="test-secret-key-long-enough",
    )
    database = await mongo_module.MongoManager(settings).connect()

    assert database is fake_client.database
    assert fake_client.database_name == "test-db"
    assert setup_calls == []
    assert fake_client.options["serverSelectionTimeoutMS"] == 8_000


@pytest.mark.asyncio
async def test_mongo_startup_setup_remains_available_when_enabled(monkeypatch):
    fake_client = _FakeClient("mongodb://unused")
    setup_calls: list[str] = []

    monkeypatch.setattr(
        mongo_module,
        "AsyncIOMotorClient",
        lambda uri, **options: fake_client,
    )

    async def record_indexes(db):
        setup_calls.append("indexes")

    async def record_admin(db, settings):
        setup_calls.append("admin")

    monkeypatch.setattr(mongo_module, "ensure_indexes", record_indexes)
    monkeypatch.setattr(mongo_module, "ensure_platform_admin", record_admin)

    settings = Settings(
        mongodb_uri="mongodb://example",
        mongodb_db_name="test-db",
        jwt_secret_key="test-secret-key-long-enough",
        run_startup_db_setup=True,
    )
    await mongo_module.MongoManager(settings).connect()

    assert setup_calls == ["indexes", "admin"]
