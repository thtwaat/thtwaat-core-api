"""Real-PostgreSQL tests for THTWAAT Deploy Phase 4B —
static_site_deployment_env_vars: unique constraint, cascade delete, and the
migration's upgrade/downgrade/upgrade cycle. Uses the same
integration_stack/db_session fixtures as tests/integration/test_flow_*.py
(tests/conftest.py) — skips cleanly when the test Postgres from
docker-compose.test.yml isn't reachable."""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy.exc import IntegrityError

pytestmark = pytest.mark.integration

import app.companies.model  # noqa: F401
import app.static_sites.models  # noqa: F401
from app.companies.model import Company
from app.static_sites.env_crypto import encrypt_value
from app.static_sites.models import StaticSite, StaticSiteDeployment, StaticSiteDeploymentEnvVar


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


def _make_deployment(db, site: StaticSite) -> StaticSiteDeployment:
    dep = StaticSiteDeployment(
        site_id=site.id, workspace_id=site.workspace_id, version=1, is_current=True,
        provider="static", status="completed", stage="completed", source_type="html", environment="production",
    )
    db.add(dep)
    db.commit()
    db.refresh(dep)
    return dep


@pytest.mark.integration
def test_unique_constraint_rejects_duplicate_key_within_same_deployment(db_session):
    company = _make_company(db_session)
    site = _make_site(db_session, company)
    dep = _make_deployment(db_session, site)

    db_session.add(StaticSiteDeploymentEnvVar(
        deployment_id=dep.id, key="DATABASE_URL", encrypted_value=encrypt_value("A"),
        environment="production", is_secret=True,
    ))
    db_session.commit()

    db_session.add(StaticSiteDeploymentEnvVar(
        deployment_id=dep.id, key="DATABASE_URL", encrypted_value=encrypt_value("B"),
        environment="production", is_secret=True,
    ))
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


@pytest.mark.integration
def test_same_key_allowed_across_different_deployments(db_session):
    company = _make_company(db_session)
    site = _make_site(db_session, company)
    dep1 = _make_deployment(db_session, site)
    dep2 = _make_deployment(db_session, site)

    for dep in (dep1, dep2):
        db_session.add(StaticSiteDeploymentEnvVar(
            deployment_id=dep.id, key="DATABASE_URL", encrypted_value=encrypt_value("v"),
            environment="production", is_secret=True,
        ))
    db_session.commit()  # must not raise — different deployment_id each time

    rows = (
        db_session.query(StaticSiteDeploymentEnvVar)
        .filter(StaticSiteDeploymentEnvVar.key == "DATABASE_URL")
        .filter(StaticSiteDeploymentEnvVar.deployment_id.in_([dep1.id, dep2.id]))
        .all()
    )
    assert len(rows) == 2


@pytest.mark.integration
def test_cascade_delete_deployment_removes_env_var_snapshot(db_session):
    company = _make_company(db_session)
    site = _make_site(db_session, company)
    dep = _make_deployment(db_session, site)
    db_session.add(StaticSiteDeploymentEnvVar(
        deployment_id=dep.id, key="DATABASE_URL", encrypted_value=encrypt_value("v"),
        environment="production", is_secret=True,
    ))
    db_session.commit()

    db_session.delete(dep)
    db_session.commit()

    remaining = (
        db_session.query(StaticSiteDeploymentEnvVar)
        .filter(StaticSiteDeploymentEnvVar.deployment_id == dep.id)
        .all()
    )
    assert remaining == []


@pytest.mark.integration
def test_a_live_env_var_edit_does_not_touch_an_existing_snapshot_row(db_session):
    """DB-level guarantee behind Phase 4B spec §17: static_site_env_vars and
    static_site_deployment_env_vars are wholly separate tables — editing one
    row in the former can never cascade/trigger a change in the latter."""
    from app.static_sites.models import StaticSiteEnvironmentVariable

    company = _make_company(db_session)
    site = _make_site(db_session, company)
    dep = _make_deployment(db_session, site)

    live = StaticSiteEnvironmentVariable(
        workspace_id=company.id, site_id=site.id, key="DATABASE_URL",
        encrypted_value=encrypt_value("A"), environment="production", is_secret=True,
    )
    db_session.add(live)
    db_session.commit()

    snapshot = StaticSiteDeploymentEnvVar(
        deployment_id=dep.id, key="DATABASE_URL", encrypted_value=live.encrypted_value,
        environment="production", is_secret=True,
    )
    db_session.add(snapshot)
    db_session.commit()

    live.encrypted_value = encrypt_value("B")
    db_session.commit()

    db_session.refresh(snapshot)
    from app.static_sites.env_crypto import decrypt_value

    assert decrypt_value(snapshot.encrypted_value) == "A"


@pytest.mark.integration
def test_migration_upgrade_downgrade_upgrade_cycle(integration_stack):
    """Confirms e3f4a5b6c7d8 (static_site_deployment_env_vars) both applies
    and reverses cleanly, without touching any other table."""
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import create_engine, inspect

    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", integration_stack["database_url"])

    command.upgrade(cfg, "head")
    engine = create_engine(integration_stack["database_url"])
    try:
        assert "static_site_deployment_env_vars" in inspect(engine).get_table_names()
    finally:
        engine.dispose()

    command.downgrade(cfg, "-1")
    engine = create_engine(integration_stack["database_url"])
    try:
        assert "static_site_deployment_env_vars" not in inspect(engine).get_table_names()
        # sibling table from the previous migration must be unaffected
        assert "static_site_env_vars" in inspect(engine).get_table_names()
    finally:
        engine.dispose()

    command.upgrade(cfg, "head")
    engine = create_engine(integration_stack["database_url"])
    try:
        assert "static_site_deployment_env_vars" in inspect(engine).get_table_names()
    finally:
        engine.dispose()
