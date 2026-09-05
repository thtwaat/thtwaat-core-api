"""Unit tests for scripts/local_provision_super_admin.py.

Focus areas per the LOCAL-ONLY provisioning helper's safety contract:
  - exact request construction (URLs, payloads, headers) for the three
    endpoints it calls
  - it never touches the invite endpoint's temporary_password
  - printed/returned summaries never leak secret fields
  - it refuses to run against a production (thtwaat.com) host
  - password confirmation logic never leaks the password itself
"""
from __future__ import annotations

import os

import pytest

import scripts.local_provision_super_admin as mod
from scripts.local_provision_super_admin import (
    COMPANY_NAME,
    COMPANY_SLUG,
    PRODUCTION_CONFIRMATION_PHRASE,
    SUPER_ADMIN_EMAIL,
    SUPER_ADMIN_ROLE,
    ProvisioningError,
    assert_not_production,
    auth_headers,
    build_company_payload,
    build_invite_payload,
    build_password_patch_payload,
    confirm_production_execution,
    create_company,
    find_company_by_slug,
    find_user_by_email,
    invite_user,
    is_production_host,
    main,
    parse_args,
    read_new_password,
    set_password,
    summarize_user,
)


# ── Request construction ─────────────────────────────────────────────────────


def test_build_company_payload_matches_company_create_schema():
    payload = build_company_payload()
    assert payload == {"name": COMPANY_NAME, "slug": COMPANY_SLUG}
    # No extra/unexpected fields beyond CompanyCreate's contract.
    assert set(payload.keys()) == {"name", "slug"}


def test_build_invite_payload_matches_admin_invite_schema():
    payload = build_invite_payload("company-123")
    assert payload["email"] == SUPER_ADMIN_EMAIL
    assert payload["company_id"] == "company-123"
    assert payload["role"] == SUPER_ADMIN_ROLE
    assert payload["role"] == "super_admin"
    assert "first_name" in payload and "last_name" in payload


def test_build_password_patch_payload_contains_only_password():
    payload = build_password_patch_payload("s3cr3t-value")
    assert payload == {"password": "s3cr3t-value"}
    assert set(payload.keys()) == {"password"}


def test_auth_headers_shape():
    headers = auth_headers("token-abc")
    assert headers == {"Authorization": "Bearer token-abc"}


# ── Fake httpx client for exercising the HTTP call sites ────────────────────


class _FakeResponse:
    def __init__(self, status_code: int, json_body):
        self.status_code = status_code
        self._json = json_body

    def json(self):
        return self._json

    def raise_for_status(self):
        if self.status_code >= 400:
            raise AssertionError(f"unexpected error status {self.status_code}")


class _RecordingClient:
    """Records call args and returns a scripted response per verb."""

    def __init__(self, response: _FakeResponse):
        self._response = response
        self.calls: list[tuple[str, str, dict]] = []

    def get(self, url, params=None, headers=None):
        self.calls.append(("GET", url, {"params": params, "headers": headers}))
        return self._response

    def post(self, url, json=None, headers=None):
        self.calls.append(("POST", url, {"json": json, "headers": headers}))
        return self._response

    def patch(self, url, json=None, headers=None):
        self.calls.append(("PATCH", url, {"json": json, "headers": headers}))
        return self._response


def test_find_company_by_slug_calls_expected_url_and_returns_none_on_404():
    client = _RecordingClient(_FakeResponse(404, {"detail": "not found"}))
    result = find_company_by_slug(client, "http://localhost:8000/api/v1", "jwt-1", COMPANY_SLUG)
    assert result is None
    method, url, kwargs = client.calls[0]
    assert method == "GET"
    assert url == f"http://localhost:8000/api/v1/companies/slug/{COMPANY_SLUG}"
    assert kwargs["headers"] == {"Authorization": "Bearer jwt-1"}


