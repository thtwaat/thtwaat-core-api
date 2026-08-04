"""Unit tests for Store Home contracts (no DB required)."""

from decimal import Decimal
from datetime import datetime, timezone
from uuid import UUID

from app.marketplace.models import (
    MarketplaceCategoryMeta,
    MarketplaceCollection,
    MarketplaceCollectionItem,
    MarketplaceTemplate,
    MarketplaceTemplateEvent,
    TemplateCategory,
)
from app.marketplace.schemas import CategoryItem, CollectionCreate, MarketplaceHomeResponse, TemplateResponse
from app.marketplace.service import CATEGORY_LABELS, DEFAULT_CATEGORY_ICONS, MarketplaceService, _parse_category


def test_store_home_categories_include_new_verticals():
    for slug in (
        "insurance",
        "government",
        "travel",
        "retail",
        "manufacturing",
        "sales",
        "erp",
        "bi",
        "devops",
        "security",
        "news",
        "media",
        "startup",
        "productivity",
        "automation",
        "multilingual",
    ):
        assert slug in CATEGORY_LABELS
        assert slug in DEFAULT_CATEGORY_ICONS
        assert _parse_category(slug) == TemplateCategory(slug)


def test_pricing_badge_helper():
    assert MarketplaceService._pricing_badge("free", Decimal("0")) == "Free"
    assert MarketplaceService._pricing_badge("pro", Decimal("29")) == "Pro"
    assert MarketplaceService._pricing_badge("enterprise", Decimal("0")) == "Enterprise"
    assert MarketplaceService._pricing_badge("free", Decimal("500")) == "Enterprise"


def test_template_response_enrichment_defaults():
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
    assert resp.screenshots == []
    assert resp.rating_avg is None
    assert resp.is_editors_choice is False
    assert resp.pricing_badge is None


def test_category_item_and_home_schemas():
    cat = CategoryItem(slug="saas", name="SaaS", count=3, icon="cloud", is_featured=True)
    assert cat.template_count is None
    home = MarketplaceHomeResponse(installed_count=1, updates_count=0)
    assert home.featured == []
    assert home.collections == []


def test_collection_create_schema():
    payload = CollectionCreate(slug="best-chatbots", name="Best Chatbots", template_ids=[])
    assert payload.collection_type == "curated"
    assert payload.is_public is True


def test_store_home_model_tables():
    assert MarketplaceCategoryMeta.__tablename__ == "marketplace_category_meta"
    assert MarketplaceCollection.__tablename__ == "marketplace_collections"
    assert MarketplaceCollectionItem.__tablename__ == "marketplace_collection_items"
    assert MarketplaceTemplateEvent.__tablename__ == "marketplace_template_events"
    cols = MarketplaceTemplate.__table__.c
    for name in (
        "banner_url",
        "screenshots",
        "video_url",
        "live_demo_url",
        "discount_percent",
        "estimated_install_minutes",
        "compatibility",
        "is_editors_choice",
    ):
        assert name in cols
