import uuid
import pytest

def test_app_product_flow(client):
    # Setup Auth
    company_slug = f"comp-{uuid.uuid4().hex[:8]}"
    company_resp = client.post("/api/v1/companies/", json={"name": "App Prod", "slug": company_slug})
    company_id = company_resp.json()["id"]

    email = f"user-{uuid.uuid4().hex[:8]}@example.com"
    client.post("/api/v1/users/", json={
        "email": email, "password": "securepassword", "company_id": company_id,
        "first_name": "App", "last_name": "User", "role": "admin"
    })
    login_resp = client.post("/api/v1/auth/login", json={"email": email, "password": "securepassword"})
    headers = {"Authorization": f"Bearer {login_resp.json()['access_token']}"}

    # 1. Create App
    app_payload = {"name": "Test App", "slug": f"app-{uuid.uuid4().hex[:8]}", "type": "web", "company_id": company_id}
    app_resp = client.post("/api/v1/apps/", json=app_payload, headers=headers)
    assert app_resp.status_code == 201
    app_id = app_resp.json()["id"]

    # 2. Create Product
    prod_payload = {"app_id": app_id, "name": "Test Product", "slug": f"prod-{uuid.uuid4().hex[:8]}", "price": 10.0, "category": "Website"}
    prod_resp = client.post("/api/v1/products/", json=prod_payload, headers=headers)
    assert prod_resp.status_code == 201
    prod_id = prod_resp.json()["id"]

    # 3. Verify relationships
    get_prod = client.get(f"/api/v1/products/{prod_id}", headers=headers)
    assert get_prod.status_code == 200
    assert get_prod.json()["app_id"] == app_id
