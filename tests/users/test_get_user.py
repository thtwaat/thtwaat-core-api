import uuid
import pytest
from main import app
from app.auth.router import get_current_user

def override_get_current_user():
    return {"id": uuid.uuid4(), "email": "test@example.com", "role": "ADMIN"}

app.dependency_overrides[get_current_user] = override_get_current_user

def setup_company(client):
    company_slug = f"comp-{uuid.uuid4().hex[:8]}"
    resp = client.post("/api/v1/companies/", json={"name": "Test Company", "slug": company_slug})
    return resp.json()["id"]

def test_get_existing_user(client):
    company_id = setup_company(client)
    email = f"user-{uuid.uuid4().hex[:8]}@example.com"
    create_resp = client.post("/api/v1/users/", json={
        "email": email,
        "password": "securepassword",
        "company_id": company_id,
        "first_name": "Test",
        "last_name": "User",
        "role": "admin"
    })
    assert create_resp.status_code == 201
    user_id = create_resp.json()["id"]
    
    get_resp = client.get(f"/api/v1/users/{user_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == user_id

def test_get_missing_user(client):
    fake_id = str(uuid.uuid4())
    get_resp = client.get(f"/api/v1/users/{fake_id}")
    assert get_resp.status_code == 404
