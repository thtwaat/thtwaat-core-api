import uuid
import pytest

from app.rbac.enums import EnterpriseRole
from app.users.model import User

def get_auth(client):
    company_slug = f"comp-{uuid.uuid4().hex[:8]}"
    company_resp = client.post("/api/v1/companies/", json={"name": "Payment Company", "slug": company_slug})
    company_id = company_resp.json()["id"]

    email = f"user-{uuid.uuid4().hex[:8]}@example.com"
    password = "securepassword"

    # "admin" is a privileged tenant role and is rejected by public signup
    # (see tests/users/test_signup_roles.py) — company_owner is the
    # public-signup-allowed equivalent for an ordinary tenant user.
    client.post("/api/v1/users/", json={
        "email": email,
        "password": password,
        "company_id": company_id,
        "first_name": "Owner",
        "last_name": "User",
        "role": "company_owner"
    })

    login_resp = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    headers = {"Authorization": f"Bearer {login_resp.json()['access_token']}"}
    return headers, company_id, email, password


def test_update_payment_status(client, db_session):
    """PATCH /payments/{id}/status is platform-admin-only (see
    app/payments/router.py) since it trusts a client-supplied status/
    gateway_transaction_id with no gateway verification. Elevate the test
    actor to super_admin directly in the DB — public signup can never mint
    a privileged role — mirroring
    tests/users/test_signup_roles.py::test_authenticated_platform_admin_can_create_super_admin."""
    headers, company_id, email, password = get_auth(client)
    row = db_session.query(User).filter(User.email == email).one()
    row.role = EnterpriseRole.SUPER_ADMIN
    db_session.commit()
    login_resp = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    admin_headers = {"Authorization": f"Bearer {login_resp.json()['access_token']}"}

    payload = {
        "amount": 20.00,
        "currency": "USD",
        "payment_method": "wallet",
        "gateway": "paypal"
    }
    create_resp = client.post("/api/v1/payments/", json=payload, headers=admin_headers)
    assert create_resp.status_code == 201
    payment_id = create_resp.json()["id"]

    update_payload = {
        "status": "success",
        "gateway_transaction_id": f"txn_{uuid.uuid4().hex[:8]}"
    }
    update_resp = client.patch(f"/api/v1/payments/{payment_id}/status", json=update_payload, headers=admin_headers)
    assert update_resp.status_code == 200
    assert update_resp.json()["status"] == "success"


def test_update_payment_status_forbidden_for_ordinary_user(client):
    """CRITICAL regression: an ordinary (non-platform-admin) authenticated
    company user must not be able to self-declare a payment 'success'."""
    headers, company_id, _email, _password = get_auth(client)
    payload = {
        "amount": 20.00,
        "currency": "USD",
        "payment_method": "wallet",
        "gateway": "paypal"
    }
    create_resp = client.post("/api/v1/payments/", json=payload, headers=headers)
    assert create_resp.status_code == 201
    payment_id = create_resp.json()["id"]

    update_payload = {
        "status": "success",
        "gateway_transaction_id": f"txn_{uuid.uuid4().hex[:8]}"
    }
    update_resp = client.patch(f"/api/v1/payments/{payment_id}/status", json=update_payload, headers=headers)
    assert update_resp.status_code == 403
