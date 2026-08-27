"""Unit tests for app.coding_agent.service — Phase 6C-1 service-token minting.

No database or live server needed: mint_service_token() is a pure
function of settings + arguments, and verification here is done with
the same jose.jwt.decode() a real relying party (AI_Project) would use
if it were written in Python with python-jose — proving the token Core
produces is a well-formed, independently-verifiable HS256 JWT.
"""

from __future__ import annotations

import uuid

import pytest
from fastapi import HTTPException
from jose import JWTError, jwt

from app.coding_agent import service as coding_agent_service

SECRET = "unit-test-secret-value-1234567890"
AUDIENCE = "coding-agent"
ISSUER = "thtwaat-core-api"


@pytest.fixture(autouse=True)
def _configure_secret(monkeypatch):
    monkeypatch.setattr(coding_agent_service.settings, "CODING_AGENT_SERVICE_JWT_SECRET", SECRET)
    monkeypatch.setattr(coding_agent_service.settings, "CODING_AGENT_JWT_AUDIENCE", AUDIENCE)
    monkeypatch.setattr(coding_agent_service.settings, "CODING_AGENT_JWT_ISSUER", ISSUER)
    monkeypatch.setattr(coding_agent_service.settings, "CODING_AGENT_SERVICE_TOKEN_TTL_SECONDS", 120)
    yield


@pytest.mark.unit
def test_mint_service_token_has_expected_claims():
    company_id = uuid.uuid4()
    user_id = uuid.uuid4()
    result = coding_agent_service.mint_service_token(company_id=company_id, user_id=user_id)

    assert result.token_type == "bearer"
    assert result.expires_in == 120
    assert result.scope == "coding_agent:access"

    payload = jwt.decode(
        result.access_token, SECRET, algorithms=["HS256"], audience=AUDIENCE, issuer=ISSUER,
    )
    assert payload["company_id"] == str(company_id)
    assert payload["user_id"] == str(user_id)
    assert payload["sub"] == str(user_id)
    assert payload["scope"] == "coding_agent:access"
    assert "jti" in payload
    assert "exp" in payload
    assert "iat" in payload


@pytest.mark.unit
def test_mint_service_token_custom_scopes():
    result = coding_agent_service.mint_service_token(
        company_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        scopes=("coding_agent:access", "coding_agent:link"),
    )
    assert result.scope == "coding_agent:access coding_agent:link"

    payload = jwt.decode(
        result.access_token, SECRET, algorithms=["HS256"], audience=AUDIENCE, issuer=ISSUER,
    )
    assert payload["scope"] == "coding_agent:access coding_agent:link"


@pytest.mark.unit
def test_mint_service_token_fails_closed_when_unconfigured(monkeypatch):
    monkeypatch.setattr(coding_agent_service.settings, "CODING_AGENT_SERVICE_JWT_SECRET", None)
    with pytest.raises(HTTPException) as exc_info:
        coding_agent_service.mint_service_token(company_id=uuid.uuid4(), user_id=uuid.uuid4())
    assert exc_info.value.status_code == 503


@pytest.mark.unit
def test_wrong_secret_fails_verification():
    result = coding_agent_service.mint_service_token(company_id=uuid.uuid4(), user_id=uuid.uuid4())
    with pytest.raises(JWTError):
        jwt.decode(
            result.access_token, "a-completely-different-secret-000000",
            algorithms=["HS256"], audience=AUDIENCE, issuer=ISSUER,
        )


@pytest.mark.unit
def test_wrong_audience_fails_verification():
    result = coding_agent_service.mint_service_token(company_id=uuid.uuid4(), user_id=uuid.uuid4())
    with pytest.raises(JWTError):
        jwt.decode(
            result.access_token, SECRET,
            algorithms=["HS256"], audience="some-other-audience", issuer=ISSUER,
        )


@pytest.mark.unit
def test_expired_token_fails_verification(monkeypatch):
    monkeypatch.setattr(coding_agent_service.settings, "CODING_AGENT_SERVICE_TOKEN_TTL_SECONDS", -10)
    result = coding_agent_service.mint_service_token(company_id=uuid.uuid4(), user_id=uuid.uuid4())
    with pytest.raises(JWTError):
        jwt.decode(
            result.access_token, SECRET, algorithms=["HS256"], audience=AUDIENCE, issuer=ISSUER,
        )
