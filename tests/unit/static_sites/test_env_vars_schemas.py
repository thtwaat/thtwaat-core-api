"""Unit tests for environment-variable key/value/environment validation in
app/static_sites/schemas.py — pure Pydantic validation, no DB/HTTP."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.static_sites.schemas import StaticSiteEnvVarCreateRequest, StaticSiteEnvVarUpdateRequest


@pytest.mark.unit
@pytest.mark.parametrize(
    "key",
    ["OPENAI_API_KEY", "DATABASE_URL", "NEXT_PUBLIC_API_URL", "VITE_API_URL", "_LEADING_UNDERSCORE", "A"],
)
def test_valid_keys_accepted(key):
    req = StaticSiteEnvVarCreateRequest(key=key, value="v", environment="production")
    assert req.key == key


@pytest.mark.unit
@pytest.mark.parametrize(
    "key",
    [
        "my key",
        "FOO-BAR",
        "FOO BAR",
        "FOO;rm",
        "$(command)",
        "FOO\nBAR",
        "foo_bar",  # lowercase not allowed by ^[A-Z_][A-Z0-9_]*$
        "1FOO",  # cannot start with a digit
        "",
        "FOO\x00BAR",
    ],
)
def test_invalid_keys_rejected(key):
    with pytest.raises(ValidationError):
        StaticSiteEnvVarCreateRequest(key=key, value="v", environment="production")


@pytest.mark.unit
def test_preview_environment_accepted():
    # THTWAAT Deploy Phase 6A adds "preview" as a valid environment tag —
    # see app/static_sites/models.py's StaticSiteEnvironmentVariable
    # docstring, which reserved this value for exactly this phase.
    req = StaticSiteEnvVarCreateRequest(key="FOO", value="v", environment="preview")
    assert req.environment == "preview"


@pytest.mark.unit
def test_invalid_environment_staging_rejected():
    with pytest.raises(ValidationError):
        StaticSiteEnvVarCreateRequest(key="FOO", value="v", environment="staging")


@pytest.mark.unit
@pytest.mark.parametrize("environment", ["production", "development", "preview"])
def test_allowed_environments_accepted(environment):
    req = StaticSiteEnvVarCreateRequest(key="FOO", value="v", environment=environment)
    assert req.environment == environment


@pytest.mark.unit
def test_empty_value_rejected():
    with pytest.raises(ValidationError):
        StaticSiteEnvVarCreateRequest(key="FOO", value="", environment="production")


@pytest.mark.unit
def test_value_with_null_byte_rejected():
    with pytest.raises(ValidationError):
        StaticSiteEnvVarCreateRequest(key="FOO", value="abc\x00def", environment="production")


@pytest.mark.unit
def test_value_is_never_interpreted_as_shell_syntax():
    # Shell-metacharacter-laden values are opaque data and must be accepted
    # verbatim, not parsed/executed or rejected for looking "shell-like".
    raw = "$(rm -rf /); echo pwned && `whoami` | cat"
    req = StaticSiteEnvVarCreateRequest(key="FOO", value=raw, environment="production")
    assert req.value == raw


@pytest.mark.unit
def test_update_request_allows_partial_fields():
    req = StaticSiteEnvVarUpdateRequest()
    assert req.value is None
    assert req.is_secret is None


@pytest.mark.unit
def test_update_request_rejects_null_byte_value():
    with pytest.raises(ValidationError):
        StaticSiteEnvVarUpdateRequest(value="abc\x00def")


@pytest.mark.unit
def test_update_request_has_no_key_or_environment_fields():
    # Key identity/environment are immutable after creation — delete/create
    # instead of renaming/moving (Phase 4A spec §8).
    assert "key" not in StaticSiteEnvVarUpdateRequest.model_fields
    assert "environment" not in StaticSiteEnvVarUpdateRequest.model_fields
