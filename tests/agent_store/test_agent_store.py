"""AI Agent Store tests — unit + optional DB integration."""
from __future__ import annotations

import hashlib
import hmac
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy.exc import OperationalError

from app.agent_store.models import ListingStatus, PricingModel, PurchaseStatus
from app.agent_store.schemas import (
    AgentStorePurchaseOrderRequest,
    AgentStorePurchaseVerifyRequest,
    ListingCreate,
    ModerateListingRequest,
    PublisherUpsert,
    ReviewCreate,
    StoreInstallRequest,
)
from app.agent_store.service import AgentStoreService
from app.marketplace.schemas import InstallationResponse, TemplateResponse


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
def test_purchase_order_request_requires_customer_identity():
    """customer_name/customer_email are required — everything else about the
    install (agent_id, config_overrides, publish_agent, ...) has a safe
    default so a minimal checkout payload is just the buyer's identity."""
    req = AgentStorePurchaseOrderRequest(customer_name="Buyer", customer_email="buyer@example.com")
    assert req.agent_id is None
    assert req.create_api_key is True
    assert req.config_overrides == {}
    assert req.version is None
    assert req.publish_agent is False

    with pytest.raises(ValidationError):
        AgentStorePurchaseOrderRequest(customer_email="buyer@example.com")  # missing customer_name
    with pytest.raises(ValidationError):
        AgentStorePurchaseOrderRequest(customer_name="Buyer")  # missing customer_email


@pytest.mark.unit
def test_purchase_verify_request_requires_all_three_razorpay_fields():
    """The verify payload is never optional-any-of — a forged/incomplete
    verification request must fail validation before it ever reaches the
    signature check in the service."""
    AgentStorePurchaseVerifyRequest(
        razorpay_order_id="order_1", razorpay_payment_id="pay_1", razorpay_signature="sig"
    )
    with pytest.raises(ValidationError):
        AgentStorePurchaseVerifyRequest(razorpay_payment_id="pay_1", razorpay_signature="sig")
    with pytest.raises(ValidationError):
        AgentStorePurchaseVerifyRequest(razorpay_order_id="order_1", razorpay_signature="sig")
    with pytest.raises(ValidationError):
        AgentStorePurchaseVerifyRequest(razorpay_order_id="order_1", razorpay_payment_id="pay_1")


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


RAZORPAY_TEST_SECRET = "test_agent_store_razorpay_secret"


def _sig(order_id: str, payment_id: str) -> str:
    msg = f"{order_id}|{payment_id}"
    return hmac.new(RAZORPAY_TEST_SECRET.encode(), msg.encode(), hashlib.sha256).hexdigest()


def _paid_listing(**overrides) -> MagicMock:
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
    listing.install_count = 0
    listing.download_count = 0
    for key, value in overrides.items():
        setattr(listing, key, value)
    return listing


def _publisher(bps: int = 7000) -> MagicMock:
    pub = MagicMock()
    pub.id = uuid.uuid4()
    pub.company_id = uuid.uuid4()  # different from any buyer used in these tests
    pub.revenue_share_bps = bps
    return pub


# ── Security fix: paid listings must never grant access without an
# authoritative, server-verified Razorpay payment ─────────────────────────────

@pytest.mark.unit
@pytest.mark.parametrize("gateway", ["manual", "razorpay", "stripe", "paypal"])
def test_direct_install_of_paid_listing_fails_closed_regardless_of_gateway(gateway):
    """The single-shot install() must never itself charge/grant a paid
    listing — a client-supplied `gateway` string used to be enough to flip a
    purchase to COMPLETED via the (unauthoritative) generic PaymentService
    stub path. Now it must fail closed for every gateway value, including
    Stripe/PayPal, neither of which the Agent Store implements at all."""
    db = MagicMock()
    listing = _paid_listing()
    publisher = _publisher()

    svc = AgentStoreService(db)
    svc._resolve_listing = MagicMock(return_value=listing)  # type: ignore[method-assign]
    svc._completed_purchase = MagicMock(return_value=None)  # type: ignore[method-assign]
    db.get.return_value = publisher

    with patch.object(svc.marketplace, "install") as mock_install:
        with pytest.raises(HTTPException) as exc:
            svc.install(
                uuid.uuid4(),
                uuid.uuid4(),
                str(listing.id),
                StoreInstallRequest(gateway=gateway, payment_method="card"),
            )
        assert exc.value.status_code == 402
        mock_install.assert_not_called()
    db.add.assert_not_called()  # no purchase/entitlement fabricated