def test_find_company_by_slug_returns_body_on_200():
    body = {"id": "c-1", "slug": COMPANY_SLUG}
    client = _RecordingClient(_FakeResponse(200, body))
    result = find_company_by_slug(client, "http://localhost:8000/api/v1", "jwt-1", COMPANY_SLUG)
    assert result == body


def test_create_company_posts_to_companies_root_without_auth_header():
    body = {"id": "c-1", "slug": COMPANY_SLUG, "name": COMPANY_NAME}
    client = _RecordingClient(_FakeResponse(201, body))
    result = create_company(client, "http://localhost:8000/api/v1")
    assert result == body
    method, url, kwargs = client.calls[0]
    assert method == "POST"
    assert url == "http://localhost:8000/api/v1/companies/"
    assert kwargs["json"] == {"name": COMPANY_NAME, "slug": COMPANY_SLUG}
    # POST /companies/ is a public endpoint per app/companies/router.py — no auth needed.
    assert "headers" not in kwargs or kwargs["headers"] is None


def test_find_user_by_email_matches_case_insensitively_and_ignores_other_rows():
    body = {
        "results": [
            {"id": "u-0", "email": "someone-else@thtwaat.com"},
            {"id": "u-1", "email": "SuperAdmin@THTWAAT.com"},
        ]
    }
    client = _RecordingClient(_FakeResponse(200, body))
    result = find_user_by_email(
        client, "http://localhost:8000/api/v1", "jwt-1", "c-1", SUPER_ADMIN_EMAIL
    )
    assert result == {"id": "u-1", "email": "SuperAdmin@THTWAAT.com"}
    method, url, kwargs = client.calls[0]
    assert method == "GET"
    assert url == "http://localhost:8000/api/v1/users/"
    assert kwargs["params"]["company_id"] == "c-1"
    assert kwargs["params"]["q"] == SUPER_ADMIN_EMAIL


def test_find_user_by_email_returns_none_when_no_exact_match():
    body = {"results": [{"id": "u-0", "email": "notthesame@thtwaat.com"}]}
    client = _RecordingClient(_FakeResponse(200, body))
    result = find_user_by_email(
        client, "http://localhost:8000/api/v1", "jwt-1", "c-1", SUPER_ADMIN_EMAIL
    )
    assert result is None


def test_invite_user_posts_expected_payload():
    body = {
        "user": {"id": "u-9", "email": SUPER_ADMIN_EMAIL, "role": "super_admin", "company_id": "c-1"},
        "temporary_password": "should-never-be-read-by-caller",
        "note": "...",
    }
    client = _RecordingClient(_FakeResponse(200, body))
    result = invite_user(client, "http://localhost:8000/api/v1", "jwt-1", "c-1")
    method, url, kwargs = client.calls[0]
    assert method == "POST"
    assert url == "http://localhost:8000/api/v1/admin/users/invite"
    assert kwargs["json"] == build_invite_payload("c-1")
    assert kwargs["headers"] == {"Authorization": "Bearer jwt-1"}
    # The function itself may return the full body; callers are responsible
    # for never reading temporary_password out of it (see main()/summarize_user).
    assert result == body


def test_set_password_patches_expected_user_and_never_echoes_password_in_url_or_headers():
    body = {"id": "u-9", "email": SUPER_ADMIN_EMAIL}
    client = _RecordingClient(_FakeResponse(200, body))
    set_password(client, "http://localhost:8000/api/v1", "jwt-1", "u-9", "operator-typed-pw")
    method, url, kwargs = client.calls[0]
    assert method == "PATCH"
    assert url == "http://localhost:8000/api/v1/users/u-9"
    assert kwargs["json"] == {"password": "operator-typed-pw"}
    assert "operator-typed-pw" not in url
    assert "operator-typed-pw" not in str(kwargs["headers"])


# ── Secret-handling behavior ──────────────────────────────────────────────────


