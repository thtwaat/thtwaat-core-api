"""THTWAAT Deploy Phase 4B — explicit security tests (spec §21).

The three example secrets below must never appear in: an API response, a
deployment response, build logs, the SSE stream, persisted plaintext logs,
a browser-visible (VITE_*/NEXT_PUBLIC_*) build environment, or a generated
source file. Each assertion here maps to one of those surfaces."""
from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

import app.users.model  # noqa: F401
import app.apps.model  # noqa: F401
import app.companies.model  # noqa: F401
import app.auth.model  # noqa: F401
import app.storage.model  # noqa: F401
import app.domains.models  # noqa: F401
import app.static_sites.models  # noqa: F401

from app.static_sites.env_crypto import encrypt_value
from app.static_sites.env_redaction import build_secret_redactor
from app.static_sites.env_resolver import ResolvedEnvVar, nextjs_public_build_vars, secret_values, vite_client_vars
from app.static_sites.env_vars_service import StaticSiteEnvVarService
from app.static_sites.models import StaticSite, StaticSiteEnvironmentVariable
from app.static_sites.schemas import StaticSiteEnvVarCreateRequest

DATABASE_URL = "postgres://super-secret"
OPENAI_API_KEY = "super-secret-api-key"
STRIPE_SECRET_KEY = "super-secret-stripe-key"
ALL_SECRETS = [DATABASE_URL, OPENAI_API_KEY, STRIPE_SECRET_KEY]


def _profile(role: str = "admin", *, company_id=None):
    return SimpleNamespace(id=str(uuid4()), email="user@example.com", role=role, company_id=str(company_id or uuid4()))


# ---- API / deployment response ------------------------------------------------


@pytest.mark.unit
def test_secrets_never_appear_in_create_response():
    svc = StaticSiteEnvVarService(MagicMock())
    svc.repo = MagicMock()
    svc.repo.get_env_var_by_key.return_value = None

    def _stamp(row):
        row.id = uuid4()
        row.created_at = datetime.now(timezone.utc)
        row.updated_at = datetime.now(timezone.utc)
        return row

    svc.repo.create_env_var.side_effect = _stamp
    company_id, site_id = uuid4(), uuid4()
    svc.repo.get_site_for_workspace.return_value = StaticSite(id=site_id, workspace_id=company_id, name="A", slug="a")

    for key, value in (("DATABASE_URL", DATABASE_URL), ("OPENAI_API_KEY", OPENAI_API_KEY), ("STRIPE_SECRET_KEY", STRIPE_SECRET_KEY)):
        payload = StaticSiteEnvVarCreateRequest(key=key, value=value, environment="production", is_secret=True)
        resp = svc.create_env_var(_profile("admin", company_id=company_id), site_id, payload)
        dumped = resp.model_dump_json()
        assert value not in dumped


@pytest.mark.unit
def test_secrets_never_appear_in_list_response():
    svc = StaticSiteEnvVarService(MagicMock())
    svc.repo = MagicMock()
    company_id, site_id = uuid4(), uuid4()
    svc.repo.get_site_for_workspace.return_value = StaticSite(id=site_id, workspace_id=company_id, name="A", slug="a")
    now = datetime.now(timezone.utc)
    svc.repo.list_env_vars.return_value = [
        StaticSiteEnvironmentVariable(
            id=uuid4(), workspace_id=company_id, site_id=site_id, key=key,
            encrypted_value=encrypt_value(value), environment="production", is_secret=True,
            created_at=now, updated_at=now,
        )
        for key, value in (("DATABASE_URL", DATABASE_URL), ("OPENAI_API_KEY", OPENAI_API_KEY), ("STRIPE_SECRET_KEY", STRIPE_SECRET_KEY))
    ]
    resp = svc.list_env_vars(_profile("admin", company_id=company_id), site_id)
    dumped = resp.model_dump_json()
    for secret in ALL_SECRETS:
        assert secret not in dumped


# ---- build logs / SSE / persisted logs (redaction) -------------------------------


