"""Unit tests for app/static_sites/github_client.py — the GitHub App API
client. No network access: httpx.AsyncClient is monkeypatched with a fake
that returns canned responses and records what was requested."""
from __future__ import annotations

import time

import httpx
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import HTTPException
from jose import jwt as jose_jwt

from app.static_sites import github_client


def _rsa_private_key_pem() -> str:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")


@pytest.fixture
def configured_app(monkeypatch):
    pem = _rsa_private_key_pem()
    monkeypatch.setattr(github_client.settings, "GITHUB_APP_ID", "123456")
    monkeypatch.setattr(github_client.settings, "GITHUB_APP_SLUG", "thtwaat-deploy")
    monkeypatch.setattr(github_client.settings, "GITHUB_APP_PRIVATE_KEY", pem)
    return pem


class _FakeAsyncClient:
    def __init__(self, response, calls):
        self._response = response
        self._calls = calls

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def get(self, url, headers=None):
        self._calls.append(("GET", url, headers))
        return self._response

    async def post(self, url, headers=None):
        self._calls.append(("POST", url, headers))
        return self._response


def _install_fake_client(monkeypatch, response, calls):
    monkeypatch.setattr(github_client.httpx, "AsyncClient", lambda timeout=None: _FakeAsyncClient(response, calls))


# ---- configuration ----------------------------------------------------------


@pytest.mark.unit
def test_app_not_configured_by_default(monkeypatch):
    monkeypatch.setattr(github_client.settings, "GITHUB_APP_ID", None)
    monkeypatch.setattr(github_client.settings, "GITHUB_APP_SLUG", None)
    monkeypatch.setattr(github_client.settings, "GITHUB_APP_PRIVATE_KEY", None)
    assert github_client.app_configured() is False
    with pytest.raises(HTTPException) as exc:
        github_client.require_app_configured()
    assert exc.value.status_code == 503


@pytest.mark.unit
def test_app_configured_when_all_three_set(configured_app):
    assert github_client.app_configured() is True


@pytest.mark.unit
def test_build_installation_url_embeds_slug_and_state(configured_app):
    url = github_client.build_installation_url(state="raw-state-value")
    assert url.startswith("https://github.com/apps/thtwaat-deploy/installations/new?state=")
    assert "raw-state-value" in url


# ---- state ------------------------------------------------------------------


@pytest.mark.unit
def test_new_state_is_random_and_long():
    a, b = github_client.new_state(), github_client.new_state()
    assert a != b
    assert len(a) >= 32


@pytest.mark.unit
def test_hash_state_is_deterministic_sha256_and_never_equals_raw_state():
    raw = "some-state-value"
    h1 = github_client.hash_state(raw)
    h2 = github_client.hash_state(raw)
    assert h1 == h2
    assert h1 != raw
    assert len(h1) == 64  # sha256 hex digest length


# ---- SSRF / path-segment validation -----------------------------------------


@pytest.mark.unit
@pytest.mark.parametrize(
    "value",
    [
        "../etc/passwd",
        "owner/../../secret",
        "repo\r\nHost: evil.com",
        "repo name with spaces",
        "",
        "a" * 200,
        "https://evil.com",
        "owner/repo",
    ],
)
def test_validate_path_segment_rejects_ssrf_and_traversal_payloads(value):
    with pytest.raises(HTTPException) as exc:
        github_client.validate_path_segment(value, field="repository name")
    assert exc.value.status_code == 400


@pytest.mark.unit
@pytest.mark.parametrize("value", ["my-repo", "my_repo.js", "Org.Name-2"])
def test_validate_path_segment_accepts_normal_github_names(value):
    assert github_client.validate_path_segment(value, field="repository name") == value


# ---- app JWT ------------------------------------------------------------------


@pytest.mark.unit
def test_app_jwt_claims_are_well_formed(configured_app):
    token = github_client._app_jwt()
    claims = jose_jwt.get_unverified_claims(token)
    assert claims["iss"] == "123456"
    now = int(time.time())
    assert claims["iat"] <= now
    assert claims["exp"] <= now + 600  # GitHub's hard cap
    assert claims["exp"] > now


@pytest.mark.unit
def test_app_jwt_fails_closed_with_invalid_key(monkeypatch):
    monkeypatch.setattr(github_client.settings, "GITHUB_APP_ID", "123456")
    monkeypatch.setattr(github_client.settings, "GITHUB_APP_SLUG", "thtwaat-deploy")
    monkeypatch.setattr(github_client.settings, "GITHUB_APP_PRIVATE_KEY", "not-a-real-pem-key")
    with pytest.raises(HTTPException) as exc:
        github_client._app_jwt()
    assert exc.value.status_code == 503
    assert "not-a-real-pem-key" not in str(exc.value.detail)


