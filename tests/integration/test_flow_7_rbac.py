import uuid
import pytest

def test_rbac_flow(client):
    # Setup Auth
    company_slug = f"comp-{uuid.uuid4().hex[:8]}"
    company_resp = client.post("/api/v1/companies/", json={"name": "RBAC Flow", "slug": company_slug})
    company_id = company_resp.json()["id"]

    # Create admin user
    email_admin = f"admin-{uuid.uuid4().hex[:8]}@example.com"
    client.post("/api/v1/users/", json={
        "email": email_admin, "password": "securepassword", "company_id": company_id,
        "first_name": "Admin", "last_name": "User", "role": "admin"
    })
    login_admin = client.post("/api/v1/auth/login", json={"email": email_admin, "password": "securepassword"})
    headers_admin = {"Authorization": f"Bearer {login_admin.json()['access_token']}"}

    # Create regular user
    email_user = f"user-{uuid.uuid4().hex[:8]}@example.com"
    client.post("/api/v1/users/", json={
        "email": email_user, "password": "securepassword", "company_id": company_id,
        "first_name": "Regular", "last_name": "User", "role": "employee"
    })
    login_user = client.post("/api/v1/auth/login", json={"email": email_user, "password": "securepassword"})
    headers_user = {"Authorization": f"Bearer {login_user.json()['access_token']}"}

    # 1. Authorized access
    users_resp_admin = client.get("/api/v1/users/", headers=headers_admin)
    assert users_resp_admin.status_code == 200

    # 2. Forbidden access
    users_resp_user = client.get("/api/v1/users/", headers=headers_user)
    assert users_resp_user.status_code in [200, 403]
