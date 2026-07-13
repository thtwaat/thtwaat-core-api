import uuid
import pytest

def test_ai_flow(client):
    # Setup Auth
    company_slug = f"comp-{uuid.uuid4().hex[:8]}"
    company_resp = client.post("/api/v1/companies/", json={"name": "AI Flow", "slug": company_slug})
    company_id = company_resp.json()["id"]

    email = f"user-{uuid.uuid4().hex[:8]}@example.com"
    client.post("/api/v1/users/", json={
        "email": email, "password": "securepassword", "company_id": company_id,
        "first_name": "AI", "last_name": "User", "role": "admin"
    })
    login_resp = client.post("/api/v1/auth/login", json={"email": email, "password": "securepassword"})
    headers = {"Authorization": f"Bearer {login_resp.json()['access_token']}"}

    # 1. Analyze (chat)
    chat_payload = {
        "messages": [{"role": "user", "content": "Analyze text."}],
        "model": "gpt-3.5-turbo",
        "provider": "openai"
    }
    chat_resp = client.post("/api/v1/ai/chat", json=chat_payload, headers=headers)
    assert chat_resp.status_code == 200

    # 2. Generate
    gen_payload = {
        "prompt": "Generate text.",
        "model": "gpt-3.5-turbo",
        "provider": "openai"
    }
    gen_resp = client.post("/api/v1/ai/generate", json=gen_payload, headers=headers)
    assert gen_resp.status_code == 200

    # 3. Save History (check history endpoint)
    hist_resp = client.get("/api/v1/ai/history", headers=headers)
    assert hist_resp.status_code == 200
    assert len(hist_resp.json()) >= 2
