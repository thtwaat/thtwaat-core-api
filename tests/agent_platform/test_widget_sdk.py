"""Ensure production widget.js is served and embed snippets work."""
import uuid


def _auth(client):
    company_slug = f"wgt-{uuid.uuid4().hex[:8]}"
    company_id = client.post(
        "/api/v1/companies/",
        json={"name": "Widget Co", "slug": company_slug},
    ).json()["id"]
    email = f"w-{uuid.uuid4().hex[:8]}@example.com"
    client.post(
        "/api/v1/users/",
        json={
            "email": email,
            "password": "securepassword",
            "company_id": company_id,
            "first_name": "W",
            "last_name": "User",
            "role": "admin",
        },
    )
    token = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "securepassword"},
    ).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_widget_js_bundle_served(client):
    resp = client.get("/widget.js")
    assert resp.status_code == 200
    body = resp.text
    assert "THTWAAT" in body
    assert "tht-launcher" in body or "launcher" in body
    assert len(body) > 5000


def test_embed_snippets_endpoint(client):
    headers = _auth(client)
    agent = client.post(
        "/v2/agents",
        json={
            "name": "Widget Agent",
            "system_prompt_template": "You are helpful.",
            "temperature": 0.2,
            "web_config": {},
        },
        headers=headers,
    ).json()
    client.post(f"/api/v1/agents/{agent['id']}/publish", headers=headers)

    embed = client.get(f"/api/v1/agents/{agent['id']}/embed", headers=headers)
    assert embed.status_code == 200, embed.text
    data = embed.json()
    assert "widget.js" in data["script"]
    assert "data-api-key" in data["script"]
    assert "data-theme" in data["script"]
    assert "iframe" in data["iframe"]
    assert data["config"]["position"] == "bottom-right"
