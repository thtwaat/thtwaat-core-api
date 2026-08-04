"""Publisher Portal additive APIs — unit coverage."""
from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.agent_store.models import ListingStatus
from app.agent_store.schemas import (
    ListingCreate,
    ListingStatusUpdate,
    PublisherAiGenerateRequest,
    PublisherAnalytics,
    PublisherPublicProfile,
    PublisherUpsert,
    ReviewReplyRequest,
)
from app.agent_store.service import AgentStoreService


@pytest.mark.unit
def test_listing_status_includes_private_and_archived():
    assert ListingStatus.PRIVATE.value == "private"
    assert ListingStatus.ARCHIVED.value == "archived"
    ListingStatusUpdate(status=ListingStatus.PRIVATE)
    ListingStatusUpdate(status=ListingStatus.ARCHIVED)
    with pytest.raises(ValidationError):
        ListingStatusUpdate(status="deleted")  # type: ignore[arg-type]


@pytest.mark.unit
def test_publisher_upsert_accepts_social_fields():
    pub = PublisherUpsert(
        display_name="Acme Labs",
        slug="acme-labs",
        bio="We ship agents",
        github_url="https://github.com/acme",
        linkedin_url="https://linkedin.com/company/acme",
        twitter_url="https://x.com/acme",
        banner_url="https://cdn.example/banner.png",
    )
    assert pub.github_url.endswith("/acme")


@pytest.mark.unit
def test_listing_create_as_private_flag():
    payload = ListingCreate(
        title="Private Agent",
        slug="private-agent",
        as_private=True,
        submit_for_review=False,
        price_amount=Decimal("0"),
    )
    assert payload.as_private is True


@pytest.mark.unit
def test_ai_generate_summary_and_tags():
    svc = AgentStoreService(db=None)  # type: ignore[arg-type]
    summary = svc.generate_listing_copy(
        PublisherAiGenerateRequest(
            kind="summary",
            title="Support Copilot",
            short_description="Answers tickets",
            categories=["helpdesk"],
        )
    )
    assert summary.kind == "summary"
    assert "Support Copilot" in summary.result

    tags = svc.generate_listing_copy(
        PublisherAiGenerateRequest(
            kind="tags",
            title="Support Copilot",
            short_description="ticket automation",
            categories=["helpdesk"],
            tags=["ai"],
        )
    )
    assert tags.kind == "tags"
    assert "ai" in tags.tags or "helpdesk" in tags.tags


@pytest.mark.unit
def test_ai_generate_rejects_unknown_kind():
    with pytest.raises(ValidationError):
        PublisherAiGenerateRequest(kind="poem", title="X")


@pytest.mark.unit
def test_review_reply_requires_text():
    ReviewReplyRequest(reply="Thanks for the feedback!")
    with pytest.raises(ValidationError):
        ReviewReplyRequest(reply="")


@pytest.mark.unit
def test_publisher_analytics_additive_defaults():
    analytics = PublisherAnalytics(
        listings=3,
        published_listings=1,
        total_installs=10,
        total_downloads=12,
        average_rating=4.5,
        review_count=2,
        completed_purchases=1,
        gross_revenue=10.0,
        publisher_revenue=8.0,
        platform_fees=2.0,
    )
    assert analytics.draft_listings == 0
    assert analytics.active_installs == 0
    assert analytics.daily_installs == []
    assert analytics.conversion_rate == 0.0


@pytest.mark.unit
def test_public_profile_schema_shape():
    from uuid import uuid4

    profile = PublisherPublicProfile(
        id=uuid4(),
        display_name="THTWAAT",
        slug="thtwaat",
        is_verified=True,
        followers_count=10,
        following_count=2,
        templates_count=5,
        published_count=3,
        average_rating=4.8,
        total_installs=100,
        listings=[],
    )
    assert profile.slug == "thtwaat"
