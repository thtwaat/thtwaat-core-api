"""White-label branding API — /api/v1/branding."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, UploadFile, status
from sqlalchemy.orm import Session

from app.auth.router import get_current_user
from app.auth.schema import UserProfileResponse
from app.branding.models import BrandingAssetType
from app.branding.schemas import (
    BrandingAssetResponse,
    BrandingPreviewResponse,
    BrandingPublishResponse,
    BrandingResponse,
    BrandingUpdate,
)
from app.branding.service import BrandingService
from app.database.database import get_db
from app.rbac.dependencies import RequirePermission
from app.rbac.enums import Permission

router = APIRouter(prefix="/branding", tags=["White Label Branding"])


def get_branding_service(db: Session = Depends(get_db)) -> BrandingService:
    return BrandingService(db)


def require_permission(permission: Permission):
    def _check(user: UserProfileResponse = Depends(get_current_user)):
        RequirePermission(permission)(user.role)
        return user

    return _check


@router.get(
    "",
    response_model=BrandingResponse,
    summary="Get company branding (draft editor state)",
)
def get_branding(
    user: UserProfileResponse = Depends(require_permission(Permission.BRANDING_READ)),
    service: BrandingService = Depends(get_branding_service),
):
    return service.get(UUID(str(user.company_id)))


@router.patch(
    "",
    response_model=BrandingResponse,
    summary="Update brand settings (draft — publish to go live)",
)
def patch_branding(
    body: BrandingUpdate,
    user: UserProfileResponse = Depends(require_permission(Permission.BRANDING_MANAGE)),
    service: BrandingService = Depends(get_branding_service),
):
    return service.update(UUID(str(user.company_id)), body)


@router.post(
    "/assets",
    response_model=BrandingAssetResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a versioned brand asset (logo, favicon, splash, …)",
)
async def upload_branding_asset(
    asset_type: BrandingAssetType = Form(...),
    file: UploadFile = File(...),
    user: UserProfileResponse = Depends(require_permission(Permission.BRANDING_MANAGE)),
    service: BrandingService = Depends(get_branding_service),
):
    return await service.upload_asset(
        company_id=UUID(str(user.company_id)),
        user_id=UUID(str(user.id)),
        asset_type=asset_type,
        file=file,
    )


@router.get(
    "/preview",
    response_model=BrandingPreviewResponse,
    summary="Preview draft branding + domain/SSL status + CSS variables",
)
def preview_branding(
    user: UserProfileResponse = Depends(require_permission(Permission.BRANDING_READ)),
    service: BrandingService = Depends(get_branding_service),
):
    return service.preview(UUID(str(user.company_id)))


@router.post(
    "/publish",
    response_model=BrandingPublishResponse,
    summary="Publish branding without downtime (atomic snapshot swap)",
)
def publish_branding(
    user: UserProfileResponse = Depends(require_permission(Permission.BRANDING_MANAGE)),
    service: BrandingService = Depends(get_branding_service),
):
    return service.publish(UUID(str(user.company_id)))


@router.post(
    "/reset",
    response_model=BrandingResponse,
    summary="Reset draft branding to defaults (live published snapshot kept until next publish)",
)
def reset_branding(
    user: UserProfileResponse = Depends(require_permission(Permission.BRANDING_MANAGE)),
    service: BrandingService = Depends(get_branding_service),
):
    return service.reset(UUID(str(user.company_id)))
