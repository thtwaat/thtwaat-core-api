import uuid
import pytest

def get_auth(client):
    company_slug = f"comp-{uuid.uuid4().hex[:8]}"
    company_resp = client.post("/api/v1/companies/", json={"name": "Notif Company", "slug": company_slug})
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

def test_create_notification(client):
    headers, company_id = get_auth(client)
    payload = {
        "channel": "email",
        "recipient": "user@example.com",
        "subject": "Hello",
        "body": "World"
    }
    resp = client.post("/api/v1/notifications/send", json=payload, headers=headers)
    assert resp.status_code == 201
    assert resp.json()["channel"] == "email"
    assert resp.json()["recipient"] == "user@example.com"

def test_create_notification_invalid_channel(client):
    headers, company_id = get_auth(client)
    payload = {
        "channel": "invalid_channel",
        "recipient": "user@example.com",
        "subject": "Hello",
        "body": "World"
    }
    resp = client.post("/api/v1/notifications/send", json=payload, headers=headers)
    assert resp.status_code == 422

def test_create_notification_invalid_recipient(client):
    headers, company_id = get_auth(client)
    payload = {
        "channel": "email",
        "recipient": {"invalid": "dict"},
        "subject": "Hello",
        "body": "World"
    }
    resp = client.post("/api/v1/notifications/send", json=payload, headers=headers)
    assert resp.status_code == 422

def test_create_notification_missing_recipient(client):
    headers, company_id = get_auth(client)
    payload = {
        "channel": "email",
        "subject": "Hello",
        "body": "World"
    }
    resp = client.post("/api/v1/notifications/send", json=payload, headers=headers)
    assert resp.status_code == 422