@pytest.mark.unit
def test_verify_rejects_forged_razorpay_signature(monkeypatch):
    monkeypatch.setattr("app.agent_store.service.settings.RAZORPAY_KEY_SECRET", RAZORPAY_TEST_SECRET)
    monkeypatch.setattr("app.agent_store.service.razorpay_enabled", lambda: True)
    db = MagicMock()
    listing = _paid_listing()

    svc = AgentStoreService(db)
    svc._resolve_listing = MagicMock(return_value=listing)  # type: ignore[method-assign]

    with patch.object(svc.marketplace, "install") as mock_install:
        with pytest.raises(HTTPException) as exc:
            svc.verify_purchase_and_install(
                uuid.uuid4(),
                uuid.uuid4(),
                str(listing.id),
                AgentStorePurchaseVerifyRequest(
                    razorpay_order_id="order_1",
                    razorpay_payment_id="pay_1",
                    razorpay_signature="not-the-real-signature",
                ),
            )
        mock_install.assert_not_called()
    assert exc.value.status_code == 400
    assert "signature" in str(exc.value.detail).lower()
    db.commit.assert_not_called()


@pytest.mark.unit
def test_verify_rejects_when_no_pending_purchase_exists(monkeypatch):
    """A syntactically valid signature over an order that was never created
    via create_purchase_order (no pending mapping) must not install."""
    monkeypatch.setattr("app.agent_store.service.settings.RAZORPAY_KEY_SECRET", RAZORPAY_TEST_SECRET)
    monkeypatch.setattr("app.agent_store.service.razorpay_enabled", lambda: True)
    db = MagicMock()
    listing = _paid_listing()

    svc = AgentStoreService(db)
    svc._resolve_listing = MagicMock(return_value=listing)  # type: ignore[method-assign]
    svc._lock_relevant_purchase = MagicMock(return_value=None)  # type: ignore[method-assign]

    order_id, payment_id = "order_2", "pay_2"
    with patch.object(svc.marketplace, "install") as mock_install:
        with pytest.raises(HTTPException) as exc:
            svc.verify_purchase_and_install(
                uuid.uuid4(),
                uuid.uuid4(),
                str(listing.id),
                AgentStorePurchaseVerifyRequest(
                    razorpay_order_id=order_id,
                    razorpay_payment_id=payment_id,
                    razorpay_signature=_sig(order_id, payment_id),
                ),
            )
        mock_install.assert_not_called()
    assert exc.value.status_code == 400
    assert "pending purchase" in str(exc.value.detail).lower()


@pytest.mark.unit
def test_verify_rejects_order_id_not_matching_pending_purchase(monkeypatch):
    """A validly-signed order for a DIFFERENT order than the one bound to
    the pending purchase must not be accepted — the plan/order binding is
    server-side, mirroring subscriptions' _trusted_plan_id_from_subscription."""
    monkeypatch.setattr("app.agent_store.service.settings.RAZORPAY_KEY_SECRET", RAZORPAY_TEST_SECRET)
    monkeypatch.setattr("app.agent_store.service.razorpay_enabled", lambda: True)
    db = MagicMock()
    listing = _paid_listing()

    pending = MagicMock()
    pending.status = PurchaseStatus.PENDING
    pending.meta = {"razorpay_order_id": "order_real", "install_request": {}}

    svc = AgentStoreService(db)
    svc._resolve_listing = MagicMock(return_value=listing)  # type: ignore[method-assign]
    svc._lock_relevant_purchase = MagicMock(return_value=pending)  # type: ignore[method-assign]

    forged_order_id, payment_id = "order_attacker", "pay_3"
    with patch.object(svc.marketplace, "install") as mock_install:
        with pytest.raises(HTTPException) as exc:
            svc.verify_purchase_and_install(
                uuid.uuid4(),
                uuid.uuid4(),
                str(listing.id),
                AgentStorePurchaseVerifyRequest(
                    razorpay_order_id=forged_order_id,
                    razorpay_payment_id=payment_id,
                    razorpay_signature=_sig(forged_order_id, payment_id),
                ),
            )
        mock_install.assert_not_called()
    assert exc.value.status_code == 400
    assert "does not match" in str(exc.value.detail).lower()


