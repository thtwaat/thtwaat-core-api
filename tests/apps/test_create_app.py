import uuid
import pytest

def get_auth(client):
    company_slug = f"comp-{uuid.uuid4().hex[:8]}"
    company_resp = client.post("/api/v1/companies/", json={"name": "Auth Company", "slug": company_slug})
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
    return {"Authorization": f"Bearer {login_resp.json()['access_token']}"}, company_id

def test_create_app(client):
    headers, company_id = get_auth(client)
    slug = f"app-{uuid.uuid4().hex[:8]}"
    resp = client.post("/api/v1/apps/", json={
        "name": "Test App",
        "slug": slug,
        "type": "web",
        "company_id": company_id
    }, headers=headers)
    assert resp.status_code == 201
    assert resp.json()["slug"] == slug

def test_create_app_duplicate_slug(client):
    headers, company_id = get_auth(client)
    slug = f"dup-{uuid.uuid4().hex[:8]}"
    payload = {
        "name": "Test App",
        "slug": slug,
        "type": "web",
        "company_id": company_id
    }
    res1 = client.post("/api/v1/apps/", json=payload, headers=headers)
    assert res1.status_code == 201
    
    res2 = client.post("/api/v1/apps/", json=payload, headers=headers)
    assert res2.status_code >= 400

def test_create_app_invalid_payload(client):
    headers, _ = get_auth(client)
    resp = client.post("/api/v1/apps/", json={"name": "Missing everything"}, headers=headers)
    assert resp.status_code == 422

def test_create_app_company_not_found(client):
    headers, _ = get_auth(client)
    fake_company_id = str(uuid.uuid4())
    resp = client.post("/api/v1/apps/", json={
        "name": "Fake App",
        "slug": f"fake-{uuid.uuid4().hex[:8]}",
        "type": "web",
        "company_id": fake_company_id
    }, headers=headers)
    assert resp.status_code >= 400
