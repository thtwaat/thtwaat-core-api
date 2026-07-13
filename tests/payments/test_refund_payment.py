import uuid
import pytest

def get_auth(client):
    company_slug = f"comp-{uuid.uuid4().hex[:8]}"
    company_resp = client.post("/api/v1/companies/", json={"name": "Payment Company", "slug": company_slug})
    company_id = company_resp.json()["id"]
    
    email = f"admin-{uuid.uuid4().hex[:8]}@example.com"
    password = "securepassword"
    
    client.post("/api/v1/users/", json={
        "email": email,
        "password": password,
        "company_id": company_id,
        "first_name": "Admin",
        "last_name": "User",
        "role": "admin"
    })
    
    login_resp = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    headers = {"Authorization": f"Bearer {login_resp.json()['access_token']}"}
    return headers, company_id

def test_refund_payment(client):
    headers, company_id = get_auth(client)
    payload = {
        "amount": 150.00,
        "currency": "USD",
        "payment_method": "card",
        "gateway": "stripe"
    }
    create_resp = client.post("/api/v1/payments/", json=payload, headers=headers)
    assert create_resp.status_code == 201
    payment_id = create_resp.json()["id"]

    update_payload = {"status": "success", "gateway_transaction_id": "txn_123"}
    client.patch(f"/api/v1/payments/{payment_id}/status", json=update_payload, headers=headers)

    refund_resp = client.post(f"/api/v1/payments/{payment_id}/refund", headers=headers)
    assert refund_resp.status_code == 200
    assert refund_resp.json()["status"] == "refunded"

def test_refund_already_refunded_payment(client):
    headers, company_id = get_auth(client)
    payload = {
        "amount": 150.00,
        "currency": "USD",
        "payment_method": "card",
        "gateway": "stripe"
    }
    create_resp = client.post("/api/v1/payments/", json=payload, headers=headers)
    payment_id = create_resp.json()["id"]

    update_payload = {"status": "success", "gateway_transaction_id": "txn_123"}
    client.patch(f"/api/v1/payments/{payment_id}/status", json=update_payload, headers=headers)

    # First refund
    client.post(f"/api/v1/payments/{payment_id}/refund", headers=headers)

    # Second refund
    refund_resp = client.post(f"/api/v1/payments/{payment_id}/refund", headers=headers)
    assert refund_resp.status_code == 400
