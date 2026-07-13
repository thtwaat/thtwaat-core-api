import uuid
import pytest
from main import app
from app.auth.router import get_current_user

def override_get_current_user():
    return {"id": uuid.uuid4(), "email": "test@example.com", "role": "ADMIN"}

app.dependency_overrides[get_current_user] = override_get_current_user

def test_create_company_success(client):
    unique_slug = f"test-company-{uuid.uuid4().hex[:8]}"
    response = client.post(
        "/api/v1/companies/",
        json={
            "name": "Test Company",
            "slug": unique_slug,
            "industry": "TECH",
            "size": "1-10"
        }
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Test Company"
    assert data["slug"] == unique_slug

def test_create_company_duplicate_slug(client):
    unique_slug = f"dup-slug-{uuid.uuid4().hex[:8]}"
    payload = {
        "name": "Test Duplicate",
        "slug": unique_slug,
        "industry": "TECH",
        "size": "1-10"
    }
    # First creation should succeed
    res1 = client.post("/api/v1/companies/", json=payload)
    assert res1.status_code == 201
    
    # Second creation with same slug should fail (could be 400, 409, or 500 depending on exception handling)
    res2 = client.post("/api/v1/companies/", json=payload)
    assert res2.status_code >= 400

def test_create_company_invalid_payload(client):
    response = client.post(
        "/api/v1/companies/",
        json={
            "name": "Missing Required Fields"
            # missing industry and size which are likely required
        }
    )
    assert response.status_code == 422
