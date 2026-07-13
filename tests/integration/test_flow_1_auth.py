import uuid
import pytest

def test_auth_flow(client):
    # 1. Setup Company and User
    company_slug = f"comp-{uuid.uuid4().hex[:8]}"
    company_resp = client.post("/api/v1/companies/", json={"name": "Auth Flow Company", "slug": company_slug})
    assert company_resp.status_code == 201
    company_id = company_resp.json()["id"]

    email = f"user-{uuid.uuid4().hex[:8]}@example.com"
    password = "securepassword"
    
    user_resp = client.post("/api/v1/users/", json={
        "email": email,
        "password": password,
        "company_id": company_id,
        "first_name": "Auth",
        "last_name": "User",
        "role": "admin"
    })
    assert user_resp.status_code == 201

    # 2. Login
    login_resp = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert login_resp.status_code == 200
    access_token = login_resp.json()["access_token"]
    refresh_token = login_resp.json()["refresh_token"]

    # 3. Protected endpoint access
    headers = {"Authorization": f"Bearer {access_token}"}
    me_resp = client.get("/api/v1/auth/me", headers=headers)
    assert me_resp.status_code == 200
    assert me_resp.json()["email"] == email

    # 4. Refresh Token
    refresh_resp = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert refresh_resp.status_code == 200
    new_access_token = refresh_resp.json()["access_token"]
    
    # 5. Logout
    logout_resp = client.post("/api/v1/auth/logout", json={"refresh_token": refresh_token})
    assert logout_resp.status_code == 200
    
    # Verify refresh token is revoked
    refresh_fail_resp = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert refresh_fail_resp.status_code in [400, 401, 403, 404]