# ---- response mapping / error handling --------------------------------------


@pytest.mark.unit
@pytest.mark.parametrize(
    "status_code,expected_status",
    [(401, 403), (403, 403), (404, 404), (429, 429), (500, 503), (502, 503), (400, 400)],
)
async def test_get_installation_maps_github_status_codes(
    monkeypatch, configured_app, status_code, expected_status
):
    response = httpx.Response(status_code=status_code, json={"message": "whatever github said"})
    calls = []
    _install_fake_client(monkeypatch, response, calls)

    with pytest.raises(HTTPException) as exc:
        await github_client.get_installation("999")
    assert exc.value.status_code == expected_status
    # GitHub's raw response body must never be echoed back to our caller.
    assert "whatever github said" not in str(exc.value.detail)


@pytest.mark.unit
async def test_get_installation_success_returns_parsed_json(monkeypatch, configured_app):
    response = httpx.Response(
        status_code=200,
        json={"id": 42, "account": {"login": "octocat", "id": 1, "type": "User"}},
    )
    calls = []
    _install_fake_client(monkeypatch, response, calls)

    data = await github_client.get_installation("42")
    assert data["account"]["login"] == "octocat"
    assert calls[0][0] == "GET"
    assert calls[0][1] == "https://api.github.com/app/installations/42"


@pytest.mark.unit
async def test_mint_installation_token_returns_token_and_never_logs_it(monkeypatch, configured_app, caplog):
    response = httpx.Response(status_code=201, json={"token": "ghs_supersecrettoken123"})
    calls = []
    _install_fake_client(monkeypatch, response, calls)

    token = await github_client.mint_installation_token("42")
    assert token == "ghs_supersecrettoken123"
    assert "ghs_supersecrettoken123" not in caplog.text


@pytest.mark.unit
async def test_mint_installation_token_missing_token_field_raises_503(monkeypatch, configured_app):
    response = httpx.Response(status_code=201, json={})
    calls = []
    _install_fake_client(monkeypatch, response, calls)

    with pytest.raises(HTTPException) as exc:
        await github_client.mint_installation_token("42")
    assert exc.value.status_code == 503


@pytest.mark.unit
async def test_get_repository_rejects_invalid_owner_before_any_request(monkeypatch, configured_app):
    calls = []
    response = httpx.Response(status_code=200, json={})
    _install_fake_client(monkeypatch, response, calls)

    with pytest.raises(HTTPException) as exc:
        await github_client.get_repository("token", "../evil", "repo")
    assert exc.value.status_code == 400
    assert calls == [], "an invalid owner must never reach an outbound HTTP call"


@pytest.mark.unit
async def test_list_branches_returns_bare_list(monkeypatch, configured_app):
    response = httpx.Response(
        status_code=200, json=[{"name": "main", "protected": True}, {"name": "dev", "protected": False}]
    )
    calls = []
    _install_fake_client(monkeypatch, response, calls)

    branches = await github_client.list_branches("token", "octocat", "hello-world")
    assert [b["name"] for b in branches] == ["main", "dev"]
    assert "octocat/hello-world/branches" in calls[0][1]


@pytest.mark.unit
async def test_installation_token_never_appears_in_authorization_of_app_jwt_calls(monkeypatch, configured_app):
    """get_installation/mint_installation_token authenticate as the APP
    (JWT), not with an installation token — assert the Authorization header
    actually carries a JWT-shaped value, not a raw installation token."""
    response = httpx.Response(status_code=200, json={"account": {"login": "x", "id": 1}})
    calls = []
    _install_fake_client(monkeypatch, response, calls)

    await github_client.get_installation("1")
    auth_header = calls[0][2]["Authorization"]
    assert auth_header.startswith("Bearer ")
    token_part = auth_header.split(" ", 1)[1]
    # A JWT has three dot-separated segments; a GitHub installation token does not.
    assert token_part.count(".") == 2


@pytest.mark.unit
async def test_network_failure_maps_to_503(monkeypatch, configured_app):
    class _BoomClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        async def get(self, url, headers=None):
            raise httpx.ConnectTimeout("boom")

    monkeypatch.setattr(github_client.httpx, "AsyncClient", lambda timeout=None: _BoomClient())

    with pytest.raises(HTTPException) as exc:
        await github_client.get_installation("1")
    assert exc.value.status_code == 503
