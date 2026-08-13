"""Command Center dashboard — read-only Super Admin metrics from Core data."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal

from app.agent_platform.models.agent import AgentConfig
from app.agent_platform.models.conversation import Conversation
from app.apps.model import App, AppStatus, AppType
from app.auth.service import AuthService
from app.companies.model import Company, CompanyPlan
from app.payments.invoices.model import Invoice, InvoiceStatus
from app.payments.plans.model import Plan
from app.payments.subscriptions.model import (
    Subscription,
    SubscriptionProvider,
    SubscriptionStatus,
)
from app.rbac.enums import EnterpriseRole
from app.usage.models import CompanyUsageMeter
from app.users.model import User


def _company(client) -> str:
    slug = f"cc-{uuid.uuid4().hex[:8]}"
    resp = client.post(
        "/api/v1/companies/",
        json={"name": f"CC Co {slug}", "slug": slug},
    )
    assert resp.status_code in (200, 201), resp.text
    return resp.json()["id"]


def _user_payload(company_id: str, role: str) -> dict:
    return {
        "email": f"u-{uuid.uuid4().hex[:8]}@example.com",
        "password": "securepassword",
        "company_id": company_id,
        "first_name": "Test",
        "last_name": "User",
        "role": role,
    }


def _bearer(db_session, user_id: str) -> dict:
    token = AuthService(db_session).create_access_token(subject=str(user_id))
    return {"Authorization": f"Bearer {token}"}


def test_command_center_unauthorized(client):
    resp = client.get("/api/v1/command-center/dashboard")
    assert resp.status_code == 401


def test_command_center_employee_forbidden(client, db_session):
    company_id = _company(client)
    payload = _user_payload(company_id, "employee")
    create = client.post("/api/v1/users/", json=payload)
    assert create.status_code in (200, 201), create.text

    headers = _bearer(db_session, create.json()["id"])
    resp = client.get("/api/v1/command-center/dashboard", headers=headers)
    assert resp.status_code == 403


def test_command_center_company_owner_forbidden(client, db_session):
    company_id = _company(client)
    payload = _user_payload(company_id, "company_owner")
    create = client.post("/api/v1/users/", json=payload)
    assert create.status_code in (200, 201), create.text

    headers = _bearer(db_session, create.json()["id"])
    resp = client.get("/api/v1/command-center/dashboard", headers=headers)
    assert resp.status_code == 403


def test_command_center_super_admin_success(client, db_session):
    company_id = _company(client)
    payload = _user_payload(company_id, "company_owner")
    create = client.post("/api/v1/users/", json=payload)
    assert create.status_code in (200, 201), create.text
    user_id = create.json()["id"]

    row = db_session.query(User).filter(User.id == user_id).one()
    row.role = EnterpriseRole.SUPER_ADMIN
    db_session.commit()

    headers = _bearer(db_session, user_id)
    resp = client.get("/api/v1/command-center/dashboard", headers=headers)
    assert resp.status_code == 200, resp.text

    data = resp.json()
    # Real Core data: at least the company we just created is an active customer.
    assert data["customers"] >= 1
    assert isinstance(data["revenue"], (int, float))
    assert isinstance(data["mrr"], (int, float))
    assert isinstance(data["active_projects"], int)
    assert isinstance(data["leads"], int)
    assert isinstance(data["conversion"], (int, float))
    assert isinstance(data["ai_tasks"], int)
    assert isinstance(data["human_escalations"], int)
    assert isinstance(data["ai_cost"], (int, float))
    assert data["revenue"] >= 0
    assert data["mrr"] >= 0


def test_command_center_reflects_seeded_core_metrics(client, db_session):
    """Dashboard must surface real rows from invoices, apps, leads, escalations, usage."""
    company_id = _company(client)
    payload = _user_payload(company_id, "company_owner")
    create = client.post("/api/v1/users/", json=payload)
    assert create.status_code in (200, 201), create.text
    user_id = create.json()["id"]

    row = db_session.query(User).filter(User.id == user_id).one()
    row.role = EnterpriseRole.SUPER_ADMIN
    db_session.commit()

    company_uuid = uuid.UUID(company_id)
    company = db_session.query(Company).filter(Company.id == company_uuid).one()
    company.plan = CompanyPlan.STARTER
    db_session.add(company)

    plan = Plan(
        name=f"CC Plan {uuid.uuid4().hex[:6]}",
        amount=Decimal("100.00"),
        currency="USD",
        interval="month",
        is_active=True,
    )
    db_session.add(plan)
    db_session.flush()

    db_session.add(
        Subscription(
            company_id=company_uuid,
            plan_id=plan.id,
            provider=SubscriptionProvider.MANUAL,
            status=SubscriptionStatus.ACTIVE,
        )
    )
    db_session.add(
        Invoice(
            company_id=company_uuid,
            provider="manual",
            amount_due=Decimal("50.00"),
            amount_paid=Decimal("50.00"),
            currency="USD",
            status=InvoiceStatus.PAID,
            paid_at=datetime.now(timezone.utc),
        )
    )
    db_session.add(
        App(
            company_id=company_uuid,
            name="Hospital Ops",
            slug=f"hosp-{uuid.uuid4().hex[:6]}",
            type=AppType.WEB,
            status=AppStatus.ACTIVE,
            api_key=f"app_{uuid.uuid4().hex}",
            settings={},
        )
    )

    agent = AgentConfig(
        company_id=company_uuid,
        name="Hospital Agent",
        system_prompt_template="You help hospital staff.",
        status="PUBLISHED",
        web_config={},
        allowed_tools=[],
    )
    db_session.add(agent)
    db_session.flush()

    db_session.add(
        Conversation(
            company_id=company_uuid,
            agent_id=agent.id,
            title="Lead chat",
            channel="widget",
            status="pending_human",
            extra_metadata={"lead": {"email": "patient@example.com", "name": "Pat"}},
        )
    )

    now = datetime.now(timezone.utc)
    period_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    db_session.add(
        CompanyUsageMeter(
            company_id=company_uuid,
            period_type="monthly",
            period_start=period_start,
            period_end=now,
            plan_key="starter",
            ai_messages=7,
            estimated_cost=Decimal("1.250000"),
        )
    )
    db_session.commit()

    headers = _bearer(db_session, user_id)
    resp = client.get("/api/v1/command-center/dashboard", headers=headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()

    assert data["customers"] >= 1
    assert data["revenue"] >= 50.0
    assert data["mrr"] >= 100.0
    assert data["active_projects"] >= 1
    assert data["leads"] >= 1
    assert data["human_escalations"] >= 1
    assert data["ai_tasks"] >= 7
    assert data["ai_cost"] >= 1.25
    assert data["conversion"] > 0
