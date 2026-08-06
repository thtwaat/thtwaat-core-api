import uuid

from main import app
from app.auth.router import get_current_user


def override_get_current_user():
    return {"id": uuid.uuid4(), "email": "test@example.com", "role": "ADMIN"}


app.dependency_overrides[get_current_user] = override_get_current_user


def test_create_company_success(client):
    unique_slug = f"test-company-{uuid.uuid4().hex[:8]}"
    response = client.post(
        "/api/v1/companies/",
        json={
            "name": f"Test Company {unique_slug}",
            "slug": unique_slug,
            "industry": "TECH",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == f"Test Company {unique_slug}"
    assert data["slug"] == unique_slug


def test_create_company_auto_slug_from_name(client):
    suffix = uuid.uuid4().hex[:8]
    response = client.post(
        "/api/v1/companies/",
        json={"name": f"Asma Garments {suffix}"},
    )
    assert response.status_code == 201, response.text
    data = response.json()
    assert data["slug"].startswith("asma-garments")


def test_create_company_duplicate_name(client):
    name = f"Dup Name Co {uuid.uuid4().hex[:8]}"
    res1 = client.post("/api/v1/companies/", json={"name": name})
    assert res1.status_code == 201, res1.text
    res2 = client.post("/api/v1/companies/", json={"name": name})
    assert res2.status_code == 409
    body = res2.json()
    detail = body.get("error") or body.get("detail") or ""
    assert "Company name already exists" in str(detail)


def test_create_company_duplicate_slug_allocates_variant(client):
    unique_slug = f"dup-slug-{uuid.uuid4().hex[:8]}"
    res1 = client.post(
        "/api/v1/companies/",
        json={"name": f"First {unique_slug}", "slug": unique_slug},
    )
    assert res1.status_code == 201
    res2 = client.post(
        "/api/v1/companies/",
        json={"name": f"Second {unique_slug}", "slug": unique_slug},
    )
    assert res2.status_code == 201, res2.text
    assert res2.json()["slug"] != unique_slug
    assert res2.json()["slug"].startswith(unique_slug)


def test_create_company_invalid_payload(client):
    response = client.post(
        "/api/v1/companies/",
        json={"name": "X"},  # too short
    )
    assert response.status_code == 422
