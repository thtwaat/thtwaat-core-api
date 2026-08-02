"""Phase 1 marketplace schema / contract unit tests (no DB required)."""

from app.marketplace.models import (
    PricingTier,
    TemplateCategory,
    TemplateFavorite,
    TemplateKind,
    MarketplaceTemplate,
)
from app.marketplace.schemas import TemplateCreate, TemplateResponse
from app.marketplace.service import CATEGORY_LABELS, _parse_category, _parse_kind, _parse_pricing_tier


def test_phase1_categories_include_prompt_verticals():
    for slug in ("writing", "coding", "marketing", "hr", "research", "ai_agents", "business", "analytics"):
        assert slug in CATEGORY_LABELS
        assert _parse_category(slug) == TemplateCategory(slug)


def test_kind_and_pricing_tier_parsers():
    assert _parse_kind("prompt") is TemplateKind.PROMPT
    assert _parse_kind(None) is TemplateKind.PACKAGE
    assert _parse_pricing_tier("pro") is PricingTier.PRO
    assert _parse_pricing_tier(None) is PricingTier.FREE


def test_template_create_schema_accepts_kind_and_tier():
    payload = TemplateCreate(
        slug="blog-writer-pro",
        name="Blog Writer",
        category="writing",
        kind="prompt",
        pricing_tier="starter",
        default_config={
            "prompt": "Write a blog about {{topic}}",
            "variables": [{"name": "topic", "required": True}],
            "temperature": 0.7,
        },
    )
    assert payload.kind == "prompt"
    assert payload.pricing_tier == "starter"
    assert payload.default_config["temperature"] == 0.7


def test_template_response_defaults_kind_and_favorite():
    from datetime import datetime, timezone
    from uuid import UUID

    now = datetime.now(timezone.utc)
    resp = TemplateResponse(
        id=UUID("00000000-0000-0000-0000-000000000001"),
        slug="x",
        name="X",
        category="saas",
        description="",
        version="1.0.0",
        author="THTWAAT",
        status="published",
        price=0,
        is_public=True,
        supports_agents=True,
        supports_domains=True,
        supports_billing=False,
        supports_mobile=False,
        created_at=now,
        updated_at=now,
    )
    assert resp.kind == "package"
    assert resp.pricing_tier == "free"
    assert resp.is_favorited is False


def test_favorite_and_template_model_tables():
    assert TemplateFavorite.__tablename__ == "marketplace_template_favorites"
    assert "kind" in MarketplaceTemplate.__table__.c
    assert "pricing_tier" in MarketplaceTemplate.__table__.c
