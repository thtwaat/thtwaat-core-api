import os
import uuid
import tempfile

def get_auth(client, role: str = "company_owner"):
    company_slug = f"comp-{uuid.uuid4().hex[:8]}"
    company_resp = client.post("/api/v1/companies/", json={"name": "Storage Company", "slug": company_slug})
    company_id = company_resp.json()["id"]

    email = f"admin-{uuid.uuid4().hex[:8]}@example.com"
    password = "securepassword"

    client.post("/api/v1/users/", json={
        "email": email,
        "password": password,
        "company_id": company_id,
        "first_name": "Admin",
        "last_name": "User",
        "role": role,
    })

    login_resp = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    headers = {"Authorization": f"Bearer {login_resp.json()['access_token']}"}
    return headers, company_id


def test_download_file(client):
    headers, _company_id = get_auth(client)

    with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as tmp:
        tmp.write(b"Hello world")
        tmp_path = tmp.name

    try:
        with open(tmp_path, "rb") as f:
            upload_resp = client.post(
                "/api/v1/storage/upload",
                files={"file": ("test.txt", f, "text/plain")},
                headers=headers,
            )
        assert upload_resp.status_code == 201
        file_id = upload_resp.json()["id"]

        download_resp = client.get(
            f"/api/v1/storage/{file_id}/download",
            headers=headers,
            follow_redirects=False,
        )
        assert download_resp.status_code == 200
        assert download_resp.content == b"Hello world"
        assert "text/plain" in (download_resp.headers.get("content-type") or "")
    finally:
        os.remove(tmp_path)


def test_download_requires_auth(client):
    fake_id = str(uuid.uuid4())
    download_resp = client.get(f"/api/v1/storage/{fake_id}/download", follow_redirects=False)
    assert download_resp.status_code in (401, 403)


def test_download_missing_file(client):
    headers, _company_id = get_auth(client)
    fake_id = str(uuid.uuid4())
    download_resp = client.get(
        f"/api/v1/storage/{fake_id}/download",
        headers=headers,
        follow_redirects=False,
    )
    assert download_resp.status_code == 404


def test_download_foreign_company_returns_404(client):
    headers_a, _ = get_auth(client)
    headers_b, _ = get_auth(client)

    with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as tmp:
        tmp.write(b"tenant-a-secret")
        tmp_path = tmp.name

    try:
        with open(tmp_path, "rb") as f:
            upload_resp = client.post(
                "/api/v1/storage/upload",
                files={"file": ("secret.txt", f, "text/plain")},
                headers=headers_a,
            )
        assert upload_resp.status_code == 201
        file_id = upload_resp.json()["id"]

        download_resp = client.get(
            f"/api/v1/storage/{file_id}/download",
            headers=headers_b,
            follow_redirects=False,
        )
        assert download_resp.status_code == 404
    finally:
        os.remove(tmp_path)
