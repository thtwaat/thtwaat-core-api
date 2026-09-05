import uuid
import pytest
from main import app
from app.auth.router import get_current_user

@pytest.fixture(autouse=True)
def clear_overrides():
    app.dependency_overrides.clear()
    yield
    app.dependency_overrides.clear()

def setup_user(client):
    company_slug = f"comp-{uuid.uuid4().hex[:8]}"
    company_resp = client.post("/api/v1/companies/", json={"name": f"Auth Company {company_slug}", "slug": company_slug})
    company_id = company_resp.json()["id"]
    
    email = f"auth-{uuid.uuid4().hex[:8]}@example.com"
    password = "securepassword123"
    
    user_resp = client.post("/api/v1/users/", json={
        "email": email,
        "password": password,
        "company_id": company_id,
        "first_name": "Auth",
        "last_name": "Test",
        "role": "company_owner"
    })
    user_id = user_resp.json()["id"]
    return email, password, user_id

def test_successful_login(client):
    email, password, user_id = setup_user(client)
    resp = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200
    assert "access_token" in resp.json()
    assert "refresh_token" in resp.json()

def test_invalid_password(client):
    email, password, user_id = setup_user(client)
    resp = client.post("/api/v1/auth/login", json={"email": email, "password": "wrongpassword"})
    assert resp.status_code in [400, 401, 403, 404]

def test_invalid_email(client):
    resp = client.post("/api/v1/auth/login", json={"email": f"fake-{uuid.uuid4().hex[:8]}@example.com", "password": "anypassword"})
    assert resp.status_code in [400, 401, 403, 404]

def setup_user_in_company(client, company_slug, email, password):
    company_resp = client.post("/api/v1/companies/", json={"name": f"Company {company_slug}", "slug": company_slug})
    company_id = company_resp.json()["id"]

    user_resp = client.post("/api/v1/users/", json={
        "email": email,
        "password": password,
        "company_id": company_id,
        "first_name": "Auth",
        "last_name": "Test",
        "role": "company_owner"
    })
    return company_id, user_resp.json()["id"]


def test_multi_org_login_without_slug_returns_409(client):
    email = f"multi-{uuid.uuid4().hex[:8]}@example.com"
    password_a = "securepasswordA1"
    password_b = "securepasswordB1"
    slug_a = f"comp-a-{uuid.uuid4().hex[:8]}"
    slug_b = f"comp-b-{uuid.uuid4().hex[:8]}"

    setup_user_in_company(client, slug_a, email, password_a)
    setup_user_in_company(client, slug_b, email, password_b)

    resp = client.post("/api/v1/auth/login", json={"email": email, "password": password_a})
    assert resp.status_code == 409
    # Global HTTPException handler (app/api/exceptions.py) wraps dict details as
    # {"error": {...}, "code": <status>}, not FastAPI's raw {"detail": {...}}.
    body = resp.json()["error"]
    assert body["code"] == "company_required"


def test_multi_org_login_with_valid_company_slug_selects_correct_user(client):
    email = f"multi-{uuid.uuid4().hex[:8]}@example.com"
    password_a = "securepasswordA1"
    password_b = "securepasswordB1"
    slug_a = f"comp-a-{uuid.uuid4().hex[:8]}"
    slug_b = f"comp-b-{uuid.uuid4().hex[:8]}"

    company_a_id, _ = setup_user_in_company(client, slug_a, email, password_a)
    setup_user_in_company(client, slug_b, email, password_b)

    resp = client.post("/api/v1/auth/login", json={
        "email": email,
        "password": password_a,
        "company_slug": slug_a
    })
    assert resp.status_code == 200
    tokens = resp.json()
    assert "access_token" in tokens

    me_resp = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {tokens['access_token']}"}
    )
    assert me_resp.status_code == 200
    assert me_resp.json()["company_id"] == company_a_id

    # Wrong password for the selected company's user must still fail, proving
    # company_slug picked the right row rather than any row with that email.
    resp_wrong_pw = client.post("/api/v1/auth/login", json={
        "email": email,
        "password": password_b,
        "company_slug": slug_a
    })
    assert resp_wrong_pw.status_code in [400, 401, 403, 404]


def test_multi_org_login_with_invalid_company_slug_fails_safely(client):
    email = f"multi-{uuid.uuid4().hex[:8]}@example.com"
    password_a = "securepasswordA1"
    password_b = "securepasswordB1"
    slug_a = f"comp-a-{uuid.uuid4().hex[:8]}"
    slug_b = f"comp-b-{uuid.uuid4().hex[:8]}"

    setup_user_in_company(client, slug_a, email, password_a)
    setup_user_in_company(client, slug_b, email, password_b)

    resp = client.post("/api/v1/auth/login", json={
        "email": email,
        "password": password_a,
        "company_slug": f"nonexistent-{uuid.uuid4().hex[:8]}"
    })
    assert resp.status_code == 401


def test_inactive_user(client):
    email, password, user_id = setup_user(client)
    
    # Deactivate the user
    # Temporary dependency override to allow delete
    app.dependency_overrides[get_current_user] = lambda: {"id": user_id, "email": email, "role": "admin"}
    del_resp = client.delete(f"/api/v1/users/{user_id}")
    app.dependency_overrides.clear()
    assert del_resp.status_code == 200
    
    # Login should fail
    resp = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert resp.status_code >= 400
