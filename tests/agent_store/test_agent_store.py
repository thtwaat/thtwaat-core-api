"""AI Agent Store tests — unit + optional DB integration."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy.exc import OperationalError

from app.agent_store.models import ListingStatus, PricingModel
from app.agent_store.schemas import (
    ListingCreate,
    ModerateListingRequest,
    PublisherUpsert,
    ReviewCreate,
    StoreInstallRequest,
)
from app.agent_store.service import AgentStoreService
from app.marketplace.schemas import InstallationResponse, TemplateResponse
from app.payments.model import PaymentStatus


def _db_available(db_session) -> bool:
    try:
        db_session.execute(__import__("sqlalchemy").text("SELECT 1"))
        return True
    except OperationalError:
        return False


# ── Pure unit (no DB) ─────────────────────────────────────────────────────────

@pytest.mark.unit
def test_listing_create_rejects_negative_price():
    with pytest.raises(ValidationError):
        ListingCreate(title="X", slug="x-agent", price_amount=Decimal("-1"))


@pytest.mark.unit
def test_review_rating_bounds():
    ReviewCreate(rating=5, title="Great")
    with pytest.raises(ValidationError):
        ReviewCreate(rating=0)
    with pytest.raises(ValidationError):
        ReviewCreate(rating=6)


@pytest.mark.unit
def test_moderate_action_pattern():
    ModerateListingRequest(action="approve")
    with pytest.raises(ValidationError):
        ModerateListingRequest(action="delete")


@pytest.mark.unit
def test_publisher_slug_pattern():
    PublisherUpsert(display_name="Acme", slug="acme-agents")
    with pytest.raises(ValidationError):
        PublisherUpsert(display_name="Acme", slug="Acme Agents")


@pytest.mark.unit
def test_install_delegates_to_marketplace_without_db():
    """Install must call MarketplaceService.install — never reimplement."""
    db = MagicMock()
    listing = MagicMock()
    listing.id = uuid.uuid4()
    listing.status = ListingStatus.PUBLISHED
    listing.publisher_id = uuid.uuid4()
    listing.template_id = uuid.uuid4()
    listing.pricing_model = PricingModel.FREE
    listing.current_version = "1.0.0"
    listing.slug = "free-agent"
    listing.title = "Free Agent"
    listing.install_count = 0
    listing.download_count = 0

    publisher = MagicMock()
    publisher.company_id = uuid.uuid4()  # different from buyer

    svc = AgentStoreService(db)
    svc._resolve_listing = MagicMock(return_value=listing)  # type: ignore[method-assign]
    db.get.return_value = publisher

    now = datetime.now(timezone.utc)
    fake_install = InstallationResponse(
        id=uuid.uuid4(),
        company_id=uuid.uuid4(),
        template_id=listing.template_id,
        installed_version="1.0.0",
        config={},
        status="ready",
        agent_id=None,
        created_at=now,
        updated_at=now,
    )

    with patch.object(svc.marketplace, "install", return_value=fake_install) as mock_install:
        with patch("app.agent_store.service.NotificationEventBus.dispatch"):
            result = svc.install(
                uuid.uuid4(),
                uuid.uuid4(),
                str(listing.id),
                StoreInstallRequest(create_api_key=False),
            )
        mock_install.assert_called_once()
        assert result.installation_id == fake_install.id
        assert result.listing_id == listing.id
    assert listing.install_count == 1
    db.commit.assert_called()


@pytest.mark.unit
def test_paid_install_blocks_on_failed_payment_without_db():
    db = MagicMock()
    listing = MagicMock()
    listing.id = uuid.uuid4()
    listing.status = ListingStatus.PUBLISHED
    listing.publisher_id = uuid.uuid4()
    listing.template_id = uuid.uuid4()
    listing.pricing_model = PricingModel.ONE_TIME
    listing.price_amount = Decimal("29.00")
    listing.currency = "USD"
    listing.slug = "paid-agent"
    listing.title = "Paid"
    listing.current_version = "1.0.0"

    publisher = MagicMock()
    publisher.company_id = uuid.uuid4()
    publisher.revenue_share_bps = 7000

    svc = AgentStoreService(db)
    svc._resolve_listing = MagicMock(return_value=listing)  # type: ignore[method-assign]
    svc._completed_purchase = MagicMock(return_value=None)  # type: ignore[method-assign]
    db.get.return_value = publisher

    failed = MagicMock()
    failed.id = uuid.uuid4()
    failed.status = PaymentStatus.FAILED

    with patch.object(svc.payments, "create_payment", return_value=failed):
        with patch.object(svc.marketplace, "install") as mock_install:
            with pytest.raises(HTTPException) as exc:
                svc.install(
                    uuid.uuid4(),
                    uuid.uuid4(),
                    str(listing.id),
                    StoreInstallRequest(gateway="manual", payment_method="card"),
                )
            assert exc.value.status_code == 402
            mock_install.assert_not_called()


@pytest.mark.unit
def test_create_listing_calls_marketplace_create_template():
    from app.agent_store.models import PublisherStatus

    db = MagicMock()
    pub = MagicMock()
    pub.id = uuid.uuid4()
    pub.display_name = "Builder"
    pub.status = PublisherStatus.ACTIVE
    pub.is_verified = False

    svc = AgentStoreService(db)
    svc._require_publisher = MagicMock(return_value=pub)  # type: ignore[method-assign]
    db.query.return_value.filter.return_value.first.return_value = None
    db.get.return_value = pub

    now = datetime.now(timezone.utc)
    fake_tpl = TemplateResponse(
        id=uuid.uuid4(),
        slug="agent-store-x",
        name="X",
        category="helpdesk",
        description="",
        version="1.0.0",
        author="Builder",
        status="draft",
        price=Decimal("0"),
        is_public=False,
        supports_agents=True,
        supports_domains=True,
        supports_billing=False,
        supports_mobile=False,
        tags=[],
        default_config={},
        created_at=now,
        updated_at=now,
    )

    def _refresh(obj):
        if getattr(obj, "id", None) is None:
            obj.id = uuid.uuid4()
        now = datetime.now(timezone.utc)
        obj.created_at = now
        obj.updated_at = now

    db.refresh.side_effect = _refresh

    with patch.object(svc.marketplace, "create_template", return_value=fake_tpl) as mock_create:
        with patch.object(svc.marketplace, "list_installed", return_value=[]):
            with patch("app.agent_store.service.NotificationEventBus.dispatch"):
                listing = svc.create_listing(
                    uuid.uuid4(),
                    uuid.uuid4(),
                    ListingCreate(
                        title="My Agent",
                        slug="my-agent-demo",
                        short_description="hi",
                        marketplace_category="helpdesk",
                    ),
                )
        mock_create.assert_called_once()
    assert listing.template_id == fake_tpl.id
    assert listing.status == ListingStatus.DRAFT
    db.add.assert_called()
    db.commit.assert_called()


# ── Integration (requires Postgres) ───────────────────────────────────────────

def _auth(client, role: str = "admin"):
    company_slug = f"astore-{uuid.uuid4().hex[:8]}"
    company_resp = client.post(
        "/api/v1/companies/",
        json={"name": "Agent Store Co", "slug": company_slug},
    )
    assert company_resp.status_code in (200, 201), company_resp.text
    company_id = company_resp.json()["id"]

    email = f"owner-{uuid.uuid4().hex[:8]}@example.com"
    password = "securepassword"
    user_resp = client.post(
        "/api/v1/users/",
        json={
            "email": email,
            "password": password,
            "company_id": company_id,
            "first_name": "Owner",
            "last_name": "User",
            "role": role,
        },
    )
    assert user_resp.status_code in (200, 201), user_resp.text

    login_resp = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert login_resp.status_code == 200, login_resp.text
    token = login_resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}, company_id


@pytest.mark.integration
def test_publisher_create_listing_and_storefront(client, db_session):
    if not _db_available(db_session):
        pytest.skip("Database host unavailable")

    from app.usage.service import UsageService
    from app.users.model import User

    headers, company_id = _auth(client)
    UsageService(db_session).apply_plan_limits(uuid.UUID(company_id), "starter", emit_upgraded=False)

    pub = client.put(
        "/api/v1/agent-store/publisher/me",
        json={
            "display_name": "Acme Agents",
            "slug": f"acme-{uuid.uuid4().hex[:6]}",
            "bio": "We ship agents",
        },
        headers=headers,
    )
    assert pub.status_code == 200, pub.text

    listing = client.post(
        "/api/v1/agent-store/publisher/listings",
        json={
            "title": "Support Copilot",
            "slug": f"support-{uuid.uuid4().hex[:6]}",
            "short_description": "Tier-1 support agent",
            "long_description": "Full description of the support agent.",
            "categories": ["support", "helpdesk"],
            "tags": ["support"],
            "pricing_model": "free",
            "screenshots": ["https://cdn.example/shot1.png"],
            "supported_languages": ["en", "hi"],
            "submit_for_review": True,
            "marketplace_category": "helpdesk",
        },
        headers=headers,
    )
    assert listing.status_code == 201, listing.text
    body = listing.json()
    assert body["status"] == "pending_review"
    listing_id = body["id"]

    search = client.get("/api/v1/agent-store/listings", headers=headers)
    assert search.status_code == 200
    assert all(i["id"] != listing_id for i in search.json())

    svc = AgentStoreService(db_session)
    admin_user = db_session.query(User).filter(User.company_id == uuid.UUID(company_id)).first()
    assert admin_user is not None
    approved = svc.moderate_listing(
        admin_user.id,
        uuid.UUID(listing_id),
        ModerateListingRequest(action="approve"),
    )
    assert approved.status == ListingStatus.PUBLISHED

    search2 = client.get("/api/v1/agent-store/listings?q=Support", headers=headers)
    assert search2.status_code == 200
    assert any(i["id"] == listing_id for i in search2.json())

    storefront = client.get("/api/v1/agent-store/storefront", headers=headers)
    assert storefront.status_code == 200
    assert "trending" in storefront.json()

    detail = client.get(f"/api/v1/agent-store/listings/{body['slug']}", headers=headers)
    assert detail.status_code == 200
    assert detail.json()["listing"]["title"] == "Support Copilot"