def test_summarize_user_strips_secret_and_unexpected_fields():
    raw = {
        "id": "u-9",
        "email": SUPER_ADMIN_EMAIL,
        "role": "super_admin",
        "company_id": "c-1",
        "status": "active",
        "is_active": True,
        "temporary_password": "must-not-appear",
        "hashed_password": "must-not-appear-either",
    }
    safe = summarize_user(raw)
    assert "temporary_password" not in safe
    assert "hashed_password" not in safe
    assert safe == {
        "id": "u-9",
        "email": SUPER_ADMIN_EMAIL,
        "role": "super_admin",
        "company_id": "c-1",
        "status": "active",
        "is_active": True,
    }


def test_summarize_user_handles_missing_optional_fields():
    safe = summarize_user({"id": "u-9", "email": SUPER_ADMIN_EMAIL})
    assert safe == {"id": "u-9", "email": SUPER_ADMIN_EMAIL}


def test_read_new_password_returns_value_without_printing(capsys):
    values = iter(["Sup3rSecret!", "Sup3rSecret!"])
    password = read_new_password(reader=lambda _prompt: next(values))
    assert password == "Sup3rSecret!"
    captured = capsys.readouterr()
    assert "Sup3rSecret!" not in captured.out
    assert "Sup3rSecret!" not in captured.err


def test_read_new_password_rejects_mismatch_then_succeeds(capsys):
    values = iter(["first-try-1", "does-not-match", "Sup3rSecret!", "Sup3rSecret!"])
    password = read_new_password(reader=lambda _prompt: next(values))
    assert password == "Sup3rSecret!"
    captured = capsys.readouterr()
    assert "do not match" in captured.out
    # Neither rejected attempt's plaintext should be printed.
    assert "first-try-1" not in captured.out
    assert "does-not-match" not in captured.out


def test_read_new_password_rejects_too_short(capsys):
    values = iter(["short", "short", "LongEnough1!", "LongEnough1!"])
    password = read_new_password(reader=lambda _prompt: next(values))
    assert password == "LongEnough1!"
    captured = capsys.readouterr()
    assert "at least 8 characters" in captured.out
    assert "short" not in captured.out


# ── Production-host guard ────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "base_url",
    [
        "https://api.thtwaat.com/api/v1",
        "https://thtwaat.com/api/v1",
        "https://developer.thtwaat.com/api/v1",
    ],
)
def test_assert_not_production_blocks_thtwaat_hosts(base_url):
    with pytest.raises(ProvisioningError):
        assert_not_production(base_url)


@pytest.mark.parametrize(
    "base_url",
    [
        "http://localhost:8000/api/v1",
        "http://127.0.0.1:8000/api/v1",
        "http://staging-internal.example.com/api/v1",
    ],
)
def test_assert_not_production_allows_non_production_hosts(base_url):
    assert_not_production(base_url) is None  # does not raise


def test_assert_not_production_raises_on_unparseable_host():
    with pytest.raises(ProvisioningError):
        assert_not_production("not-a-url")


@pytest.mark.parametrize(
    "base_url",
    ["https://api.thtwaat.com/api/v1", "https://thtwaat.com/api/v1"],
)
def test_is_production_host_true_for_thtwaat_hosts(base_url):
    assert is_production_host(base_url) is True


@pytest.mark.parametrize("base_url", ["http://localhost:8000/api/v1", "http://127.0.0.1:8000/api/v1"])
def test_is_production_host_false_for_local_hosts(base_url):
    assert is_production_host(base_url) is False


def test_assert_not_production_allows_production_when_flag_set():
    # allow_production=True lifts this low-level guard; main() still gates
    # the actual run behind an interactive confirmation phrase (see below).
    assert_not_production("https://api.thtwaat.com/api/v1", allow_production=True) is None


# ── --allow-production flag parsing ─────────────────────────────────────────


def test_parse_args_defaults_allow_production_false():
    args = parse_args([])
    assert args.allow_production is False


