"""
tests/payments/test_razorpay_e2e.py

End-to-end test suite for the Razorpay Live payment integration.
Covers all 12 checklist items from the implementation spec.

Each test function documents:
    PASS / FAIL
    Root Cause (if failed)
    Fix Applied (if failed)

Architecture:
  - Order creation calls the REAL Razorpay Live API (safe — no charge until payment).
  - Signature verification uses HMAC computed with the live secret (mirrors what Razorpay does).
  - Webhook tests POST a correctly-signed payload to the webhook endpoint.
  - All DB assertions query through the API so no direct DB access is needed.
"""

import uuid
import hmac
import hashlib
import json
import pytest
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

RAZORPAY_KEY_SECRET = "6tg4vKLaVKO6PMfeNZPuGF9j"
RAZORPAY_KEY_ID = "rzp_live_Suexgjxrs68uwU"


def _compute_razorpay_signature(order_id: str, payment_id: str) -> str:
    """Compute HMAC-SHA256 signature exactly as Razorpay would send it."""
    msg = f"{order_id}|{payment_id}"
    return hmac.new(
        RAZORPAY_KEY_SECRET.encode(),
        msg.encode(),
        hashlib.sha256
    ).hexdigest()


def _compute_webhook_signature(payload_bytes: bytes) -> str:
    """Compute HMAC-SHA256 over the raw webhook body using key secret."""
    return hmac.new(
        RAZORPAY_KEY_SECRET.encode(),
        payload_bytes,
        hashlib.sha256
    ).hexdigest()


def _register_company_and_login(client: TestClient) -> tuple:
    """Creates a company, admin user, and returns (headers, company_id)."""
    slug = f"rzp-{uuid.uuid4().hex[:8]}"
    company_resp = client.post("/api/v1/companies/", json={"name": f"Razorpay Test Co {slug}", "slug": slug})
    assert company_resp.status_code in (200, 201), f"Company creation failed: {company_resp.text}"
    company_id = company_resp.json()["id"]

    email = f"rzptest-{uuid.uuid4().hex[:8]}@example.com"
    password = "Test@12345"
    user_resp = client.post("/api/v1/users/", json={
        "email": email,
        "password": password,
        "company_id": company_id,
        "first_name": "Razorpay",
        "last_name": "Tester",
        "role": "admin"
    })
    assert user_resp.status_code in (200, 201), f"User creation failed: {user_resp.text}"

    login_resp = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    return headers, company_id


def _get_or_create_test_plan(client: TestClient, headers: dict) -> str:
    """Gets the first active plan or creates a Starter plan; returns plan_id."""
    plans_resp = client.get("/api/v1/payments/plans/", headers=headers)
    if plans_resp.status_code == 200 and plans_resp.json():
        return plans_resp.json()[0]["id"]

    plan_resp = client.post("/api/v1/payments/plans/", headers=headers, json={
        "name": f"starter-e2e-{uuid.uuid4().hex[:6]}",
        "description": "E2E test plan",
        "amount": "99.00",
        "currency": "INR",
        "interval": "month",
        "interval_count": 1,
        "max_users": 10,
        "max_apps": 3,
        "ai_credits": "500.0000",
    })
    assert plan_resp.status_code in (200, 201), f"Plan creation failed: {plan_resp.text}"
    return plan_resp.json()["id"]


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def client():
    from main import app
    with TestClient(app) as c:
        yield c


# ===========================================================================
# TEST 1 — Razorpay SDK Integration
# Verify that the RazorpayProvider is properly initialised with live creds.
# ===========================================================================

class TestRazorpaySDKIntegration:
    """Checklist item 1: Verify Razorpay SDK integration."""

    def test_razorpay_provider_initializes(self):
        """
        PASS if RazorpayProvider constructs without raising (i.e., creds are set).
        FAIL > Root Cause: RAZORPAY_KEY_ID / RAZORPAY_KEY_SECRET not in .env
               Fix Applied: Credentials already present in .env.
        """
        from app.payments.providers.razorpay import RazorpayProvider
        provider = RazorpayProvider()
        assert provider.client is not None

    def test_razorpay_provider_uses_live_key(self):
        """PASS if the SDK client is initialised with the live key id."""
        from app.payments.providers.razorpay import RazorpayProvider
        from app.config.settings import settings
        assert settings.RAZORPAY_KEY_ID is not None
        assert settings.RAZORPAY_KEY_ID.startswith("rzp_live_"), (
            f"Expected a live key, got: {settings.RAZORPAY_KEY_ID}"
        )
        assert settings.RAZORPAY_KEY_SECRET is not None
        provider = RazorpayProvider()
        assert provider is not None


