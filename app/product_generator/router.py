"""AI Product Generator API routes."""
from __future__ import annotations

from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.auth.router import get_current_user
from app.auth.schema import UserProfileResponse
from app.database.database import get_db
from app.product_generator.schemas import (
    AnalysisResponse,
    AnalyzeRequest,
    GenerateRequest,
    ProductGenerationResponse,
    ProductGeneratorOutput,
    PublishProductRequest,
)
from app.product_generator.service import ProductGeneratorService
from app.rbac.dependencies import RequirePermission
from app.rbac.enums import Permission

router = APIRouter(prefix="/product-generator", tags=["AI Product Generator"])


def get_service(db: Session = Depends(get_db)) -> ProductGeneratorService:
    return ProductGeneratorService(db)


def require_permission(permission: Permission):
    def _check(user: UserProfileResponse = Depends(get_current_user)):
        RequirePermission(permission)(user.role)
        return user

    return _check


# ── Analyze ───────────────────────────────────────────────────────────────────

@router.post("/analyze", response_model=AnalysisResponse)
def analyze_prompt(
    payload: AnalyzeRequest,
    user: UserProfileResponse = Depends(require_permission(Permission.TEMPLATES_READ)),
    service: ProductGeneratorService = Depends(get_service),
):
    """Step 1–2: Extract industry, type, features, tone and recommend a template."""
    return service.analyze(payload.prompt, UUID(str(user.company_id)))


# ── Generate ──────────────────────────────────────────────────────────────────

@router.post(
    "/generate",
    response_model=ProductGenerationResponse,
    status_code=status.HTTP_201_CREATED,
)
def generate_product(
    payload: GenerateRequest,
    user: UserProfileResponse = Depends(require_permission(Permission.TEMPLATES_MANAGE)),
    service: ProductGeneratorService = Depends(get_service),
):
    """
    Full orchestration: Steps 1–6 (and optional 7 if auto_publish=true).
    Returns preview_url, widget, api_key, deployment_checklist.
    """
    return service.generate(
        UUID(str(user.company_id)),
        UUID(str(user.id)),
        payload,
    )


# ── Generations list ──────────────────────────────────────────────────────────

@router.get("/generations", response_model=List[ProductGenerationResponse])
def list_generations(
    limit: int = Query(default=50, ge=1, le=100),
    user: UserProfileResponse = Depends(require_permission(Permission.TEMPLATES_READ)),
    service: ProductGeneratorService = Depends(get_service),
):
    return service.list(UUID(str(user.company_id)), limit=limit)


@router.get("/generations/{generation_id}", response_model=ProductGenerationResponse)
def get_generation(
    generation_id: UUID,
    user: UserProfileResponse = Depends(require_permission(Permission.TEMPLATES_READ)),
    service: ProductGeneratorService = Depends(get_service),
):
    return service.get(UUID(str(user.company_id)), generation_id)


# ── Canonical output ──────────────────────────────────────────────────────────

@router.get("/generations/{generation_id}/output", response_model=ProductGeneratorOutput)
def get_output(
    generation_id: UUID,
    user: UserProfileResponse = Depends(require_permission(Permission.TEMPLATES_READ)),
    service: ProductGeneratorService = Depends(get_service),
):
    """Returns structured output and clears the one-time API key from the record."""
    return service.output(UUID(str(user.company_id)), generation_id)


# ── Publish ───────────────────────────────────────────────────────────────────

@router.post("/generations/{generation_id}/publish", response_model=ProductGenerationResponse)
def publish_product(
    generation_id: UUID,
    payload: PublishProductRequest = PublishProductRequest(),
    user: UserProfileResponse = Depends(require_permission(Permission.TEMPLATES_MANAGE)),
    service: ProductGeneratorService = Depends(get_service),
):
    """Step 7: Publish agent via Publish Service and mark installation PUBLISHED."""
    return service.publish_product(
        UUID(str(user.company_id)),
        UUID(str(user.id)),
        generation_id,
        hostname=payload.hostname,
    )
