"""Unit-test fixtures: SQLite + fakeredis — no Docker required."""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from tests.support import ensure_test_env
from tests.support.sqlite_compat import register_sqlite_pg_compat

ensure_test_env()
register_sqlite_pg_compat()


@pytest.fixture(scope="session")
def sqlite_engine():
    """In-memory SQLite engine shared for the unit session."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def _fk_on(dbapi_conn, _):  # noqa: ANN001
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    yield engine
    engine.dispose()


@pytest.fixture
def unit_db_session(sqlite_engine) -> Session:
    """Lightweight session — no full ORM create_all (PG enums/arrays differ)."""
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=sqlite_engine)
    session = SessionLocal()
    try:
        session.execute(text("SELECT 1"))
        yield session
    finally:
        session.close()


@pytest.fixture
def fake_redis():
    """In-process Redis stand-in for unit tests."""
    fakeredis = pytest.importorskip("fakeredis")
    client = fakeredis.FakeRedis(decode_responses=True)
    try:
        yield client
    finally:
        client.flushall()
