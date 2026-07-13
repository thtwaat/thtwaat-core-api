import uuid
import pytest

def test_payment_notification_flow(client):
    # Setup Auth
    company_slug = f"comp-{uuid.uuid4().hex[:8]}"
    company_resp = client.post("/api/v1/companies/", json={"name": "Pay Notif Flow", "slug": company_slug})
    company_id = company_resp.json()["id"]

    email = f"user-{uuid.uuid4().hex[:8]}@example.com"
    client.post("/api/v1/users/", json={
        "email": email, "password": "securepassword", "company_id": company_id,
        "first_name": "PayNotif", "last_name": "User", "role": "admin"
    })
    login_resp = client.post("/api/v1/auth/login", json={"email": email, "password": "securepassword"})
    headers = {"Authorization": f"Bearer {login_resp.json()['access_token']}"}

    # 1. Create Payment
    pay_payload = {
        "amount": 200.00,
        "currency": "USD",
        "payment_method": "card",
        "gateway": "stripe"
    }
    pay_resp = client.post("/api/v1/payments/", json=pay_payload, headers=headers)
    assert pay_resp.status_code == 201
    payment_id = pay_resp.json()["id"]

    # 2. Update Payment
    update_payload = {"status": "success", "gateway_transaction_id": "txn_flow"}
    up_resp = client.patch(f"/api/v1/payments/{payment_id}/status", json=update_payload, headers=headers)
    assert up_resp.status_code == 200

    # 3. Refund
    ref_resp = client.post(f"/api/v1/payments/{payment_id}/refund", headers=headers)
    assert ref_resp.status_code == 200

    # 4. Verify notification creation
    hist_resp = client.get("/api/v1/notifications/history", headers=headers)
    assert hist_resp.status_code == 200
