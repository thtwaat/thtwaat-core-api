import uuid
import pytest
from main import app

@pytest.fixture(autouse=True)
def clear_overrides():
    app.dependency_overrides.clear()
    yield
    app.dependency_overrides.clear()

def setup_company_and_user(client):
    company_slug = f"comp-{uuid.uuid4().hex[:8]}"
    company_resp = client.post("/api/v1/companies/", json={"name": "Auth Company", "slug": company_slug})
    company_id = company_resp.json()["id"]
    
    email = f"auth-{uuid.uuid4().hex[:8]}@example.com"
    password = "securepassword123"
    
    client.post("/api/v1/users/", json={
        "email": email,
        "password": password,
        "company_id": company_id,
        "first_name": "Auth",
        "last_name": "Test",
        "role": "admin"
    })
    
    login_resp = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    return login_resp.json()

def test_get_current_user_me(client):
    tokens = setup_company_and_user(client)
    access_token = tokens["access_token"]
    
    resp = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {access_token}"})
    assert resp.status_code == 200
    assert "email" in resp.json()

def test_unauthorized_access_to_me(client):
    # No header
    resp = client.get("/api/v1/auth/me")
    assert resp.status_code in [401, 403]
    
    # Invalid token
    resp_invalid = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer fake-token"})
    assert resp_invalid.status_code in [401, 403]
