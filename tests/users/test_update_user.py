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

def test_update_user(client):
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
    
    update_resp = client.patch(
        f"/api/v1/users/{user_id}",
        json={"first_name": "UpdatedName"}
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["first_name"] == "UpdatedName"

def test_update_missing_user(client):
    fake_id = str(uuid.uuid4())
    update_resp = client.patch(
        f"/api/v1/users/{fake_id}",
        json={"first_name": "Will Fail"}
    )
    assert update_resp.status_code == 404
