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

def test_delete_payment(client):
    headers, company_id = get_auth(client)
    payload = {
        "amount": 25.00,
        "currency": "USD",
        "payment_method": "card",
        "gateway": "stripe"
    }
    create_resp = client.post("/api/v1/payments/", json=payload, headers=headers)
    assert create_resp.status_code == 201
    payment_id = create_resp.json()["id"]

    del_resp = client.delete(f"/api/v1/payments/{payment_id}", headers=headers)
    assert del_resp.status_code == 204

    get_resp = client.get(f"/api/v1/payments/{payment_id}", headers=headers)
    assert get_resp.status_code == 404

def test_delete_missing_payment(client):
    headers, company_id = get_auth(client)
    fake_id = str(uuid.uuid4())
    del_resp = client.delete(f"/api/v1/payments/{fake_id}", headers=headers)
    assert del_resp.status_code == 404
