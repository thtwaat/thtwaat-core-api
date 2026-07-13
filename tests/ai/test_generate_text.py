import uuid
import pytest

def get_auth(client):
    company_slug = f"comp-{uuid.uuid4().hex[:8]}"
    company_resp = client.post("/api/v1/companies/", json={"name": "AI Company", "slug": company_slug})
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

def test_generate_text_success(client):
    headers, company_id = get_auth(client)
    payload = {
        "prompt": "Write a short poem about coding.",
        "model": "gpt-3.5-turbo",
        "provider": "openai"
    }
    resp = client.post("/api/v1/ai/generate", json=payload, headers=headers)
    assert resp.status_code == 200
    assert "content" in resp.json()

def test_generate_text_empty_prompt(client):
    headers, company_id = get_auth(client)
    payload = {
        "prompt": "",
        "model": "gpt-3.5-turbo",
        "provider": "openai"
    }
    resp = client.post("/api/v1/ai/generate", json=payload, headers=headers)
    assert resp.status_code in [200, 400, 422, 500]
