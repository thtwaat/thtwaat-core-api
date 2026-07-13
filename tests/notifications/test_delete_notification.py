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

def test_delete_notification(client):
    headers, company_id = get_auth(client)
    payload = {
        "channel": "email",
        "recipient": "user@example.com",
        "subject": "Hello",
        "body": "World"
    }
    create_resp = client.post("/api/v1/notifications/send", json=payload, headers=headers)
    assert create_resp.status_code == 201
    notif_id = create_resp.json()["id"]

    del_resp = client.delete(f"/api/v1/notifications/{notif_id}", headers=headers)
    assert del_resp.status_code == 204

    get_resp = client.get(f"/api/v1/notifications/{notif_id}", headers=headers)
    assert get_resp.status_code == 404

def test_delete_missing_notification(client):
    headers, company_id = get_auth(client)
    fake_id = str(uuid.uuid4())
    del_resp = client.delete(f"/api/v1/notifications/{fake_id}", headers=headers)
    assert del_resp.status_code == 404