@pytest.mark.unit
def test_create_order_then_verify_installs_paid_listing_after_real_payment(monkeypatch):
    """The authoritative happy path: create a server-pinned Razorpay order,
    then verify with the matching signature — only then does install/
    revenue-share happen."""
    monkeypatch.setattr("app.agent_store.service.settings.RAZORPAY_KEY_SECRET", RAZORPAY_TEST_SECRET)
    monkeypatch.setattr("app.agent_store.service.settings.RAZORPAY_KEY_ID", "rzp_test_id")
    monkeypatch.setattr("app.agent_store.service.razorpay_enabled", lambda: True)

    db = MagicMock()
    listing = _paid_listing()
    publisher = _publisher(bps=7000)
    company_id, user_id = uuid.uuid4(), uuid.uuid4()
    order_id, payment_id = "order_happy", "pay_happy"

    svc = AgentStoreService(db)
    svc._resolve_listing = MagicMock(return_value=listing)  # type: ignore[method-assign]
    svc._completed_purchase = MagicMock(return_value=None)  # type: ignore[method-assign]
    svc._pending_purchase = MagicMock(return_value=None)  # type: ignore[method-assign]
    db.get.return_value = publisher

    # Real AgentStorePurchase() construction pulls in the full SQLAlchemy
    # mapper registry, which some unrelated model needs another module
    # imported first to resolve in a narrow test run — patch the class
    # itself (this is a pure logic test, not an ORM/DB test) so the fixture
    # doesn't depend on unrelated import order.
    mock_purchase = MagicMock()
    mock_purchase.id = uuid.uuid4()
    mock_purchase.publisher_share = 0
    mock_purchase.installation_id = None
    mock_purchase.payment_id = None

    def _construct_purchase(**kwargs):
        # Mirror the real ORM constructor: fields passed in become attributes
        # on the (shared) mock row, so meta/status set by create_purchase_order
        # are actually visible to the later verify_purchase_and_install call.
        for key, value in kwargs.items():
            setattr(mock_purchase, key, value)
        return mock_purchase

    with patch("app.agent_store.service.AgentStorePurchase", side_effect=_construct_purchase):
        with patch("razorpay.Client") as mock_client_cls:
            mock_client_cls.return_value.order.create.return_value = {"id": order_id}
            order_resp = svc.create_purchase_order(
                company_id,
                user_id,
                str(listing.id),
                AgentStorePurchaseOrderRequest(customer_name="Buyer", customer_email="buyer@example.com"),
            )

    assert order_resp.order_id == order_id
    purchase = mock_purchase
    assert purchase.status == PurchaseStatus.PENDING

    # No entitlement/revenue exists yet — order creation alone must not install.
    assert purchase.publisher_share == 0
    assert purchase.installation_id is None

    svc._pending_purchase = MagicMock(return_value=purchase)  # type: ignore[method-assign]
    svc._lock_relevant_purchase = MagicMock(return_value=purchase)  # type: ignore[method-assign]

    now = datetime.now(timezone.utc)
    fake_install = InstallationResponse(
        id=uuid.uuid4(),
        company_id=company_id,
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
            result = svc.verify_purchase_and_install(
                company_id,
                user_id,
                str(listing.id),
                AgentStorePurchaseVerifyRequest(
                    razorpay_order_id=order_id,
                    razorpay_payment_id=payment_id,
                    razorpay_signature=_sig(order_id, payment_id),
                ),
            )
        mock_install.assert_called_once()

    assert result.installation_id == fake_install.id
    assert purchase.status == PurchaseStatus.COMPLETED
    assert purchase.publisher_share == Decimal("20.30")  # 70% of 29.00
    assert purchase.platform_share == Decimal("8.70")


@pytest.mark.unit
def test_verify_replay_is_idempotent_no_duplicate_install_or_payout(monkeypatch):
    """Resubmitting an already-verified payment (retry/replay) must return
    the existing result — never a second install, purchase row, or revenue
    share computation."""
    monkeypatch.setattr("app.agent_store.service.settings.RAZORPAY_KEY_SECRET", RAZORPAY_TEST_SECRET)
    monkeypatch.setattr("app.agent_store.service.razorpay_enabled", lambda: True)
    db = MagicMock()
    listing = _paid_listing()
    order_id, payment_id = "order_dup", "pay_dup"

    completed = MagicMock()
    completed.id = uuid.uuid4()
    completed.status = PurchaseStatus.COMPLETED
    completed.installation_id = uuid.uuid4()
    completed.payment_id = None
    completed.meta = {"razorpay_order_id": order_id, "razorpay_payment_id": payment_id}

    svc = AgentStoreService(db)
    svc._resolve_listing = MagicMock(return_value=listing)  # type: ignore[method-assign]
    svc._completed_purchase = MagicMock(return_value=completed)  # type: ignore[method-assign]
    svc._lock_relevant_purchase = MagicMock(return_value=completed)  # type: ignore[method-assign]

    with patch.object(svc.marketplace, "install") as mock_install:
        result = svc.verify_purchase_and_install(
            uuid.uuid4(),
            uuid.uuid4(),
            str(listing.id),
            AgentStorePurchaseVerifyRequest(
                razorpay_order_id=order_id,
                razorpay_payment_id=payment_id,
                razorpay_signature=_sig(order_id, payment_id),
            ),
        )
        mock_install.assert_not_called()
    db.commit.assert_not_called()
    assert result.purchase_id == completed.id
    assert result.installation_id == completed.installation_id


@pytest.mark.unit
def test_verify_rejects_new_payment_for_already_purchased_listing(monkeypatch):
    """A second, different payment against a listing already purchased must
    be rejected outright rather than silently re-charging/re-crediting."""
    monkeypatch.setattr("app.agent_store.service.settings.RAZORPAY_KEY_SECRET", RAZORPAY_TEST_SECRET)
    monkeypatch.setattr("app.agent_store.service.razorpay_enabled", lambda: True)
    db = MagicMock()
    listing = _paid_listing()

    completed = MagicMock()
    completed.status = PurchaseStatus.COMPLETED
    completed.meta = {"razorpay_order_id": "order_old", "razorpay_payment_id": "pay_old"}

    svc = AgentStoreService(db)
    svc._resolve_listing = MagicMock(return_value=listing)  # type: ignore[method-assign]
    svc._completed_purchase = MagicMock(return_value=completed)  # type: ignore[method-assign]
    svc._lock_relevant_purchase = MagicMock(return_value=completed)  # type: ignore[method-assign]

    order_id, payment_id = "order_new", "pay_new"
    with patch.object(svc.marketplace, "install") as mock_install:
        with pytest.raises(HTTPException) as exc:
            svc.verify_purchase_and_install(
                uuid.uuid4(),
                uuid.uuid4(),
                str(listing.id),
                AgentStorePurchaseVerifyRequest(
                    razorpay_order_id=order_id,
                    razorpay_payment_id=payment_id,
                    razorpay_signature=_sig(order_id, payment_id),
                ),
            )
        mock_install.assert_not_called()
    assert exc.value.status_code == 409


# ── Second-pass fixes: atomic purchase completion + concurrent verify ─────────

def _pending_paid_purchase(order_id: str) -> MagicMock:
    purchase = MagicMock()
    purchase.id = uuid.uuid4()
    purchase.status = PurchaseStatus.PENDING
    purchase.amount = Decimal("29.00")
    purchase.publisher_share = Decimal("0")
    purchase.platform_share = Decimal("0")
    purchase.installation_id = None
    purchase.payment_id = None
    purchase.meta = {"razorpay_order_id": order_id, "install_request": {}}
    return purchase


@pytest.mark.unit
def test_verify_install_failure_leaves_purchase_pending_then_retry_completes(monkeypatch):
    """CRITICAL #1: if MarketplaceService.install() raises (quota exceeded,
    template unavailable, etc.), verify_purchase_and_install must NOT mark
    the purchase COMPLETED and must NOT book any publisher/platform revenue
    share — a verified payment must not be lost just because installation
    temporarily failed. A later retry, once install() succeeds, must then
    complete the same purchase exactly once."""
    monkeypatch.setattr("app.agent_store.service.settings.RAZORPAY_KEY_SECRET", RAZORPAY_TEST_SECRET)
    monkeypatch.setattr("app.agent_store.service.razorpay_enabled", lambda: True)
    db = MagicMock()
    listing = _paid_listing()
    publisher = _publisher(bps=7000)
    order_id, payment_id = "order_retry", "pay_retry"
    purchase = _pending_paid_purchase(order_id)

    svc = AgentStoreService(db)
    svc._resolve_listing = MagicMock(return_value=listing)  # type: ignore[method-assign]
    svc._lock_relevant_purchase = MagicMock(return_value=purchase)  # type: ignore[method-assign]
    db.get.return_value = publisher

    req = AgentStorePurchaseVerifyRequest(
        razorpay_order_id=order_id,
        razorpay_payment_id=payment_id,
        razorpay_signature=_sig(order_id, payment_id),
    )

    with patch.object(
        svc.marketplace, "install", side_effect=HTTPException(status_code=429, detail="Quota exceeded")
    ) as mock_install:
        with pytest.raises(HTTPException) as exc:
            svc.verify_purchase_and_install(uuid.uuid4(), uuid.uuid4(), str(listing.id), req)
        mock_install.assert_called_once()
    assert exc.value.status_code == 429

    # No persisted COMPLETED purchase, no revenue booked — safely retryable.
    assert purchase.status == PurchaseStatus.PENDING
    assert purchase.publisher_share == Decimal("0")
    assert purchase.platform_share == Decimal("0")
    assert purchase.installation_id is None
    db.commit.assert_not_called()

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
    with patch.object(svc.marketplace, "install", return_value=fake_install) as mock_install2:
        with patch("app.agent_store.service.NotificationEventBus.dispatch"):
            result = svc.verify_purchase_and_install(uuid.uuid4(), uuid.uuid4(), str(listing.id), req)
        mock_install2.assert_called_once()

    assert result.installation_id == fake_install.id
    assert purchase.status == PurchaseStatus.COMPLETED
    assert purchase.publisher_share == Decimal("20.30")  # 70% of 29.00
    assert purchase.platform_share == Decimal("8.70")


@pytest.mark.unit
def test_verify_duplicate_sequential_only_one_install_and_payout(monkeypatch):
    """Two sequential verify calls carrying the same verified payment must
    install and pay out exactly once — the second is a pure idempotent
    replay against the same purchase row."""
    monkeypatch.setattr("app.agent_store.service.settings.RAZORPAY_KEY_SECRET", RAZORPAY_TEST_SECRET)
    monkeypatch.setattr("app.agent_store.service.razorpay_enabled", lambda: True)
    db = MagicMock()
    listing = _paid_listing()
    publisher = _publisher(bps=7000)
    company_id, user_id = uuid.uuid4(), uuid.uuid4()
    order_id, payment_id = "order_seq", "pay_seq"
    purchase = _pending_paid_purchase(order_id)

    svc = AgentStoreService(db)
    svc._resolve_listing = MagicMock(return_value=listing)  # type: ignore[method-assign]
    svc._lock_relevant_purchase = MagicMock(return_value=purchase)  # type: ignore[method-assign]
    db.get.return_value = publisher

    now = datetime.now(timezone.utc)
    fake_install = InstallationResponse(
        id=uuid.uuid4(), company_id=company_id, template_id=listing.template_id,
        installed_version="1.0.0", config={}, status="ready", agent_id=None,
        created_at=now, updated_at=now,
    )
    req = AgentStorePurchaseVerifyRequest(
        razorpay_order_id=order_id, razorpay_payment_id=payment_id,
        razorpay_signature=_sig(order_id, payment_id),
    )

    with patch.object(svc.marketplace, "install", return_value=fake_install) as mock_install:
        with patch("app.agent_store.service.NotificationEventBus.dispatch"):
            first = svc.verify_purchase_and_install(company_id, user_id, str(listing.id), req)
            second = svc.verify_purchase_and_install(company_id, user_id, str(listing.id), req)
        mock_install.assert_called_once()  # only one installation across both calls

    assert first.installation_id == fake_install.id
    assert second.installation_id == fake_install.id
    assert second.purchase_id == purchase.id
    assert purchase.status == PurchaseStatus.COMPLETED
    assert purchase.publisher_share == Decimal("20.30")  # only one payout booked
    assert purchase.platform_share == Decimal("8.70")


@pytest.mark.unit
def test_concurrent_verify_calls_serialize_only_one_installs(monkeypatch):
    """CRITICAL #2 (concurrency): two simultaneous verify calls for the same
    purchase must not both install/pay out.

    This runs two REAL OS threads (ThreadPoolExecutor) against one shared
    AgentStoreService/purchase, so the interleaving is genuine, not just two
    sequential mock calls. `_lock_relevant_purchase` is stubbed to block on a
    real `threading.Lock` — standing in for Postgres's `SELECT ... FOR
    UPDATE`, which blocks a second transaction until the first releases the
    row lock at commit — and `db.commit` releases that lock, mirroring
    production where the lock is held for exactly the same span (see
    _lock_relevant_purchase's docstring). Whichever thread acquires the lock
    first re-checks status, installs, and commits (releasing the lock); the
    other unblocks afterwards, re-checks, finds COMPLETED, and returns the
    existing result without a second install or payout.

    Limitation: this suite has no live Postgres connection, so it cannot
    exercise actual multi-connection row-level locking or the narrower
    window where MarketplaceService.install()'s OWN internal commit releases
    the row lock before this purchase is marked COMPLETED (that recovery
    branch — folding a marketplace "already installed" 409 back into the
    idempotent response — is covered deterministically by
    test_concurrent_verify_marketplace_conflict_folds_back_to_idempotent
    below). The lock's query shape (filtered to one listing+company+status,
    never a broad table lock) is reviewed by inspection; the same code path
    also runs against real Postgres whenever this file's @pytest.mark.integration
    tests execute against the docker-compose.test.yml stack.
    """
    monkeypatch.setattr("app.agent_store.service.settings.RAZORPAY_KEY_SECRET", RAZORPAY_TEST_SECRET)
    monkeypatch.setattr("app.agent_store.service.razorpay_enabled", lambda: True)
    db = MagicMock()
    listing = _paid_listing()
    publisher = _publisher(bps=7000)
    order_id, payment_id = "order_race", "pay_race"
    purchase = _pending_paid_purchase(order_id)

    row_lock = threading.Lock()

    def _locking_lookup(_listing_id, _company_id):
        row_lock.acquire()  # blocks until the other thread's "transaction" commits
        return purchase

    def _commit_releases_lock():
        if row_lock.locked():
            row_lock.release()

    svc = AgentStoreService(db)
    svc._resolve_listing = MagicMock(return_value=listing)  # type: ignore[method-assign]
    svc._lock_relevant_purchase = MagicMock(side_effect=_locking_lookup)  # type: ignore[method-assign]
    db.get.return_value = publisher
    db.commit.side_effect = _commit_releases_lock

    now = datetime.now(timezone.utc)
    fake_install = InstallationResponse(
        id=uuid.uuid4(), company_id=uuid.uuid4(), template_id=listing.template_id,
        installed_version="1.0.0", config={}, status="ready", agent_id=None,
        created_at=now, updated_at=now,
    )
    req = AgentStorePurchaseVerifyRequest(
        razorpay_order_id=order_id, razorpay_payment_id=payment_id,
        razorpay_signature=_sig(order_id, payment_id),
    )

    def _run(_n):
        return svc.verify_purchase_and_install(uuid.uuid4(), uuid.uuid4(), str(listing.id), req)

    with patch.object(svc.marketplace, "install", return_value=fake_install) as mock_install:
        with patch("app.agent_store.service.NotificationEventBus.dispatch"):
            with ThreadPoolExecutor(max_workers=2) as pool:
                results = list(pool.map(_run, range(2)))

    mock_install.assert_called_once()  # exactly one installation across both threads
    assert purchase.status == PurchaseStatus.COMPLETED
    assert purchase.publisher_share == Decimal("20.30")  # exactly one payout
    assert purchase.platform_share == Decimal("8.70")
    for result in results:
        assert result.installation_id == fake_install.id
        assert result.purchase_id == purchase.id


@pytest.mark.unit
def test_concurrent_verify_marketplace_conflict_folds_back_to_idempotent(monkeypatch):
    """Deterministic exercise of the narrow window CRITICAL #2 flags:
    MarketplaceService.install() commits its own transaction internally, so
    a second verify call can acquire the purchase row lock, see it still
    PENDING (the winner hasn't marked it COMPLETED yet), and also attempt
    install — hitting marketplace's own (company, template) uniqueness
    constraint (409 'Template already installed') instead of a raw duplicate
    install. This must fold back into the same idempotent response once the
    winner's completion is visible, never surface as a confusing error and
    never trigger a second install/payout."""
    monkeypatch.setattr("app.agent_store.service.settings.RAZORPAY_KEY_SECRET", RAZORPAY_TEST_SECRET)
    monkeypatch.setattr("app.agent_store.service.razorpay_enabled", lambda: True)
    db = MagicMock()
    listing = _paid_listing()
    order_id, payment_id = "order_fold", "pay_fold"

    # Simulates: thread A already flipped this purchase to COMPLETED (its
    # own install() call committed and it finished updating the row) by the
    # time thread B's except-handler re-reads it.
    completed = MagicMock()
    completed.id = uuid.uuid4()
    completed.status = PurchaseStatus.COMPLETED
    completed.installation_id = uuid.uuid4()
    completed.payment_id = None
    completed.meta = {"razorpay_order_id": order_id, "razorpay_payment_id": payment_id}

    # Thread B: acquired the lock after A's install()-internal commit
    # released it, but before A updated `status` — still reads PENDING.
    still_pending = _pending_paid_purchase(order_id)

    svc = AgentStoreService(db)
    svc._resolve_listing = MagicMock(return_value=listing)  # type: ignore[method-assign]
    svc._lock_relevant_purchase = MagicMock(return_value=still_pending)  # type: ignore[method-assign]
    svc._completed_purchase = MagicMock(return_value=completed)  # type: ignore[method-assign]

    with patch.object(
        svc.marketplace, "install",
        side_effect=HTTPException(status_code=409, detail="Template already installed"),
    ) as mock_install:
        result = svc.verify_purchase_and_install(
            uuid.uuid4(),
            uuid.uuid4(),
            str(listing.id),
            AgentStorePurchaseVerifyRequest(
                razorpay_order_id=order_id,
                razorpay_payment_id=payment_id,
                razorpay_signature=_sig(order_id, payment_id),
            ),
        )
        mock_install.assert_called_once()  # attempted once, never a second time

    assert result.installation_id == completed.installation_id
    assert result.purchase_id == completed.id
    db.commit.assert_not_called()  # thread B books no purchase state / no revenue itself


@pytest.mark.unit
def test_verify_rejects_publisher_purchasing_own_listing(monkeypatch):
    """Same 'publisher cannot purchase own listing' defense as install() and
    create_purchase_order, added to verify_purchase_and_install."""
    monkeypatch.setattr("app.agent_store.service.settings.RAZORPAY_KEY_SECRET", RAZORPAY_TEST_SECRET)
    monkeypatch.setattr("app.agent_store.service.razorpay_enabled", lambda: True)
    db = MagicMock()
    listing = _paid_listing()
    company_id = uuid.uuid4()
    publisher = MagicMock()
    publisher.company_id = company_id  # same as the buyer attempting to verify

    svc = AgentStoreService(db)
    svc._resolve_listing = MagicMock(return_value=listing)  # type: ignore[method-assign]
    db.get.return_value = publisher

    order_id, payment_id = "order_self", "pay_self"
    with patch.object(svc.marketplace, "install") as mock_install:
        with pytest.raises(HTTPException) as exc:
            svc.verify_purchase_and_install(
                company_id,
                uuid.uuid4(),
                str(listing.id),
                AgentStorePurchaseVerifyRequest(
                    razorpay_order_id=order_id,
                    razorpay_payment_id=payment_id,
                    razorpay_signature=_sig(order_id, payment_id),
                ),
            )
        mock_install.assert_not_called()
    assert exc.value.status_code == 400
    assert "own listing" in str(exc.value.detail).lower()
    db.commit.assert_not_called()


@pytest.mark.unit
def test_verify_rejects_when_razorpay_disabled(monkeypatch):
    """Mirrors create_purchase_order: verify must use the same
    razorpay_enabled() feature-flag + configured-keys check, not just a bare
    RAZORPAY_KEY_SECRET truthiness check (which ignores BILLING_ENABLE_RAZORPAY
    and a missing RAZORPAY_KEY_ID)."""
    monkeypatch.setattr("app.agent_store.service.settings.RAZORPAY_KEY_SECRET", RAZORPAY_TEST_SECRET)
    monkeypatch.setattr("app.agent_store.service.razorpay_enabled", lambda: False)
    db = MagicMock()
    listing = _paid_listing()

    svc = AgentStoreService(db)
    svc._resolve_listing = MagicMock(return_value=listing)  # type: ignore[method-assign]

    order_id, payment_id = "order_disabled", "pay_disabled"
    with patch.object(svc.marketplace, "install") as mock_install:
        with pytest.raises(HTTPException) as exc:
            svc.verify_purchase_and_install(
                uuid.uuid4(),
                uuid.uuid4(),
                str(listing.id),
                AgentStorePurchaseVerifyRequest(
                    razorpay_order_id=order_id,
                    razorpay_payment_id=payment_id,
                    razorpay_signature=_sig(order_id, payment_id),
                ),
            )
        mock_install.assert_not_called()
    assert exc.value.status_code == 503
    db.commit.assert_not_called()


@pytest.mark.unit
def test_install_rejects_other_tenants_private_listing():
    """Tenant boundary: a listing that isn't PUBLISHED is 404 to everyone
    except (via a separate, unrelated code path) its own publisher — install
    must never leak or install a private/draft listing owned by another
    company."""
    db = MagicMock()
    other_tenant_listing = MagicMock()
    other_tenant_listing.status = ListingStatus.PRIVATE
    other_tenant_listing.publisher_id = uuid.uuid4()
    db.get.return_value = other_tenant_listing  # _resolve_listing's db.get(AgentStoreListing, lid)

    svc = AgentStoreService(db)
    with pytest.raises(HTTPException) as exc:
        svc.install(uuid.uuid4(), uuid.uuid4(), str(uuid.uuid4()), StoreInstallRequest())
    assert exc.value.status_code == 404


@pytest.mark.unit
def test_create_purchase_order_rejects_other_tenants_private_listing():
    db = MagicMock()
    other_tenant_listing = MagicMock()
    other_tenant_listing.status = ListingStatus.DRAFT
    other_tenant_listing.publisher_id = uuid.uuid4()
    db.get.return_value = other_tenant_listing

    svc = AgentStoreService(db)
    with pytest.raises(HTTPException) as exc:
        svc.create_purchase_order(
            uuid.uuid4(),
            uuid.uuid4(),
            str(uuid.uuid4()),
            AgentStorePurchaseOrderRequest(customer_name="A", customer_email="a@example.com"),
        )
    assert exc.value.status_code == 404


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


@pytest.mark.unit
def test_purchase_router_endpoints_delegate_with_authenticated_tenant_and_enforce_permission():
    """Router-level check (no live DB — get_agent_store_service and
    get_current_user are dependency-overridden) for both new purchase
    endpoints: an authorized caller's OWN company_id/user_id must be what
    reaches the service (never anything client-supplied), and a caller
    lacking Permission.TEMPLATES_MANAGE must be rejected before the service
    is ever invoked."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.agent_store import router as agent_store_router_module
    from app.agent_store.schemas import AgentStorePurchaseOrderResponse, StoreInstallResponse
    from app.auth.router import get_current_user

    app = FastAPI()
    app.include_router(agent_store_router_module.router, prefix="/api/v1")

    company_id, user_id = uuid.uuid4(), uuid.uuid4()

    fake_order_resp = AgentStorePurchaseOrderResponse(
        order_id="order_router_test", purchase_id=uuid.uuid4(), amount=Decimal("29.00"), currency="USD"
    )
    fake_install_resp = StoreInstallResponse(
        listing_id=uuid.uuid4(), installation_id=uuid.uuid4(), status="ready"
    )
    fake_service = MagicMock()
    fake_service.create_purchase_order.return_value = fake_order_resp
    fake_service.verify_purchase_and_install.return_value = fake_install_resp

    app.dependency_overrides[agent_store_router_module.get_agent_store_service] = lambda: fake_service

    def _authorized_user():
        user = MagicMock()
        user.company_id = company_id
        user.id = user_id
        user.role = "company_owner"  # has Permission.TEMPLATES_MANAGE
        return user

    app.dependency_overrides[get_current_user] = _authorized_user

    with TestClient(app) as client:
        order_resp = client.post(
            "/api/v1/agent-store/listings/my-listing/purchase/razorpay-order",
            json={"customer_name": "Buyer", "customer_email": "buyer@example.com"},
        )
        assert order_resp.status_code == 201, order_resp.text
        assert order_resp.json()["order_id"] == "order_router_test"

        verify_resp = client.post(
            "/api/v1/agent-store/listings/my-listing/purchase/razorpay-verify",
            json={
                "razorpay_order_id": "order_router_test",
                "razorpay_payment_id": "pay_x",
                "razorpay_signature": "sig_x",
            },
        )
        assert verify_resp.status_code == 200, verify_resp.text

    fake_service.create_purchase_order.assert_called_once()
    order_args = fake_service.create_purchase_order.call_args.args
    assert order_args[0] == company_id  # authenticated tenant, never client-supplied
    assert order_args[1] == user_id
    assert order_args[2] == "my-listing"

    fake_service.verify_purchase_and_install.assert_called_once()
    verify_args = fake_service.verify_purchase_and_install.call_args.args
    assert verify_args[0] == company_id
    assert verify_args[1] == user_id
    assert verify_args[2] == "my-listing"

    # A role without Permission.TEMPLATES_MANAGE must be rejected before the
    # service is ever touched.
    def _unauthorized_user():
        user = MagicMock()
        user.company_id = uuid.uuid4()
        user.id = uuid.uuid4()
        user.role = "not-a-real-role"
        return user

    app.dependency_overrides[get_current_user] = _unauthorized_user
    with TestClient(app) as client:
        denied = client.post(
            "/api/v1/agent-store/listings/my-listing/purchase/razorpay-order",
            json={"customer_name": "Buyer", "customer_email": "buyer@example.com"},
        )
    assert denied.status_code == 403
    fake_service.create_purchase_order.assert_called_once()  # still just the one authorized call


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
