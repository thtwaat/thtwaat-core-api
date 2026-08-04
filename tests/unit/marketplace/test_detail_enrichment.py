"""Unit tests for Phase 3 template detail enrichment."""
from __future__ import annotations

from types import SimpleNamespace

from app.marketplace.detail_enrichment import (
    derive_feature_keys,
    derive_permissions,
    enrich_detail_fields,
    feature_cards_for,
)
from app.marketplace.schemas import TemplateResponse, TemplateReviewsResponse


def _tpl(**kwargs):
    base = dict(
        supports_agents=True,
        supports_domains=True,
        supports_billing=False,
        tags=["rag", "automation"],
        industry="saas",
        description="A helpful agent template",
        default_config={
            "store": {
                "what_it_does": "Answers support questions",
                "best_for": ["SMB support"],
                "use_cases": ["Ticket deflection"],
                "languages": ["en", "hi"],
                "license": "MIT",
                "quick_start": "Install then open Agents",
                "supported_providers": ["openai"],
            }
        },
        compatibility=None,
    )
    base.update(kwargs)
    return SimpleNamespace(**base)


def test_enrich_detail_fields_from_store_config():
    fields = enrich_detail_fields(_tpl(), bridge={"listing_id": None})
    assert fields["what_it_does"] == "Answers support questions"
    assert fields["best_for"] == ["SMB support"]
    assert "en" in fields["languages"]
    assert fields["license"] == "MIT"
    assert fields["quick_start"]
    assert any(c["key"] == "rag" for c in fields["feature_cards"])


def test_permissions_and_features_from_flags():
    tpl = _tpl(supports_agents=True, supports_domains=True, tags=["webhooks"])
    perms = derive_permissions(tpl, tpl.default_config["store"])
    assert "Agents" in perms
    assert "Widget" in perms
    keys = derive_feature_keys(tpl, tpl.default_config["store"])
    assert "webhooks" in keys or "webhook" in keys or "ai_chat" in keys
    cards = feature_cards_for(["ai_chat", "knowledge_base"])
    assert cards[0]["title"] == "AI Chat"


def test_template_response_accepts_phase3_fields():
    from datetime import datetime, timezone
    from uuid import UUID
    from decimal import Decimal

    now = datetime.now(timezone.utc)
    resp = TemplateResponse(
        id=UUID("00000000-0000-0000-0000-000000000001"),
        slug="demo",
        name="Demo",
        category="saas",
        description="d",
        version="1.0.0",
        author="THTWAAT",
        status="published",
        price=Decimal("0"),
        is_public=True,
        supports_agents=True,
        supports_domains=True,
        supports_billing=False,
        supports_mobile=False,
        created_at=now,
        updated_at=now,
        feature_cards=[{"key": "api", "title": "API", "description": "API access"}],
        permissions=["Agents", "API Keys"],
        languages=["en"],
    )
    assert resp.feature_cards[0]["key"] == "api"
    assert resp.permissions[0] == "Agents"


def test_reviews_response_schema():
    from uuid import UUID

    body = TemplateReviewsResponse(
        template_id=UUID("00000000-0000-0000-0000-000000000001"),
        review_count=0,
        distribution={"1": 0, "2": 0, "3": 0, "4": 0, "5": 0},
        items=[],
    )
    assert body.items == []
