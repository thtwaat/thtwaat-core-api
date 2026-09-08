import uuid

from app.rbac.enums import EnterpriseRole
from app.users.model import User


def _create_company(client) -> str:
    company_slug = f"comp-{uuid.uuid4().hex[:8]}"
    company_resp = client.post("/api/v1/companies/", json={"name": "Payment Company", "slug": company_slug})
    return company_resp.json()["id"]


def _create_ordinary_user(client, company_id: str) -> tuple[dict, str, str]:
    """Signs up an ordinary (non-platform-admin) tenant user and returns
    (auth_headers, email, password). "admin" is itself a privileged role
    rejected by public signup (see tests/users/test_signup_roles.py), so
    company_owner — a normal, company-scoped role — is used here."""
    email = f"user-{uuid.uuid4().hex[:8]}@example.com"
    password = "securepassword"
    client.post("/api/v1/users/", json={
        "email": email,
        "password": password,
        "company_id": company_id,
        "first_name": "Owner",
        "last_name": "User",
        "role": "company_owner",
    })
    login_resp = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    headers = {"Authorization": f"Bearer {login_resp.json()['access_token']}"}
    return headers, email, password


def _elevate_to_platform_admin(client, db_session, company_id: str) -> dict:
    """Creates a second user in the SAME company and elevates it to
    super_admin directly in the DB — public signup can never mint a
    privileged role, so this mirrors
    tests/users/test_signup_roles.py::test_authenticated_platform_admin_can_create_super_admin.
    Kept in the same company as the ordinary user so both can act on the
    same payment rows (this router scopes everything by company_id,
    unchanged by the permission fix)."""
    headers, email, password = _create_ordinary_user(client, company_id)
    row = db_session.query(User).filter(User.email == email).one()
    row.role = EnterpriseRole.SUPER_ADMIN
    db_session.commit()

    login_resp = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    return {"Authorization": f"Bearer {login_resp.json()['access_token']}"}


def _create_pending_payment(client, headers) -> str:
    payload = {
        "amount": 150.00,
        "currency": "USD",
        "payment_method": "card",
        "gateway": "stripe",
    }
    create_resp = client.post("/api/v1/payments/", json=payload, headers=headers)
    assert create_resp.status_code == 201
    return create_resp.json()["id"]


def test_refund_payment(client, db_session):
    """PLATFORM_ADMIN can mark a payment successful and refund it via the
    legacy admin-only endpoints."""
    company_id = _create_company(client)
    admin_headers = _elevate_to_platform_admin(client, db_session, company_id)
    payment_id = _create_pending_payment(client, admin_headers)

    update_payload = {"status": "success", "gateway_transaction_id": "txn_123"}
    update_resp = client.patch(f"/api/v1/payments/{payment_id}/status", json=update_payload, headers=admin_headers)
    assert update_resp.status_code == 200

    refund_resp = client.post(f"/api/v1/payments/{payment_id}/refund", headers=admin_headers)
    assert refund_resp.status_code == 200
    assert refund_resp.json()["status"] == "refunded"


def test_refund_already_refunded_payment(client, db_session):
    company_id = _create_company(client)
    admin_headers = _elevate_to_platform_admin(client, db_session, company_id)
    payment_id = _create_pending_payment(client, admin_headers)

    update_payload = {"status": "success", "gateway_transaction_id": "txn_123"}
    client.patch(f"/api/v1/payments/{payment_id}/status", json=update_payload, headers=admin_headers)

    # First refund
    client.post(f"/api/v1/payments/{payment_id}/refund", headers=admin_headers)

    # Second refund
    refund_resp = client.post(f"/api/v1/payments/{payment_id}/refund", headers=admin_headers)
    assert refund_resp.status_code == 400


def test_ordinary_user_cannot_fabricate_a_successful_payment(client):
    """CRITICAL regression: an ordinary (non-platform-admin) authenticated
    company user must not be able to self-declare a payment 'success' with
    a client-supplied gateway_transaction_id."""
    company_id = _create_company(client)
    headers, _email, _password = _create_ordinary_user(client, company_id)
    payment_id = _create_pending_payment(client, headers)

    update_payload = {"status": "success", "gateway_transaction_id": "txn_fabricated"}
    resp = client.patch(f"/api/v1/payments/{payment_id}/status", json=update_payload, headers=headers)
    assert resp.status_code == 403

    # The forbidden request must not have mutated state.
    get_resp = client.get(f"/api/v1/payments/{payment_id}", headers=headers)
    assert get_resp.status_code == 200
    assert get_resp.json()["status"] == "pending"


def test_ordinary_user_cannot_trigger_a_refund(client, db_session):
    """HIGH regression: an ordinary (non-platform-admin) authenticated
    company user must not be able to trigger a real gateway refund call,
    even for a payment a platform admin already marked successful."""
    company_id = _create_company(client)
    headers, _email, _password = _create_ordinary_user(client, company_id)
    admin_headers = _elevate_to_platform_admin(client, db_session, company_id)

    payment_id = _create_pending_payment(client, headers)
    update_payload = {"status": "success", "gateway_transaction_id": "txn_123"}
    admin_update = client.patch(f"/api/v1/payments/{payment_id}/status", json=update_payload, headers=admin_headers)
    assert admin_update.status_code == 200

    refund_resp = client.post(f"/api/v1/payments/{payment_id}/refund", headers=headers)
    assert refund_resp.status_code == 403

    get_resp = client.get(f"/api/v1/payments/{payment_id}", headers=headers)
    assert get_resp.status_code == 200
    assert get_resp.json()["status"] == "success"