def test_parse_args_accepts_allow_production_flag():
    args = parse_args(["--allow-production"])
    assert args.allow_production is True


def test_parse_args_has_no_confirmation_phrase_argument():
    # The confirmation phrase must never be accepted as a CLI argument.
    with pytest.raises(SystemExit):
        parse_args(["--confirm", PRODUCTION_CONFIRMATION_PHRASE])


# ── Interactive production confirmation phrase ──────────────────────────────


def test_confirm_production_execution_true_on_exact_match():
    assert confirm_production_execution(reader=lambda _prompt: PRODUCTION_CONFIRMATION_PHRASE) is True


@pytest.mark.parametrize(
    "typed",
    ["", "create thtwaat platform super admin", "CREATE THTWAAT PLATFORM SUPER ADMIN ", "yes", "confirm"],
)
def test_confirm_production_execution_false_on_any_mismatch(typed):
    assert confirm_production_execution(reader=lambda _prompt: typed) is False


def test_confirm_production_execution_ignores_environment_variable(monkeypatch):
    # Even if some unrelated env var happens to hold the right phrase, only
    # the interactive reader's return value can satisfy the confirmation.
    monkeypatch.setenv("SOME_OTHER_CONFIRM_VAR", PRODUCTION_CONFIRMATION_PHRASE)
    assert confirm_production_execution(reader=lambda _prompt: "wrong") is False


def test_confirm_production_execution_prompt_does_not_leak_via_return_value(capsys):
    confirm_production_execution(reader=lambda _prompt: "wrong")
    captured = capsys.readouterr()
    # The phrase itself is intentionally shown (it's not a secret) so the
    # operator can copy it exactly; this asserts nothing else sensitive leaks.
    assert "Bearer " not in captured.out


# ── main(): end-to-end flag/confirmation gating with a fake HTTP client ─────


class _FakeHttpResponse:
    def __init__(self, status_code: int, json_body):
        self.status_code = status_code
        self._json = json_body
        self.request = None

    def json(self):
        return self._json

    def raise_for_status(self):
        if self.status_code >= 400:
            raise AssertionError(f"unexpected HTTP {self.status_code} in test")


class _FakeHttpClient:
    """Minimal stand-in for httpx.Client used as a context manager in main()."""

    def __init__(self, *_args, **_kwargs):
        self.calls: list[tuple[str, str]] = []

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False

    def get(self, url, params=None, headers=None):
        self.calls.append(("GET", url))
        if url.endswith(f"/companies/slug/{COMPANY_SLUG}"):
            return _FakeHttpResponse(200, {"id": "c-1", "slug": COMPANY_SLUG, "name": COMPANY_NAME})
        if url.endswith("/users/"):
            return _FakeHttpResponse(200, {"results": []})
        raise AssertionError(f"unexpected GET {url}")

    def post(self, url, json=None, headers=None):
        self.calls.append(("POST", url))
        if url.endswith("/admin/users/invite"):
            return _FakeHttpResponse(
                200,
                {
                    "user": {
                        "id": "u-9",
                        "email": SUPER_ADMIN_EMAIL,
                        "role": SUPER_ADMIN_ROLE,
                        "company_id": "c-1",
                    },
                    "temporary_password": "must-never-reach-stdout",
                    "note": "...",
                },
            )
        raise AssertionError(f"unexpected POST {url}")

    def patch(self, url, json=None, headers=None):
        self.calls.append(("PATCH", url))
        return _FakeHttpResponse(200, {"id": "u-9", "email": SUPER_ADMIN_EMAIL})


class _ClientMustNotBeConstructed:
    def __init__(self, *_args, **_kwargs):
        raise AssertionError("httpx.Client must not be constructed before confirmation succeeds")


def _stub_common(monkeypatch, *, base_url: str, jwt: str = "test-jwt-value.abc"):
    monkeypatch.setattr(mod, "resolve_base_url", lambda: base_url)
    monkeypatch.setattr(mod, "resolve_jwt", lambda: jwt)
    monkeypatch.setattr(mod, "read_new_password", lambda: "OperatorPassw0rd!")


