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

def test_get_existing_app(client):
    headers, company_id = get_auth(client)
    slug = f"app-{uuid.uuid4().hex[:8]}"
    create_resp = client.post("/api/v1/apps/", json={
        "name": "Test App",
        "slug": slug,
        "type": "web",
        "company_id": company_id
    }, headers=headers)
    assert create_resp.status_code == 201
    app_id = create_resp.json()["id"]
    
    get_resp = client.get(f"/api/v1/apps/{app_id}", headers=headers)
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == app_id

def test_get_missing_app(client):
    headers, _ = get_auth(client)
    fake_id = str(uuid.uuid4())
    get_resp = client.get(f"/api/v1/apps/{fake_id}", headers=headers)
    assert get_resp.status_code == 404
