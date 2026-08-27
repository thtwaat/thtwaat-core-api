"""Unit tests for app/static_sites/env_vars_service.py — RBAC, company
isolation, encryption-at-rest, and CRUD semantics for THTWAAT Deploy Phase
4A. Mirrors tests/unit/static_sites/test_service.py's MagicMock(db)/
MagicMock(repo) style — no real database required."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError

# Same registry-priming rationale as test_service.py: constructing real ORM
# instances triggers SQLAlchemy mapper configuration for the whole shared
# Base registry.
import app.users.model  # noqa: F401
import app.apps.model  # noqa: F401
import app.companies.model  # noqa: F401
import app.auth.model  # noqa: F401
import app.storage.model  # noqa: F401
import app.domains.models  # noqa: F401
import app.static_sites.models  # noqa: F401

from app.static_sites.env_crypto import EnvVarCryptoError, decrypt_value
from app.static_sites.env_vars_service import StaticSiteEnvVarService
from app.static_sites.models import StaticSite, StaticSiteEnvironmentVariable
from app.static_sites.schemas import StaticSiteEnvVarCreateRequest, StaticSiteEnvVarUpdateRequest

SECRET_PLAINTEXT = "SUPER_SECRET_123456"


def _profile(role: str, *, company_id=None, user_id=None):
    return SimpleNamespace(
        id=str(user_id or uuid4()),
        email="user@example.com",
        role=role,
        company_id=str(company_id or uuid4()),
    )


def _stamp_defaults(row):
    if getattr(row, "id", None) is None:
        row.id = uuid4()
    if getattr(row, "created_at", None) is None:
        row.created_at = datetime.now(timezone.utc)
    if getattr(row, "updated_at", None) is None:
        row.updated_at = datetime.now(timezone.utc)
    return row


def _service() -> StaticSiteEnvVarService:
    svc = StaticSiteEnvVarService(MagicMock())
    svc.repo = MagicMock()
    svc.repo.create_env_var.side_effect = _stamp_defaults
    svc.repo.save_env_var.side_effect = _stamp_defaults
    return svc


def _site(workspace_id, site_id=None) -> StaticSite:
    return StaticSite(id=site_id or uuid4(), workspace_id=workspace_id, name="Acme", slug="acme")


def _env_row(*, workspace_id, site_id, key="FOO", environment="production", encrypted_value="tok") -> StaticSiteEnvironmentVariable:
    return StaticSiteEnvironmentVariable(
        id=uuid4(),
        workspace_id=workspace_id,
        site_id=site_id,
        key=key,
        encrypted_value=encrypted_value,
        environment=environment,
        is_secret=True,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


# ---- RBAC ------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.parametrize("role", ["employee", "viewer", "manager", "developer"])
def test_viewer_and_non_manager_roles_cannot_create(role):
    svc = _service()
    company_id = uuid4()
    site_id = uuid4()
    svc.repo.get_site_for_workspace.return_value = _site(company_id, site_id)

    payload = StaticSiteEnvVarCreateRequest(key="FOO", value="bar", environment="production")
    with pytest.raises(HTTPException) as exc:
        svc.create_env_var(_profile(role, company_id=company_id), site_id, payload)
    assert exc.value.status_code == 403


@pytest.mark.unit
@pytest.mark.parametrize("role", ["employee", "viewer"])
def test_viewer_cannot_update(role):
    svc = _service()
    with pytest.raises(HTTPException) as exc:
        svc.update_env_var(_profile(role), uuid4(), uuid4(), StaticSiteEnvVarUpdateRequest(value="x"))
    assert exc.value.status_code == 403


@pytest.mark.unit
@pytest.mark.parametrize("role", ["employee", "viewer"])
def test_viewer_cannot_delete(role):
    svc = _service()
    with pytest.raises(HTTPException) as exc:
        svc.delete_env_var(_profile(role), uuid4(), uuid4())
    assert exc.value.status_code == 403


@pytest.mark.unit
@pytest.mark.parametrize("role", ["employee", "viewer"])
def test_viewer_cannot_list(role):
    svc = _service()
    with pytest.raises(HTTPException) as exc:
        svc.list_env_vars(_profile(role), uuid4())
    assert exc.value.status_code == 403


@pytest.mark.unit
@pytest.mark.parametrize("role", ["company_owner", "admin", "super_admin"])
def test_owner_admin_super_admin_can_create(role):
    svc = _service()
    company_id = uuid4()
    site_id = uuid4()
    svc.repo.get_site_for_workspace.return_value = _site(company_id, site_id)
    svc.repo.get_env_var_by_key.return_value = None

    payload = StaticSiteEnvVarCreateRequest(key="FOO", value="bar", environment="production")
    resp = svc.create_env_var(_profile(role, company_id=company_id), site_id, payload)
    assert resp.key == "FOO"


# ---- create / encryption at rest -------------------------------------------


@pytest.mark.unit
def test_create_env_var_stores_encrypted_value_not_plaintext():
    svc = _service()
    company_id = uuid4()
    site_id = uuid4()
    svc.repo.get_site_for_workspace.return_value = _site(company_id, site_id)
    svc.repo.get_env_var_by_key.return_value = None

    payload = StaticSiteEnvVarCreateRequest(key="SECRET", value=SECRET_PLAINTEXT, environment="production")
    svc.create_env_var(_profile("admin", company_id=company_id), site_id, payload)

    saved_row = svc.repo.create_env_var.call_args[0][0]
    assert saved_row.encrypted_value != SECRET_PLAINTEXT
    assert SECRET_PLAINTEXT not in saved_row.encrypted_value
    # Round trip inside the service/crypto layer only — never via an API response.
    assert decrypt_value(saved_row.encrypted_value) == SECRET_PLAINTEXT


@pytest.mark.unit
def test_create_env_var_response_never_contains_plaintext_or_encrypted_value():
    svc = _service()
    company_id = uuid4()
    site_id = uuid4()
    svc.repo.get_site_for_workspace.return_value = _site(company_id, site_id)
    svc.repo.get_env_var_by_key.return_value = None

    payload = StaticSiteEnvVarCreateRequest(key="SECRET", value=SECRET_PLAINTEXT, environment="production")
    resp = svc.create_env_var(_profile("admin", company_id=company_id), site_id, payload)

    dumped = resp.model_dump_json()
    assert SECRET_PLAINTEXT not in dumped
    assert "value" not in resp.model_fields
    assert "encrypted_value" not in resp.model_fields


@pytest.mark.unit
def test_create_env_var_sets_workspace_id_and_created_by():
    svc = _service()
    company_id = uuid4()
    site_id = uuid4()
    user_id = uuid4()
    svc.repo.get_site_for_workspace.return_value = _site(company_id, site_id)
    svc.repo.get_env_var_by_key.return_value = None

    payload = StaticSiteEnvVarCreateRequest(key="FOO", value="bar", environment="production")
    svc.create_env_var(_profile("admin", company_id=company_id, user_id=user_id), site_id, payload)

    saved_row = svc.repo.create_env_var.call_args[0][0]
    assert saved_row.workspace_id == company_id
    assert saved_row.site_id == site_id
    assert str(saved_row.created_by) == str(user_id)


@pytest.mark.unit
def test_duplicate_key_pre_check_rejected_with_409():
    svc = _service()
    company_id = uuid4()
    site_id = uuid4()
    svc.repo.get_site_for_workspace.return_value = _site(company_id, site_id)
    svc.repo.get_env_var_by_key.return_value = _env_row(workspace_id=company_id, site_id=site_id)

    payload = StaticSiteEnvVarCreateRequest(key="FOO", value="bar", environment="production")
    with pytest.raises(HTTPException) as exc:
        svc.create_env_var(_profile("admin", company_id=company_id), site_id, payload)
    assert exc.value.status_code == 409
    svc.repo.create_env_var.assert_not_called()


@pytest.mark.unit
def test_concurrent_duplicate_creation_relies_on_db_unique_constraint():
    """Simulates two requests racing past the pre-flight check (TOCTOU) —
    the repository's INSERT hits the real UniqueConstraint and raises
    IntegrityError, which the service must map to a clean 409, not a 500."""
    svc = _service()
    company_id = uuid4()
    site_id = uuid4()
    svc.repo.get_site_for_workspace.return_value = _site(company_id, site_id)
    svc.repo.get_env_var_by_key.return_value = None  # pre-check sees no row (race)
    svc.repo.create_env_var.side_effect = IntegrityError("insert", {}, Exception("unique violation"))

    payload = StaticSiteEnvVarCreateRequest(key="FOO", value="bar", environment="production")
    with pytest.raises(HTTPException) as exc:
        svc.create_env_var(_profile("admin", company_id=company_id), site_id, payload)
    assert exc.value.status_code == 409
    svc.db.rollback.assert_called_once()


@pytest.mark.unit
def test_missing_encryption_key_fails_safely_on_create(monkeypatch):
    from app.static_sites import env_vars_service

    svc = _service()
    company_id = uuid4()
    site_id = uuid4()
    svc.repo.get_site_for_workspace.return_value = _site(company_id, site_id)
    svc.repo.get_env_var_by_key.return_value = None

    def _boom(_value):
        raise EnvVarCryptoError("Environment variable encryption is unavailable: no encryption key is configured.")

    monkeypatch.setattr(env_vars_service, "encrypt_value", _boom)

    payload = StaticSiteEnvVarCreateRequest(key="FOO", value=SECRET_PLAINTEXT, environment="production")
    with pytest.raises(HTTPException) as exc:
        svc.create_env_var(_profile("admin", company_id=company_id), site_id, payload)
    assert exc.value.status_code == 503
    assert SECRET_PLAINTEXT not in str(exc.value.detail)
    svc.repo.create_env_var.assert_not_called()


@pytest.mark.unit
def test_plaintext_never_logged_on_create(monkeypatch, caplog):
    svc = _service()
    company_id = uuid4()
    site_id = uuid4()
    svc.repo.get_site_for_workspace.return_value = _site(company_id, site_id)
    svc.repo.get_env_var_by_key.return_value = None

    with caplog.at_level(logging.DEBUG):
        payload = StaticSiteEnvVarCreateRequest(key="SECRET", value=SECRET_PLAINTEXT, environment="production")
        svc.create_env_var(_profile("admin", company_id=company_id), site_id, payload)

    assert SECRET_PLAINTEXT not in caplog.text


@pytest.mark.unit
def test_plaintext_never_appears_in_exception_on_unexpected_db_failure():
    svc = _service()
    company_id = uuid4()
    site_id = uuid4()
    svc.repo.get_site_for_workspace.return_value = _site(company_id, site_id)
    svc.repo.get_env_var_by_key.return_value = None
    svc.repo.create_env_var.side_effect = RuntimeError("db exploded")

    payload = StaticSiteEnvVarCreateRequest(key="SECRET", value=SECRET_PLAINTEXT, environment="production")
    with pytest.raises(HTTPException) as exc:
        svc.create_env_var(_profile("admin", company_id=company_id), site_id, payload)
    assert exc.value.status_code == 500
    assert SECRET_PLAINTEXT not in str(exc.value.detail)
    assert "db exploded" not in str(exc.value.detail)


# ---- list / get -------------------------------------------------------------


@pytest.mark.unit
def test_list_env_vars_returns_metadata_only():
    svc = _service()
    company_id = uuid4()
    site_id = uuid4()
    svc.repo.get_site_for_workspace.return_value = _site(company_id, site_id)
    svc.repo.list_env_vars.return_value = [
        _env_row(workspace_id=company_id, site_id=site_id, key="A", encrypted_value="enc-a"),
        _env_row(workspace_id=company_id, site_id=site_id, key="B", encrypted_value="enc-b"),
    ]

    resp = svc.list_env_vars(_profile("admin", company_id=company_id), site_id)
    assert resp.total == 2
    dumped = resp.model_dump_json()
    assert "enc-a" not in dumped and "enc-b" not in dumped


@pytest.mark.unit
def test_get_env_var_returns_metadata_only():
    svc = _service()
    company_id = uuid4()
    site_id = uuid4()
    row = _env_row(workspace_id=company_id, site_id=site_id, encrypted_value=SECRET_PLAINTEXT + "-enc")
    svc.repo.get_site_for_workspace.return_value = _site(company_id, site_id)
    svc.repo.get_env_var.return_value = row

    resp = svc.get_env_var(_profile("admin", company_id=company_id), site_id, row.id)
    assert SECRET_PLAINTEXT not in resp.model_dump_json()


# ---- company isolation -------------------------------------------------------


@pytest.mark.unit
def test_company_isolation_on_list_site_not_found():
    svc = _service()
    svc.repo.get_site_for_workspace.return_value = None
    with pytest.raises(HTTPException) as exc:
        svc.list_env_vars(_profile("admin"), uuid4())
    assert exc.value.status_code == 404


@pytest.mark.unit
def test_company_isolation_on_get_site_not_found():
    svc = _service()
    svc.repo.get_site_for_workspace.return_value = None
    with pytest.raises(HTTPException) as exc:
        svc.get_env_var(_profile("admin"), uuid4(), uuid4())
    assert exc.value.status_code == 404


@pytest.mark.unit
def test_company_isolation_on_update_site_not_found():
    svc = _service()
    svc.repo.get_site_for_workspace.return_value = None
    with pytest.raises(HTTPException) as exc:
        svc.update_env_var(_profile("admin"), uuid4(), uuid4(), StaticSiteEnvVarUpdateRequest(value="x"))
    assert exc.value.status_code == 404


@pytest.mark.unit
def test_company_isolation_on_delete_site_not_found():
    svc = _service()
    svc.repo.get_site_for_workspace.return_value = None
    with pytest.raises(HTTPException) as exc:
        svc.delete_env_var(_profile("admin"), uuid4(), uuid4())
    assert exc.value.status_code == 404


@pytest.mark.unit
def test_env_var_belonging_to_different_site_returns_404():
    """Site exists and belongs to the caller's workspace, but the env var
    row belongs to a DIFFERENT site/workspace (e.g. spoofed IDs) — still a
    plain 404, not a 403 (never confirm the other row's existence)."""
    svc = _service()
    company_id = uuid4()
    site_id = uuid4()
    svc.repo.get_site_for_workspace.return_value = _site(company_id, site_id)
    other_company = uuid4()
    other_site = uuid4()
    svc.repo.get_env_var.return_value = _env_row(workspace_id=other_company, site_id=other_site)

    with pytest.raises(HTTPException) as exc:
        svc.get_env_var(_profile("admin", company_id=company_id), site_id, uuid4())
    assert exc.value.status_code == 404
    assert exc.value.detail == "Environment variable not found"


@pytest.mark.unit
def test_site_workspace_mismatch_rejected_before_env_var_lookup():
    """Company A's admin cannot even reach the env-var lookup for a site_id
    that belongs to Company B — get_site_for_workspace() scopes by workspace
    so a cross-company site_id resolves to None."""
    svc = _service()
    svc.repo.get_site_for_workspace.return_value = None
    with pytest.raises(HTTPException) as exc:
        svc.list_env_vars(_profile("admin", company_id=uuid4()), uuid4())
    assert exc.value.status_code == 404
    svc.repo.list_env_vars.assert_not_called()


# ---- update / delete ---------------------------------------------------------


@pytest.mark.unit
def test_update_env_var_re_encrypts_new_value():
    svc = _service()
    company_id = uuid4()
    site_id = uuid4()
    row = _env_row(workspace_id=company_id, site_id=site_id, encrypted_value="old-enc")
    svc.repo.get_site_for_workspace.return_value = _site(company_id, site_id)
    svc.repo.get_env_var.return_value = row

    new_secret = "ROTATED_SECRET_9999"
    svc.update_env_var(_profile("admin", company_id=company_id), site_id, row.id, StaticSiteEnvVarUpdateRequest(value=new_secret))

    assert row.encrypted_value != "old-enc"
    assert row.encrypted_value != new_secret
    assert decrypt_value(row.encrypted_value) == new_secret


@pytest.mark.unit
def test_update_env_var_can_flip_is_secret_without_changing_value():
    svc = _service()
    company_id = uuid4()
    site_id = uuid4()
    row = _env_row(workspace_id=company_id, site_id=site_id, encrypted_value="unchanged-enc")
    row.is_secret = True
    svc.repo.get_site_for_workspace.return_value = _site(company_id, site_id)
    svc.repo.get_env_var.return_value = row

    resp = svc.update_env_var(_profile("admin", company_id=company_id), site_id, row.id, StaticSiteEnvVarUpdateRequest(is_secret=False))
    assert resp.is_secret is False
    assert row.encrypted_value == "unchanged-enc"


@pytest.mark.unit
def test_delete_env_var_calls_repo_delete():
    svc = _service()
    company_id = uuid4()
    site_id = uuid4()
    row = _env_row(workspace_id=company_id, site_id=site_id)
    svc.repo.get_site_for_workspace.return_value = _site(company_id, site_id)
    svc.repo.get_env_var.return_value = row

    svc.delete_env_var(_profile("admin", company_id=company_id), site_id, row.id)
    svc.repo.delete_env_var.assert_called_once_with(row)