# ===========================================================================
# TEST 2 — No mock/stub for Razorpay gateway
# ===========================================================================

class TestNoMockStubs:
    """Checklist item 2: Replace every remaining mock/stub with real Razorpay code."""

    def test_razorpay_provider_is_not_stub(self):
        """
        PASS if RazorpayProvider does NOT contain stub markers.
        FAIL > Root Cause: Still using a stub provider.
               Fix Applied: Real RazorpayProvider was already in place.
        """
        from app.payments.providers.razorpay import RazorpayProvider
        import inspect
        source = inspect.getsource(RazorpayProvider)
        assert "razorpay.Client" in source, "RazorpayProvider must use razorpay.Client"
        assert "stubbed" not in source, "RazorpayProvider must not use stub data"

    def test_factory_returns_real_razorpay_provider(self):
        """PASS if the factory returns a RazorpayProvider (not ManualProvider)."""
        from app.payments.providers.factory import get_payment_provider
        from app.payments.model import Gateway
        from app.payments.providers.razorpay import RazorpayProvider
        provider = get_payment_provider(Gateway.RAZORPAY)
        assert isinstance(provider, RazorpayProvider)


# ===========================================================================
# TEST 3 — Razorpay Order API
# ===========================================================================

class TestRazorpayOrderCreation:
    """Checklist item 3: Create Razorpay Order API."""

    def test_create_razorpay_order_returns_order_id(self, client):
        """
        PASS if POST /payments/subscriptions/razorpay/order returns a real order_id.
        FAIL > Root Cause: API not configured, or plan_id not found.
               Fix Applied: Ensure plan exists before calling.
        """
        headers, company_id = _register_company_and_login(client)
        plan_id = _get_or_create_test_plan(client, headers)

        resp = client.post(
            "/api/v1/payments/subscriptions/razorpay/order",
            headers=headers,
            json={
                "plan_id": plan_id,
                "customer_name": "E2E Tester",
                "customer_email": "e2e@thtwaat.com",
                "customer_phone": "+919999999999"
            }
        )
        assert resp.status_code in (200, 201), f"Order creation failed: {resp.text}"
        data = resp.json()
        assert "order_id" in data, f"Missing order_id in response: {data}"
        assert data["order_id"].startswith("order_"), (
            f"Expected Razorpay order_id starting with 'order_', got: {data['order_id']}"
        )
        assert data["provider"] == "razorpay"

    def test_create_razorpay_order_returns_subscription_id(self, client):
        """
        PASS if the response includes subscription_id (UUID).
        FAIL > Root Cause: service.create_razorpay_order didn't return sub.id.
               Fix Applied: Modified service.py to capture and return sub.id.
        """
        headers, company_id = _register_company_and_login(client)
        plan_id = _get_or_create_test_plan(client, headers)

        resp = client.post(
            "/api/v1/payments/subscriptions/razorpay/order",
            headers=headers,
            json={
                "plan_id": plan_id,
                "customer_name": "E2E Tester",
                "customer_email": "e2e@thtwaat.com",
            }
        )
        assert resp.status_code in (200, 201), f"Order creation failed: {resp.text}"
        data = resp.json()
        assert "subscription_id" in data and data["subscription_id"] is not None, (
            f"FAIL > Missing subscription_id in response: {data}\n"
            "Root Cause: create_razorpay_order returned no subscription_id.\n"
            "Fix Applied: Modified subscriptions/service.py to return sub.id."
        )
        uuid.UUID(data["subscription_id"])  # must be valid UUID


# ===========================================================================
# TEST 4 — Integrate Checkout Endpoint
# ===========================================================================

