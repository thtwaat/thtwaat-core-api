import uuid
import pytest
from main import app
from app.auth.router import get_current_user

def override_get_current_user():
    return {"id": uuid.uuid4(), "email": "test@example.com", "role": "ADMIN"}

app.dependency_overrides[get_current_user] = override_get_current_user

def test_update_company(client):
    unique_slug = f"update-slug-{uuid.uuid4().hex[:8]}"
    create_response = client.post(
        "/api/v1/companies/",
        json={
            "name": "Update Test",
            "slug": unique_slug,
            "industry": "TECH",
            "size": "1-10"
        }
    )
    assert create_response.status_code == 201
    company_id = create_response.json()["id"]
    
    update_response = client.patch(
        f"/api/v1/companies/{company_id}",
        json={"name": "Updated Name"}
    )
    assert update_response.status_code == 200
    assert update_response.json()["name"] == "Updated Name"

def test_update_invalid_company(client):
    fake_id = str(uuid.uuid4())
    update_response = client.patch(
        f"/api/v1/companies/{fake_id}",
        json={"name": "Will Fail"}
    )
    assert update_response.status_code == 404
