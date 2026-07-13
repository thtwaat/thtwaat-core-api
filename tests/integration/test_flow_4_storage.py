import uuid
import os
import tempfile
import pytest

def test_storage_flow(client):
    # Setup Auth
    company_slug = f"comp-{uuid.uuid4().hex[:8]}"
    company_resp = client.post("/api/v1/companies/", json={"name": "Storage Flow", "slug": company_slug})
    company_id = company_resp.json()["id"]

    email = f"user-{uuid.uuid4().hex[:8]}@example.com"
    client.post("/api/v1/users/", json={
        "email": email, "password": "securepassword", "company_id": company_id,
        "first_name": "Storage", "last_name": "User", "role": "admin"
    })
    login_resp = client.post("/api/v1/auth/login", json={"email": email, "password": "securepassword"})
    headers = {"Authorization": f"Bearer {login_resp.json()['access_token']}"}

    # 1. Upload
    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        tmp.write(b"Hello Storage Integration")
        tmp_path = tmp.name

    try:
        with open(tmp_path, "rb") as f:
            upload_resp = client.post(
                "/api/v1/storage/upload",
                files={"file": ("integration.txt", f, "text/plain")},
                headers=headers
            )
        assert upload_resp.status_code == 201
        file_id = upload_resp.json()["id"]

        # 2. Metadata
        meta_resp = client.get(f"/api/v1/storage/{file_id}", headers=headers)
        assert meta_resp.status_code == 200
        assert meta_resp.json()["id"] == file_id

        # 3. Download
        dl_resp = client.get(f"/api/v1/storage/{file_id}/download", headers=headers, follow_redirects=False)
        assert dl_resp.status_code in [200, 302, 303, 307]

        # 4. Delete
        del_resp = client.delete(f"/api/v1/storage/{file_id}", headers=headers)
        assert del_resp.status_code == 204

        # Verify deletion
        meta_after = client.get(f"/api/v1/storage/{file_id}", headers=headers)
        assert meta_after.status_code == 404

    finally:
        os.unlink(tmp_path)
