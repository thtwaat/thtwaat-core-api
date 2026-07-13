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

def test_update_payment_status(client):
    headers, company_id = get_auth(client)
    payload = {
        "amount": 20.00,
        "currency": "USD",
        "payment_method": "wallet",
        "gateway": "paypal"
    }
    create_resp = client.post("/api/v1/payments/", json=payload, headers=headers)
    assert create_resp.status_code == 201
    payment_id = create_resp.json()["id"]

    update_payload = {
        "status": "success",
        "gateway_transaction_id": f"txn_{uuid.uuid4().hex[:8]}"
    }
    update_resp = client.patch(f"/api/v1/payments/{payment_id}/status", json=update_payload, headers=headers)
    assert update_resp.status_code == 200
    assert update_resp.json()["status"] == "success"