def test_main_blocks_production_without_allow_production_flag(monkeypatch, capsys):
    _stub_common(monkeypatch, base_url="https://api.thtwaat.com/api/v1")
    monkeypatch.setattr(mod.httpx, "Client", _ClientMustNotBeConstructed)

    rc = main([])

    assert rc == 1
    out = capsys.readouterr().out
    assert "--allow-production" in out


def test_main_blocks_production_confirmation_prompt_never_reached_without_flag(monkeypatch):
    # Guards against a regression where confirmation runs before the flag check.
    called = {"confirm": False}

    def _fake_confirm():
        called["confirm"] = True
        return True

    _stub_common(monkeypatch, base_url="https://api.thtwaat.com/api/v1")
    monkeypatch.setattr(mod, "confirm_production_execution", _fake_confirm)
    monkeypatch.setattr(mod.httpx, "Client", _ClientMustNotBeConstructed)

    rc = main([])

    assert rc == 1
    assert called["confirm"] is False


def test_main_aborts_on_wrong_confirmation_before_any_api_call(monkeypatch, capsys):
    _stub_common(monkeypatch, base_url="https://api.thtwaat.com/api/v1")
    monkeypatch.setattr(mod, "confirm_production_execution", lambda: False)
    monkeypatch.setattr(mod.httpx, "Client", _ClientMustNotBeConstructed)

    rc = main(["--allow-production"])

    assert rc == 1
    assert "Aborting before any API call" in capsys.readouterr().out


def test_main_proceeds_against_production_after_flag_and_exact_confirmation(monkeypatch, capsys):
    fake_client = _FakeHttpClient()
    _stub_common(monkeypatch, base_url="https://api.thtwaat.com/api/v1")
    monkeypatch.setattr(mod, "confirm_production_execution", lambda: True)
    monkeypatch.setattr(mod.httpx, "Client", lambda *a, **k: fake_client)

    rc = main(["--allow-production"])

    assert rc == 0
    # It actually reached the API calls this time.
    methods_and_urls = fake_client.calls
    assert ("GET", "https://api.thtwaat.com/api/v1/companies/slug/thtwaat-platform") in methods_and_urls
    assert ("POST", "https://api.thtwaat.com/api/v1/admin/users/invite") in methods_and_urls
    assert ("PATCH", "https://api.thtwaat.com/api/v1/users/u-9") in methods_and_urls


def test_main_production_flow_never_prints_jwt_password_or_temporary_password(monkeypatch, capsys):
    fake_client = _FakeHttpClient()
    jwt_value = "super-secret-jwt-token-value"
    password_value = "OperatorChosenPassw0rd!"
    _stub_common(monkeypatch, base_url="https://api.thtwaat.com/api/v1", jwt=jwt_value)
    monkeypatch.setattr(mod, "read_new_password", lambda: password_value)
    monkeypatch.setattr(mod, "confirm_production_execution", lambda: True)
    monkeypatch.setattr(mod.httpx, "Client", lambda *a, **k: fake_client)

    rc = main(["--allow-production"])

    assert rc == 0
    captured = capsys.readouterr()
    combined = captured.out + captured.err
    assert jwt_value not in combined
    assert password_value not in combined
    assert "must-never-reach-stdout" not in combined  # the invite temporary_password


def test_main_allow_production_flag_is_noop_for_local_host(monkeypatch, capsys):
    fake_client = _FakeHttpClient()
    _stub_common(monkeypatch, base_url="http://localhost:8000/api/v1")
    monkeypatch.setattr(mod.httpx, "Client", lambda *a, **k: fake_client)

    rc = main(["--allow-production"])

    assert rc == 0
    assert "no effect against a non-production host" in capsys.readouterr().out
