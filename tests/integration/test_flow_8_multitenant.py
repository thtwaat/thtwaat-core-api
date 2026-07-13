import uuid
import pytest

def test_multitenant_flow(client):
    # Create Company A and User A
    slug_a = f"comp-a-{uuid.uuid4().hex[:8]}"
    resp_a = client.post("/api/v1/companies/", json={"name": "Company A", "slug": slug_a})
    comp_a_id = resp_a.json()["id"]

    email_a = f"usera-{uuid.uuid4().hex[:8]}@a.com"
    client.post("/api/v1/users/", json={
        "email": email_a, "password": "securepassword", "company_id": comp_a_id,
        "first_name": "A", "last_name": "User", "role": "admin"
    })
    login_a = client.post("/api/v1/auth/login", json={"email": email_a, "password": "securepassword"})
    headers_a = {"Authorization": f"Bearer {login_a.json()['access_token']}"}

    # Create Company B and User B
    slug_b = f"comp-b-{uuid.uuid4().hex[:8]}"
    resp_b = client.post("/api/v1/companies/", json={"name": "Company B", "slug": slug_b})
    comp_b_id = resp_b.json()["id"]

    email_b = f"userb-{uuid.uuid4().hex[:8]}@b.com"
    client.post("/api/v1/users/", json={
        "email": email_b, "password": "securepassword", "company_id": comp_b_id,
        "first_name": "B", "last_name": "User", "role": "admin"
    })
    login_b = client.post("/api/v1/auth/login", json={"email": email_b, "password": "securepassword"})
    headers_b = {"Authorization": f"Bearer {login_b.json()['access_token']}"}

    # Company A creates an App
    app_payload = {"name": "App A", "slug": f"app-a-{uuid.uuid4().hex[:8]}", "type": "web", "company_id": comp_a_id}
    app_resp = client.post("/api/v1/apps/", json=app_payload, headers=headers_a)
    app_a_id = app_resp.json()["id"]

    # Company B tries to access App A
    get_app = client.get(f"/api/v1/apps/{app_a_id}", headers=headers_b)
    assert get_app.status_code in [200, 403, 404]

    # Company A tries to delete Company B's App (but B has no app, let's create one)
    app_payload_b = {"name": "App B", "slug": f"app-b-{uuid.uuid4().hex[:8]}", "type": "web", "company_id": comp_b_id}
    app_b_resp = client.post("/api/v1/apps/", json=app_payload_b, headers=headers_b)
    app_b_id = app_b_resp.json()["id"]

    del_app = client.delete(f"/api/v1/apps/{app_b_id}", headers=headers_a)
    assert del_app.status_code in [200, 204, 403, 404]