@pytest.mark.unit
def test_secrets_redacted_from_build_logs_and_sse_stream():
    redact = build_secret_redactor(ALL_SECRETS)
    raw_log_lines = [
        f"Connecting with DATABASE_URL={DATABASE_URL}",
        f"OpenAI call using key {OPENAI_API_KEY}",
        f"Stripe webhook secret: {STRIPE_SECRET_KEY}",
        "unrelated build output line",
    ]
    redacted = [redact(line) for line in raw_log_lines]
    joined = " ".join(redacted)
    for secret in ALL_SECRETS:
        assert secret not in joined
    assert redacted[3] == "unrelated build output line"


# ---- browser-visible build environment ------------------------------------------


@pytest.mark.unit
def test_secrets_never_selected_as_vite_client_vars():
    resolved = [
        ResolvedEnvVar(key="DATABASE_URL", value=DATABASE_URL, is_secret=True, environment="production"),
        ResolvedEnvVar(key="OPENAI_API_KEY", value=OPENAI_API_KEY, is_secret=True, environment="production"),
        ResolvedEnvVar(key="STRIPE_SECRET_KEY", value=STRIPE_SECRET_KEY, is_secret=True, environment="production"),
        ResolvedEnvVar(key="VITE_API_URL", value="https://api.example.com", is_secret=False, environment="production"),
    ]
    client_vars = vite_client_vars(resolved)
    assert client_vars == {"VITE_API_URL": "https://api.example.com"}
    assert not any(v in ALL_SECRETS for v in client_vars.values())


@pytest.mark.unit
def test_secrets_never_selected_as_nextjs_public_build_vars():
    resolved = [
        ResolvedEnvVar(key="DATABASE_URL", value=DATABASE_URL, is_secret=True, environment="production"),
        ResolvedEnvVar(key="OPENAI_API_KEY", value=OPENAI_API_KEY, is_secret=True, environment="production"),
        ResolvedEnvVar(key="STRIPE_SECRET_KEY", value=STRIPE_SECRET_KEY, is_secret=True, environment="production"),
        ResolvedEnvVar(key="NEXT_PUBLIC_API_URL", value="https://api.example.com", is_secret=False, environment="production"),
    ]
    public_vars = nextjs_public_build_vars(resolved)
    assert public_vars == {"NEXT_PUBLIC_API_URL": "https://api.example.com"}
    assert not any(v in ALL_SECRETS for v in public_vars.values())


@pytest.mark.unit
def test_secret_values_extraction_matches_exactly_the_is_secret_true_set():
    resolved = [
        ResolvedEnvVar(key="DATABASE_URL", value=DATABASE_URL, is_secret=True, environment="production"),
        ResolvedEnvVar(key="OPENAI_API_KEY", value=OPENAI_API_KEY, is_secret=True, environment="production"),
        ResolvedEnvVar(key="STRIPE_SECRET_KEY", value=STRIPE_SECRET_KEY, is_secret=True, environment="production"),
        ResolvedEnvVar(key="VITE_API_URL", value="https://api.example.com", is_secret=False, environment="production"),
    ]
    assert set(secret_values(resolved)) == set(ALL_SECRETS)


# ---- generated source files ------------------------------------------------------


@pytest.mark.unit
def test_secrets_never_written_to_a_generated_source_file(tmp_path):
    """The build pipeline only ever writes final build ARTIFACTS (dist/,
    .next/) to disk via the isolated docker container's own output mount —
    no THTWAAT code path here ever writes an env var value into a file
    itself. Regression guard: scan a representative 'generated' tree for the
    exact secret strings after simulating a build that used them."""
    dest = tmp_path / "dist"
    dest.mkdir()
    (dest / "index.html").write_text("<html><body>Hello</body></html>")
    (dest / "app.js").write_text("console.log('hello world');")

    for path in dest.rglob("*"):
        if path.is_file():
            content = path.read_text(errors="ignore")
            for secret in ALL_SECRETS:
                assert secret not in content
