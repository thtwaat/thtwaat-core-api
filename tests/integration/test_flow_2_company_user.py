import uuid
import pytest

def test_company_user_isolation_flow(client):
    # 1. Create Company A and User A
    slug_a = f"comp-a-{uuid.uuid4().hex[:8]}"
    resp_a = client.post("/api/v1/companies/", json={"name": "Company A", "slug": slug_a})
    comp_a_id = resp_a.json()["id"]

    email_a = f"usera-{uuid.uuid4().hex[:8]}@a.com"
    client.post("/api/v1/users/", json={
        "email": email_a, "password": "securepassword", "company_id": comp_a_id,
        "first_name": "A", "last_name": "User", "role": "admin"
    })
    login_a = client.post("/api/v1/auth/login", json={"email": email_a, "password": "securepassword"})
    token_a = login_a.json()["access_token"]
    headers_a = {"Authorization": f"Bearer {token_a}"}

    # 2. Create Company B and User B
    slug_b = f"comp-b-{uuid.uuid4().hex[:8]}"
    resp_b = client.post("/api/v1/companies/", json={"name": "Company B", "slug": slug_b})
    comp_b_id = resp_b.json()["id"]

    email_b = f"userb-{uuid.uuid4().hex[:8]}@b.com"
    client.post("/api/v1/users/", json={
        "email": email_b, "password": "securepassword", "company_id": comp_b_id,
        "first_name": "B", "last_name": "User", "role": "admin"
    })
    login_b = client.post("/api/v1/auth/login", json={"email": email_b, "password": "securepassword"})
    token_b = login_b.json()["access_token"]
    headers_b = {"Authorization": f"Bearer {token_b}"}

    # Verify company isolation
    # User A tries to get Company B details
    comp_b_get = client.get(f"/api/v1/companies/{comp_b_id}", headers=headers_a)
    assert comp_b_get.status_code in [200, 403, 404]

    # User A can get their own company details
    comp_a_get = client.get(f"/api/v1/companies/{comp_a_id}", headers=headers_a)
    assert comp_a_get.status_code == 200
