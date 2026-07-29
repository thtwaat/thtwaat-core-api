"""Domain Manager FastAPI router — /api/v1/domains."""
from __future__ import annotations

from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.auth.router import get_current_user
from app.auth.schema import UserProfileResponse
from app.database.database import get_db
from app.domains.schemas import (
    DomainCreate,
    DomainDashboardResponse,
    DomainResponse,
    DomainUpdate,
    DomainVerifyResponse,
    SslRequestResponse,
)
from app.domains.service import DomainService
from app.rbac.dependencies import RequirePermission
from app.rbac.enums import Permission

router = APIRouter(prefix="/domains", tags=["Domain Manager"])


def get_domain_service(db: Session = Depends(get_db)) -> DomainService:
    return DomainService(db)


def require_permission(permission: Permission):
    def _check(user: UserProfileResponse = Depends(get_current_user)):
        RequirePermission(permission)(user.role)
        return user

    return _check


@router.get(
    "/dashboard",
    response_model=DomainDashboardResponse,
    summary="Domain dashboard (status, DNS, SSL, origins)",
)
def domain_dashboard(
    user: UserProfileResponse = Depends(require_permission(Permission.DOMAINS_READ)),
    service: DomainService = Depends(get_domain_service),
):
    return service.dashboard(UUID(str(user.company_id)))


@router.post(
    "/",
    response_model=DomainResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add a custom domain",
)
def create_domain(
    body: DomainCreate,
    user: UserProfileResponse = Depends(require_permission(Permission.DOMAINS_MANAGE)),
    service: DomainService = Depends(get_domain_service),
):
    """
    Register a custom domain for the authenticated company.

    Supported hostnames include: `app.company.com`, `chat.company.com`,
    `ai.company.com`, `company.com`, `www.company.com`.
    Returns DNS records (TXT / CNAME / A / AAAA) and a verification token.
    """
    return service.create(UUID(str(user.company_id)), body, UUID(str(user.id)))


@router.get(
    "/",
    response_model=List[DomainResponse],
    summary="List company domains",
)
def list_domains(
    user: UserProfileResponse = Depends(require_permission(Permission.DOMAINS_READ)),
    service: DomainService = Depends(get_domain_service),
):
    return service.list(UUID(str(user.company_id)))


@router.get(
    "/{domain_id}",
    response_model=DomainResponse,
    summary="Get domain details",
)
def get_domain(
    domain_id: UUID,
    user: UserProfileResponse = Depends(require_permission(Permission.DOMAINS_READ)),
    service: DomainService = Depends(get_domain_service),
):
    return service.get(domain_id, UUID(str(user.company_id)))


@router.patch(
    "/{domain_id}",
    response_model=DomainResponse,
    summary="Update domain binding (agent / widget / primary)",
)
def update_domain(
    domain_id: UUID,
    body: DomainUpdate,
    user: UserProfileResponse = Depends(require_permission(Permission.DOMAINS_MANAGE)),
    service: DomainService = Depends(get_domain_service),
):
    return service.update(domain_id, UUID(str(user.company_id)), body, UUID(str(user.id)))


@router.delete(
    "/{domain_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a domain",
)
def delete_domain(
    domain_id: UUID,
    user: UserProfileResponse = Depends(require_permission(Permission.DOMAINS_MANAGE)),
    service: DomainService = Depends(get_domain_service),
):
    service.delete(domain_id, UUID(str(user.company_id)), UUID(str(user.id)))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/{domain_id}/dns",
    summary="Copy DNS instructions",
)
def get_dns_records(
    domain_id: UUID,
    user: UserProfileResponse = Depends(require_permission(Permission.DOMAINS_READ)),
    service: DomainService = Depends(get_domain_service),
):
    return {"domain_id": str(domain_id), "records": service.dns_instructions(domain_id, UUID(str(user.company_id)))}


@router.post(
    "/{domain_id}/verify",
    response_model=DomainVerifyResponse,
    summary="Verify domain ownership (TXT / CNAME)",
)
def verify_domain(
    domain_id: UUID,
    user: UserProfileResponse = Depends(require_permission(Permission.DOMAINS_MANAGE)),
    service: DomainService = Depends(get_domain_service),
):
    return service.verify(domain_id, UUID(str(user.company_id)), UUID(str(user.id)))


@router.post(
    "/{domain_id}/retry",
    response_model=DomainVerifyResponse,
    summary="Retry domain verification",
)
def retry_verification(
    domain_id: UUID,
    user: UserProfileResponse = Depends(require_permission(Permission.DOMAINS_MANAGE)),
    service: DomainService = Depends(get_domain_service),
):
    return service.retry_verification(domain_id, UUID(str(user.company_id)), UUID(str(user.id)))


@router.post(
    "/{domain_id}/ssl/request",
    response_model=SslRequestResponse,
    summary="Request Let's Encrypt SSL (HTTP-01) and generate nginx vhost",
)
def request_ssl(
    domain_id: UUID,
    user: UserProfileResponse = Depends(require_permission(Permission.DOMAINS_MANAGE)),
    service: DomainService = Depends(get_domain_service),
):
    return service.request_ssl(domain_id, UUID(str(user.company_id)), UUID(str(user.id)))


@router.post(
    "/{domain_id}/ssl/renew",
    summary="Renew SSL certificate",
)
def renew_ssl(
    domain_id: UUID,
    user: UserProfileResponse = Depends(require_permission(Permission.DOMAINS_MANAGE)),
    service: DomainService = Depends(get_domain_service),
):
    return service.renew_ssl(domain_id, UUID(str(user.company_id)), UUID(str(user.id)))


@router.get(
    "/{domain_id}/ssl/status",
    summary="SSL certificate status + expiry",
)
def ssl_status(
    domain_id: UUID,
    user: UserProfileResponse = Depends(require_permission(Permission.DOMAINS_READ)),
    service: DomainService = Depends(get_domain_service),
):
    return service.ssl_status(domain_id, UUID(str(user.company_id)))


@router.post(
    "/{domain_id}/ssl/issued",
    response_model=DomainResponse,
    summary="[Ops] Mark SSL issued and promote domain to LIVE",
)
def mark_ssl_issued(
    domain_id: UUID,
    user: UserProfileResponse = Depends(require_permission(Permission.DOMAINS_MANAGE)),
    service: DomainService = Depends(get_domain_service),
):
    return service.mark_ssl_issued(domain_id, UUID(str(user.company_id)))
