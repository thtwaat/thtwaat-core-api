"""Unit tests for production AI Product Architect."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.studio.architect import (
    ai_blueprint_is_usable,
    architect_blueprint,
    build_heuristic_blueprint,
    build_recommendations,
    normalize_ai_blueprint,
    validate_blueprint,
)
from app.studio.schemas import ProductBlueprint


@pytest.mark.unit
def test_hospital_heuristic_fallback_still_works():
    bp = build_heuristic_blueprint(
        "Create a Hospital Management SaaS with AI appointment booking, "
        "patient chat, billing, admin dashboard and website."
    )
    assert bp.industry == "healthcare"
    assert bp.ai_features
    assert bp.pages


@pytest.mark.unit
def test_normalize_ai_blueprint_preserves_ai_fields():
    raw = {
        "industry": "healthcare",
        "product_type": "saas",
        "target_users": ["Doctors", "Patients", "Admins"],
        "pages": ["Landing", "Login", "Admin", "Patients", "Appointments", "Billing"],
        "dashboard_modules": ["Overview", "Schedule", "Revenue"],
        "backend_modules": ["Auth", "Users", "RBAC", "Billing", "AI Gateway", "Knowledge", "Storage"],
        "database_tables": ["users", "patients", "appointments", "invoices", "agents"],
        "roles": ["company_owner", "admin", "doctor", "patient"],
        "permissions": ["patients:read", "billing:manage"],
        "authentication": {"methods": ["email_password", "otp"], "mfa": True, "jwt": True, "rbac": True},
        "billing": {"enabled": True, "plans": ["starter", "pro"], "metering": True},
        "payments": {"providers": ["stripe", "razorpay"], "region_pricing": True},
        "ai_features": ["chat", "rag", "appointment_assistant", "memory"],
        "knowledge": {"enabled": True, "rag": True, "packs": ["clinical-faq"]},
        "workflows": ["appointment_booking", "patient_intake", "human_handoff"],
        "integrations": ["stripe", "email", "calendar", "webhooks"],
        "deployment": {
            "targets": ["docker", "compose"],
            "ssl": True,
            "healthchecks": True,
            "workers": True,
            "monitoring": True,
        },
        "marketplace_category": "saas",
        "estimated_complexity": "high",
        "estimated_build_time": "4-8 weeks",
    }
    bp = normalize_ai_blueprint(raw)
    assert bp.industry == "healthcare"
    assert "Appointments" in bp.pages
    assert "patients" in bp.database_tables
    assert "appointment_assistant" in bp.ai_features
    assert bp.billing["enabled"] is True
    assert ai_blueprint_is_usable(bp)


@pytest.mark.unit
def test_sparse_ai_blueprint_rejected():
    bp = normalize_ai_blueprint({"industry": "x", "pages": ["Home"]})
    assert ai_blueprint_is_usable(bp) is False


@pytest.mark.unit
def test_validation_detects_expanded_gaps():
    thin = ProductBlueprint(
        industry="saas",
        product_type="saas",
        pages=[],
        backend_modules=[],
        database_tables=[],
        roles=["member"],
        authentication={},
        billing={"enabled": True},
        payments={},
        ai_features=["rag"],
        knowledge={"enabled": False},
        workflows=[],
        integrations=[],
        deployment={},
    )
    codes = {w.code for w in validate_blueprint(thin)}
    assert "missing_auth" in codes
    assert "missing_pages" in codes
    assert "missing_database" in codes
    assert "missing_payment_providers" in codes
    assert "missing_deployment" in codes
    assert "missing_workflows" in codes


@pytest.mark.unit
def test_recommendations_use_blueprint_signals():
    bp = normalize_ai_blueprint(
        {
            "industry": "crm",
            "product_type": "crm",
            "pages": ["Dashboard", "Leads", "Admin"],
            "backend_modules": ["Auth", "Billing", "Storage", "AI Gateway"],
            "database_tables": ["users", "leads", "deals"],
            "roles": ["admin", "sales_rep"],
            "authentication": {"jwt": True},
            "billing": {"enabled": True},
            "payments": {"providers": ["stripe"]},
            "ai_features": ["chat", "rag"],
            "knowledge": {"enabled": True, "rag": True},
            "workflows": ["lead_capture"],
            "integrations": ["email"],
            "deployment": {"targets": ["docker"], "ssl": True, "monitoring": True},
            "marketplace_category": "crm",
        }
    )
    recs = build_recommendations(bp)
    assert any("crm" in t for t in recs.templates)
    assert any("rag" in a or "chat" in a or "assistant" in a for a in recs.agents)
    assert any("stripe" in i.lower() or "razorpay" in i.lower() for i in recs.integrations)
    assert recs.knowledge_packs


@pytest.mark.unit
@pytest.mark.asyncio
async def test_architect_prefers_ai_without_heuristic_merge():
    ai_payload = {
        "industry": "healthcare",
        "product_type": "saas",
        "target_users": ["Doctors"],
        "pages": ["Landing", "Admin", "Patients", "Appointments", "Billing"],
        "dashboard_modules": ["Schedule"],
        "backend_modules": ["Auth", "Billing", "AI Gateway", "Storage", "Knowledge"],
        "database_tables": ["users", "patients", "appointments"],
        "roles": ["admin", "doctor"],
        "permissions": ["patients:read"],
        "authentication": {"jwt": True, "rbac": True, "methods": ["email_password"]},
        "billing": {"enabled": True, "plans": ["pro"]},
        "payments": {"providers": ["razorpay"]},
        "ai_features": ["chat", "appointment_assistant"],
        "knowledge": {"enabled": True, "rag": True},
        "workflows": ["appointment_booking"],
        "integrations": ["razorpay", "email", "storage"],
        "deployment": {"targets": ["docker"], "ssl": True, "monitoring": True},
        "marketplace_category": "saas",
        "estimated_complexity": "high",
        "estimated_build_time": "4-8 weeks",
    }

    mock_result = MagicMock()
    mock_result.content = __import__("json").dumps(ai_payload)

    with patch("app.studio.architect._resolve_provider_model", return_value=("openai", "gpt-4o-mini")):
        with patch("app.ai.service.AIService") as svc_cls:
            svc_cls.return_value.generate = AsyncMock(return_value=mock_result)
            bp, source = await architect_blueprint(
                prompt="Create a Hospital Management SaaS with AI appointment booking",
                company_id=MagicMock(),
                user_id=MagicMock(),
                db=MagicMock(),
                use_ai=True,
            )

    assert source == "ai_gateway"
    assert bp.industry == "healthcare"
    # Must be pure AI output — not heuristic-merged extras like Medical Records unless AI said so
    assert bp.pages == [
        "Landing",
        "Admin",
        "Patients",
        "Appointments",
        "Billing",
    ]
    assert "Medical Records" not in bp.pages


@pytest.mark.unit
@pytest.mark.asyncio
async def test_architect_falls_back_when_ai_fails():
    with patch("app.studio.architect._generate_ai_blueprint", AsyncMock(side_effect=RuntimeError("down"))):
        bp, source = await architect_blueprint(
            prompt="Create a CRM SaaS with leads billing and AI chat",
            company_id=MagicMock(),
            user_id=MagicMock(),
            db=MagicMock(),
            use_ai=True,
        )
    assert source == "heuristic"
    assert bp.industry in {"crm", "saas"}
    assert bp.pages
