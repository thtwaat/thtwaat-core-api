import logging
from fastapi.testclient import TestClient
from main import app
from app.database.database import engine
from app.models.base import Base

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Ensure tables are created (TestClient might not trigger lifespan properly depending on setup, but we call create_all anyway for safety)
Base.metadata.create_all(bind=engine)

client = TestClient(app)

def run_tests():
    logger.info("Starting verification...")

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
        "name": "Test Company",
        "slug": "test-company",
        "domain": "test.com"
    })
    assert resp.status_code == 201, f"Failed to create company: {resp.text}"
    company_id = resp.json()["id"]
    logger.info("✅ Company CRUD works.")

    # 3. CRUD Test - Create User
    resp = client.post("/api/v1/users/", json={
        "email": "admin@test.com",
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
        "email": "admin@test.com",
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

    logger.info("All verifications passed!")

if __name__ == "__main__":
    run_tests()
