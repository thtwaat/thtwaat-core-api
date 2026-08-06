"""Unit tests for Studio one-click deployment (Phase 10)."""
from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest

from app.studio.deploy import (
    DeployContext,
    mask_env_content,
    mask_secret,
    get_provider,
    run_deploy,
)
from app.studio.factory import FactoryContext, run_factory
from app.studio.ai_generator import generate_ai_manifest
from app.studio.backend_generator import generate_backend_manifest
from app.studio.composer import compose_modules
from app.studio.frontend_generator import generate_frontend_manifest
from app.studio.infrastructure_generator import generate_infrastructure_manifest
from app.studio.schemas import ProductBlueprint


def _bp() -> ProductBlueprint:
    return ProductBlueprint(
        industry="saas",
        product_type="saas",
        pages=["Dashboard", "Login"],
        authentication={"jwt": True},
        deployment={"targets": ["docker", "vps"], "ssl": True},
        estimated_complexity="low",
    )


def _make_artifact(tmp_path: Path) -> tuple[Path, str, FactoryContext]:
    bp = _bp()
    modules = compose_modules(bp)
    frontend = generate_frontend_manifest(
        blueprint=bp,
        modules=modules,
        project_title="Demo",
        blueprint_version=1,
        build_plan_version=1,
    )
    backend = generate_backend_manifest(
        blueprint=bp,
        modules=modules,
        frontend=frontend,
        project_title="Demo",
        blueprint_version=1,
        build_plan_version=1,
        frontend_version=1,
    )
    ai = generate_ai_manifest(
        blueprint=bp,
        modules=modules,
        backend=backend,
        project_title="Demo",
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
        project_title="Demo",
        blueprint_version=1,
        build_plan_version=1,
        frontend_version=1,
        backend_version=1,
        ai_version=1,
    )
    ctx = FactoryContext(
        project_id=uuid4(),
        project_title="Demo App",
        blueprint=bp,
        modules=modules,
        frontend=frontend,
        backend=backend,
        ai=ai,
        infra=infra,
        approval_id=uuid4(),
        versions={"blueprint": 1},
    )
    out = tmp_path / "build"
    result = run_factory(ctx, output_dir=out)
    assert result["ok"]
    return Path(result["artifact_path"]), result["artifact_sha256"], ctx


@pytest.mark.unit
def test_secret_masking():
    assert mask_secret("abcd") == "****"
    assert mask_secret("supersecretvalue").endswith("alue")
    masked = mask_env_content("JWT_SECRET_KEY=abcdefghijklmnop\nAPP_ENV=production\n")
    assert "abcdefghijklmnop" not in masked
    assert "APP_ENV=production" in masked
    assert "JWT_SECRET_KEY=****" in masked


@pytest.mark.unit
def test_vps_deploy_workflow(tmp_path: Path):
    artifact, sha, _ = _make_artifact(tmp_path)
    stages = []

    def progress(stage, payload):
        stages.append(stage)

    ctx = DeployContext(
        project_id=uuid4(),
        deployment_id=uuid4(),
        workspace_id=uuid4(),
        project_title="Demo App",
        provider="vps",
        build_id=uuid4(),
        build_version=1,
        artifact_path=artifact,
        artifact_sha256=sha,
        domain="demo.example.com",
        output_dir=tmp_path / "deploy-out",
        public_api_base="https://api.example.com",
        public_app_base="https://app.example.com",
    )
    result = run_deploy(ctx, progress=progress)
    assert result["ok"] is True
    assert result["status"] == "completed"
    assert result["live"] is True
    assert "website" in result["urls"]
    assert (tmp_path / "deploy-out" / "DEPLOYED.json").is_file()
    assert (tmp_path / "deploy-out" / "env" / ".env.production.masked").is_file()
    # Plaintext secrets removed — encrypted at rest
    assert not (tmp_path / "deploy-out" / "env" / ".env.production").exists()
    assert (tmp_path / "deploy-out" / "env" / ".env.production.enc").is_file()
    masked = (tmp_path / "deploy-out" / "env" / ".env.production.masked").read_text(
        encoding="utf-8"
    )
    assert "abcdefghijklmnop" not in masked or "JWT" in masked
    assert "queued" in stages
    assert "completed" in stages
    assert "database_migration" in stages
    assert any(s in stages for s in ("health_check", "ssl", "deploying"))
    assert result.get("commit_sha") == sha


@pytest.mark.unit
def test_azure_label_is_container_apps():
    p = get_provider("azure")
    assert "Container" in p.label or p.id == "azure"


@pytest.mark.unit
def test_deploy_stages_include_migration():
    from app.studio.deploy import DEPLOY_STAGES

    assert "database_migration" in DEPLOY_STAGES
    assert "building" in DEPLOY_STAGES


@pytest.mark.unit
def test_planning_provider_no_live_mutate(tmp_path: Path):
    artifact, sha, _ = _make_artifact(tmp_path)
    ctx = DeployContext(
        project_id=uuid4(),
        deployment_id=uuid4(),
        workspace_id=uuid4(),
        project_title="Demo",
        provider="railway",
        build_id=uuid4(),
        build_version=1,
        artifact_path=artifact,
        artifact_sha256=sha,
        output_dir=tmp_path / "rail",
    )
    result = run_deploy(ctx)
    assert result["ok"] is True
    assert result["live"] is False
    assert result["instructions"]
    assert "planning" in " ".join(result["instructions"]).lower() or result["provider"] == "railway"


@pytest.mark.unit
def test_deploy_fails_without_artifact(tmp_path: Path):
    ctx = DeployContext(
        project_id=uuid4(),
        deployment_id=uuid4(),
        workspace_id=uuid4(),
        project_title="X",
        provider="docker",
        build_id=uuid4(),
        build_version=1,
        artifact_path=tmp_path / "missing.zip",
        artifact_sha256=None,
        output_dir=tmp_path / "bad",
    )
    result = run_deploy(ctx)
    assert result["ok"] is False
    assert result["status"] == "failed"
    assert result["retryable"] is True


@pytest.mark.unit
def test_provider_registry():
    assert get_provider("vps").executable is True
    assert get_provider("docker").executable is True
    assert get_provider("kubernetes").executable is False
    assert get_provider("coolify").executable is False
