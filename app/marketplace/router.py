"""Template Registry + Marketplace API routes."""
from __future__ import annotations

from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.auth.router import get_current_user
from app.auth.schema import UserProfileResponse
from app.database.database import get_db
from app.marketplace.schemas import (
    CategoryItem,
    CollectionCreate,
    CollectionDetail,
    CollectionSummary,
    CollectionUpdate,
    ConnectRequest,
    InstallActionRequest,
    InstallRequest,
    InstallationResponse,
    MarketplaceAnalytics,
    MarketplaceDashboard,
    MarketplaceHomeResponse,
    TemplateCreate,
    TemplateListPage,
    TemplateResponse,
    TemplateReviewsResponse,
    TemplateUpdate,
    TemplateVersionCreate,
    TemplateVersionResponse,
    TemplateVersionUpdate,
    UpdateNotification,
)
from app.marketplace.service import MarketplaceService
from app.rbac.dependencies import RequirePermission
from app.rbac.enums import Permission

router = APIRouter(prefix="/marketplace", tags=["Template Marketplace"])


def get_marketplace_service(db: Session = Depends(get_db)) -> MarketplaceService:
    return MarketplaceService(db)


def require_permission(permission: Permission):
    def _check(user: UserProfileResponse = Depends(get_current_user)):
        RequirePermission(permission)(user.role)
        return user

    return _check


# ── Browse ────────────────────────────────────────────────────────────────────

@router.get("/dashboard", response_model=MarketplaceDashboard)
def marketplace_dashboard(
    user: UserProfileResponse = Depends(require_permission(Permission.TEMPLATES_READ)),
    service: MarketplaceService = Depends(get_marketplace_service),
):
    return service.dashboard(UUID(str(user.company_id)))


@router.get("/home", response_model=MarketplaceHomeResponse)
def marketplace_home(
    user: UserProfileResponse = Depends(require_permission(Permission.TEMPLATES_READ)),
    service: MarketplaceService = Depends(get_marketplace_service),
):
    """Store Home rails: featured, newest, trending, collections, categories."""
    return service.home(
        UUID(str(user.company_id)),
        user_id=UUID(str(user.id)),
    )


@router.get("/analytics", response_model=MarketplaceAnalytics)
def marketplace_analytics(
    days: int = Query(default=30, ge=1, le=90),
    user: UserProfileResponse = Depends(require_permission(Permission.TEMPLATES_READ)),
    service: MarketplaceService = Depends(get_marketplace_service),
):
    """Company marketplace analytics (installs, favorites, trends)."""
    return service.analytics(UUID(str(user.company_id)), days=days, include_catalog=False)


@router.get("/admin/analytics", response_model=MarketplaceAnalytics)
def marketplace_admin_analytics(
    days: int = Query(default=30, ge=1, le=90),
    user: UserProfileResponse = Depends(require_permission(Permission.TEMPLATES_MANAGE)),
    service: MarketplaceService = Depends(get_marketplace_service),
):
    """Company + catalog-wide analytics for registry operators."""
    return service.analytics(UUID(str(user.company_id)), days=days, include_catalog=True)


@router.get("/categories", response_model=List[CategoryItem])
def list_categories(
    user: UserProfileResponse = Depends(require_permission(Permission.TEMPLATES_READ)),
    service: MarketplaceService = Depends(get_marketplace_service),
):
    return service.categories()


@router.get("/templates", response_model=TemplateListPage)
def list_templates(
    q: Optional[str] = Query(default=None),
    category: Optional[str] = Query(default=None),
    featured: Optional[bool] = Query(default=None),
    kind: Optional[str] = Query(default=None),
    pricing_tier: Optional[str] = Query(default=None),
    newest: bool = Query(default=False),
    sort: Optional[str] = Query(
        default=None,
        description="featured | newest | name | installs | updated | relevance",
    ),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    user: UserProfileResponse = Depends(require_permission(Permission.TEMPLATES_READ)),
    service: MarketplaceService = Depends(get_marketplace_service),
):
    return service.list_templates(
        UUID(str(user.company_id)),
        q=q,
        category=category,
        featured=featured,
        kind=kind,
        pricing_tier=pricing_tier,
        newest=newest,
        sort=sort,
        limit=limit,
        offset=offset,
    )


