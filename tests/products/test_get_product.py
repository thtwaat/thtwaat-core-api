import uuid
import pytest

def get_auth_and_app(client):
    company_slug = f"comp-{uuid.uuid4().hex[:8]}"
    company_resp = client.post("/api/v1/companies/", json={"name": "Prod Company", "slug": company_slug})
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
    
    app_resp = client.post("/api/v1/apps/", json={
        "name": "Test App",
        "slug": f"app-{uuid.uuid4().hex[:8]}",
        "type": "web",
        "company_id": company_id
    }, headers=headers)
    app_id = app_resp.json()["id"]

    return headers, company_id, app_id

def test_get_existing_product(client):
    headers, company_id, app_id = get_auth_and_app(client)
    slug = f"prod-{uuid.uuid4().hex[:8]}"
    create_resp = client.post("/api/v1/products/", json={
        "name": "Test Product",
        "slug": slug,
        "app_id": app_id,
        "category": "Website"
    }, headers=headers)
    assert create_resp.status_code == 201
    prod_id = create_resp.json()["id"]
    
    get_resp = client.get(f"/api/v1/products/{prod_id}", headers=headers)
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == prod_id

def test_get_missing_product(client):
    headers, _, _ = get_auth_and_app(client)
    fake_id = str(uuid.uuid4())
    get_resp = client.get(f"/api/v1/products/{fake_id}", headers=headers)
    assert get_resp.status_code == 404
