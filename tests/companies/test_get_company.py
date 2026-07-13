import uuid
import pytest
from main import app
from app.auth.router import get_current_user

def override_get_current_user():
    return {"id": uuid.uuid4(), "email": "test@example.com", "role": "ADMIN"}

app.dependency_overrides[get_current_user] = override_get_current_user

def test_get_existing_company(client):
    unique_slug = f"get-slug-{uuid.uuid4().hex[:8]}"
    create_response = client.post(
        "/api/v1/companies/",
        json={
            "name": "Get Test",
            "slug": unique_slug,
            "industry": "TECH",
            "size": "1-10"
        }
    )
    assert create_response.status_code == 201
    company_id = create_response.json()["id"]
    
    get_response = client.get(f"/api/v1/companies/{company_id}")
    assert get_response.status_code == 200
    assert get_response.json()["id"] == company_id

def test_get_missing_company(client):
    fake_id = str(uuid.uuid4())
    get_response = client.get(f"/api/v1/companies/{fake_id}")
    assert get_response.status_code == 404