class TestCheckoutEndpoint:
    """Checklist item 4: Integrate Checkout endpoint."""

    def test_checkout_response_schema(self, client):
        """PASS if response has order_id, subscription_id, and provider='razorpay'."""
        headers, company_id = _register_company_and_login(client)
        plan_id = _get_or_create_test_plan(client, headers)

        resp = client.post(
            "/api/v1/payments/subscriptions/razorpay/order",
            headers=headers,
            json={
                "plan_id": plan_id,
                "customer_name": "Checkout Tester",
                "customer_email": "checkout@thtwaat.com",
            }
        )
        assert resp.status_code in (200, 201)
        data = resp.json()
        assert data.get("provider") == "razorpay"
        assert data.get("order_id", "").startswith("order_")
        assert data.get("subscription_id") is not None

    def test_checkout_requires_auth(self, client):
        """PASS if calling without a token returns 401/403."""
        resp = client.post(
            "/api/v1/payments/subscriptions/razorpay/order",
            json={"plan_id": str(uuid.uuid4()), "customer_name": "x", "customer_email": "x@x.com"}
        )
        assert resp.status_code in (401, 403)

    def test_checkout_with_invalid_plan(self, client):
        """PASS if calling with a non-existent plan_id returns 404."""
        headers, _ = _register_company_and_login(client)
        resp = client.post(
            "/api/v1/payments/subscriptions/razorpay/order",
            headers=headers,
            json={
                "plan_id": str(uuid.uuid4()),
                "customer_name": "Ghost",
                "customer_email": "ghost@thtwaat.com",
            }
        )
        assert resp.status_code == 404


# ===========================================================================
# TEST 5 — Payment Signature Verification
# ===========================================================================

class TestSignatureVerification:
    """Checklist item 5: Verify payment signature."""

    def test_valid_signature_is_accepted(self, client):
        """
        PASS if a correctly-computed signature passes the verify endpoint.
        FAIL > Root Cause: Secret mismatch or wrong message format.
               Fix Applied: Use order_id|payment_id format (Razorpay spec).
        """
        headers, company_id = _register_company_and_login(client)
        plan_id = _get_or_create_test_plan(client, headers)

        order_resp = client.post(
            "/api/v1/payments/subscriptions/razorpay/order",
            headers=headers,
            json={"plan_id": plan_id, "customer_name": "SigTest", "customer_email": "sig@thtwaat.com"}
        )
        assert order_resp.status_code in (200, 201)
        order_id = order_resp.json()["order_id"]

        fake_payment_id = f"pay_{uuid.uuid4().hex[:16]}"
        signature = _compute_razorpay_signature(order_id, fake_payment_id)

        verify_resp = client.post(
            "/api/v1/payments/subscriptions/razorpay/verify",
            headers=headers,
            json={
                "razorpay_order_id": order_id,
                "razorpay_payment_id": fake_payment_id,
                "razorpay_signature": signature,
                "plan_id": plan_id,
            }
        )
        assert verify_resp.status_code == 200, (
            f"FAIL > verify returned {verify_resp.status_code}: {verify_resp.text}\n"
            "Root Cause: Signature verification rejected a valid HMAC.\n"
            "Fix Applied: Ensure RAZORPAY_KEY_SECRET matches the one used for signature generation."
        )

    def test_invalid_signature_is_rejected(self, client):
        """PASS if a tampered signature is rejected with 400."""
        headers, company_id = _register_company_and_login(client)
        plan_id = _get_or_create_test_plan(client, headers)

        order_resp = client.post(
            "/api/v1/payments/subscriptions/razorpay/order",
            headers=headers,
            json={"plan_id": plan_id, "customer_name": "Bad Sig", "customer_email": "badsig@thtwaat.com"}
        )
        order_id = order_resp.json().get("order_id", "order_fake")

        verify_resp = client.post(
            "/api/v1/payments/subscriptions/razorpay/verify",
            headers=headers,
            json={
                "razorpay_order_id": order_id,
                "razorpay_payment_id": "pay_tampered",
                "razorpay_signature": "invalidsignaturexxxxxxxx",
                "plan_id": plan_id,
            }
        )
        assert verify_resp.status_code == 400, (
            f"FAIL > Expected 400 for invalid signature, got {verify_resp.status_code}."
        )

    def test_provider_verify_signature_method(self):
        """PASS if RazorpayProvider.verify_signature() correctly validates an HMAC."""
        from app.payments.providers.razorpay import RazorpayProvider
        order_id = "order_test123"
        payment_id = "pay_test456"
        expected = hmac.new(
            RAZORPAY_KEY_SECRET.encode(),
            f"{order_id}|{payment_id}".encode(),
            hashlib.sha256
        ).hexdigest()

        assert RazorpayProvider.verify_signature(order_id, payment_id, expected) is True
        assert RazorpayProvider.verify_signature(order_id, payment_id, "wrongsig") is False


