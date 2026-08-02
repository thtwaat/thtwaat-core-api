"""HTTP-level unit tests for iframe embed (no Redis/Postgres required)."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.agent_platform.publish.embed_tokens import mint_embed_token
from app.agent_platform.routers import public_router
from app.database.database import get_db


def _app() -> FastAPI:
    app = FastAPI()
    app.include_router(public_router.router)

    def _db():
        yield MagicMock()

    app.dependency_overrides[get_db] = _db
    return app


@pytest.mark.unit
def test_iframe_http_rejects_live_api_key_query():
    with TestClient(_app()) as client:
        resp = client.get("/public/v1/widget/embed?api_key=tht_live_secretvalue")
    assert resp.status_code == 400
    assert "iframe" in resp.text.lower() or "Live API keys" in resp.text


@pytest.mark.unit
def test_iframe_http_rejects_invalid_token():
    with TestClient(_app()) as client:
        resp = client.get(
            "/public/v1/widget/embed?widget_id=wgt_x&embed_token=bogus"
        )
    assert resp.status_code == 401


@pytest.mark.unit
def test_iframe_http_rejects_expired_token():
    wid = "wgt_expired"
    past = datetime.now(timezone.utc) - timedelta(hours=2)
    token = mint_embed_token(
        widget_id=wid,
        agent_id=uuid.uuid4(),
        company_id=uuid.uuid4(),
        ttl_seconds=30,
        now=past,
    )
    with TestClient(_app()) as client:
        resp = client.get(
            f"/public/v1/widget/embed?widget_id={wid}&embed_token={token}"
        )
    assert resp.status_code == 401


@pytest.mark.unit
def test_iframe_http_success_has_no_live_key_in_html():
    wid = "wgt_ok"
    aid = uuid.uuid4()
    cid = uuid.uuid4()
    token = mint_embed_token(widget_id=wid, agent_id=aid, company_id=cid, ttl_seconds=120)

    with patch.object(
        public_router.PublishService,
        "get_public_widget",
        return_value={
            "widget_id": wid,
            "agent_name": "Bot",
            "status": "PUBLISHED",
            "config": {
                "theme": "light",
                "position": "bottom-right",
                "primary_color": "#111827",
                "agent_name": "Bot",
            },
        },
    ):
        with TestClient(_app()) as client:
            resp = client.get(
                f"/public/v1/widget/embed?widget_id={wid}&embed_token={token}"
            )

    assert resp.status_code == 200
    assert "tht_live_" not in resp.text
    assert "api_key=tht_live_" not in str(resp.request.url)
    assert "tht_embed_" in resp.text
    assert wid in resp.text
    assert "widget.js" in resp.text
