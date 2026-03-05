import pytest
from httpx import ASGITransport, AsyncClient
from mongomock_motor import AsyncMongoMockClient

from app.db.mongo import get_database
from app.main import create_app


@pytest.fixture
def test_db():
    client = AsyncMongoMockClient()
    return client["nuno_test"]


@pytest.fixture
def app(test_db):
    application = create_app(disable_startup_db=True)

    async def _override_get_db():
        return test_db

    application.dependency_overrides[get_database] = _override_get_db
    return application


@pytest.fixture
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac
