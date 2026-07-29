"""Enterprise API — /api/v1/enterprise/*."""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response, status
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.router import get_current_user
from app.auth.schema import TokenResponse, UserProfileResponse
from app.database.database import get_db
from app.enterprise.models import (
    AuditSeverity,
    EnterpriseCustomRole,
    EnterprisePermissionGroup,
    EnterpriseRoleAssignment,
    UnitType,
)
from app.enterprise.middleware import EnterpriseSecurityMiddleware
from app.enterprise.schemas import (
    AuditLogResponse,
    BulkInviteRequest,
    BulkInviteResult,
    ConsentCreate,
    ConsentResponse,
    CustomRoleCreate,
    CustomRoleResponse,
    CustomRoleUpdate,
    EffectivePermissionsResponse,
    EnterpriseDashboardResponse,
    ExportRequest,
    ExportResponse,
    InviteAccept,
    InviteMember,
    InviteResult,
    InvitationResponse,
    MembershipCreate,
    MembershipResponse,
    MemberStatusUpdate,
    OIDCCallbackRequest,
    PermissionGroupCreate,
    PermissionGroupResponse,
    PrivacySettingsUpdate,
    ReportResponse,
    RetentionPolicyCreate,
    RetentionPolicyResponse,
    RoleAssignmentCreate,
    SecurityPolicyResponse,
    SecurityPolicyUpdate,
    SessionResponse,
    SSOConnectionCreate,
    SSOConnectionResponse,
    SSOConnectionUpdate,
    SSOInitiateResponse,
    TrustedDeviceCreate,
    TrustedDeviceResponse,
    UnitCreate,
    UnitResponse,
    UnitUpdate,
)
from app.enterprise.service import EnterpriseService
from app.rbac.enums import EnterpriseRole, Permission
from app.rbac.policy import ROLE_PERMISSIONS
from app.users.model import UserStatus
from app.users.schema import UserListResponse, UserResponse

router = APIRouter(prefix="/enterprise", tags=["Enterprise"])


def get_service(db: Session = Depends(get_db)) -> EnterpriseService:
    return EnterpriseService(db)


def require(permission: Permission):
    def dependency(
        user: UserProfileResponse = Depends(get_current_user),
        db: Session = Depends(get_db),
    ):
        try:
            builtin = EnterpriseRole(user.role)
        except ValueError:
            builtin = None
        if builtin and permission in ROLE_PERMISSIONS.get(builtin, set()):
            return user

        assignments = db.scalars(
            select(EnterpriseRoleAssignment).where(
                EnterpriseRoleAssignment.company_id == user.company_id,
                EnterpriseRoleAssignment.user_id == user.id,
            )
        ).all()
        effective: set[str] = set()
        for assignment in assignments:
            role = db.get(EnterpriseCustomRole, assignment.role_id)
            if not role or not role.is_active:
                continue
            effective.update(role.permissions or [])
            for group_id in role.permission_group_ids or []:
                group = db.get(EnterprisePermissionGroup, UUID(str(group_id)))
                if group:
                    effective.update(group.permissions or [])
        if permission.value not in effective:
            raise HTTPException(
                status_code=403,
                detail=f"You do not have the necessary permission: {permission.value}",
            )
        return user

    return dependency


def _company_id(user: UserProfileResponse) -> UUID:
    return UUID(str(user.company_id))


def _user_id(user: UserProfileResponse) -> UUID:
    return UUID(str(user.id))


# ── Dashboard ────────────────────────────────────────────────────────────────


@router.get("/dashboard", response_model=EnterpriseDashboardResponse)
def dashboard(
    user: UserProfileResponse = Depends(require(Permission.ENTERPRISE_READ)),
    service: EnterpriseService = Depends(get_service),
):
    return service.dashboard(_company_id(user))


# ── Organization hierarchy ──────────────────────────────────────────────────


@router.get("/units", response_model=List[UnitResponse])
def list_units(
    unit_type: Optional[UnitType] = None,
    user: UserProfileResponse = Depends(require(Permission.ENTERPRISE_READ)),
    service: EnterpriseService = Depends(get_service),
):
    return service.list_units(_company_id(user), unit_type)


@router.post("/units", response_model=UnitResponse, status_code=status.HTTP_201_CREATED)
def create_unit(
    body: UnitCreate,
    user: UserProfileResponse = Depends(require(Permission.ENTERPRISE_MANAGE)),
    service: EnterpriseService = Depends(get_service),
):
    return service.create_unit(_company_id(user), _user_id(user), body)


@router.patch("/units/{unit_id}", response_model=UnitResponse)
def update_unit(
    unit_id: UUID,
    body: UnitUpdate,
    user: UserProfileResponse = Depends(require(Permission.ENTERPRISE_MANAGE)),
    service: EnterpriseService = Depends(get_service),
):
    return service.update_unit(_company_id(user), _user_id(user), unit_id, body)


@router.get("/organizations", response_model=List[UnitResponse])
def organizations(
    user: UserProfileResponse = Depends(require(Permission.ENTERPRISE_READ)),
    service: EnterpriseService = Depends(get_service),
):
    return service.list_units(_company_id(user), UnitType.ORGANIZATION)


@router.get("/departments", response_model=List[UnitResponse])
def departments(
    user: UserProfileResponse = Depends(require(Permission.ENTERPRISE_READ)),
    service: EnterpriseService = Depends(get_service),
):
    return service.list_units(_company_id(user), UnitType.DEPARTMENT)


@router.get("/teams", response_model=List[UnitResponse])
def teams(
    user: UserProfileResponse = Depends(require(Permission.ENTERPRISE_READ)),
    service: EnterpriseService = Depends(get_service),
):
    return service.list_units(_company_id(user), UnitType.TEAM)


@router.get("/business-units", response_model=List[UnitResponse])
def business_units(
    user: UserProfileResponse = Depends(require(Permission.ENTERPRISE_READ)),
    service: EnterpriseService = Depends(get_service),
):
    return service.list_units(_company_id(user), UnitType.BUSINESS_UNIT)


@router.post(
    "/units/{unit_id}/members",
    response_model=MembershipResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_unit_member(
    unit_id: UUID,
    body: MembershipCreate,
    user: UserProfileResponse = Depends(require(Permission.ENTERPRISE_MANAGE)),
    service: EnterpriseService = Depends(get_service),
):
    return service.add_membership(_company_id(user), _user_id(user), unit_id, body)


@router.delete("/units/{unit_id}/members/{member_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_unit_member(
    unit_id: UUID,
    member_id: UUID,
    user: UserProfileResponse = Depends(require(Permission.ENTERPRISE_MANAGE)),
    service: EnterpriseService = Depends(get_service),
):
    service.remove_membership(_company_id(user), _user_id(user), unit_id, member_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ── Members / invitations ────────────────────────────────────────────────────


@router.get("/members", response_model=UserListResponse)
def members(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    member_status: Optional[UserStatus] = None,
    user: UserProfileResponse = Depends(require(Permission.ENTERPRISE_READ)),
    service: EnterpriseService = Depends(get_service),
):
    return service.list_members(_company_id(user), page, page_size, member_status)


@router.post("/members/invite", response_model=InviteResult, status_code=status.HTTP_201_CREATED)
def invite_member(
    body: InviteMember,
    user: UserProfileResponse = Depends(require(Permission.ENTERPRISE_MANAGE)),
    service: EnterpriseService = Depends(get_service),
):
    return service.invite_member(_company_id(user), _user_id(user), body)


@router.post("/members/bulk-invite", response_model=BulkInviteResult)
def bulk_invite(
    body: BulkInviteRequest,
    user: UserProfileResponse = Depends(require(Permission.ENTERPRISE_MANAGE)),
    service: EnterpriseService = Depends(get_service),
):
    return service.bulk_invite(_company_id(user), _user_id(user), body)


@router.get("/invitations", response_model=List[InvitationResponse])
def invitations(
    user: UserProfileResponse = Depends(require(Permission.ENTERPRISE_READ)),
    service: EnterpriseService = Depends(get_service),
):
    return service.list_invitations(_company_id(user))


@router.post("/invitations/accept", response_model=UserResponse)
def accept_invitation(
    body: InviteAccept,
    service: EnterpriseService = Depends(get_service),
):
    return service.accept_invitation(body)


@router.delete("/invitations/{invitation_id}", response_model=InvitationResponse)
def revoke_invitation(
    invitation_id: UUID,
    user: UserProfileResponse = Depends(require(Permission.ENTERPRISE_MANAGE)),
    service: EnterpriseService = Depends(get_service),
):
    return service.revoke_invitation(_company_id(user), _user_id(user), invitation_id)


@router.patch("/members/{member_id}/status", response_model=UserResponse)
def update_member_status(
    member_id: UUID,
    body: MemberStatusUpdate,
    user: UserProfileResponse = Depends(require(Permission.ENTERPRISE_MANAGE)),
    service: EnterpriseService = Depends(get_service),
):
    return service.update_member_status(
        _company_id(user), _user_id(user), member_id, body.status
    )


# ── Fine-grained RBAC ────────────────────────────────────────────────────────


@router.get("/rbac/permissions")
def permissions(
    user: UserProfileResponse = Depends(require(Permission.ENTERPRISE_READ)),
):
    return [{"value": permission.value, "name": permission.name} for permission in Permission]


@router.get("/rbac/role-templates")
def role_templates(
    user: UserProfileResponse = Depends(require(Permission.ENTERPRISE_READ)),
):
    return EnterpriseService.role_templates()


@router.get("/rbac/permission-groups", response_model=List[PermissionGroupResponse])
def permission_groups(
    user: UserProfileResponse = Depends(require(Permission.ENTERPRISE_READ)),
    service: EnterpriseService = Depends(get_service),
):
    return service.list_permission_groups(_company_id(user))


@router.post(
    "/rbac/permission-groups",
    response_model=PermissionGroupResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_permission_group(
    body: PermissionGroupCreate,
    user: UserProfileResponse = Depends(require(Permission.ENTERPRISE_MANAGE)),
    service: EnterpriseService = Depends(get_service),
):
    return service.create_permission_group(_company_id(user), _user_id(user), body)


@router.get("/rbac/roles", response_model=List[CustomRoleResponse])
def roles(
    user: UserProfileResponse = Depends(require(Permission.ENTERPRISE_READ)),
    service: EnterpriseService = Depends(get_service),
):
    return service.list_roles(_company_id(user))


@router.post("/rbac/roles", response_model=CustomRoleResponse, status_code=status.HTTP_201_CREATED)
def create_role(
    body: CustomRoleCreate,
    user: UserProfileResponse = Depends(require(Permission.ENTERPRISE_MANAGE)),
    service: EnterpriseService = Depends(get_service),
):
    return service.create_role(_company_id(user), _user_id(user), body)


@router.patch("/rbac/roles/{role_id}", response_model=CustomRoleResponse)
def update_role(
    role_id: UUID,
    body: CustomRoleUpdate,
    user: UserProfileResponse = Depends(require(Permission.ENTERPRISE_MANAGE)),
    service: EnterpriseService = Depends(get_service),
):
    return service.update_role(_company_id(user), _user_id(user), role_id, body)


@router.post("/rbac/assignments", status_code=status.HTTP_201_CREATED)
def assign_role(
    body: RoleAssignmentCreate,
    user: UserProfileResponse = Depends(require(Permission.ENTERPRISE_MANAGE)),
    service: EnterpriseService = Depends(get_service),
):
    row = service.assign_role(_company_id(user), _user_id(user), body)
    return {
        "id": row.id,
        "user_id": row.user_id,
        "role_id": row.role_id,
        "unit_id": row.unit_id,
    }


@router.get("/rbac/effective/{member_id}", response_model=EffectivePermissionsResponse)
def effective_permissions(
    member_id: UUID,
    user: UserProfileResponse = Depends(require(Permission.ENTERPRISE_READ)),
    service: EnterpriseService = Depends(get_service),
):
    return service.effective_permissions(_company_id(user), member_id)


# ── SSO ──────────────────────────────────────────────────────────────────────


@router.get("/sso/connections", response_model=List[SSOConnectionResponse])
def sso_connections(
    user: UserProfileResponse = Depends(require(Permission.ENTERPRISE_SECURITY)),
    service: EnterpriseService = Depends(get_service),
):
    return service.list_sso(_company_id(user))


@router.post(
    "/sso/connections",
    response_model=SSOConnectionResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_sso(
    body: SSOConnectionCreate,
    user: UserProfileResponse = Depends(require(Permission.ENTERPRISE_SECURITY)),
    service: EnterpriseService = Depends(get_service),
):
    return service.create_sso(_company_id(user), _user_id(user), body)


@router.patch("/sso/connections/{connection_id}", response_model=SSOConnectionResponse)
def update_sso(
    connection_id: UUID,
    body: SSOConnectionUpdate,
    user: UserProfileResponse = Depends(require(Permission.ENTERPRISE_SECURITY)),
    service: EnterpriseService = Depends(get_service),
):
    return service.update_sso(_company_id(user), _user_id(user), connection_id, body)


@router.post("/sso/oidc/callback", response_model=TokenResponse)
async def oidc_callback(
    body: OIDCCallbackRequest,
    service: EnterpriseService = Depends(get_service),
):
    return await service.complete_oidc(body)


@router.get("/sso/{connection_id}/initiate", response_model=SSOInitiateResponse)
def initiate_sso(
    connection_id: UUID,
    redirect_uri: str = Query(...),
    service: EnterpriseService = Depends(get_service),
):
    return service.initiate_sso(connection_id, redirect_uri)


# ── Security ─────────────────────────────────────────────────────────────────


@router.get("/security/policy", response_model=SecurityPolicyResponse)
def security_policy(
    user: UserProfileResponse = Depends(require(Permission.ENTERPRISE_SECURITY)),
    service: EnterpriseService = Depends(get_service),
):
    return service.get_security_policy(_company_id(user))


@router.patch("/security/policy", response_model=SecurityPolicyResponse)
def update_security_policy(
    body: SecurityPolicyUpdate,
    user: UserProfileResponse = Depends(require(Permission.ENTERPRISE_SECURITY)),
    service: EnterpriseService = Depends(get_service),
):
    return service.update_security_policy(_company_id(user), _user_id(user), body)


@router.get("/security/sessions", response_model=List[SessionResponse])
def sessions(
    member_id: Optional[UUID] = None,
    user: UserProfileResponse = Depends(require(Permission.ENTERPRISE_SECURITY)),
    service: EnterpriseService = Depends(get_service),
):
    return [
        SessionResponse(
            id=row.id,
            user_id=row.user_id,
            created_at=row.created_at,
            expires_at=row.expires_at,
            revoked_at=row.revoked_at,
        )
        for row in service.list_sessions(_company_id(user), member_id)
    ]


@router.delete("/security/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_session(
    session_id: UUID,
    user: UserProfileResponse = Depends(require(Permission.ENTERPRISE_SECURITY)),
    service: EnterpriseService = Depends(get_service),
):
    service.revoke_session(_company_id(user), _user_id(user), session_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/security/mfa")
def mfa_posture(
    user: UserProfileResponse = Depends(require(Permission.ENTERPRISE_SECURITY)),
    service: EnterpriseService = Depends(get_service),
):
    report = service.report(_company_id(user), "security")
    return {
        "policy": report.data["policy"],
        "setup_endpoint": "/api/v1/auth/mfa/setup",
        "enable_endpoint": "/api/v1/auth/mfa/enable",
        "verify_endpoint": "/api/v1/auth/mfa/verify",
    }


@router.get(
    "/security/trusted-devices/{member_id}", response_model=List[TrustedDeviceResponse]
)
def trusted_devices(
    member_id: UUID,
    user: UserProfileResponse = Depends(require(Permission.ENTERPRISE_SECURITY)),
    service: EnterpriseService = Depends(get_service),
):
    return service.list_trusted_devices(_company_id(user), member_id)


@router.post(
    "/security/trusted-devices",
    response_model=TrustedDeviceResponse,
    status_code=status.HTTP_201_CREATED,
)
def register_trusted_device(
    body: TrustedDeviceCreate,
    request: Request,
    user: UserProfileResponse = Depends(get_current_user),
    service: EnterpriseService = Depends(get_service),
):
    return service.register_trusted_device(
        _company_id(user),
        _user_id(user),
        body,
        EnterpriseSecurityMiddleware._client_ip(request),
    )


@router.delete(
    "/security/trusted-devices/{device_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def revoke_trusted_device(
    device_id: UUID,
    user: UserProfileResponse = Depends(require(Permission.ENTERPRISE_SECURITY)),
    service: EnterpriseService = Depends(get_service),
):
    service.revoke_trusted_device(_company_id(user), _user_id(user), device_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ── Audit ────────────────────────────────────────────────────────────────────


@router.get("/audit/logs", response_model=List[AuditLogResponse])
def audit_logs(
    action: Optional[str] = None,
    actor_user_id: Optional[UUID] = None,
    severity: Optional[AuditSeverity] = None,
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    user: UserProfileResponse = Depends(require(Permission.ENTERPRISE_AUDIT)),
    service: EnterpriseService = Depends(get_service),
):
    return service.list_audit_logs(
        _company_id(user),
        action=action,
        actor_user_id=actor_user_id,
        severity=severity,
        start=start,
        end=end,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/audit/timeline/{resource_type}/{resource_id}", response_model=List[AuditLogResponse]
)
def activity_timeline(
    resource_type: str,
    resource_id: str,
    user: UserProfileResponse = Depends(require(Permission.ENTERPRISE_AUDIT)),
    service: EnterpriseService = Depends(get_service),
):
    return service.activity_timeline(_company_id(user), resource_type, resource_id)


# ── Compliance ───────────────────────────────────────────────────────────────


@router.get("/compliance/retention", response_model=List[RetentionPolicyResponse])
def retention_policies(
    user: UserProfileResponse = Depends(require(Permission.ENTERPRISE_COMPLIANCE)),
    service: EnterpriseService = Depends(get_service),
):
    return service.list_retention(_company_id(user))


@router.put("/compliance/retention", response_model=RetentionPolicyResponse)
def upsert_retention(
    body: RetentionPolicyCreate,
    user: UserProfileResponse = Depends(require(Permission.ENTERPRISE_COMPLIANCE)),
    service: EnterpriseService = Depends(get_service),
):
    return service.upsert_retention(_company_id(user), _user_id(user), body)


@router.post("/compliance/retention/apply")
def apply_retention(
    user: UserProfileResponse = Depends(require(Permission.ENTERPRISE_COMPLIANCE)),
    service: EnterpriseService = Depends(get_service),
):
    result = service.apply_retention_policies(_company_id(user))
    service.audit(
        _company_id(user),
        _user_id(user),
        "enterprise.retention.applied",
        "retention_policy",
        metadata=result,
    )
    return result


@router.get("/compliance/privacy")
def privacy_settings(
    user: UserProfileResponse = Depends(require(Permission.ENTERPRISE_COMPLIANCE)),
    service: EnterpriseService = Depends(get_service),
):
    return service.privacy_settings(_company_id(user))


@router.patch("/compliance/privacy")
def update_privacy_settings(
    body: PrivacySettingsUpdate,
    user: UserProfileResponse = Depends(require(Permission.ENTERPRISE_COMPLIANCE)),
    service: EnterpriseService = Depends(get_service),
):
    result = service.privacy_settings(_company_id(user), body)
    service.audit(
        _company_id(user),
        _user_id(user),
        "enterprise.privacy.updated",
        "company_privacy_settings",
        str(user.company_id),
        after=result,
    )
    return result


@router.post(
    "/compliance/consents",
    response_model=ConsentResponse,
    status_code=status.HTTP_201_CREATED,
)
def record_consent(
    body: ConsentCreate,
    request: Request,
    user: UserProfileResponse = Depends(get_current_user),
    service: EnterpriseService = Depends(get_service),
):
    return service.record_consent(
        _company_id(user), body, EnterpriseSecurityMiddleware._client_ip(request)
    )


@router.get("/compliance/consents", response_model=List[ConsentResponse])
def consent_logs(
    subject_id: Optional[str] = None,
    user: UserProfileResponse = Depends(require(Permission.ENTERPRISE_COMPLIANCE)),
    service: EnterpriseService = Depends(get_service),
):
    return service.list_consents(_company_id(user), subject_id)


# ── Reports / exports ────────────────────────────────────────────────────────


@router.get("/reports/{report_type}", response_model=ReportResponse)
def report(
    report_type: str,
    user: UserProfileResponse = Depends(require(Permission.ENTERPRISE_REPORTS)),
    service: EnterpriseService = Depends(get_service),
):
    return service.report(_company_id(user), report_type)


@router.post("/exports", response_model=ExportResponse, status_code=status.HTTP_201_CREATED)
async def create_export(
    body: ExportRequest,
    user: UserProfileResponse = Depends(require(Permission.ENTERPRISE_REPORTS)),
    service: EnterpriseService = Depends(get_service),
):
    return await service.create_export(_company_id(user), _user_id(user), body)


@router.get("/exports", response_model=List[ExportResponse])
def exports(
    user: UserProfileResponse = Depends(require(Permission.ENTERPRISE_REPORTS)),
    service: EnterpriseService = Depends(get_service),
):
    return service.list_exports(_company_id(user))
