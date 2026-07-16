import pytest
from fastapi.testclient import TestClient

# We assume there's an app instance available from main
from main import app

@pytest.fixture(scope="module")
def client():
    """FastAPI TestClient fixture."""
    with TestClient(app) as c:
        yield c

@pytest.fixture(scope="function")
def db_session():
    """Database session fixture."""
    from app.database.database import SessionLocal
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@pytest.fixture(scope="function")
def user():
    """User fixture placeholder."""
    # TODO: Implement user creation/mocking
    yield {"id": "00000000-0000-0000-0000-000000000001", "email": "test@example.com"}

@pytest.fixture(scope="function")
def company():
    """Company fixture placeholder."""
    # TODO: Implement company creation/mocking
    yield {"id": "00000000-0000-0000-0000-000000000002", "name": "Test Company"}

@pytest.fixture(scope="function")
def auth_token():
    """Authentication token fixture placeholder."""
    # TODO: Implement token generation
    yield "mock-jwt-token"
