import logging
from fastapi.testclient import TestClient
from main import app
from app.database.database import engine
from app.models.base import Base

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

client = TestClient(app)

def run_tests():
    logger.info("Starting verification...")
    import uuid
    uid = uuid.uuid4().hex[:6]

    # 1. Verify all routers are in swagger
    resp = client.get("/openapi.json")
    assert resp.status_code == 200
    openapi = resp.json()
    paths = openapi["paths"]
    assert "/api/v1/companies/" in paths, "Companies router missing"
    assert "/api/v1/users/" in paths, "Users router missing"
    assert "/api/v1/auth/login" in paths, "Auth router missing"
    assert "/api/v1/apps/" in paths, "Apps router missing"
    logger.info("✅ All routers appear in Swagger.")

    # 2. CRUD Test - Create Company
    resp = client.post("/api/v1/companies/", json={
        "name": f"Test Company {uid}",
        "slug": f"test-company-{uid}",
        "domain": f"test{uid}.com"
    })
    assert resp.status_code == 201, f"Failed to create company: {resp.text}"
    company_id = resp.json()["id"]
    logger.info("✅ Company CRUD works.")

    # 3. CRUD Test - Create User
    resp = client.post("/api/v1/users/", json={
        "email": f"admin{uid}@test.com",
        "password": "securepassword",
        "company_id": company_id,
        "first_name": "Admin",
        "last_name": "User",
        "role": "admin"
    })
    assert resp.status_code == 201, f"Failed to create user: {resp.text}"
    logger.info("✅ User CRUD works.")

    # 4. Login works
    resp = client.post("/api/v1/auth/login", json={
        "email": f"admin{uid}@test.com",
        "password": "securepassword"
    })
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    tokens = resp.json()
    access_token = tokens["access_token"]
    logger.info("✅ Login works.")

    # 5. RBAC returns correct permissions (Create App requires APPS_CREATE)
    # The 'admin' role has APPS_CREATE permission in policy.py
    headers = {"Authorization": f"Bearer {access_token}"}
    resp = client.post("/api/v1/apps/", json={
        "name": "Test App",
        "slug": "test-app",
        "type": "web",
        "company_id": company_id
    }, headers=headers)
    assert resp.status_code == 201, f"App creation failed (RBAC issue?): {resp.text}"
    logger.info("✅ RBAC returns correct permissions.")
    logger.info("✅ Apps CRUD works.")

    # 6. Test Storage Upload
    import os
    with open("dummy.txt", "w") as f:
        f.write("Hello world!")
    
    with open("dummy.txt", "rb") as f:
        resp = client.post(
            "/api/v1/storage/upload",
            headers={"Authorization": f"Bearer {access_token}"},
            files={"file": ("dummy.txt", f, "text/plain")}
        )
    assert resp.status_code == 201, f"Upload failed: {resp.text}"
    file_id = resp.json()["id"]
    logger.info("✅ Upload endpoint works.")
    
    # 7. Get Metadata
    resp = client.get(
        f"/api/v1/storage/{file_id}",
        headers={"Authorization": f"Bearer {access_token}"}
    )
    assert resp.status_code == 200, f"Get metadata failed: {resp.text}"
    logger.info("✅ File metadata retrieval works.")
    
    os.remove("dummy.txt")

    logger.info("All verifications passed!")

if __name__ == "__main__":
    run_tests()
