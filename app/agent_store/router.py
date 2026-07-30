"""AI Agent Marketplace & Store API — /api/v1/agent-store/*."""
from __future__ import annotations

from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.agent_store.schemas import (
    AbuseReportCreate,
    AbuseReportResponse,
    AbuseResolveRequest,
    ListingCreate,
    ListingDetailResponse,
    ListingResponse,
    ListingUpdate,
    ListingVersionCreate,
    ModerateListingRequest,
    PublisherAnalytics,
    PublisherResponse,
    PublisherUpsert,
    ReviewCreate,
    ReviewResponse,
    StoreAdminStats,
    StoreInstallRequest,
    StoreInstallResponse,
    StorefrontResponse,
)
from app.agent_store.service import AgentStoreService
from app.auth.router import get_current_user
from app.auth.schema import UserProfileResponse
from app.database.database import get_db
from app.rbac.dependencies import RequirePermission
from app.rbac.enums import Permission

router = APIRouter(prefix="/agent-store", tags=["AI Agent Store"])


def get_agent_store_service(db: Session = Depends(get_db)) -> AgentStoreService:
    return AgentStoreService(db)


def require_permission(permission: Permission):
    def _check(user: UserProfileResponse = Depends(get_current_user)):
        RequirePermission(permission)(user.role)
        return user

    return _check


# ── Storefront / discovery ────────────────────────────────────────────────────

@router.get("/storefront", response_model=StorefrontResponse)
def storefront(
    user: UserProfileResponse = Depends(require_permission(Permission.TEMPLATES_READ)),
    service: AgentStoreService = Depends(get_agent_store_service),
):
    return service.storefront(UUID(str(user.company_id)))


@router.get("/listings", response_model=List[ListingResponse])
def search_listings(
    q: Optional[str] = Query(default=None),
    category: Optional[str] = Query(default=None),
    pricing_model: Optional[str] = Query(default=None),
    featured: Optional[bool] = Query(default=None),
    verified: Optional[bool] = Query(default=None),
    language: Optional[str] = Query(default=None),
    min_rating: Optional[float] = Query(default=None, ge=0, le=5),
    sort: str = Query(
        default="trending",
        pattern="^(trending|newest|top_rated|most_installed|price_asc|price_desc)$",
    ),
    limit: int = Query(default=50, ge=1, le=100),
    user: UserProfileResponse = Depends(require_permission(Permission.TEMPLATES_READ)),
    service: AgentStoreService = Depends(get_agent_store_service),
):
    return service.search_listings(
        UUID(str(user.company_id)),
        q=q,
        category=category,
        pricing_model=pricing_model,
        featured=featured,
        verified=verified,
        language=language,
        min_rating=min_rating,
        sort=sort,
        limit=limit,
    )


@router.get("/listings/{listing_id_or_slug}", response_model=ListingDetailResponse)
def get_listing(
    listing_id_or_slug: str,
    user: UserProfileResponse = Depends(require_permission(Permission.TEMPLATES_READ)),
    service: AgentStoreService = Depends(get_agent_store_service),
):
    return service.get_listing(listing_id_or_slug, UUID(str(user.company_id)))


# ── Install lifecycle ─────────────────────────────────────────────────────────

@router.post(
    "/listings/{listing_id_or_slug}/install",
    response_model=StoreInstallResponse,
    status_code=status.HTTP_201_CREATED,
)
def install_listing(
    listing_id_or_slug: str,
    payload: StoreInstallRequest,
    user: UserProfileResponse = Depends(require_permission(Permission.TEMPLATES_MANAGE)),
    service: AgentStoreService = Depends(get_agent_store_service),
):
    return service.install(
        UUID(str(user.company_id)),
        UUID(str(user.id)),
        listing_id_or_slug,
        payload,
    )


@router.get("/installed")
def list_installed(
    user: UserProfileResponse = Depends(require_permission(Permission.TEMPLATES_READ)),
    service: AgentStoreService = Depends(get_agent_store_service),
):
    return service.list_installed(UUID(str(user.company_id)))


@router.post("/installations/{installation_id}/update")
def update_installation(
    installation_id: UUID,
    version: Optional[str] = Query(default=None),
    user: UserProfileResponse = Depends(require_permission(Permission.TEMPLATES_MANAGE)),
    service: AgentStoreService = Depends(get_agent_store_service),
):
    return service.update_install(UUID(str(user.company_id)), installation_id, version)


@router.post("/installations/{installation_id}/rollback")
def rollback_installation(
    installation_id: UUID,
    user: UserProfileResponse = Depends(require_permission(Permission.TEMPLATES_MANAGE)),
    service: AgentStoreService = Depends(get_agent_store_service),
):
    return service.rollback_install(UUID(str(user.company_id)), installation_id)


@router.delete("/installations/{installation_id}")
def uninstall_installation(
    installation_id: UUID,
    user: UserProfileResponse = Depends(require_permission(Permission.TEMPLATES_MANAGE)),
    service: AgentStoreService = Depends(get_agent_store_service),
):
    return service.uninstall(UUID(str(user.company_id)), installation_id)


# ── Reviews / abuse ───────────────────────────────────────────────────────────

