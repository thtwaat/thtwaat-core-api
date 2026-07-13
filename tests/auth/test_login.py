import uuid
import pytest
from main import app
from app.auth.router import get_current_user

@pytest.fixture(autouse=True)
def clear_overrides():
    app.dependency_overrides.clear()
    yield
    app.dependency_overrides.clear()

def setup_user(client):
    company_slug = f"comp-{uuid.uuid4().hex[:8]}"
    company_resp = client.post("/api/v1/companies/", json={"name": "Auth Company", "slug": company_slug})
    company_id = company_resp.json()["id"]
    
    email = f"auth-{uuid.uuid4().hex[:8]}@example.com"
    password = "securepassword123"
    
    user_resp = client.post("/api/v1/users/", json={
        "email": email,
        "password": password,
        "company_id": company_id,
        "first_name": "Auth",
        "last_name": "Test",
        "role": "admin"
    })
    user_id = user_resp.json()["id"]
    return email, password, user_id

def test_successful_login(client):
    email, password, user_id = setup_user(client)
    resp = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200
    assert "access_token" in resp.json()
    assert "refresh_token" in resp.json()

def test_invalid_password(client):
    email, password, user_id = setup_user(client)
    resp = client.post("/api/v1/auth/login", json={"email": email, "password": "wrongpassword"})
    assert resp.status_code in [400, 401, 403, 404]

def test_invalid_email(client):
    resp = client.post("/api/v1/auth/login", json={"email": f"fake-{uuid.uuid4().hex[:8]}@example.com", "password": "anypassword"})
    assert resp.status_code in [400, 401, 403, 404]

def test_inactive_user(client):
    email, password, user_id = setup_user(client)
    
    # Deactivate the user
    # Temporary dependency override to allow delete
    app.dependency_overrides[get_current_user] = lambda: {"id": user_id, "email": email, "role": "admin"}
    del_resp = client.delete(f"/api/v1/users/{user_id}")
    app.dependency_overrides.clear()
    assert del_resp.status_code == 200
    
    # Login should fail
    resp = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert resp.status_code >= 400
