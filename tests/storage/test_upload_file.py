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

def test_upload_valid_file(client):
    headers, company_id = get_auth(client)
    
    with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as tmp:
        tmp.write(b"Hello world")
        tmp_path = tmp.name
        
    try:
        with open(tmp_path, "rb") as f:
            resp = client.post("/api/v1/storage/upload", files={"file": ("test.txt", f, "text/plain")}, headers=headers)
        assert resp.status_code == 201
        assert resp.json()["mime_type"] == "text/plain"
    finally:
        os.remove(tmp_path)

def test_upload_invalid_mime_type(client):
    headers, company_id = get_auth(client)
    
    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tmp:
        tmp.write(b"fake video content")
        tmp_path = tmp.name
        
    try:
        with open(tmp_path, "rb") as f:
            resp = client.post("/api/v1/storage/upload", files={"file": ("test.mp4", f, "video/mp4")}, headers=headers)
        assert resp.status_code == 415
    finally:
        os.remove(tmp_path)

def test_upload_oversized_file(client):
    headers, company_id = get_auth(client)
    
    with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as tmp:
        # Write 51 MB
        tmp.write(b"0" * (51 * 1024 * 1024))
        tmp_path = tmp.name
        
    try:
        with open(tmp_path, "rb") as f:
            resp = client.post("/api/v1/storage/upload", files={"file": ("large.txt", f, "text/plain")}, headers=headers)
        assert resp.status_code == 413
    finally:
        os.remove(tmp_path)

def test_upload_missing_file(client):
    headers, company_id = get_auth(client)
    resp = client.post("/api/v1/storage/upload", headers=headers)
    assert resp.status_code == 422
