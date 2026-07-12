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
    logger.info("✅ All routers appear in Swagger.")

    # 2. CRUD Test - Create Company
    resp = client.post("/api/v1/companies/", json={
        "name": f"Test Company {uid}",
        "slug": f"test-company-{uid}",
        "domain": f"test{uid}.com"
    })
    assert resp.status_code == 201, f"Failed to create company: {resp.text}"
    company_id = resp.json()["id"]
    logger.info("✅ Company CRUD works.")

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
    logger.info("✅ User CRUD works.")

    # 4. Login works
    resp = client.post("/api/v1/auth/login", json={
        "email": f"admin{uid}@test.com",
        "password": "securepassword"
    })
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    tokens = resp.json()
    access_token = tokens["access_token"]
    logger.info("✅ Login works.")

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
    logger.info("✅ RBAC returns correct permissions.")
    logger.info("✅ Apps CRUD works.")

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
    logger.info("✅ Upload endpoint works.")
    
    # 7. Get Metadata
    resp = client.get(
        f"/api/v1/storage/{file_id}",
        headers={"Authorization": f"Bearer {access_token}"}
    )
    assert resp.status_code == 200, f"Get metadata failed: {resp.text}"
    logger.info("✅ File metadata retrieval works.")
    
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
    logger.info("✅ Notification send endpoint works.")
    
    # 9. Test Notification History
    resp = client.get(
        "/api/v1/notifications/history",
        headers={"Authorization": f"Bearer {access_token}"}
    )
    assert resp.status_code == 200, f"Notification history failed: {resp.text}"
    history = resp.json()
    assert len(history) >= 1
    logger.info("✅ Notification history retrieval works.")

    # 10. Test Payments
    resp = client.post(
        "/api/v1/payments/",
        headers={"Authorization": f"Bearer {access_token}"},
        json={
            "amount": "100.50",
            "currency": "USD",
            "payment_method": "card",
            "gateway": "stripe",
            "invoice_number": "INV-1001",
            "metadata": {"source": "verify.py"}
        }
    )
    assert resp.status_code == 201, f"Payment creation failed: {resp.text}"
    payment_data = resp.json()
    payment_id = payment_data["id"]
    assert payment_data["status"] == "success", "Stub should have marked as success"
    assert payment_data["gateway_transaction_id"] is not None
    logger.info("✅ Payment creation (Stripe Stub) works.")

    resp = client.get(
        f"/api/v1/payments/{payment_id}",
        headers={"Authorization": f"Bearer {access_token}"}
    )
    assert resp.status_code == 200, f"Get payment failed: {resp.text}"
    logger.info("✅ Get single payment works.")

    resp = client.post(
        f"/api/v1/payments/{payment_id}/refund",
        headers={"Authorization": f"Bearer {access_token}"}
    )
    assert resp.status_code == 200, f"Refund failed: {resp.text}"
    assert resp.json()["status"] == "refunded", "Stub should have refunded"
    logger.info("✅ Payment refund (Stripe Stub) works.")
    
    resp = client.get(
        "/api/v1/payments/",
        headers={"Authorization": f"Bearer {access_token}"}
    )
    assert resp.status_code == 200, f"List payments failed: {resp.text}"
    assert len(resp.json()) >= 1
    logger.info("✅ List payments works.")

    logger.info("All verifications passed!")

if __name__ == "__main__":
    run_tests()
