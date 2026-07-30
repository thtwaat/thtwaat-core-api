"""Root pytest fixtures and marker wiring.

Unit tests must not import ``main`` at collection time (avoids Redis/Postgres).
Integration fixtures lazily boot the FastAPI app against the test stack.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from tests.support import (
    ensure_test_env,
    mock_ai_provider,
    mock_payment_provider,
    parse_host_port_from_database_url,
    postgres_dsn_from_env,
    redis_host_port,
    tcp_open,
    wait_for_tcp,
)

ensure_test_env()

REPORTS_DIR = Path(__file__).resolve().parent.parent / "reports"


def pytest_configure(config: pytest.Config) -> None:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    (REPORTS_DIR / ".gitkeep").touch(exist_ok=True)


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Auto-mark by directory when no explicit unit/integration/e2e marker is set."""
    for item in items:
        names = {m.name for m in item.iter_markers()}
        if names & {"unit", "integration", "e2e"}:
            continue
        path = Path(str(item.fspath)).as_posix()
        if "/tests/e2e/" in path or path.endswith("/tests/e2e"):
            item.add_marker(pytest.mark.e2e)
        elif "/tests/integration/" in path:
            item.add_marker(pytest.mark.integration)
        elif "/tests/unit/" in path:
            item.add_marker(pytest.mark.unit)
        else:
            # Legacy module tests historically assume Postgres + Redis
            item.add_marker(pytest.mark.integration)


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--run-integration",
        action="store_true",
        default=False,
        help="Allow integration tests (also implied by -m integration)",
    )
    parser.addoption(
        "--run-e2e",
        action="store_true",
        default=False,
        help="Allow e2e tests (also implied by -m e2e)",
    )


def _stack_ready() -> tuple[bool, str]:
    dsn = postgres_dsn_from_env()
    db_host, db_port = parse_host_port_from_database_url(dsn)
    redis_host, redis_port = redis_host_port()
    if not tcp_open(db_host, db_port):
        return False, f"PostgreSQL not reachable at {db_host}:{db_port}"
    if not tcp_open(redis_host, redis_port):
        return False, f"Redis not reachable at {redis_host}:{redis_port}"
    return True, "ok"


@pytest.fixture(scope="session")
def reports_dir() -> Path:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    return REPORTS_DIR


@pytest.fixture
def tmp_storage(tmp_path, monkeypatch):
    """Isolated local upload directory for storage-related tests."""
    upload_dir = tmp_path / "uploads"
    upload_dir.mkdir()
    monkeypatch.setenv("LOCAL_STORAGE_DIR", str(upload_dir))
    monkeypatch.setenv("STORAGE_PROVIDER", "local")
    return upload_dir


@pytest.fixture
def mock_payments():
    """Stub payment provider — use in unit tests instead of live gateways."""
    return mock_payment_provider()


@pytest.fixture
def mock_ai():
    """Stub AI provider responses."""
    return mock_ai_provider()


@pytest.fixture(scope="session")
def redis_url() -> str:
    host, port = redis_host_port()
    return f"redis://{host}:{port}/0"


@pytest.fixture(scope="session")
def integration_stack():
    """Skip session early when Postgres/Redis are down."""
    ok, reason = _stack_ready()
    if not ok:
        pytest.skip(f"Integration stack unavailable: {reason}. Start with: docker compose -f docker-compose.test.yml up -d")
    # Align app settings with the test compose ports when using defaults
    os.environ.setdefault("DATABASE_URL", postgres_dsn_from_env())
    host, port = redis_host_port()
    os.environ.setdefault("REDIS_HOST", host)
    os.environ.setdefault("REDIS_PORT", str(port))
    return {"database_url": os.environ["DATABASE_URL"], "redis_host": host, "redis_port": port}


@pytest.fixture(scope="module")
def client(integration_stack):
    """FastAPI TestClient against the real app (integration)."""
    # Re-bind settings/engine if DATABASE_URL was set for the test stack
    from fastapi.testclient import TestClient

    from main import app

    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="function")
def db_session(integration_stack):
    """SQLAlchemy session bound to the integration PostgreSQL database."""
    from app.database.database import SessionLocal

    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(scope="function")
def redis_client(integration_stack, redis_url):
    """Sync Redis client for integration assertions."""
    import redis

    client = redis.from_url(redis_url, decode_responses=True)
    try:
        client.ping()
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"Redis ping failed: {exc}")
    try:
        yield client
    finally:
        client.close()


@pytest.fixture(scope="function")
def user():
    """Placeholder user dict for lightweight assertions."""
    yield {"id": "00000000-0000-0000-0000-000000000001", "email": "test@example.com"}


@pytest.fixture(scope="function")
def company():
    """Placeholder company dict for lightweight assertions."""
    yield {"id": "00000000-0000-0000-0000-000000000002", "name": "Test Company"}


@pytest.fixture(scope="function")
def auth_token():
    """Placeholder bearer token (not a real JWT)."""
    yield "mock-jwt-token"


@pytest.fixture(scope="session")
def wait_for_integration_services():
    """Optional explicit wait used by scripts before pytest starts."""
    dsn = postgres_dsn_from_env()
    db_host, db_port = parse_host_port_from_database_url(dsn)
    redis_host, redis_port = redis_host_port()
    if not wait_for_tcp(db_host, db_port, timeout=60):
        pytest.skip(f"Timed out waiting for Postgres at {db_host}:{db_port}")
    if not wait_for_tcp(redis_host, redis_port, timeout=60):
        pytest.skip(f"Timed out waiting for Redis at {redis_host}:{redis_port}")
