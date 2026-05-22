import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from mongomock_motor import AsyncMongoMockClient

from app.api.deps import get_email_sender
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

    class FakeEmailSender:
        def send_signup_verification_code(self, recipient_email: str, full_name: str, code: str, expires_in: int) -> None:
            return None

        def send_password_reset_code(self, recipient_email: str, full_name: str, code: str, expires_in: int) -> None:
            return None

    application.dependency_overrides[get_database] = _override_get_db
    application.dependency_overrides[get_email_sender] = lambda: FakeEmailSender()
    return application


@pytest_asyncio.fixture
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac
