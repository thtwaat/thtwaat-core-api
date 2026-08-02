"""P0: iframe embeds must not leak live API keys in URLs."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from app.agent_platform.publish.embed_tokens import (
    EMBED_TOKEN_PREFIX,
    format_embed_credential,
    mint_embed_token,
    verify_embed_token,
)
from app.agent_platform.publish.service import PublishService, KEY_PREFIX


@pytest.mark.unit
def test_mint_and_verify_embed_token():
    wid = "wgt_abc"
    aid = uuid.uuid4()
    cid = uuid.uuid4()
    token = mint_embed_token(widget_id=wid, agent_id=aid, company_id=cid, ttl_seconds=60)
    claims = verify_embed_token(token)
    assert claims["wid"] == wid
    assert claims["aid"] == str(aid)
    assert claims["cid"] == str(cid)


@pytest.mark.unit
def test_embed_token_expires():
    wid = "wgt_exp"
    aid = uuid.uuid4()
    cid = uuid.uuid4()
    past = datetime.now(timezone.utc) - timedelta(hours=2)
    token = mint_embed_token(
        widget_id=wid,
        agent_id=aid,
        company_id=cid,
        ttl_seconds=60,
        now=past,
    )
    with pytest.raises(HTTPException) as exc:
        verify_embed_token(token)
    assert exc.value.status_code == 401
    assert "expired" in str(exc.value.detail).lower() or "invalid" in str(exc.value.detail).lower()


@pytest.mark.unit
def test_invalid_embed_token_rejected():
    with pytest.raises(HTTPException) as exc:
        verify_embed_token("not-a-real-jwt")
    assert exc.value.status_code == 401


@pytest.mark.unit
def test_iframe_url_contains_no_api_key():
    svc = PublishService(db=MagicMock())
    wid = "wgt_no_key"
    aid = uuid.uuid4()
    cid = uuid.uuid4()
    url = svc.build_iframe_url(wid, agent_id=aid, company_id=cid)
    assert "api_key=" not in url
    assert "tht_live_" not in url
    assert f"widget_id={wid}" in url
    assert "embed_token=" in url


@pytest.mark.unit
def test_script_tag_embed_still_uses_data_api_key():
    svc = PublishService(db=MagicMock())
    key = f"{KEY_PREFIX}examplekey123"
    script = svc.build_embed_script(key)
    assert "widget.js" in script
    assert f'data-api-key="{key}"' in script
    assert "api_key=" not in script  # not a URL query


@pytest.mark.unit
def test_format_embed_credential_prefix():
    raw = mint_embed_token(
        widget_id="wgt_x",
        agent_id=uuid.uuid4(),
        company_id=uuid.uuid4(),
        ttl_seconds=30,
    )
    cred = format_embed_credential(raw)
    assert cred.startswith(EMBED_TOKEN_PREFIX)
    assert format_embed_credential(cred) == cred
