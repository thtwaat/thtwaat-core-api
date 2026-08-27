"""Real-PostgreSQL tests for THTWAAT Deploy Phase 4A — the
static_site_env_vars unique constraint under real concurrency, and the
alembic migration's upgrade/downgrade/upgrade cycle.

Uses the SAME integration_stack/db_session fixtures as
tests/integration/test_flow_*.py (tests/conftest.py) rather than a second
database abstraction — skips cleanly (via integration_stack) when the test
Postgres from docker-compose.test.yml isn't reachable.
"""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy.exc import IntegrityError

pytestmark = pytest.mark.integration

import app.companies.model  # noqa: F401
import app.static_sites.models  # noqa: F401
from app.companies.model import Company
from app.static_sites.env_crypto import encrypt_value
from app.static_sites.models import StaticSite, StaticSiteEnvironmentVariable


def _make_company(db) -> Company:
    company = Company(slug=f"acme-{uuid.uuid4().hex[:12]}", name="Acme Test Co")
    db.add(company)
    db.commit()
    db.refresh(company)
    return company


def _make_site(db, company: Company) -> StaticSite:
    site = StaticSite(workspace_id=company.id, name="Test Site", slug=f"site-{uuid.uuid4().hex[:12]}")
    db.add(site)
    db.commit()
    db.refresh(site)
    return site


@pytest.mark.integration
def test_unique_constraint_rejects_duplicate_site_environment_key(db_session):
    company = _make_company(db_session)
    site = _make_site(db_session, company)

    row1 = StaticSiteEnvironmentVariable(
        workspace_id=company.id, site_id=site.id, key="DUPLICATE_KEY",
        encrypted_value=encrypt_value("v1"), environment="production", is_secret=True,
    )
    db_session.add(row1)
    db_session.commit()

    row2 = StaticSiteEnvironmentVariable(
        workspace_id=company.id, site_id=site.id, key="DUPLICATE_KEY",
        encrypted_value=encrypt_value("v2"), environment="production", is_secret=True,
    )
    db_session.add(row2)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


@pytest.mark.integration
def test_same_key_allowed_across_different_environments(db_session):
    company = _make_company(db_session)
    site = _make_site(db_session, company)

    for env in ("production", "development"):
        db_session.add(
            StaticSiteEnvironmentVariable(
                workspace_id=company.id, site_id=site.id, key="SAME_KEY",
                encrypted_value=encrypt_value("v"), environment=env, is_secret=True,
            )
        )
    db_session.commit()  # must not raise — (site_id, environment, key) differs per row

    rows = (
        db_session.query(StaticSiteEnvironmentVariable)
        .filter(StaticSiteEnvironmentVariable.site_id == site.id, StaticSiteEnvironmentVariable.key == "SAME_KEY")
        .all()
    )
    assert len(rows) == 2


@pytest.mark.integration
def test_cascade_delete_site_removes_env_vars(db_session):
    company = _make_company(db_session)
    site = _make_site(db_session, company)
    db_session.add(
        StaticSiteEnvironmentVariable(
            workspace_id=company.id, site_id=site.id, key="CASCADE_KEY",
            encrypted_value=encrypt_value("v"), environment="production", is_secret=True,
        )
    )
    db_session.commit()

    db_session.delete(site)
    db_session.commit()

    remaining = (
        db_session.query(StaticSiteEnvironmentVariable)
        .filter(StaticSiteEnvironmentVariable.workspace_id == company.id)
        .all()
    )
    assert remaining == []


@pytest.mark.integration
def test_migration_upgrade_downgrade_upgrade_cycle(integration_stack):
    """Confirms d2e3f4a5b6c7 (static_site_env_vars) both applies and
    reverses cleanly against the real test database, without touching any
    other table."""
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import create_engine, inspect

    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", integration_stack["database_url"])

    command.upgrade(cfg, "head")
    engine = create_engine(integration_stack["database_url"])
    try:
        assert "static_site_env_vars" in inspect(engine).get_table_names()
    finally:
        engine.dispose()

    command.downgrade(cfg, "-1")
    engine = create_engine(integration_stack["database_url"])
    try:
        assert "static_site_env_vars" not in inspect(engine).get_table_names()
    finally:
        engine.dispose()

    command.upgrade(cfg, "head")
    engine = create_engine(integration_stack["database_url"])
    try:
        assert "static_site_env_vars" in inspect(engine).get_table_names()
    finally:
        engine.dispose()
