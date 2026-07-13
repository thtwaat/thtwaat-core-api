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

def test_update_app(client):
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
    
    update_resp = client.patch(
        f"/api/v1/apps/{app_id}",
        json={"name": "Updated App Name"},
        headers=headers
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["name"] == "Updated App Name"

def test_update_missing_app(client):
    headers, _ = get_auth(client)
    fake_id = str(uuid.uuid4())
    update_resp = client.patch(
        f"/api/v1/apps/{fake_id}",
        json={"name": "Will Fail"},
        headers=headers
    )
    assert update_resp.status_code == 404
