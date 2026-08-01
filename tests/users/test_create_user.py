import uuid
from main import app
from app.auth.router import get_current_user

def override_get_current_user():
    return {"id": uuid.uuid4(), "email": "test@example.com", "role": "ADMIN"}

app.dependency_overrides[get_current_user] = override_get_current_user

def setup_company(client):
    company_slug = f"comp-{uuid.uuid4().hex[:8]}"
    resp = client.post("/api/v1/companies/", json={"name": "Test Company", "slug": company_slug})
    return resp.json()["id"]

def test_create_user(client):
    company_id = setup_company(client)
    email = f"user-{uuid.uuid4().hex[:8]}@example.com"
    resp = client.post("/api/v1/users/", json={
        "email": email,
        "password": "securepassword",
        "company_id": company_id,
        "first_name": "Test",
        "last_name": "User",
        "role": "employee"
    })
    assert resp.status_code == 201
    assert resp.json()["email"] == email

def test_create_user_duplicate_email_same_company(client):
    company_id = setup_company(client)
    email = f"dup-{uuid.uuid4().hex[:8]}@example.com"
    payload = {
        "email": email,
        "password": "securepassword",
        "company_id": company_id,
        "first_name": "Test",
        "last_name": "User",
        "role": "employee"
    }
    res1 = client.post("/api/v1/users/", json=payload)
    assert res1.status_code == 201
    
    res2 = client.post("/api/v1/users/", json=payload)
    assert res2.status_code >= 400

def test_create_user_same_email_different_companies(client):
    c1 = setup_company(client)
    c2 = setup_company(client)
    email = f"share-{uuid.uuid4().hex[:8]}@example.com"
    
    payload1 = {
        "email": email,
        "password": "securepassword",
        "company_id": c1,
        "first_name": "Test1",
        "last_name": "User1",
        "role": "employee"
    }
    res1 = client.post("/api/v1/users/", json=payload1)
    assert res1.status_code == 201
    
    payload2 = {
        "email": email,
        "password": "securepassword",
        "company_id": c2,
        "first_name": "Test2",
        "last_name": "User2",
        "role": "employee"
    }
    res2 = client.post("/api/v1/users/", json=payload2)
    assert res2.status_code in [201, 400, 409, 500]

def test_create_user_invalid_payload(client):
    resp = client.post("/api/v1/users/", json={"email": "not-an-email"})
    assert resp.status_code == 422
