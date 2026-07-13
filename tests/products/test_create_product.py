import uuid
import pytest
from main import app
from app.auth.router import get_current_user

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

def test_create_product(client):
    headers, company_id, app_id = get_auth_and_app(client)
    slug = f"prod-{uuid.uuid4().hex[:8]}"
    resp = client.post("/api/v1/products/", json={
        "name": "Test Product",
        "slug": slug,
        "app_id": app_id,
        "category": "Website",
        "description": "Desc"
    }, headers=headers)
    assert resp.status_code == 201
    assert resp.json()["slug"] == slug

def test_create_product_duplicate_slug(client):
    headers, company_id, app_id = get_auth_and_app(client)
    slug = f"dup-{uuid.uuid4().hex[:8]}"
    payload = {
        "name": "Test Product",
        "slug": slug,
        "app_id": app_id,
        "category": "Website"
    }
    r1 = client.post("/api/v1/products/", json=payload, headers=headers)
    assert r1.status_code == 201
    
    r2 = client.post("/api/v1/products/", json=payload, headers=headers)
    assert r2.status_code == 201
    assert r2.json()["slug"] != r1.json()["slug"]
    assert r2.json()["slug"].startswith(slug)

def test_create_product_invalid_payload(client):
    headers, _, _ = get_auth_and_app(client)
    resp = client.post("/api/v1/products/", json={"name": "only name"}, headers=headers)
    assert resp.status_code == 422

class DummyUser:
    def __init__(self, company_id):
        self.company_id = company_id
        self.id = uuid.uuid4()
        self.role = "admin"

def test_create_product_company_not_found(client):
    headers, company_id, app_id = get_auth_and_app(client)
    fake_company_id = uuid.uuid4()
    
    app.dependency_overrides[get_current_user] = lambda: DummyUser(company_id=fake_company_id)
    
    resp = client.post("/api/v1/products/", json={
        "name": "Test Product",
        "slug": f"fake-{uuid.uuid4().hex[:8]}",
        "category": "Website"
    }, headers=headers)
    
    app.dependency_overrides.clear()
    assert resp.status_code >= 400

def test_create_product_app_not_found(client):
    headers, company_id, app_id = get_auth_and_app(client)
    fake_app_id = str(uuid.uuid4())
    resp = client.post("/api/v1/products/", json={
        "name": "Test Product",
        "slug": f"appfake-{uuid.uuid4().hex[:8]}",
        "app_id": fake_app_id,
        "category": "Website"
    }, headers=headers)
    assert resp.status_code >= 400
