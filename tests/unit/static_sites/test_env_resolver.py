"""Unit tests for app/static_sites/env_resolver.py — snapshot/resolve/split
logic for THTWAAT Deploy Phase 4B. Functions take a StaticSiteRepository
directly (dependency injection, same instance StaticSiteService already
uses for deployment CRUD) so a MagicMock stands in for it — no real
database required."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from app.static_sites import env_resolver
from app.static_sites.env_crypto import EnvVarCryptoError, encrypt_value
from app.static_sites.env_resolver import (
    EnvVarResolutionError,
    ResolvedEnvVar,
    clone_env_var_snapshot,
    nextjs_public_build_vars,
    nextjs_server_runtime_vars,
    resolve_deployment_env_vars,
    secret_values,
    snapshot_env_vars,
    vite_client_vars,
)

SECRET_PLAINTEXT = "SUPER_SECRET_123456"


def _live_row(key, value, *, environment="production", is_secret=True):
    return SimpleNamespace(key=key, encrypted_value=encrypt_value(value), environment=environment, is_secret=is_secret)


def _snapshot_row(key, value, *, environment="production", is_secret=True):
    return SimpleNamespace(key=key, encrypted_value=encrypt_value(value), environment=environment, is_secret=is_secret)


@pytest.fixture
def fake_repo():
    return MagicMock()


# ---- snapshotting ------------------------------------------------------------


@pytest.mark.unit
def test_snapshot_copies_ciphertext_verbatim_without_decrypting(fake_repo):
    live = [_live_row("DATABASE_URL", "postgres://prod"), _live_row("VITE_API_URL", "https://api", is_secret=False)]
    fake_repo.list_env_vars.return_value = live
    fake_repo.create_deployment_env_var_snapshot.side_effect = lambda rows: rows

    deployment_id = uuid4()
    snapshot_env_vars(fake_repo, deployment_id=deployment_id, workspace_id=uuid4(), site_id=uuid4(), environment="production")

    inserted = fake_repo.create_deployment_env_var_snapshot.call_args[0][0]
    assert len(inserted) == 2
    for src, dst in zip(live, inserted):
        assert dst.encrypted_value == src.encrypted_value  # copied, not re-encrypted
        assert dst.deployment_id == deployment_id


@pytest.mark.unit
def test_snapshot_scoped_to_single_environment(fake_repo):
    fake_repo.list_env_vars.return_value = []
    fake_repo.create_deployment_env_var_snapshot.side_effect = lambda rows: rows
    site_id = uuid4()
    workspace_id = uuid4()

    snapshot_env_vars(fake_repo, deployment_id=uuid4(), workspace_id=workspace_id, site_id=site_id, environment="development")

    fake_repo.list_env_vars.assert_called_once_with(site_id, workspace_id, environment="development")


# ---- resolution (decrypt) ----------------------------------------------------


@pytest.mark.unit
def test_resolve_deployment_env_vars_decrypts_snapshot(fake_repo):
    fake_repo.list_deployment_env_var_snapshot.return_value = [
        _snapshot_row("OPENAI_API_KEY", SECRET_PLAINTEXT),
        _snapshot_row("VITE_API_URL", "https://api.example.com", is_secret=False),
    ]
    resolved = resolve_deployment_env_vars(fake_repo, deployment_id=uuid4())
    values = {r.key: r.value for r in resolved}
    assert values["OPENAI_API_KEY"] == SECRET_PLAINTEXT
    assert values["VITE_API_URL"] == "https://api.example.com"


@pytest.mark.unit
def test_resolve_fails_closed_on_undecryptable_row(fake_repo):
    bad_row = SimpleNamespace(key="BROKEN", encrypted_value="not-a-real-token", environment="production", is_secret=True)
    fake_repo.list_deployment_env_var_snapshot.return_value = [bad_row]
    with pytest.raises(EnvVarResolutionError) as exc:
        resolve_deployment_env_vars(fake_repo, deployment_id=uuid4())
    assert "BROKEN" in str(exc.value)


@pytest.mark.unit
def test_resolve_fails_closed_never_returns_partial_set(fake_repo):
    """One bad row among several good ones must fail the WHOLE resolution —
    never silently drop the bad one and return the rest (Phase 4B spec §16)."""
    bad_row = SimpleNamespace(key="BROKEN", encrypted_value="not-a-real-token", environment="production", is_secret=True)
    fake_repo.list_deployment_env_var_snapshot.return_value = [
        _snapshot_row("GOOD_ONE", "value"),
        bad_row,
    ]
    with pytest.raises(EnvVarResolutionError):
        resolve_deployment_env_vars(fake_repo, deployment_id=uuid4())


@pytest.mark.unit
def test_resolve_rejects_too_many_vars(fake_repo):
    fake_repo.list_deployment_env_var_snapshot.return_value = [
        _snapshot_row(f"KEY_{i}", "v") for i in range(env_resolver.MAX_ENV_VARS_PER_DEPLOYMENT + 1)
    ]
    with pytest.raises(EnvVarResolutionError):
        resolve_deployment_env_vars(fake_repo, deployment_id=uuid4())


# ---- rollback cloning ---------------------------------------------------------


@pytest.mark.unit
def test_clone_snapshot_copies_from_target_to_new_deployment(fake_repo):
    from_id, to_id = uuid4(), uuid4()
    fake_repo.list_deployment_env_var_snapshot.return_value = [_snapshot_row("DATABASE_URL", "A")]
    fake_repo.create_deployment_env_var_snapshot.side_effect = lambda rows: rows

    clone_env_var_snapshot(fake_repo, from_deployment_id=from_id, to_deployment_id=to_id)

    fake_repo.list_deployment_env_var_snapshot.assert_called_once_with(from_id)
    inserted = fake_repo.create_deployment_env_var_snapshot.call_args[0][0]
    assert inserted[0].deployment_id == to_id


# ---- public/private split -----------------------------------------------------


@pytest.mark.unit
def test_vite_client_vars_only_vite_prefix():
    resolved = [
        ResolvedEnvVar(key="VITE_API_URL", value="https://api", is_secret=False, environment="production"),
        ResolvedEnvVar(key="DATABASE_URL", value="postgres://x", is_secret=True, environment="production"),
    ]
    assert vite_client_vars(resolved) == {"VITE_API_URL": "https://api"}


@pytest.mark.unit
def test_nextjs_public_build_vars_only_next_public_prefix():
    resolved = [
        ResolvedEnvVar(key="NEXT_PUBLIC_API_URL", value="https://api", is_secret=False, environment="production"),
        ResolvedEnvVar(key="STRIPE_SECRET_KEY", value="sk_live_x", is_secret=True, environment="production"),
    ]
    assert nextjs_public_build_vars(resolved) == {"NEXT_PUBLIC_API_URL": "https://api"}


@pytest.mark.unit
def test_nextjs_server_runtime_vars_includes_everything():
    resolved = [
        ResolvedEnvVar(key="NEXT_PUBLIC_API_URL", value="https://api", is_secret=False, environment="production"),
        ResolvedEnvVar(key="STRIPE_SECRET_KEY", value="sk_live_x", is_secret=True, environment="production"),
    ]
    server_vars = nextjs_server_runtime_vars(resolved)
    assert server_vars == {"NEXT_PUBLIC_API_URL": "https://api", "STRIPE_SECRET_KEY": "sk_live_x"}


@pytest.mark.unit
def test_secret_values_only_includes_is_secret_true():
    resolved = [
        ResolvedEnvVar(key="OPENAI_API_KEY", value=SECRET_PLAINTEXT, is_secret=True, environment="production"),
        ResolvedEnvVar(key="VITE_API_URL", value="https://api", is_secret=False, environment="production"),
    ]
    assert secret_values(resolved) == [SECRET_PLAINTEXT]
