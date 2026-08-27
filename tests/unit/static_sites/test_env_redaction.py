"""Unit tests for app/static_sites/env_redaction.py — exact-value secret
redaction for THTWAAT Deploy Phase 4B deployment logs."""
from __future__ import annotations

import pytest

from app.static_sites.env_redaction import REDACTED_PLACEHOLDER, build_secret_redactor, redact_lines


@pytest.mark.unit
def test_redacts_secret_value_regardless_of_surrounding_text():
    redact = build_secret_redactor(["sk_live_123456"])
    assert redact("Using key sk_live_123456") == f"Using key {REDACTED_PLACEHOLDER}"


@pytest.mark.unit
def test_redacts_multiple_occurrences():
    redact = build_secret_redactor(["sk_live_123456"])
    line = "key=sk_live_123456 again sk_live_123456"
    assert "sk_live_123456" not in redact(line)


@pytest.mark.unit
def test_redacts_across_multiple_distinct_secrets():
    redact = build_secret_redactor(["postgres://super-secret", "super-secret-api-key", "super-secret-stripe-key"])
    line = "DATABASE_URL=postgres://super-secret OPENAI_API_KEY=super-secret-api-key STRIPE_SECRET_KEY=super-secret-stripe-key"
    result = redact(line)
    assert "postgres://super-secret" not in result
    assert "super-secret-api-key" not in result
    assert "super-secret-stripe-key" not in result
    assert result.count(REDACTED_PLACEHOLDER) == 3


@pytest.mark.unit
def test_longest_secret_wins_when_one_is_a_substring_of_another():
    redact = build_secret_redactor(["secret", "secret-extended-value"])
    assert redact("token=secret-extended-value") == f"token={REDACTED_PLACEHOLDER}"


@pytest.mark.unit
def test_non_secret_public_values_are_not_redacted():
    redact = build_secret_redactor(["sk_live_123456"])
    assert redact("VITE_API_URL=https://api.example.com") == "VITE_API_URL=https://api.example.com"


@pytest.mark.unit
def test_empty_secret_list_is_a_no_op():
    redact = build_secret_redactor([])
    assert redact("anything at all") == "anything at all"


@pytest.mark.unit
def test_very_short_secret_is_not_redacted_to_avoid_mangling_logs():
    redact = build_secret_redactor(["ab"])
    assert redact("grab a coffee") == "grab a coffee"


@pytest.mark.unit
def test_redact_lines_applies_to_every_line():
    redact = build_secret_redactor(["sk_live_123456"])
    lines = ["normal line", "Using key sk_live_123456", "another normal line"]
    result = redact_lines(lines, redact)
    assert result[0] == "normal line"
    assert "sk_live_123456" not in result[1]
    assert result[2] == "another normal line"


@pytest.mark.unit
def test_redact_lines_handles_empty_list():
    redact = build_secret_redactor(["sk_live_123456"])
    assert redact_lines([], redact) == []


@pytest.mark.unit
def test_redactor_repr_never_leaks_secret():
    redact = build_secret_redactor(["sk_live_123456"])
    assert "sk_live_123456" not in repr(redact)
    assert "sk_live_123456" not in str(redact)