@router.get("/templates/{template_id_or_slug}/versions", response_model=List[TemplateVersionResponse])
def list_versions(
    template_id_or_slug: str,
    user: UserProfileResponse = Depends(require_permission(Permission.TEMPLATES_READ)),
    service: MarketplaceService = Depends(get_marketplace_service),
):
    return service.list_versions(template_id_or_slug)


@router.get(
    "/templates/{template_id_or_slug}/versions/{version_ref}",
    response_model=TemplateVersionResponse,
)
def get_version(
    template_id_or_slug: str,
    version_ref: str,
    user: UserProfileResponse = Depends(require_permission(Permission.TEMPLATES_READ)),
    service: MarketplaceService = Depends(get_marketplace_service),
):
    return service.get_version(template_id_or_slug, version_ref)


@router.get("/templates/{template_id_or_slug}", response_model=TemplateResponse)
def get_template(
    template_id_or_slug: str,
    user: UserProfileResponse = Depends(require_permission(Permission.TEMPLATES_READ)),
    service: MarketplaceService = Depends(get_marketplace_service),
):
    return service.get_template(
        template_id_or_slug,
        UUID(str(user.company_id)),
        user_id=UUID(str(user.id)),
        record_view=True,
    )


@router.get(
    "/templates/{template_id_or_slug}/reviews",
    response_model=TemplateReviewsResponse,
)
def list_template_reviews(
    template_id_or_slug: str,
    limit: int = Query(default=50, ge=1, le=100),
    user: UserProfileResponse = Depends(require_permission(Permission.TEMPLATES_READ)),
    service: MarketplaceService = Depends(get_marketplace_service),
):
    """Additive: bridge agent-store reviews for a marketplace template."""
    return service.list_template_reviews(template_id_or_slug, limit=limit)


# ── Collections ───────────────────────────────────────────────────────────────

@router.get("/collections", response_model=List[CollectionSummary])
def list_collections(
    user: UserProfileResponse = Depends(require_permission(Permission.TEMPLATES_READ)),
    service: MarketplaceService = Depends(get_marketplace_service),
):
    return service.list_collections(public_only=True)


@router.get("/collections/{slug}", response_model=CollectionDetail)
def get_collection(
    slug: str,
    user: UserProfileResponse = Depends(require_permission(Permission.TEMPLATES_READ)),
    service: MarketplaceService = Depends(get_marketplace_service),
):
    return service.get_collection(slug, UUID(str(user.company_id)))


@router.get("/admin/collections", response_model=List[CollectionSummary])
def admin_list_collections(
    user: UserProfileResponse = Depends(require_permission(Permission.TEMPLATES_MANAGE)),
    service: MarketplaceService = Depends(get_marketplace_service),
):
    return service.list_collections(public_only=False)


@router.post(
    "/admin/collections",
    response_model=CollectionDetail,
    status_code=status.HTTP_201_CREATED,
)
def admin_create_collection(
    payload: CollectionCreate,
    user: UserProfileResponse = Depends(require_permission(Permission.TEMPLATES_MANAGE)),
    service: MarketplaceService = Depends(get_marketplace_service),
):
    return service.create_collection(payload)


@router.patch("/admin/collections/{collection_id_or_slug}", response_model=CollectionDetail)
def admin_update_collection(
    collection_id_or_slug: str,
    payload: CollectionUpdate,
    user: UserProfileResponse = Depends(require_permission(Permission.TEMPLATES_MANAGE)),
    service: MarketplaceService = Depends(get_marketplace_service),
):
    return service.update_collection(collection_id_or_slug, payload)


@router.delete("/admin/collections/{collection_id_or_slug}")
def admin_delete_collection(
    collection_id_or_slug: str,
    user: UserProfileResponse = Depends(require_permission(Permission.TEMPLATES_MANAGE)),
    service: MarketplaceService = Depends(get_marketplace_service),
):
    return service.delete_collection(collection_id_or_slug)


# ── Favorites ─────────────────────────────────────────────────────────────────

@router.get("/favorites", response_model=List[TemplateResponse])
def list_favorites(
    user: UserProfileResponse = Depends(require_permission(Permission.TEMPLATES_READ)),
    service: MarketplaceService = Depends(get_marketplace_service),
):
    return service.list_favorites(UUID(str(user.company_id)), UUID(str(user.id)))