@router.post(
    "/listings/{listing_id}/reviews",
    response_model=ReviewResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_review(
    listing_id: UUID,
    payload: ReviewCreate,
    user: UserProfileResponse = Depends(require_permission(Permission.TEMPLATES_READ)),
    service: AgentStoreService = Depends(get_agent_store_service),
):
    return service.add_review(
        UUID(str(user.company_id)),
        UUID(str(user.id)),
        listing_id,
        payload,
    )


@router.post(
    "/listings/{listing_id}/abuse-reports",
    response_model=AbuseReportResponse,
    status_code=status.HTTP_201_CREATED,
)
def report_abuse(
    listing_id: UUID,
    payload: AbuseReportCreate,
    user: UserProfileResponse = Depends(require_permission(Permission.TEMPLATES_READ)),
    service: AgentStoreService = Depends(get_agent_store_service),
):
    return service.report_abuse(
        UUID(str(user.company_id)),
        UUID(str(user.id)),
        listing_id,
        payload,
    )


# ── Publisher portal ──────────────────────────────────────────────────────────

@router.put("/publisher/me", response_model=PublisherResponse)
def upsert_publisher(
    payload: PublisherUpsert,
    user: UserProfileResponse = Depends(require_permission(Permission.TEMPLATES_MANAGE)),
    service: AgentStoreService = Depends(get_agent_store_service),
):
    return service.upsert_publisher(UUID(str(user.company_id)), payload)


@router.get("/publisher/me", response_model=PublisherResponse)
def get_publisher(
    user: UserProfileResponse = Depends(require_permission(Permission.TEMPLATES_READ)),
    service: AgentStoreService = Depends(get_agent_store_service),
):
    return service.get_my_publisher(UUID(str(user.company_id)))


@router.get("/publisher/listings", response_model=List[ListingResponse])
def my_listings(
    user: UserProfileResponse = Depends(require_permission(Permission.TEMPLATES_READ)),
    service: AgentStoreService = Depends(get_agent_store_service),
):
    return service.list_my_listings(UUID(str(user.company_id)))


@router.post(
    "/publisher/listings",
    response_model=ListingResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_listing(
    payload: ListingCreate,
    user: UserProfileResponse = Depends(require_permission(Permission.TEMPLATES_MANAGE)),
    service: AgentStoreService = Depends(get_agent_store_service),
):
    return service.create_listing(
        UUID(str(user.company_id)),
        UUID(str(user.id)),
        payload,
    )


@router.patch("/publisher/listings/{listing_id}", response_model=ListingResponse)
def update_listing(
    listing_id: UUID,
    payload: ListingUpdate,
    user: UserProfileResponse = Depends(require_permission(Permission.TEMPLATES_MANAGE)),
    service: AgentStoreService = Depends(get_agent_store_service),
):
    return service.update_listing(UUID(str(user.company_id)), listing_id, payload)


@router.post("/publisher/listings/{listing_id}/submit", response_model=ListingResponse)
def submit_listing(
    listing_id: UUID,
    user: UserProfileResponse = Depends(require_permission(Permission.TEMPLATES_MANAGE)),
    service: AgentStoreService = Depends(get_agent_store_service),
):
    return service.submit_listing(
        UUID(str(user.company_id)),
        listing_id,
        UUID(str(user.id)),
    )


@router.post("/publisher/listings/{listing_id}/versions", response_model=ListingResponse)
def add_version(
    listing_id: UUID,
    payload: ListingVersionCreate,
    user: UserProfileResponse = Depends(require_permission(Permission.TEMPLATES_MANAGE)),
    service: AgentStoreService = Depends(get_agent_store_service),
):
    return service.add_listing_version(UUID(str(user.company_id)), listing_id, payload)


@router.get("/publisher/analytics", response_model=PublisherAnalytics)
def publisher_analytics(
    user: UserProfileResponse = Depends(require_permission(Permission.TEMPLATES_READ)),
    service: AgentStoreService = Depends(get_agent_store_service),
):
    return service.publisher_analytics(UUID(str(user.company_id)))


# ── Admin ─────────────────────────────────────────────────────────────────────

@router.get("/admin/stats", response_model=StoreAdminStats)
def admin_stats(
    user: UserProfileResponse = Depends(require_permission(Permission.PLATFORM_ADMIN)),
    service: AgentStoreService = Depends(get_agent_store_service),
):
    return service.admin_stats()


@router.get("/admin/pending", response_model=List[ListingResponse])
def admin_pending(
    limit: int = Query(default=50, ge=1, le=200),
    user: UserProfileResponse = Depends(require_permission(Permission.PLATFORM_ADMIN)),
    service: AgentStoreService = Depends(get_agent_store_service),
):
    return service.list_pending_listings(limit=limit)


@router.post("/admin/listings/{listing_id}/moderate", response_model=ListingResponse)
def admin_moderate(
    listing_id: UUID,
    payload: ModerateListingRequest,
    user: UserProfileResponse = Depends(require_permission(Permission.PLATFORM_ADMIN)),
    service: AgentStoreService = Depends(get_agent_store_service),
):
    return service.moderate_listing(UUID(str(user.id)), listing_id, payload)


@router.get("/admin/abuse-reports", response_model=List[AbuseReportResponse])
def admin_abuse_reports(
    status_filter: Optional[str] = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=200),
    user: UserProfileResponse = Depends(require_permission(Permission.PLATFORM_ADMIN)),
    service: AgentStoreService = Depends(get_agent_store_service),
):
    return service.list_abuse_reports(status_filter=status_filter, limit=limit)


@router.post("/admin/abuse-reports/{report_id}/resolve", response_model=AbuseReportResponse)
def admin_resolve_abuse(
    report_id: UUID,
    payload: AbuseResolveRequest,
    user: UserProfileResponse = Depends(require_permission(Permission.PLATFORM_ADMIN)),
    service: AgentStoreService = Depends(get_agent_store_service),
):
    return service.resolve_abuse(report_id, payload)