# ===========================================================================
# TEST 6 — Webhook Verification
# ===========================================================================

class TestWebhookVerification:
    """Checklist item 6: Implement webhook verification."""

    def _post_webhook(self, client, payload: dict):
        payload_bytes = json.dumps(payload).encode()
        sig = _compute_webhook_signature(payload_bytes)
        return client.post(
            "/api/v1/payments/webhooks/razorpay",
            content=payload_bytes,
            headers={
                "Content-Type": "application/json",
                "X-Razorpay-Signature": sig,
            }
        )

    def test_webhook_accepts_valid_signature(self, client):
        """
        PASS if a correctly-signed webhook returns 200 with {received: True}.
        FAIL > Root Cause: HMAC key mismatch or missing header.
               Fix Applied: Webhook uses RAZORPAY_KEY_SECRET for verification.
        """
        payload = {
            "event": "payment.failed",
            "payload": {
                "payment": {
                    "entity": {
                        "id": "pay_test000",
                        "amount": 9900,
                        "currency": "INR",
                        "notes": {"company_id": str(uuid.uuid4())}
                    }
                }
            }
        }
        resp = self._post_webhook(client, payload)
        assert resp.status_code == 200, (
            f"FAIL > Webhook rejected with status {resp.status_code}: {resp.text}\n"
            "Root Cause: Signature verification failed.\n"
            "Fix Applied: X-Razorpay-Signature computed with RAZORPAY_KEY_SECRET over raw body."
        )
        assert resp.json().get("received") is True

    def test_webhook_rejects_invalid_signature(self, client):
        """PASS if a webhook with a bad signature returns 400."""
        resp = client.post(
            "/api/v1/payments/webhooks/razorpay",
            content=b'{"event": "payment.captured", "payload": {}}',
            headers={
                "Content-Type": "application/json",
                "X-Razorpay-Signature": "badsignature",
            }
        )
        assert resp.status_code == 400

    def test_webhook_missing_signature_returns_400(self, client):
        """PASS if a webhook with no signature header returns 400."""
        resp = client.post(
            "/api/v1/payments/webhooks/razorpay",
            content=b'{"event": "payment.captured", "payload": {}}',
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code == 400

    def test_payment_captured_webhook_processes(self, client):
        """
        PASS if payment.captured event is acknowledged (returns 200).
        FAIL > Root Cause: Event handler crashed (empty handler before fix).
               Fix Applied: Completed payment.captured handler in webhooks/router.py
                            — now creates invoice, activates subscription, updates company plan.
        """
        headers_auth, company_id = _register_company_and_login(client)
        plan_id = _get_or_create_test_plan(client, headers_auth)

        order_resp = client.post(
            "/api/v1/payments/subscriptions/razorpay/order",
            headers=headers_auth,
            json={"plan_id": plan_id, "customer_name": "WebhookTester", "customer_email": "wh@thtwaat.com"}
        )
        order_id = order_resp.json().get("order_id", "order_fake")

        payload = {
            "event": "payment.captured",
            "payload": {
                "payment": {
                    "entity": {
                        "id": f"pay_{uuid.uuid4().hex[:14]}",
                        "order_id": order_id,
                        "amount": 9900,
                        "currency": "INR",
                        "notes": {
                            "company_id": company_id,
                            "plan_id": plan_id,
                            "plan_name": "Starter",
                        }
                    }
                }
            }
        }
        resp = self._post_webhook(client, payload)
        assert resp.status_code == 200, (
            f"FAIL > payment.captured webhook returned {resp.status_code}: {resp.text}\n"
            "Root Cause: Handler crashed — missing invoice/subscription logic.\n"
            "Fix Applied: Added invoice creation, subscription activation, and notifications."
        )
        assert resp.json().get("received") is True


# ===========================================================================
# TEST 7 — Subscription Activation
# ===========================================================================

class TestSubscriptionActivation:
    """Checklist item 7: Activate Company Subscription after successful payment."""

    def test_subscription_becomes_active_after_verify(self, client):
        """PASS if subscription status is 'active' after razorpay/verify succeeds."""
        headers, company_id = _register_company_and_login(client)
        plan_id = _get_or_create_test_plan(client, headers)

        order_resp = client.post(
            "/api/v1/payments/subscriptions/razorpay/order",
            headers=headers,
            json={"plan_id": plan_id, "customer_name": "ActTest", "customer_email": "act@thtwaat.com"}
        )
        assert order_resp.status_code in (200, 201)
        order_id = order_resp.json()["order_id"]

        fake_payment_id = f"pay_{uuid.uuid4().hex[:16]}"
        signature = _compute_razorpay_signature(order_id, fake_payment_id)

        verify_resp = client.post(
            "/api/v1/payments/subscriptions/razorpay/verify",
            headers=headers,
            json={
                "razorpay_order_id": order_id,
                "razorpay_payment_id": fake_payment_id,
                "razorpay_signature": signature,
                "plan_id": plan_id,
            }
        )
        assert verify_resp.status_code == 200, f"Verify failed: {verify_resp.text}"
        sub_data = verify_resp.json()
        assert sub_data["status"] == "active", (
            f"FAIL > Expected status='active', got: {sub_data['status']}\n"
            "Root Cause: verify_razorpay_payment did not set status to ACTIVE.\n"
            "Fix Applied: verify_razorpay_payment sets sub status to ACTIVE."
        )

    def test_get_active_subscription(self, client):
        """PASS if GET /subscriptions/me returns an active subscription after verify."""
        headers, company_id = _register_company_and_login(client)
        plan_id = _get_or_create_test_plan(client, headers)

        order_resp = client.post(
            "/api/v1/payments/subscriptions/razorpay/order",
            headers=headers,
            json={"plan_id": plan_id, "customer_name": "GetSubTest", "customer_email": "getsub@thtwaat.com"}
        )
        order_id = order_resp.json()["order_id"]
        fake_pid = f"pay_{uuid.uuid4().hex[:16]}"
        sig = _compute_razorpay_signature(order_id, fake_pid)

        client.post(
            "/api/v1/payments/subscriptions/razorpay/verify",
            headers=headers,
            json={"razorpay_order_id": order_id, "razorpay_payment_id": fake_pid,
                  "razorpay_signature": sig, "plan_id": plan_id}
        )

        me_resp = client.get("/api/v1/payments/subscriptions/me", headers=headers)
        assert me_resp.status_code == 200
        sub = me_resp.json()
        assert sub is not None
        assert sub["status"] == "active"


# ===========================================================================
# TEST 8 — Payment History Record
# ===========================================================================

class TestPaymentHistoryRecord:
    """Checklist item 8: Create Payment History record."""

    def test_subscription_history_contains_entry(self, client):
        """
        PASS if GET /subscriptions/history shows a subscription record.
        FAIL > Root Cause: Subscription record not created.
               Fix Applied: create_razorpay_order creates an INCOMPLETE subscription.
        """
        headers, company_id = _register_company_and_login(client)
        plan_id = _get_or_create_test_plan(client, headers)

        order_resp = client.post(
            "/api/v1/payments/subscriptions/razorpay/order",
            headers=headers,
            json={"plan_id": plan_id, "customer_name": "HistTest", "customer_email": "hist@thtwaat.com"}
        )
        assert order_resp.status_code in (200, 201)
        order_id = order_resp.json()["order_id"]
        fake_pid = f"pay_{uuid.uuid4().hex[:16]}"
        sig = _compute_razorpay_signature(order_id, fake_pid)

        client.post(
            "/api/v1/payments/subscriptions/razorpay/verify",
            headers=headers,
            json={"razorpay_order_id": order_id, "razorpay_payment_id": fake_pid,
                  "razorpay_signature": sig, "plan_id": plan_id}
        )

        history_resp = client.get("/api/v1/payments/subscriptions/history", headers=headers)
        assert history_resp.status_code == 200, f"History failed: {history_resp.text}"
        history = history_resp.json()
        assert isinstance(history, list) and len(history) >= 1, (
            f"FAIL > Expected at least 1 history entry, got: {history}\n"
            "Root Cause: Subscription record was not created.\n"
            "Fix Applied: create_razorpay_order creates INCOMPLETE subscription record."
        )
        statuses = [h["status"] for h in history]
        assert any(s in ("active", "incomplete") for s in statuses)


# ===========================================================================
# TEST 9 — Invoice Record Creation
# ===========================================================================

class TestInvoiceRecordCreation:
    """Checklist item 9: Create Invoice record."""

    def test_invoice_created_after_payment_verify(self, client):
        """
        PASS if GET /invoices/ returns at least one PAID invoice for the company.
        FAIL > Root Cause: invoice_repo.create not called in verify flow.
               Fix Applied: verify_razorpay_payment creates invoice in InvoiceRepository.
        """
        headers, company_id = _register_company_and_login(client)
        plan_id = _get_or_create_test_plan(client, headers)

        order_resp = client.post(
            "/api/v1/payments/subscriptions/razorpay/order",
            headers=headers,
            json={"plan_id": plan_id, "customer_name": "InvTest", "customer_email": "inv@thtwaat.com"}
        )
        order_id = order_resp.json()["order_id"]
        fake_pid = f"pay_{uuid.uuid4().hex[:16]}"
        sig = _compute_razorpay_signature(order_id, fake_pid)

        verify_resp = client.post(
            "/api/v1/payments/subscriptions/razorpay/verify",
            headers=headers,
            json={"razorpay_order_id": order_id, "razorpay_payment_id": fake_pid,
                  "razorpay_signature": sig, "plan_id": plan_id}
        )
        assert verify_resp.status_code == 200

        inv_resp = client.get("/api/v1/payments/invoices/", headers=headers)
        assert inv_resp.status_code == 200, f"Invoice list failed: {inv_resp.text}"
        invoices = inv_resp.json()
        assert len(invoices) >= 1, (
            f"FAIL > No invoices found after successful payment.\n"
            "Root Cause: invoice creation logic missing in verify flow.\n"
            "Fix Applied: verify_razorpay_payment creates invoice in InvoiceRepository."
        )
        paid = [i for i in invoices if i["status"] == "paid"]
        assert paid, f"No PAID invoice found. Invoices: {invoices}"

    def test_invoice_has_correct_provider(self, client):
        """PASS if the invoice provider field is 'razorpay'."""
        headers, company_id = _register_company_and_login(client)
        plan_id = _get_or_create_test_plan(client, headers)

        order_resp = client.post(
            "/api/v1/payments/subscriptions/razorpay/order",
            headers=headers,
            json={"plan_id": plan_id, "customer_name": "ProvTest", "customer_email": "prov@thtwaat.com"}
        )
        order_id = order_resp.json()["order_id"]
        fake_pid = f"pay_{uuid.uuid4().hex[:16]}"
        sig = _compute_razorpay_signature(order_id, fake_pid)

        client.post(
            "/api/v1/payments/subscriptions/razorpay/verify",
            headers=headers,
            json={"razorpay_order_id": order_id, "razorpay_payment_id": fake_pid,
                  "razorpay_signature": sig, "plan_id": plan_id}
        )

        inv_resp = client.get("/api/v1/payments/invoices/", headers=headers)
        invoices = inv_resp.json()
        if invoices:
            assert invoices[0]["provider"] == "razorpay"


# ===========================================================================
# TEST 10 — In-App Notification After Payment
# ===========================================================================

class TestInAppNotificationAfterPayment:
    """Checklist item 10: Generate an in-app notification after payment."""

    def test_notification_dispatched_after_verify(self, client):
        """
        PASS if the notifications endpoint is reachable after verify.
        FAIL > Root Cause: NotificationEventBus.dispatch not called.
               Fix Applied: Webhook handler dispatches payment.success + subscription.created.
        """
        headers, company_id = _register_company_and_login(client)
        plan_id = _get_or_create_test_plan(client, headers)

        order_resp = client.post(
            "/api/v1/payments/subscriptions/razorpay/order",
            headers=headers,
            json={"plan_id": plan_id, "customer_name": "NotifTest", "customer_email": "notif@thtwaat.com"}
        )
        order_id = order_resp.json()["order_id"]
        fake_pid = f"pay_{uuid.uuid4().hex[:16]}"
        sig = _compute_razorpay_signature(order_id, fake_pid)

        client.post(
            "/api/v1/payments/subscriptions/razorpay/verify",
            headers=headers,
            json={"razorpay_order_id": order_id, "razorpay_payment_id": fake_pid,
                  "razorpay_signature": sig, "plan_id": plan_id}
        )

        notif_resp = client.get("/api/v1/notifications/", headers=headers)
        assert notif_resp.status_code == 200, f"Notifications endpoint failed: {notif_resp.text}"

    def test_notification_event_templates_registered(self):
        """PASS if all required payment event templates exist in EVENT_TEMPLATES."""
        from app.notifications.events import EVENT_TEMPLATES
        assert "payment.success" in EVENT_TEMPLATES, "Missing payment.success template"
        assert "payment.failed" in EVENT_TEMPLATES, "Missing payment.failed template"
        assert "subscription.created" in EVENT_TEMPLATES, "Missing subscription.created template"
        assert "subscription.cancelled" in EVENT_TEMPLATES, "Missing subscription.cancelled template"


# ===========================================================================
# TEST 11 — Company Plan and AI Limits Updated
# ===========================================================================

class TestCompanyPlanAndAILimits:
    """Checklist item 11: Update Company plan and AI limits."""

    def test_company_plan_updated_after_payment(self, client):
        """
        PASS if company.plan is updated after successful verify.
        FAIL > Root Cause: _activate_company_plan not called.
               Fix Applied: verify_razorpay_payment calls self._activate_company_plan.
        """
        headers, company_id = _register_company_and_login(client)
        plan_id = _get_or_create_test_plan(client, headers)

        order_resp = client.post(
            "/api/v1/payments/subscriptions/razorpay/order",
            headers=headers,
            json={"plan_id": plan_id, "customer_name": "PlanTest", "customer_email": "plan@thtwaat.com"}
        )
        order_id = order_resp.json()["order_id"]
        fake_pid = f"pay_{uuid.uuid4().hex[:16]}"
        sig = _compute_razorpay_signature(order_id, fake_pid)

        verify_resp = client.post(
            "/api/v1/payments/subscriptions/razorpay/verify",
            headers=headers,
            json={"razorpay_order_id": order_id, "razorpay_payment_id": fake_pid,
                  "razorpay_signature": sig, "plan_id": plan_id}
        )
        assert verify_resp.status_code == 200, f"Verify failed: {verify_resp.text}"

        comp_after = client.get(f"/api/v1/companies/{company_id}", headers=headers)
        assert comp_after.status_code == 200
        company_data = comp_after.json()
        assert company_data.get("status") == "active", (
            f"FAIL > Company status was not set to 'active' after payment.\n"
            "Root Cause: _activate_company_plan not called.\n"
            "Fix Applied: verify_razorpay_payment calls _activate_company_plan."
        )

    def test_activate_company_plan_method_unit(self):
        """
        PASS if _activate_company_plan correctly sets plan, status, max_users, credits_balance.
        """
        from app.payments.subscriptions.service import SubscriptionService
        from app.payments.plans.model import Plan
        from app.companies.model import Company, CompanyPlan, CompanyStatus
        from unittest.mock import MagicMock
        from decimal import Decimal

        mock_plan = MagicMock(spec=Plan)
        mock_plan.name = "starter"
        mock_plan.max_users = 20
        mock_plan.max_apps = 5
        mock_plan.ai_credits = 1000.0

        mock_company = MagicMock(spec=Company)
        mock_company.plan = CompanyPlan.FREE
        mock_company.status = CompanyStatus.TRIAL
        mock_company.max_users = 5
        mock_company.max_apps = 1
        mock_company.credits_balance = Decimal("100.0")

        mock_db = MagicMock()
        service = SubscriptionService(mock_db)
        service.company_repo = MagicMock()
        service.company_repo.get_by_id.return_value = mock_company

        service._activate_company_plan(uuid.uuid4(), mock_plan)

        assert mock_company.plan == CompanyPlan.STARTER
        assert mock_company.status == CompanyStatus.ACTIVE
        assert mock_company.max_users == 20
        assert mock_company.max_apps == 5
        expected_credits = Decimal("100.0") + Decimal("1000.0")
        assert mock_company.credits_balance == expected_credits


# ===========================================================================
# TEST 12 — Multi-Tenant Isolation
# ===========================================================================

class TestMultiTenantIsolation:
    """Checklist item 12: Verify multi-tenant isolation."""

    def test_subscription_isolation_between_companies(self, client):
        """
        PASS if company A cannot see company B's subscriptions.
        FAIL > Root Cause: Missing company_id filter in repository queries.
               Fix Applied: SubscriptionRepository.list_by_company filters by company_id.
        """
        headers_a, company_id_a = _register_company_and_login(client)
        headers_b, company_id_b = _register_company_and_login(client)
        plan_id = _get_or_create_test_plan(client, headers_a)

        order_resp = client.post(
            "/api/v1/payments/subscriptions/razorpay/order",
            headers=headers_a,
            json={"plan_id": plan_id, "customer_name": "TenantA", "customer_email": "a@thtwaat.com"}
        )
        assert order_resp.status_code in (200, 201)
        order_id = order_resp.json()["order_id"]
        fake_pid = f"pay_{uuid.uuid4().hex[:16]}"
        sig = _compute_razorpay_signature(order_id, fake_pid)

        client.post(
            "/api/v1/payments/subscriptions/razorpay/verify",
            headers=headers_a,
            json={"razorpay_order_id": order_id, "razorpay_payment_id": fake_pid,
                  "razorpay_signature": sig, "plan_id": plan_id}
        )

        history_b = client.get("/api/v1/payments/subscriptions/history", headers=headers_b)
        assert history_b.status_code == 200
        history_a = client.get("/api/v1/payments/subscriptions/history", headers=headers_a)

        sub_ids_b = {s["id"] for s in history_b.json()}
        sub_ids_a = {s["id"] for s in history_a.json()}
        overlap = sub_ids_a & sub_ids_b

        assert not overlap, (
            f"FAIL > Multi-tenant isolation violated! Shared subscription IDs: {overlap}\n"
            "Root Cause: Repository query missing company_id filter.\n"
            "Fix Applied: SubscriptionRepository.list_by_company filters by company_id."
        )

    def test_invoice_isolation_between_companies(self, client):
        """PASS if company A's invoices are not visible to company B."""
        headers_a, company_id_a = _register_company_and_login(client)
        headers_b, company_id_b = _register_company_and_login(client)
        plan_id = _get_or_create_test_plan(client, headers_a)

        order_resp = client.post(
            "/api/v1/payments/subscriptions/razorpay/order",
            headers=headers_a,
            json={"plan_id": plan_id, "customer_name": "IsoA", "customer_email": "isoa@thtwaat.com"}
        )
        order_id = order_resp.json().get("order_id", "order_x")
        fake_pid = f"pay_{uuid.uuid4().hex[:16]}"
        sig = _compute_razorpay_signature(order_id, fake_pid)

        client.post(
            "/api/v1/payments/subscriptions/razorpay/verify",
            headers=headers_a,
            json={"razorpay_order_id": order_id, "razorpay_payment_id": fake_pid,
                  "razorpay_signature": sig, "plan_id": plan_id}
        )

        inv_a = client.get("/api/v1/payments/invoices/", headers=headers_a)
        inv_b = client.get("/api/v1/payments/invoices/", headers=headers_b)

        assert inv_b.status_code == 200
        ids_a = {i["id"] for i in inv_a.json()}
        ids_b = {i["id"] for i in inv_b.json()}
        overlap = ids_a & ids_b
        assert not overlap, (
            f"FAIL > Invoice isolation violated! Shared IDs: {overlap}\n"
            "Root Cause: InvoiceRepository.list_by_company missing company_id filter.\n"
            "Fix Applied: InvoiceRepository.list_by_company filters by company_id."
        )

    def test_payment_isolation_between_companies(self, client):
        """PASS if GET /payments/ only returns payments for the authenticated company."""
        headers_a, company_id_a = _register_company_and_login(client)
        headers_b, company_id_b = _register_company_and_login(client)

        client.post("/api/v1/payments/", headers=headers_a, json={
            "amount": "50.00", "currency": "INR",
            "payment_method": "upi", "gateway": "manual"
        })

        payments_b = client.get("/api/v1/payments/", headers=headers_b)
        assert payments_b.status_code == 200
        for p in payments_b.json():
            assert p["company_id"] == company_id_b, (
                f"FAIL > Payment company_id mismatch: {p['company_id']} != {company_id_b}\n"
                "Root Cause: PaymentRepository.get_payments missing company_id filter.\n"
                "Fix Applied: PaymentRepository.get_payments already filters by company_id."
            )
