import logging
from fastapi.testclient import TestClient
from main import app
from app.database.database import engine
from app.models.base import Base

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

client = TestClient(app)

def run_tests():
    logger.info("Starting verification...")
    import uuid
    uid = uuid.uuid4().hex[:6]

    # 1. Verify all routers are in swagger
    resp = client.get("/openapi.json")
    assert resp.status_code == 200
    openapi = resp.json()
    paths = openapi["paths"]
    assert "/api/v1/companies/" in paths, "Companies router missing"
    assert "/api/v1/users/" in paths, "Users router missing"
    assert "/api/v1/auth/login" in paths, "Auth router missing"
    assert "/api/v1/apps/" in paths, "Apps router missing"
    logger.info("[OK] All routers appear in Swagger.")

    # 2. CRUD Test - Create Company
    resp = client.post("/api/v1/companies/", json={
        "name": f"Test Company {uid}",
        "slug": f"test-company-{uid}",
        "domain": f"test{uid}.com"
    })
    assert resp.status_code == 201, f"Failed to create company: {resp.text}"
    company_id = resp.json()["id"]
    logger.info("[OK] Company CRUD works.")

    # 3. CRUD Test - Create User
    resp = client.post("/api/v1/users/", json={
        "email": f"admin{uid}@test.com",
        "password": "securepassword",
        "company_id": company_id,
        "first_name": "Admin",
        "last_name": "User",
        "role": "admin"
    })
    assert resp.status_code == 201, f"Failed to create user: {resp.text}"
    logger.info("[OK] User CRUD works.")

    # 4. Login works
    resp = client.post("/api/v1/auth/login", json={
        "email": f"admin{uid}@test.com",
        "password": "securepassword"
    })
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    tokens = resp.json()
    access_token = tokens["access_token"]
    logger.info("[OK] Login works.")

    # 5. RBAC returns correct permissions (Create App requires APPS_CREATE)
    # The 'admin' role has APPS_CREATE permission in policy.py
    headers = {"Authorization": f"Bearer {access_token}"}
    resp = client.post("/api/v1/apps/", json={
        "name": "Test App",
        "slug": "test-app",
        "type": "web",
        "company_id": company_id
    }, headers=headers)
    assert resp.status_code == 201, f"App creation failed (RBAC issue?): {resp.text}"
    logger.info("[OK] RBAC returns correct permissions.")
    logger.info("[OK] Apps CRUD works.")

    # 6. Test Storage Upload
    import os
    with open("dummy.txt", "w") as f:
        f.write("Hello world!")
    
    with open("dummy.txt", "rb") as f:
        resp = client.post(
            "/api/v1/storage/upload",
            headers={"Authorization": f"Bearer {access_token}"},
            files={"file": ("dummy.txt", f, "text/plain")}
        )
    assert resp.status_code == 201, f"Upload failed: {resp.text}"
    file_id = resp.json()["id"]
    logger.info("[OK] Upload endpoint works.")
    
    # 7. Get Metadata
    resp = client.get(
        f"/api/v1/storage/{file_id}",
        headers={"Authorization": f"Bearer {access_token}"}
    )
    assert resp.status_code == 200, f"Get metadata failed: {resp.text}"
    logger.info("[OK] File metadata retrieval works.")
    
    os.remove("dummy.txt")

    # 8. Test Notifications
    resp = client.post(
        "/api/v1/notifications/send",
        headers={"Authorization": f"Bearer {access_token}"},
        json={
            "channel": "email",
            "recipient": "test@example.com",
            "subject": "Test Notification",
            "body": "Hello {name}",
            "template_name": "welcome_email",
            "template_data": {"name": "Admin"}
        }
    )
    assert resp.status_code == 201, f"Notification send failed: {resp.text}"
    notif_id = resp.json()["id"]
    logger.info("[OK] Notification send endpoint works.")
    
    # 9. Test Notification History
    resp = client.get(
        "/api/v1/notifications/history",
        headers={"Authorization": f"Bearer {access_token}"}
    )
    assert resp.status_code == 200, f"Notification history failed: {resp.text}"
    history = resp.json()
    assert len(history) >= 1
    logger.info("[OK] Notification history retrieval works.")

    # 10. Test Payments
    resp = client.post(
        "/api/v1/payments/",
        headers={"Authorization": f"Bearer {access_token}"},
        json={
            "amount": "100.50",
            "currency": "USD",
            "payment_method": "card",
            "gateway": "stripe",
            "invoice_number": f"INV-{uid}",
            "metadata": {"source": "verify.py"}
        }
    )
    assert resp.status_code == 201, f"Payment creation failed: {resp.text}"
    payment_data = resp.json()
    payment_id = payment_data["id"]
    assert payment_data["status"] == "success", "Stub should have marked as success"
    assert payment_data["gateway_transaction_id"] is not None
    logger.info("[OK] Payment creation (Stripe Stub) works.")

    resp = client.get(
        f"/api/v1/payments/{payment_id}",
        headers={"Authorization": f"Bearer {access_token}"}
    )
    assert resp.status_code == 200, f"Get payment failed: {resp.text}"
    logger.info("[OK] Get single payment works.")

    resp = client.post(
        f"/api/v1/payments/{payment_id}/refund",
        headers={"Authorization": f"Bearer {access_token}"}
    )
    assert resp.status_code == 200, f"Refund failed: {resp.text}"
    assert resp.json()["status"] == "refunded", "Stub should have refunded"
    logger.info("[OK] Payment refund (Stripe Stub) works.")
    
    resp = client.get(
        "/api/v1/payments/",
        headers={"Authorization": f"Bearer {access_token}"}
    )
    assert resp.status_code == 200, f"List payments failed: {resp.text}"
    assert len(resp.json()) >= 1
    logger.info("[OK] List payments works.")

    # 11. Test AI Gateway
    resp = client.get(
        "/api/v1/ai/health",
        headers={"Authorization": f"Bearer {access_token}"}
    )
    assert resp.status_code == 200, f"AI Health failed: {resp.text}"
    logger.info("[OK] AI Gateway Health endpoint works.")

    resp = client.post(
        "/api/v1/ai/generate",
        headers={"Authorization": f"Bearer {access_token}"},
        json={
            "prompt": "Write a test.",
            "provider": "openai",
            "model": "gpt-4o"
        }
    )
    assert resp.status_code == 200, f"AI Generate failed: {resp.text}"
    logger.info("[OK] AI Generate endpoint works (OpenAI Stub).")

    resp = client.post(
        "/api/v1/ai/chat",
        headers={"Authorization": f"Bearer {access_token}"},
        json={
            "messages": [{"role": "user", "content": "Hello"}],
            "provider": "gemini",
            "model": "gemini-1.5-pro"
        }
    )
    assert resp.status_code == 200, f"AI Chat failed: {resp.text}"
    logger.info("[OK] AI Chat endpoint works (Gemini Stub).")

    resp = client.get(
        "/api/v1/ai/history",
        headers={"Authorization": f"Bearer {access_token}"}
    )
    assert resp.status_code == 200, f"AI History failed: {resp.text}"
    history_len = len(resp.json())
    assert history_len >= 2, f"Expected at least 2 AI requests in history, got {history_len}"
    logger.info("[OK] AI History endpoint works.")

    # 12. Test Products Module
    product_name = f"My New Website {uuid.uuid4().hex[:6]}"
    resp = client.post(
        "/api/v1/products/",
        headers={"Authorization": f"Bearer {access_token}"},
        json={
            "name": product_name,
            "category": "Website",
            "description": "A test website product",
            "ai_enabled": True
        }
    )
    assert resp.status_code == 201, f"Product creation failed: {resp.text}"
    product_data = resp.json()
    product_id = product_data["id"]
    expected_slug = product_name.lower().replace(" ", "-")
    assert product_data["slug"] == expected_slug, f"Slug generation failed: {product_data['slug']}"
    assert product_data["ai_enabled"] is True
    logger.info("[OK] Product creation and auto-slug works.")

    resp = client.patch(
        f"/api/v1/products/{product_id}",
        headers={"Authorization": f"Bearer {access_token}"},
        json={
            "name": f"Updated {product_name}"
        }
    )
    assert resp.status_code == 200, f"Product update failed: {resp.text}"
    expected_updated_slug = f"updated-{expected_slug}"
    assert resp.json()["slug"] == expected_updated_slug, "Slug should auto-update if name changes and slug not provided"
    logger.info("[OK] Product update works.")

    resp = client.get(
        "/api/v1/products/",
        headers={"Authorization": f"Bearer {access_token}"}
    )
    assert resp.status_code == 200, f"List products failed: {resp.text}"
    assert len(resp.json()) >= 1
    logger.info("[OK] List products works.")

    resp = client.delete(
        f"/api/v1/products/{product_id}",
        headers={"Authorization": f"Bearer {access_token}"}
    )
    assert resp.status_code == 200, f"Delete product failed: {resp.text}"
    logger.info("[OK] Product deletion works.")

    # 13. Password reset via email link (OTP removed)
    import unittest.mock as mock
    from app.auth.service import AuthService

    captured: dict = {}

    def _capture_reset(self, recipient: str, reset_url: str) -> None:
        captured["reset_url"] = reset_url

    with mock.patch.object(AuthService, "_send_password_reset_email", _capture_reset):
        resp = client.post("/api/v1/auth/forgot-password", json={"email": f"admin{uid}@test.com"})
        assert resp.status_code == 200, f"Forgot password failed: {resp.text}"
        assert "token=" in captured.get("reset_url", "")
        token = captured["reset_url"].split("token=", 1)[1]
        resp = client.post(
            "/api/v1/auth/reset-password",
            json={"token": token, "new_password": "newsecurepassword123"},
        )
        assert resp.status_code == 200, f"Reset password failed: {resp.text}"
        logger.info("[OK] Password Reset works.")

    # OTP routes must be gone
    assert client.post("/api/v1/auth/send-otp", json={"purpose": "LOGIN", "email": f"admin{uid}@test.com"}).status_code == 404
    logger.info("[OK] OTP routes removed.")

    # 15. Test MFA Flow
    # First login with new password to get access token
    resp = client.post("/api/v1/auth/login", json={
        "email": f"admin{uid}@test.com",
        "password": "newsecurepassword123"
    })
    assert resp.status_code == 200
    access_token = resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {access_token}"}
    
    # Setup MFA
    resp = client.post("/api/v1/auth/mfa/setup", headers=headers)
    assert resp.status_code == 200, f"MFA Setup failed: {resp.text}"
    mfa_secret = resp.json()["secret"]
    logger.info("[OK] MFA Setup works.")
    
    # Enable MFA
    import pyotp
    totp = pyotp.TOTP(mfa_secret)
    valid_code = totp.now()
    resp = client.post("/api/v1/auth/mfa/enable", headers=headers, json={"code": valid_code})
    assert resp.status_code == 200, f"MFA Enable failed: {resp.text}"
    logger.info("[OK] MFA Enable works.")
    
    # Login again with MFA enabled
    resp = client.post("/api/v1/auth/login", json={
        "email": f"admin{uid}@test.com",
        "password": "newsecurepassword123"
    })
    assert resp.status_code == 200, f"Login with MFA enabled failed: {resp.text}"
    assert resp.json()["mfa_required"] == True
    mfa_token = resp.json()["mfa_token"]
    logger.info("[OK] Login returned MFA token.")
    
    # Verify MFA
    valid_code = totp.now()
    resp = client.post("/api/v1/auth/mfa/verify", json={"mfa_token": mfa_token, "totp": valid_code})
    assert resp.status_code == 200, f"MFA Verify failed: {resp.text}"
    assert "access_token" in resp.json()
    logger.info("[OK] MFA Verify works.")

    logger.info("All verifications passed!")

if __name__ == "__main__":
    run_tests()
