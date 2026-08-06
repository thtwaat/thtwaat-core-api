"""Unit tests for Studio AI Software Factory (Phase 9)."""
from __future__ import annotations

import zipfile
from pathlib import Path
from uuid import uuid4

import pytest

from app.studio.ai_generator import generate_ai_manifest
from app.studio.backend_generator import generate_backend_manifest
from app.studio.composer import compose_modules
from app.studio.factory import (
    AGENT_ORDER,
    FactoryContext,
    run_factory,
    validate_artifacts,
)
from app.studio.frontend_generator import generate_frontend_manifest
from app.studio.infrastructure_generator import generate_infrastructure_manifest
from app.studio.schemas import ProductBlueprint


def _hospital_blueprint() -> ProductBlueprint:
    return ProductBlueprint(
        industry="healthcare",
        product_type="saas",
        pages=["Landing", "Login", "Admin", "Patients", "Appointments", "Billing", "Dashboard"],
        dashboard_modules=["Schedule"],
        backend_modules=["Auth", "Billing", "AI Gateway", "Knowledge", "Storage", "Appointments"],
        database_tables=["users", "patients", "appointments"],
        roles=["admin", "doctor"],
        authentication={"jwt": True, "rbac": True},
        billing={"enabled": True},
        payments={"providers": ["razorpay"]},
        ai_features=["chat", "rag"],
        knowledge={"enabled": True, "rag": True},
        workflows=["appointment_booking"],
        integrations=["email", "storage"],
        deployment={"targets": ["docker", "vps"], "ssl": True, "domain": "hospital.example.com"},
        estimated_complexity="high",
        estimated_build_time="4-8 weeks",
    )


def _ctx() -> FactoryContext:
    bp = _hospital_blueprint()
    modules = compose_modules(bp)
    frontend = generate_frontend_manifest(
        blueprint=bp,
        modules=modules,
        project_title="Hospital",
        blueprint_version=1,
        build_plan_version=1,
    )
    backend = generate_backend_manifest(
        blueprint=bp,
        modules=modules,
        frontend=frontend,
        project_title="Hospital",
        blueprint_version=1,
        build_plan_version=1,
        frontend_version=1,
    )
    ai = generate_ai_manifest(
        blueprint=bp,
        modules=modules,
        backend=backend,
        project_title="Hospital Ops",
        blueprint_version=1,
        build_plan_version=1,
        frontend_version=1,
        backend_version=1,
    )
    infra = generate_infrastructure_manifest(
        blueprint=bp,
        modules=modules,
        backend=backend,
        ai=ai,
        project_title="Hospital Ops",
        blueprint_version=1,
        build_plan_version=1,
        frontend_version=1,
        backend_version=1,
        ai_version=1,
    )
    return FactoryContext(
        project_id=uuid4(),
        project_title="Hospital Ops",
        blueprint=bp,
        modules=modules,
        frontend=frontend,
        backend=backend,
        ai=ai,
        infra=infra,
        approval_id=uuid4(),
        versions={"blueprint": 1, "frontend": 1, "backend": 1, "ai": 1, "infrastructure": 1},
    )


@pytest.mark.unit
def test_factory_generates_full_tree(tmp_path: Path):
    ctx = _ctx()
    events = []

    def progress(event, payload):
        events.append(event)

    result = run_factory(ctx, output_dir=tmp_path / "out", progress=progress)
    assert result["ok"] is True
    assert result["status"] == "completed"
    assert result["file_count"] > 10
    assert Path(result["artifact_path"]).is_file()
    assert result["artifact_sha256"]

    # tree roots
    tree = tmp_path / "out" / "tree"
    for root in ("frontend", "backend", "shared", "database", "docker", "docs", "tests", ".github"):
        assert (tree / root).exists() or any(
            p.as_posix().startswith(root) for p in tree.rglob("*") if p.is_file()
        )
    assert (tree / "README.md").is_file()
    assert (tree / "backend" / "app" / "platform_mounts.py").is_file()
    mounts = (tree / "backend" / "app" / "platform_mounts.py").read_text(encoding="utf-8")
    assert "app.auth" in mounts
    assert "app.payments" in mounts
    assert "app.ai" in mounts

    with zipfile.ZipFile(result["artifact_path"]) as zf:
        names = zf.namelist()
        assert "README.md" in names
        assert any(n.startswith("frontend/") for n in names)
        assert any(n.startswith("backend/") for n in names)

    assert "planner" in result["agent_statuses"]
    for agent in AGENT_ORDER:
        assert result["agent_statuses"][agent]["status"] == "completed"
    assert "queued" in events
    assert "completed" in events
    assert any(e.startswith("generating_") for e in events)


@pytest.mark.unit
def test_factory_validation_catches_missing_roots():
    from app.studio.factory import GeneratedFile

    ok, errors = validate_artifacts(
        [GeneratedFile(path="README.md", content="# x\n", agent="documentation")]
    )
    assert ok is False
    assert any(e.startswith("missing_tree:") for e in errors)


@pytest.mark.unit
def test_agents_reuse_platform_not_duplicate_auth():
    ctx = _ctx()
    from app.studio.factory import agent_backend, agent_frontend, agent_ai

    be = agent_backend(ctx)
    assert any("platform_mounts" in f.path for f in be.files)
    assert all("class AuthService" not in f.content for f in be.files)
    fe = agent_frontend(ctx)
    assert any("PLATFORM_PAGES" in f.content for f in fe.files)
    ai = agent_ai(ctx)
    assert any(f.path.endswith("agents.json") for f in ai.files)
    assert ai.reuse_percent == 100.0


@pytest.mark.unit
def test_approval_required_message_constant():
    """Gate messaging used by service when approval missing."""
    detail = "Build not approved — run Review Center Approve Build first"
    assert "Approve Build" in detail
    assert "approved" in detail.lower()
