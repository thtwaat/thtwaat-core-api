import os
import uuid
import tempfile
import pytest

def get_auth(client):
    company_slug = f"comp-{uuid.uuid4().hex[:8]}"
    company_resp = client.post("/api/v1/companies/", json={"name": "Storage Company", "slug": company_slug})
    company_id = company_resp.json()["id"]
    
    email = f"admin-{uuid.uuid4().hex[:8]}@example.com"
    password = "securepassword"
    
    client.post("/api/v1/users/", json={
        "email": email,
        "password": password,
        "company_id": company_id,
        "first_name": "Admin",
        "last_name": "User",
        "role": "admin"
    })
    
    login_resp = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    headers = {"Authorization": f"Bearer {login_resp.json()['access_token']}"}
    return headers, company_id

def test_get_metadata(client):
    headers, company_id = get_auth(client)
    
    with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as tmp:
        tmp.write(b"Hello metadata")
        tmp_path = tmp.name
        
    try:
        with open(tmp_path, "rb") as f:
            upload_resp = client.post("/api/v1/storage/upload", files={"file": ("meta.txt", f, "text/plain")}, headers=headers)
        assert upload_resp.status_code == 201
        file_id = upload_resp.json()["id"]
        
        meta_resp = client.get(f"/api/v1/storage/{file_id}", headers=headers)
        assert meta_resp.status_code == 200
        assert meta_resp.json()["id"] == file_id
    finally:
        os.remove(tmp_path)

def test_get_missing_metadata(client):
    headers, company_id = get_auth(client)
    fake_id = str(uuid.uuid4())
    
    meta_resp = client.get(f"/api/v1/storage/{fake_id}", headers=headers)
    assert meta_resp.status_code == 404