@router.post(
    "/templates/{template_id_or_slug}/favorite",
    response_model=TemplateResponse,
    status_code=status.HTTP_200_OK,
)
def add_favorite(
    template_id_or_slug: str,
    user: UserProfileResponse = Depends(require_permission(Permission.TEMPLATES_MANAGE)),
    service: MarketplaceService = Depends(get_marketplace_service),
):
    return service.add_favorite(
        UUID(str(user.company_id)),
        UUID(str(user.id)),
        template_id_or_slug,
    )


@router.delete("/templates/{template_id_or_slug}/favorite")
def remove_favorite(
    template_id_or_slug: str,
    user: UserProfileResponse = Depends(require_permission(Permission.TEMPLATES_MANAGE)),
    service: MarketplaceService = Depends(get_marketplace_service),
):
    return service.remove_favorite(
        UUID(str(user.company_id)),
        UUID(str(user.id)),
        template_id_or_slug,
    )


# ── Installations ─────────────────────────────────────────────────────────────

@router.get("/installed", response_model=List[InstallationResponse])
def list_installed(
    user: UserProfileResponse = Depends(require_permission(Permission.TEMPLATES_READ)),
    service: MarketplaceService = Depends(get_marketplace_service),
):
    return service.list_installed(UUID(str(user.company_id)))


@router.get("/updates", response_model=List[UpdateNotification])
def list_updates(
    user: UserProfileResponse = Depends(require_permission(Permission.TEMPLATES_READ)),
    service: MarketplaceService = Depends(get_marketplace_service),
):
    return service.list_update_notifications(UUID(str(user.company_id)))


@router.post("/templates/update", response_model=InstallationResponse)
def update_template_install_alias(
    payload: InstallActionRequest,
    user: UserProfileResponse = Depends(require_permission(Permission.TEMPLATES_MANAGE)),
    service: MarketplaceService = Depends(get_marketplace_service),
):
    """Phase 2 alias → POST /installations/{id}/update."""
    return service.update_installation(
        UUID(str(user.company_id)),
        payload.installation_id,
        payload.version,
    )


@router.post("/templates/uninstall")
def uninstall_template_alias(
    payload: InstallActionRequest,
    user: UserProfileResponse = Depends(require_permission(Permission.TEMPLATES_MANAGE)),
    service: MarketplaceService = Depends(get_marketplace_service),
):
    """Phase 2 alias → DELETE /installations/{id}."""
    return service.uninstall(UUID(str(user.company_id)), payload.installation_id)


@router.post(
    "/templates/{template_id_or_slug}/install",
    response_model=InstallationResponse,
    status_code=status.HTTP_201_CREATED,
)
def install_template(
    template_id_or_slug: str,
    payload: InstallRequest,
    user: UserProfileResponse = Depends(require_permission(Permission.TEMPLATES_MANAGE)),
    service: MarketplaceService = Depends(get_marketplace_service),
):
    return service.install(
        UUID(str(user.company_id)),
        UUID(str(user.id)),
        template_id_or_slug,
        payload,
    )


@router.post("/installations/{install_id}/connect", response_model=InstallationResponse)
def connect_installation(
    install_id: UUID,
    payload: ConnectRequest,
    user: UserProfileResponse = Depends(require_permission(Permission.TEMPLATES_MANAGE)),
    service: MarketplaceService = Depends(get_marketplace_service),
):
    return service.connect(UUID(str(user.company_id)), install_id, payload)


@router.post("/installations/{install_id}/publish", response_model=InstallationResponse)
def publish_installation(
    install_id: UUID,
    user: UserProfileResponse = Depends(require_permission(Permission.TEMPLATES_MANAGE)),
    service: MarketplaceService = Depends(get_marketplace_service),
):
    return service.publish_installation(UUID(str(user.company_id)), install_id)


@router.post("/installations/{install_id}/update", response_model=InstallationResponse)
def update_installation(
    install_id: UUID,
    version: Optional[str] = Query(default=None),
    user: UserProfileResponse = Depends(require_permission(Permission.TEMPLATES_MANAGE)),
    service: MarketplaceService = Depends(get_marketplace_service),
):
    return service.update_installation(UUID(str(user.company_id)), install_id, version)


@router.post("/installations/{install_id}/rollback", response_model=InstallationResponse)
def rollback_installation(
    install_id: UUID,
    user: UserProfileResponse = Depends(require_permission(Permission.TEMPLATES_MANAGE)),
    service: MarketplaceService = Depends(get_marketplace_service),
):
    return service.rollback_installation(UUID(str(user.company_id)), install_id)


