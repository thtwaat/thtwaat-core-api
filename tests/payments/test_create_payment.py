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

def test_create_payment(client):
    headers, company_id = get_auth(client)
    payload = {
        "amount": 100.50,
        "currency": "USD",
        "payment_method": "card",
        "gateway": "stripe"
    }
    resp = client.post("/api/v1/payments/", json=payload, headers=headers)
    assert resp.status_code == 201
    assert resp.json()["amount"] == 100.50
    # The provider stub sets it to success or failed, check it doesn't 500
    assert resp.json()["status"] in ["pending", "success", "failed"]

def test_create_payment_invalid_amount(client):
    headers, company_id = get_auth(client)
    payload = {
        "amount": -50.00,
        "currency": "USD",
        "payment_method": "card",
        "gateway": "stripe"
    }
    resp = client.post("/api/v1/payments/", json=payload, headers=headers)
    assert resp.status_code == 422

def test_create_payment_invalid_payment_method(client):
    headers, company_id = get_auth(client)
    payload = {
        "amount": 100.50,
        "currency": "USD",
        "payment_method": "telepathy",
        "gateway": "stripe"
    }
    resp = client.post("/api/v1/payments/", json=payload, headers=headers)
    assert resp.status_code == 422
