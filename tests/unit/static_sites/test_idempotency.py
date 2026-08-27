"""Tests for the upload Idempotency-Key mechanism (Phase 2 staging
validation report §6/§12/§9 items G/H) — the synchronous upload endpoint
must resolve a retried/duplicated request to the same deployment instead of
launching a second Docker build.

Service-level tests here mock the repo (matching test_service.py's
convention). test_repository_claim_race_is_atomic below is the one test in
this module that hits a real Postgres — it's the actual proof the
concurrency guard works, since a mocked repo can't demonstrate a genuine
unique-constraint race.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

import app.apps.model  # noqa: F401
import app.auth.model  # noqa: F401
import app.companies.model  # noqa: F401
import app.domains.models  # noqa: F401
import app.static_sites.models  # noqa: F401
import app.storage.model  # noqa: F401
import app.users.model  # noqa: F401

from app.static_sites.models import StaticSite, StaticSiteDeployment
from app.static_sites.service import StaticSiteService


def _profile(role: str = "admin", *, company_id=None):
    return SimpleNamespace(id=str(uuid4()), email="user@example.com", role=role, company_id=str(company_id or uuid4()))


def _stamp(row):
    defaults = {
        "id": lambda: uuid4(), "instructions": lambda: [], "logs": lambda: [], "urls": lambda: {},
        "health": lambda: {}, "ssl": lambda: {}, "duration_ms": lambda: 0, "retryable": lambda: False,
        "file_count": lambda: 0, "total_bytes": lambda: 0, "upload_size_bytes": lambda: 0,
        "is_current": lambda: True, "live": lambda: False, "environment": lambda: "production",
        "provider": lambda: "static", "status": lambda: "queued", "stage": lambda: "queued",
        "created_at": lambda: datetime.now(timezone.utc), "updated_at": lambda: datetime.now(timezone.utc),
    }
    for field, factory in defaults.items():
        if getattr(row, field, None) is None:
            setattr(row, field, factory())
    return row


def _service() -> StaticSiteService:
    svc = StaticSiteService(MagicMock())
    svc.repo = MagicMock()
    svc.repo.create_deployment.side_effect = _stamp
    svc.repo.save_deployment.side_effect = _stamp
    return svc


@pytest.mark.unit
def test_repeat_request_with_known_key_returns_existing_deployment_without_running_pipeline(tmp_path, monkeypatch):
    svc = _service()
    site = StaticSite(id=uuid4(), workspace_id=uuid4(), name="Demo", slug="demo")
    svc.repo.get_site_for_workspace.return_value = site

    existing = _stamp(StaticSiteDeployment(
        id=uuid4(), site_id=site.id, workspace_id=site.workspace_id, version=1,
        source_type="html", environment="production", status="completed", stage="completed",
    ))
    svc.repo.get_idempotent_deployment.return_value = existing

    pipeline_called = {"yes": False}
    monkeypatch.setattr(svc, "_run_pipeline", lambda **kw: pipeline_called.__setitem__("yes", True))

    upload = tmp_path / "index.html"
    upload.write_text("<html>hi</html>")

    result = svc.deploy_upload(
        _profile(company_id=site.workspace_id), site.id,
        upload_path=upload, source_type="html", original_filename="index.html",
        upload_size_bytes=upload.stat().st_size, idempotency_key="client-key-123",
    )

    assert result.id == existing.id
    assert pipeline_called["yes"] is False, "a known idempotency key must never trigger a second pipeline run"
    assert not upload.exists(), "the redundant upload's temp file must still be cleaned up"
    svc.repo.create_deployment.assert_not_called()


@pytest.mark.unit
def test_losing_the_claim_race_deletes_own_row_and_returns_winner(tmp_path, monkeypatch):
    svc = _service()
    site = StaticSite(id=uuid4(), workspace_id=uuid4(), name="Demo", slug="demo")
    svc.repo.get_site_for_workspace.return_value = site
    svc.repo.next_deployment_version.return_value = 1
    # No existing record on the fast-path check (this request got there
    # first)...
    winner = _stamp(StaticSiteDeployment(
        id=uuid4(), site_id=site.id, workspace_id=site.workspace_id, version=1,
        source_type="html", environment="production", status="queued", stage="queued",
    ))
    svc.repo.get_idempotent_deployment.side_effect = [None, winner]
    # ...but a concurrent request claimed the key first.
    svc.repo.claim_idempotency_key.return_value = False

    pipeline_called = {"yes": False}
    monkeypatch.setattr(svc, "_run_pipeline", lambda **kw: pipeline_called.__setitem__("yes", True))

    upload = tmp_path / "index.html"
    upload.write_text("<html>hi</html>")

    result = svc.deploy_upload(
        _profile(company_id=site.workspace_id), site.id,
        upload_path=upload, source_type="html", original_filename="index.html",
        upload_size_bytes=upload.stat().st_size, idempotency_key="client-key-123",
    )

    assert result.id == winner.id
    assert pipeline_called["yes"] is False
    svc.repo.delete_deployment.assert_called_once()


@pytest.mark.unit
def test_no_idempotency_key_behaves_exactly_as_before(tmp_path, monkeypatch):
    """Regression: omitting Idempotency-Key must not touch any of the new
    repo methods at all — existing callers/tests are unaffected."""
    svc = _service()
    site = StaticSite(id=uuid4(), workspace_id=uuid4(), name="Demo", slug="demo")
    svc.repo.get_site_for_workspace.return_value = site
    svc.repo.next_deployment_version.return_value = 1
    monkeypatch.setattr(svc, "_run_pipeline", lambda **kw: None)

    upload = tmp_path / "index.html"
    upload.write_text("<html>hi</html>")

    svc.deploy_upload(
        _profile(company_id=site.workspace_id), site.id,
        upload_path=upload, source_type="html", original_filename="index.html",
        upload_size_bytes=upload.stat().st_size,
    )

    svc.repo.get_idempotent_deployment.assert_not_called()
    svc.repo.claim_idempotency_key.assert_not_called()


@pytest.mark.integration
def test_repository_claim_race_is_atomic(db_session):
    """The real test: two 'requests' racing to claim the same
    (site_id, idempotency_key) against a real Postgres unique constraint —
    exactly one must win. A mocked repo cannot demonstrate this; this is
    the one test in this module that needs the real integration stack
    (docker compose -f docker-compose.test.yml up -d db redis)."""
    from app.companies.model import Company
    from app.static_sites.repository import StaticSiteRepository

    company = Company(id=uuid4(), slug=f"idem-test-{uuid4().hex[:8]}", name="Idempotency Test Co")
    db_session.add(company)
    db_session.commit()

    site = StaticSite(id=uuid4(), workspace_id=company.id, name="Site", slug=f"site-{uuid4().hex[:8]}")
    db_session.add(site)
    db_session.commit()

    dep_a = StaticSiteDeployment(
        id=uuid4(), site_id=site.id, workspace_id=company.id, version=1,
        source_type="html", environment="production", status="queued", stage="queued",
    )
    dep_b = StaticSiteDeployment(
        id=uuid4(), site_id=site.id, workspace_id=company.id, version=2,
        source_type="html", environment="production", status="queued", stage="queued",
    )
    db_session.add_all([dep_a, dep_b])
    db_session.commit()

    repo = StaticSiteRepository(db_session)
    key = f"race-key-{uuid4().hex}"

    won_a = repo.claim_idempotency_key(site.id, key, dep_a.id)
    won_b = repo.claim_idempotency_key(site.id, key, dep_b.id)

    assert won_a is True
    assert won_b is False, "a second claim on the same (site_id, key) must never succeed"

    resolved = repo.get_idempotent_deployment(site.id, key)
    assert resolved is not None
    assert resolved.id == dep_a.id, "the key must resolve to whichever request actually won the claim"


@pytest.mark.integration
def test_repository_expired_idempotency_key_is_ignored(db_session):
    """A key older than the TTL must be treated as if it never existed —
    a fresh upload proceeds normally rather than replaying stale state."""
    from app.companies.model import Company
    from app.static_sites.models import StaticSiteUploadIdempotency
    from app.static_sites.repository import StaticSiteRepository

    company = Company(id=uuid4(), slug=f"idem-ttl-{uuid4().hex[:8]}", name="Idempotency TTL Co")
    db_session.add(company)
    db_session.commit()

    site = StaticSite(id=uuid4(), workspace_id=company.id, name="Site", slug=f"site-{uuid4().hex[:8]}")
    db_session.add(site)
    db_session.commit()

    dep = StaticSiteDeployment(
        id=uuid4(), site_id=site.id, workspace_id=company.id, version=1,
        source_type="html", environment="production", status="completed", stage="completed",
    )
    db_session.add(dep)
    db_session.commit()

    key = f"stale-key-{uuid4().hex}"
    record = StaticSiteUploadIdempotency(id=uuid4(), site_id=site.id, idempotency_key=key, deployment_id=dep.id)
    db_session.add(record)
    db_session.commit()
    record_id = record.id  # capture before any expire/delete — see below
    # Force it stale — created_at has a server_default of now(), so
    # backdate it directly rather than fighting the default at insert time.
    db_session.query(StaticSiteUploadIdempotency).filter_by(id=record_id).update(
        {"created_at": datetime.now(timezone.utc) - timedelta(hours=48)}
    )
    db_session.commit()

    repo = StaticSiteRepository(db_session)
    assert repo.get_idempotent_deployment(site.id, key, ttl_hours=24) is None

    removed = repo.purge_expired_idempotency_keys(ttl_hours=24)
    assert removed >= 1
    # record is expired (session commits above) and its row is now gone —
    # look up by the plain UUID captured earlier, never via record.id
    # (accessing an expired, deleted instance's attribute triggers a
    # refresh-from-DB that raises ObjectDeletedError).
    assert db_session.query(StaticSiteUploadIdempotency).filter_by(id=record_id).first() is None