@router.delete("/installations/{install_id}", status_code=status.HTTP_200_OK)
def uninstall_template(
    install_id: UUID,
    user: UserProfileResponse = Depends(require_permission(Permission.TEMPLATES_MANAGE)),
    service: MarketplaceService = Depends(get_marketplace_service),
):
    return service.uninstall(UUID(str(user.company_id)), install_id)


# ── Registry admin (platform / manage) ────────────────────────────────────────

@router.get("/admin/templates", response_model=TemplateListPage)
def admin_list_templates(
    q: Optional[str] = Query(default=None),
    category: Optional[str] = Query(default=None),
    kind: Optional[str] = Query(default=None),
    pricing_tier: Optional[str] = Query(default=None),
    status_filter: Optional[str] = Query(
        default="all",
        alias="status",
        description="draft | published | archived | all",
    ),
    sort: Optional[str] = Query(default="updated"),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    user: UserProfileResponse = Depends(require_permission(Permission.TEMPLATES_MANAGE)),
    service: MarketplaceService = Depends(get_marketplace_service),
):
    """Registry view — includes draft/archived (not limited to public published)."""
    return service.list_templates(
        UUID(str(user.company_id)),
        q=q,
        category=category,
        kind=kind,
        pricing_tier=pricing_tier,
        status=status_filter,
        is_public=None,
        sort=sort,
        limit=limit,
        offset=offset,
    )


@router.post(
    "/templates",
    response_model=TemplateResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_template(
    payload: TemplateCreate,
    user: UserProfileResponse = Depends(require_permission(Permission.TEMPLATES_MANAGE)),
    service: MarketplaceService = Depends(get_marketplace_service),
):
    return service.create_template(payload)


@router.patch("/templates/{template_id}", response_model=TemplateResponse)
@router.put("/templates/{template_id}", response_model=TemplateResponse)
def update_template(
    template_id: UUID,
    payload: TemplateUpdate,
    user: UserProfileResponse = Depends(require_permission(Permission.TEMPLATES_MANAGE)),
    service: MarketplaceService = Depends(get_marketplace_service),
):
    return service.update_template(template_id, payload)


@router.delete("/templates/{template_id}", response_model=TemplateResponse)
def delete_template(
    template_id: UUID,
    user: UserProfileResponse = Depends(require_permission(Permission.TEMPLATES_MANAGE)),
    service: MarketplaceService = Depends(get_marketplace_service),
):
    """Soft-delete (archive) — preserves installation FK history."""
    return service.archive_template(template_id)


@router.post("/templates/{template_id}/publish", response_model=TemplateResponse)
def publish_catalog_template(
    template_id: UUID,
    user: UserProfileResponse = Depends(require_permission(Permission.TEMPLATES_MANAGE)),
    service: MarketplaceService = Depends(get_marketplace_service),
):
    return service.publish_template(template_id)


@router.post(
    "/templates/{template_id}/versions",
    response_model=TemplateVersionResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_version(
    template_id: UUID,
    payload: TemplateVersionCreate,
    user: UserProfileResponse = Depends(require_permission(Permission.TEMPLATES_MANAGE)),
    service: MarketplaceService = Depends(get_marketplace_service),
):
    return service.add_version(template_id, payload)


@router.patch(
    "/templates/{template_id_or_slug}/versions/{version_ref}",
    response_model=TemplateVersionResponse,
)
def update_version(
    template_id_or_slug: str,
    version_ref: str,
    payload: TemplateVersionUpdate,
    user: UserProfileResponse = Depends(require_permission(Permission.TEMPLATES_MANAGE)),
    service: MarketplaceService = Depends(get_marketplace_service),
):
    """Edit release notes / config; pass set_latest=true to promote."""
    return service.update_version(template_id_or_slug, version_ref, payload)


@router.post(
    "/templates/{template_id_or_slug}/versions/{version_ref}/promote",
    response_model=TemplateVersionResponse,
)
def promote_version(
    template_id_or_slug: str,
    version_ref: str,
    user: UserProfileResponse = Depends(require_permission(Permission.TEMPLATES_MANAGE)),
    service: MarketplaceService = Depends(get_marketplace_service),
):
    """Mark an existing version as the latest catalog release."""
    return service.promote_version(template_id_or_slug, version_ref)
