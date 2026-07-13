import uuid
import pytest
from main import app
from app.auth.router import get_current_user

def override_get_current_user():
    return {"id": uuid.uuid4(), "email": "test@example.com", "role": "ADMIN"}

app.dependency_overrides[get_current_user] = override_get_current_user

def test_delete_company(client):
    unique_slug = f"delete-slug-{uuid.uuid4().hex[:8]}"
    create_response = client.post(
        "/api/v1/companies/",
        json={
            "name": "Delete Test",
            "slug": unique_slug,
            "industry": "TECH",
            "size": "1-10"
        }
    )
    assert create_response.status_code == 201
    company_id = create_response.json()["id"]
    
    delete_response = client.delete(f"/api/v1/companies/{company_id}")
    assert delete_response.status_code == 200
    
    # Check that it's actually deactivated/deleted
    # It might return 404, or 403 Forbidden, or return with status='INACTIVE'
    get_response = client.get(f"/api/v1/companies/{company_id}")
    if get_response.status_code == 200:
        assert get_response.json()["status"] == "INACTIVE"
    else:
        assert get_response.status_code in [403, 404]

def test_delete_missing_company(client):
    fake_id = str(uuid.uuid4())
    delete_response = client.delete(f"/api/v1/companies/{fake_id}")
    assert delete_response.status_code == 404
