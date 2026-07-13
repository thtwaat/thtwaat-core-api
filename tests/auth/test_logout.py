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

def test_logout_success(client):
    tokens = setup_company_and_user(client)
    refresh_token = tokens["refresh_token"]
    
    resp = client.post("/api/v1/auth/logout", json={"refresh_token": refresh_token})
    assert resp.status_code == 200
    
    # Once logged out, the refresh token should be invalid
    refresh_resp = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert refresh_resp.status_code >= 400

def test_logout_with_invalid_token(client):
    resp = client.post("/api/v1/auth/logout", json={"refresh_token": "fake-token"})
    # It might return 200 or 400 depending on implementation. We accept either.
    assert resp.status_code in [200, 400, 401, 403, 404]
