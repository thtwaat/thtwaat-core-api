"""Enterprise orchestration service; delegates platform business operations."""
from __future__ import annotations

import base64
import csv
import hashlib
import io
import json
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Dict, Iterable, List, Optional
from urllib.parse import urlencode

import httpx
from cryptography.fernet import Fernet
from fastapi import HTTPException
from jose import JWTError, jwt
from sqlalchemy import delete, func, inspect, select, update
from sqlalchemy.orm import Session
from starlette.datastructures import Headers, UploadFile

from app.auth.model import MFASettings, RefreshToken
from app.auth.repository import AuthRepository
from app.branding.service import BrandingService
from app.companies.repository import CompanyRepository
from app.config.settings import settings
from app.enterprise.models import (
    AuditSeverity,
    EnterpriseAuditLog,
    EnterpriseConsentLog,
    EnterpriseCustomRole,
    EnterpriseExportJob,
    EnterpriseInvitation,
    EnterprisePermissionGroup,
    EnterpriseRetentionPolicy,
    EnterpriseRoleAssignment,
    EnterpriseSecurityPolicy,
    EnterpriseSSOConnection,
    EnterpriseTrustedDevice,
    EnterpriseUnit,
    EnterpriseUnitMembership,
    ExportStatus,
    InvitationStatus,
    SSOProvider,
    UnitType,
)
from app.enterprise.schemas import (
    BulkInviteRequest,
    BulkInviteResult,
    ConsentCreate,
    CustomRoleCreate,
    CustomRoleUpdate,
    EffectivePermissionsResponse,
    EnterpriseDashboardResponse,
    ExportRequest,
    InviteAccept,
    InviteMember,
    InviteResult,
    MembershipCreate,
    OIDCCallbackRequest,
    PermissionGroupCreate,
    PrivacySettingsUpdate,
    ReportResponse,
    RetentionPolicyCreate,
    RoleAssignmentCreate,
    SecurityPolicyUpdate,
    SSOConnectionCreate,
    SSOConnectionUpdate,
    SSOInitiateResponse,
    TrustedDeviceCreate,
    UnitCreate,
    UnitUpdate,
)
from app.marketplace.service import MarketplaceService
from app.payments.invoices.service import InvoiceService
from app.payments.subscriptions.service import SubscriptionService
from app.rbac.enums import EnterpriseRole, Permission
from app.rbac.policy import ROLE_PERMISSIONS
from app.storage.service import StorageService
from app.usage.service import UsageService
from app.users.model import User, UserStatus
from app.users.repository import UserRepository
from app.users.schema import UserCreate, UserUpdate
from app.users.service import UserService


ROLE_TEMPLATES: Dict[str, List[str]] = {
    "organization_admin": [
        Permission.ENTERPRISE_READ.value,
        Permission.ENTERPRISE_MANAGE.value,
        Permission.ENTERPRISE_SECURITY.value,
        Permission.ENTERPRISE_AUDIT.value,
        Permission.ENTERPRISE_COMPLIANCE.value,
        Permission.ENTERPRISE_REPORTS.value,
    ],
    "security_admin": [
        Permission.ENTERPRISE_READ.value,
        Permission.ENTERPRISE_SECURITY.value,
        Permission.ENTERPRISE_AUDIT.value,
    ],
    "compliance_manager": [
        Permission.ENTERPRISE_READ.value,
        Permission.ENTERPRISE_AUDIT.value,
        Permission.ENTERPRISE_COMPLIANCE.value,
        Permission.ENTERPRISE_REPORTS.value,
    ],
    "billing_analyst": [
        Permission.ENTERPRISE_READ.value,
        Permission.ENTERPRISE_REPORTS.value,
    ],
    "team_manager": [
        Permission.ENTERPRISE_READ.value,
        Permission.USERS_READ.value,
        Permission.USERS_UPDATE.value,
    ],
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _enum_value(value: Any) -> Any:
    return value.value if hasattr(value, "value") else value


def _jsonable(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    if isinstance(value, (datetime, uuid.UUID)):
        return str(value)
    if isinstance(value, Decimal):
        return float(value)
    if hasattr(value, "value"):
        return value.value
    if hasattr(value, "__table__"):
        return {
            attribute.key: _jsonable(getattr(value, attribute.key))
            for attribute in inspect(value).mapper.column_attrs
        }
    return value


class EnterpriseService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.companies = CompanyRepository(db)
        self.users = UserRepository(db)
        self.user_service = UserService(db)
        self.auth = AuthRepository(db)
        self.usage = UsageService(db)
        self.invoices = InvoiceService(db)
        self.subscriptions = SubscriptionService(db)
        self.branding = BrandingService(db)
        self.marketplace = MarketplaceService(db)
        self.storage = StorageService(db)

    # ── Common guards / audit ────────────────────────────────────────────────

    def _company(self, company_id: uuid.UUID):
        company = self.companies.get_by_id(company_id)
        if not company:
            raise HTTPException(status_code=404, detail="Company not found")
        return company

    def _owned(self, model, row_id: uuid.UUID, company_id: uuid.UUID):
        row = self.db.get(model, row_id)
        if not row or row.company_id != company_id:
            raise HTTPException(status_code=404, detail=f"{model.__name__} not found")
        return row

    def _user(self, user_id: uuid.UUID, company_id: uuid.UUID) -> User:
        user = self.users.get_by_id(user_id)
        if not user or user.company_id != company_id:
            raise HTTPException(status_code=404, detail="Member not found")
        return user

    def audit(
        self,
        company_id: uuid.UUID,
        actor_user_id: Optional[uuid.UUID],
        action: str,
        resource_type: str,
        resource_id: Optional[str] = None,
        *,
        severity: AuditSeverity = AuditSeverity.INFO,
        before: Optional[Dict[str, Any]] = None,
        after: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        request_id: Optional[str] = None,
        commit: bool = True,
    ) -> EnterpriseAuditLog:
        row = EnterpriseAuditLog(
            company_id=company_id,
            actor_user_id=actor_user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            severity=severity,
            ip_address=ip_address,
            user_agent=user_agent,
            request_id=request_id,
            before=_jsonable(before),
            after=_jsonable(after),
            metadata_=metadata or {},
            created_at=_now(),
        )
        self.db.add(row)
        if commit:
            self.db.commit()
            self.db.refresh(row)
        return row

    # ── Organization hierarchy ───────────────────────────────────────────────

    def list_units(
        self, company_id: uuid.UUID, unit_type: Optional[UnitType] = None
    ) -> List[EnterpriseUnit]:
        stmt = select(EnterpriseUnit).where(EnterpriseUnit.company_id == company_id)
        if unit_type:
            stmt = stmt.where(EnterpriseUnit.unit_type == unit_type)
        return list(self.db.scalars(stmt.order_by(EnterpriseUnit.name)).all())

    def create_unit(
        self, company_id: uuid.UUID, actor_id: uuid.UUID, body: UnitCreate
    ) -> EnterpriseUnit:
        self._company(company_id)
        if body.parent_id:
            parent = self._owned(EnterpriseUnit, body.parent_id, company_id)
            if body.unit_type == UnitType.ORGANIZATION:
                raise HTTPException(status_code=422, detail="Organizations cannot have a parent")
            if parent.unit_type == UnitType.TEAM:
                raise HTTPException(status_code=422, detail="A team cannot contain child units")
        elif body.unit_type != UnitType.ORGANIZATION:
            raise HTTPException(status_code=422, detail="Non-organization units require a parent")

        row = EnterpriseUnit(
            company_id=company_id,
            parent_id=body.parent_id,
            unit_type=body.unit_type,
            name=body.name,
            slug=body.slug,
            description=body.description,
            manager_user_id=body.manager_user_id,
            cost_center=body.cost_center,
            metadata_=body.metadata,
        )
        self.db.add(row)
        self.db.flush()
        self.audit(
            company_id,
            actor_id,
            "enterprise.unit.created",
            "enterprise_unit",
            str(row.id),
            after=body.model_dump(mode="json"),
            commit=False,
        )
        self.db.commit()
        self.db.refresh(row)
        return row

    def update_unit(
        self, company_id: uuid.UUID, actor_id: uuid.UUID, unit_id: uuid.UUID, body: UnitUpdate
    ) -> EnterpriseUnit:
        row = self._owned(EnterpriseUnit, unit_id, company_id)
        before = {
            "name": row.name,
            "parent_id": str(row.parent_id) if row.parent_id else None,
            "is_active": row.is_active,
        }
        changes = body.model_dump(exclude_unset=True)
        if "parent_id" in changes and changes["parent_id"]:
            if changes["parent_id"] == unit_id:
                raise HTTPException(status_code=422, detail="A unit cannot be its own parent")
            self._owned(EnterpriseUnit, changes["parent_id"], company_id)
        if "metadata" in changes:
            changes["metadata_"] = changes.pop("metadata")
        for key, value in changes.items():
            setattr(row, key, value)
        self.audit(
            company_id,
            actor_id,
            "enterprise.unit.updated",
            "enterprise_unit",
            str(row.id),
            before=before,
            after=body.model_dump(exclude_unset=True, mode="json"),
            commit=False,
        )
        self.db.commit()
        self.db.refresh(row)
        return row

    def add_membership(
        self,
        company_id: uuid.UUID,
        actor_id: uuid.UUID,
        unit_id: uuid.UUID,
        body: MembershipCreate,
    ) -> EnterpriseUnitMembership:
        self._owned(EnterpriseUnit, unit_id, company_id)
        self._user(body.user_id, company_id)
        existing = self.db.scalar(
            select(EnterpriseUnitMembership).where(
                EnterpriseUnitMembership.unit_id == unit_id,
                EnterpriseUnitMembership.user_id == body.user_id,
            )
        )
        if existing:
            raise HTTPException(status_code=409, detail="Member already belongs to unit")
        if body.is_primary:
            for membership in self.db.scalars(
                select(EnterpriseUnitMembership).where(
                    EnterpriseUnitMembership.company_id == company_id,
                    EnterpriseUnitMembership.user_id == body.user_id,
                    EnterpriseUnitMembership.is_primary.is_(True),
                )
            ):
                membership.is_primary = False
        row = EnterpriseUnitMembership(
            company_id=company_id,
            unit_id=unit_id,
            user_id=body.user_id,
            title=body.title,
            is_primary=body.is_primary,
        )
        self.db.add(row)
        self.db.flush()
        self.audit(
            company_id,
            actor_id,
            "enterprise.membership.created",
            "enterprise_unit_membership",
            str(row.id),
            after=body.model_dump(mode="json"),
            commit=False,
        )
        self.db.commit()
        self.db.refresh(row)
        return row

    def remove_membership(
        self, company_id: uuid.UUID, actor_id: uuid.UUID, unit_id: uuid.UUID, user_id: uuid.UUID
    ) -> None:
        row = self.db.scalar(
            select(EnterpriseUnitMembership).where(
                EnterpriseUnitMembership.company_id == company_id,
                EnterpriseUnitMembership.unit_id == unit_id,
                EnterpriseUnitMembership.user_id == user_id,
            )
        )
        if not row:
            raise HTTPException(status_code=404, detail="Membership not found")
        self.db.delete(row)
        self.audit(
            company_id,
            actor_id,
            "enterprise.membership.deleted",
            "enterprise_unit_membership",
            str(row.id),
            commit=False,
        )
        self.db.commit()

    # ── Member invitations / lifecycle (delegates UserService) ───────────────

    def invite_member(
        self, company_id: uuid.UUID, actor_id: uuid.UUID, body: InviteMember
    ) -> InviteResult:
        self._company(company_id)
        if self.users.email_exists_in_company(str(body.email), company_id):
            raise HTTPException(status_code=409, detail="Email is already a company member")
        try:
            EnterpriseRole(body.builtin_role)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="Unknown built-in role") from exc
        if body.custom_role_id:
            self._owned(EnterpriseCustomRole, body.custom_role_id, company_id)
        for unit_id in body.unit_ids:
            self._owned(EnterpriseUnit, unit_id, company_id)

        pending = self.db.scalar(
            select(EnterpriseInvitation).where(
                EnterpriseInvitation.company_id == company_id,
                EnterpriseInvitation.email == str(body.email).lower(),
                EnterpriseInvitation.status == InvitationStatus.PENDING,
                EnterpriseInvitation.expires_at > _now(),
            )
        )
        if pending:
            raise HTTPException(status_code=409, detail="A pending invitation already exists")

        raw_token = secrets.token_urlsafe(48)
        row = EnterpriseInvitation(
            company_id=company_id,
            email=str(body.email).lower(),
            first_name=body.first_name,
            last_name=body.last_name,
            builtin_role=body.builtin_role,
            custom_role_id=body.custom_role_id,
            unit_ids=[str(v) for v in body.unit_ids],
            token_hash=hashlib.sha256(raw_token.encode()).hexdigest(),
            status=InvitationStatus.PENDING,
            invited_by=actor_id,
            expires_at=_now() + timedelta(days=body.expires_in_days),
        )
        self.db.add(row)
        self.db.flush()
        self.audit(
            company_id,
            actor_id,
            "enterprise.invitation.created",
            "enterprise_invitation",
            str(row.id),
            after={"email": row.email, "role": row.builtin_role},
            commit=False,
        )
        self.db.commit()
        self.db.refresh(row)
        try:
            from app.branding.email import render_branded_email
            from app.notifications.model import NotificationChannel
            from app.notifications.schema import SendNotificationRequest
            from app.notifications.service import NotificationService

            company = self._company(company_id)
            invitation_text = (
                f"You were invited to {company.display_name or company.name}. "
                f"Invitation token: {raw_token}"
            )
            branded = render_branded_email(
                self.db,
                company_id,
                "notification",
                {"title": "Organization invitation", "body": invitation_text},
            )
            NotificationService(self.db).send_notification(
                SendNotificationRequest(
                    channel=NotificationChannel.EMAIL,
                    recipient=row.email,
                    subject=f"Invitation to {company.display_name or company.name}",
                    body=branded["body"] or invitation_text,
                    template_name="enterprise.member_invited",
                ),
                company_id,
                actor_id,
            )
        except Exception:
            pass
        try:
            from app.notifications.events import NotificationEventBus

            NotificationEventBus.dispatch(
                "enterprise.member_invited",
                self.db,
                company_id,
                None,
                {"email": row.email, "invitation_id": str(row.id)},
                actor_id,
            )
        except Exception:
            pass
        return InviteResult(invitation=row, invite_token=raw_token)

    def list_members(
        self,
        company_id: uuid.UUID,
        page: int = 1,
        page_size: int = 50,
        status_filter: Optional[UserStatus] = None,
    ):
        return self.user_service.list_users(
            company_id=company_id,
            page=page,
            page_size=page_size,
            status_filter=status_filter,
        )

    def list_invitations(self, company_id: uuid.UUID) -> List[EnterpriseInvitation]:
        return list(
            self.db.scalars(
                select(EnterpriseInvitation)
                .where(EnterpriseInvitation.company_id == company_id)
                .order_by(EnterpriseInvitation.created_at.desc())
                .limit(1000)
            ).all()
        )

    def revoke_invitation(
        self, company_id: uuid.UUID, actor_id: uuid.UUID, invitation_id: uuid.UUID
    ) -> EnterpriseInvitation:
        row = self._owned(EnterpriseInvitation, invitation_id, company_id)
        if row.status != InvitationStatus.PENDING:
            raise HTTPException(status_code=409, detail="Only pending invitations can be revoked")
        row.status = InvitationStatus.REVOKED
        self.audit(
            company_id,
            actor_id,
            "enterprise.invitation.revoked",
            "enterprise_invitation",
            str(row.id),
            commit=False,
        )
        self.db.commit()
        self.db.refresh(row)
        return row

    def bulk_invite(
        self, company_id: uuid.UUID, actor_id: uuid.UUID, body: BulkInviteRequest
    ) -> BulkInviteResult:
        invited: List[InviteResult] = []
        rejected: List[Dict[str, str]] = []
        seen: set[str] = set()
        for member in body.members:
            email = str(member.email).lower()
            if email in seen:
                rejected.append({"email": email, "reason": "Duplicate in request"})
                continue
            seen.add(email)
            try:
                invited.append(self.invite_member(company_id, actor_id, member))
            except HTTPException as exc:
                rejected.append({"email": email, "reason": str(exc.detail)})
        return BulkInviteResult(invited=invited, rejected=rejected)

    def accept_invitation(self, body: InviteAccept):
        digest = hashlib.sha256(body.token.encode()).hexdigest()
        invite = self.db.scalar(
            select(EnterpriseInvitation).where(EnterpriseInvitation.token_hash == digest)
        )
        if not invite or invite.status != InvitationStatus.PENDING:
            raise HTTPException(status_code=400, detail="Invitation is invalid or already used")
        if invite.expires_at <= _now():
            invite.status = InvitationStatus.EXPIRED
            self.db.commit()
            raise HTTPException(status_code=400, detail="Invitation has expired")

        user = self.user_service.create_user(
            UserCreate(
                email=invite.email,
                password=body.password,
                company_id=invite.company_id,
                first_name=invite.first_name,
                last_name=invite.last_name,
                role=EnterpriseRole(invite.builtin_role),
            )
        )
        for unit_id in invite.unit_ids or []:
            unit_uuid = uuid.UUID(str(unit_id))
            if self.db.get(EnterpriseUnit, unit_uuid):
                self.db.add(
                    EnterpriseUnitMembership(
                        company_id=invite.company_id,
                        unit_id=unit_uuid,
                        user_id=user.id,
                        is_primary=False,
                    )
                )
        if invite.custom_role_id:
            self.db.add(
                EnterpriseRoleAssignment(
                    company_id=invite.company_id,
                    user_id=user.id,
                    role_id=invite.custom_role_id,
                    assigned_by=invite.invited_by,
                )
            )
        invite.status = InvitationStatus.ACCEPTED
        invite.accepted_at = _now()
        self.audit(
            invite.company_id,
            user.id,
            "enterprise.invitation.accepted",
            "enterprise_invitation",
            str(invite.id),
            commit=False,
        )
        self.db.commit()
        return user

    def update_member_status(
        self, company_id: uuid.UUID, actor_id: uuid.UUID, user_id: uuid.UUID, status_value: str
    ):
        user = self._user(user_id, company_id)
        before = {"status": _enum_value(user.status), "is_active": user.is_active}
        target = UserStatus(status_value)
        updated = self.user_service.update_user(
            user_id,
            UserUpdate(status=target, is_active=target == UserStatus.ACTIVE),
        )
        if target != UserStatus.ACTIVE:
            self.auth.revoke_all_user_tokens(user_id)
        self.audit(
            company_id,
            actor_id,
            f"enterprise.member.{status_value}",
            "user",
            str(user_id),
            before=before,
            after={"status": status_value, "is_active": target == UserStatus.ACTIVE},
        )
        return updated

    # ── Custom RBAC (extends built-in RBAC) ──────────────────────────────────

    @staticmethod
    def role_templates() -> Dict[str, List[str]]:
        return ROLE_TEMPLATES

    @staticmethod
    def _validate_permissions(permissions: Iterable[str]) -> List[str]:
        valid = {permission.value for permission in Permission}
        requested = list(dict.fromkeys(permissions))
        unknown = sorted(set(requested) - valid)
        if unknown:
            raise HTTPException(status_code=422, detail={"unknown_permissions": unknown})
        return requested

    def list_permission_groups(self, company_id: uuid.UUID) -> List[EnterprisePermissionGroup]:
        return list(
            self.db.scalars(
                select(EnterprisePermissionGroup)
                .where(EnterprisePermissionGroup.company_id == company_id)
                .order_by(EnterprisePermissionGroup.name)
            ).all()
        )

    def create_permission_group(
        self, company_id: uuid.UUID, actor_id: uuid.UUID, body: PermissionGroupCreate
    ) -> EnterprisePermissionGroup:
        row = EnterprisePermissionGroup(
            company_id=company_id,
            name=body.name,
            description=body.description,
            permissions=self._validate_permissions(body.permissions),
        )
        self.db.add(row)
        self.db.flush()
        self.audit(
            company_id,
            actor_id,
            "enterprise.permission_group.created",
            "permission_group",
            str(row.id),
            after=body.model_dump(),
            commit=False,
        )
        self.db.commit()
        self.db.refresh(row)
        return row

    def list_roles(self, company_id: uuid.UUID) -> List[EnterpriseCustomRole]:
        return list(
            self.db.scalars(
                select(EnterpriseCustomRole)
                .where(EnterpriseCustomRole.company_id == company_id)
                .order_by(EnterpriseCustomRole.name)
            ).all()
        )

    def create_role(
        self, company_id: uuid.UUID, actor_id: uuid.UUID, body: CustomRoleCreate
    ) -> EnterpriseCustomRole:
        permissions = list(body.permissions)
        if body.template_key:
            if body.template_key not in ROLE_TEMPLATES:
                raise HTTPException(status_code=422, detail="Unknown role template")
            permissions = list(dict.fromkeys(ROLE_TEMPLATES[body.template_key] + permissions))
        for group_id in body.permission_group_ids:
            self._owned(EnterprisePermissionGroup, group_id, company_id)
        row = EnterpriseCustomRole(
            company_id=company_id,
            name=body.name,
            description=body.description,
            template_key=body.template_key,
            permissions=self._validate_permissions(permissions),
            permission_group_ids=[str(v) for v in body.permission_group_ids],
        )
        self.db.add(row)
        self.db.flush()
        self.audit(
            company_id,
            actor_id,
            "enterprise.role.created",
            "custom_role",
            str(row.id),
            after=body.model_dump(mode="json"),
            commit=False,
        )
        self.db.commit()
        self.db.refresh(row)
        return row

    def update_role(
        self,
        company_id: uuid.UUID,
        actor_id: uuid.UUID,
        role_id: uuid.UUID,
        body: CustomRoleUpdate,
    ) -> EnterpriseCustomRole:
        row = self._owned(EnterpriseCustomRole, role_id, company_id)
        before = {"name": row.name, "permissions": row.permissions}
        changes = body.model_dump(exclude_unset=True)
        if "permissions" in changes:
            changes["permissions"] = self._validate_permissions(changes["permissions"])
        if "permission_group_ids" in changes:
            for group_id in changes["permission_group_ids"]:
                self._owned(EnterprisePermissionGroup, group_id, company_id)
            changes["permission_group_ids"] = [str(v) for v in changes["permission_group_ids"]]
        for key, value in changes.items():
            setattr(row, key, value)
        self.audit(
            company_id,
            actor_id,
            "enterprise.role.updated",
            "custom_role",
            str(row.id),
            before=before,
            after=body.model_dump(exclude_unset=True, mode="json"),
            commit=False,
        )
        self.db.commit()
        self.db.refresh(row)
        return row

    def assign_role(
        self, company_id: uuid.UUID, actor_id: uuid.UUID, body: RoleAssignmentCreate
    ) -> EnterpriseRoleAssignment:
        self._user(body.user_id, company_id)
        self._owned(EnterpriseCustomRole, body.role_id, company_id)
        if body.unit_id:
            self._owned(EnterpriseUnit, body.unit_id, company_id)
        existing = self.db.scalar(
            select(EnterpriseRoleAssignment).where(
                EnterpriseRoleAssignment.company_id == company_id,
                EnterpriseRoleAssignment.user_id == body.user_id,
                EnterpriseRoleAssignment.role_id == body.role_id,
                EnterpriseRoleAssignment.unit_id == body.unit_id,
            )
        )
        if existing:
            return existing
        row = EnterpriseRoleAssignment(
            company_id=company_id,
            user_id=body.user_id,
            role_id=body.role_id,
            unit_id=body.unit_id,
            assigned_by=actor_id,
        )
        self.db.add(row)
        self.db.flush()
        self.audit(
            company_id,
            actor_id,
            "enterprise.role.assigned",
            "role_assignment",
            str(row.id),
            after=body.model_dump(mode="json"),
            commit=False,
        )
        self.db.commit()
        self.db.refresh(row)
        return row

    def effective_permissions(
        self, company_id: uuid.UUID, user_id: uuid.UUID
    ) -> EffectivePermissionsResponse:
        user = self._user(user_id, company_id)
        builtin_role = (
            user.role if isinstance(user.role, EnterpriseRole) else EnterpriseRole(str(user.role))
        )
        effective = {p.value for p in ROLE_PERMISSIONS.get(builtin_role, set())}
        details: List[Dict[str, Any]] = []
        assignments = self.db.scalars(
            select(EnterpriseRoleAssignment).where(
                EnterpriseRoleAssignment.company_id == company_id,
                EnterpriseRoleAssignment.user_id == user_id,
            )
        ).all()
        for assignment in assignments:
            role = self.db.get(EnterpriseCustomRole, assignment.role_id)
            if not role or not role.is_active:
                continue
            role_permissions = set(role.permissions or [])
            groups: List[str] = []
            for group_id in role.permission_group_ids or []:
                group = self.db.get(EnterprisePermissionGroup, uuid.UUID(str(group_id)))
                if group:
                    groups.append(group.name)
                    role_permissions.update(group.permissions or [])
            effective.update(role_permissions)
            details.append(
                {
                    "assignment_id": str(assignment.id),
                    "role_id": str(role.id),
                    "role": role.name,
                    "unit_id": str(assignment.unit_id) if assignment.unit_id else None,
                    "permission_groups": groups,
                }
            )
        return EffectivePermissionsResponse(
            user_id=user_id,
            builtin_role=builtin_role.value,
            permissions=sorted(effective),
            assignments=details,
        )

    # ── SSO configuration / initiation ───────────────────────────────────────

    @staticmethod
    def _fernet() -> Fernet:
        digest = hashlib.sha256(settings.JWT_SECRET_KEY.encode()).digest()
        return Fernet(base64.urlsafe_b64encode(digest))

    def list_sso(self, company_id: uuid.UUID) -> List[EnterpriseSSOConnection]:
        return list(
            self.db.scalars(
                select(EnterpriseSSOConnection)
                .where(EnterpriseSSOConnection.company_id == company_id)
                .order_by(EnterpriseSSOConnection.name)
            ).all()
        )

    def create_sso(
        self, company_id: uuid.UUID, actor_id: uuid.UUID, body: SSOConnectionCreate
    ) -> EnterpriseSSOConnection:
        if body.provider != SSOProvider.SAML and not body.allowed_redirect_uris:
            raise HTTPException(
                status_code=422,
                detail="OIDC connections require at least one allowed_redirect_uri",
            )
        values = body.model_dump(exclude={"client_secret"})
        if body.provider == SSOProvider.GOOGLE_WORKSPACE:
            values["issuer"] = body.issuer or "https://accounts.google.com"
            values["authorization_endpoint"] = (
                body.authorization_endpoint or "https://accounts.google.com/o/oauth2/v2/auth"
            )
            values["token_endpoint"] = body.token_endpoint or "https://oauth2.googleapis.com/token"
            values["jwks_uri"] = body.jwks_uri or "https://www.googleapis.com/oauth2/v3/certs"
        elif body.provider == SSOProvider.MICROSOFT_ENTRA:
            tenant = body.issuer or "common"
            base = (
                tenant
                if tenant.startswith("https://")
                else f"https://login.microsoftonline.com/{tenant}/v2.0"
            )
            values["issuer"] = base
            values["authorization_endpoint"] = body.authorization_endpoint or f"{base}/authorize"
            values["token_endpoint"] = body.token_endpoint or f"{base}/token"
            values["jwks_uri"] = (
                body.jwks_uri
                or (
                    "https://login.microsoftonline.com/common/discovery/v2.0/keys"
                    if tenant.startswith("https://")
                    else f"https://login.microsoftonline.com/{tenant}/discovery/v2.0/keys"
                )
            )
        elif body.provider == SSOProvider.OIDC:
            if not body.issuer or not body.client_id:
                raise HTTPException(status_code=422, detail="OIDC requires issuer and client_id")
        elif body.provider == SSOProvider.SAML:
            if not body.entity_id or not body.sso_url or not body.certificate:
                raise HTTPException(
                    status_code=422,
                    detail="SAML requires entity_id, sso_url, and certificate",
                )
        values["company_id"] = company_id
        values["domain"] = body.domain.lower()
        values["encrypted_client_secret"] = (
            self._fernet().encrypt(body.client_secret.encode()).decode()
            if body.client_secret
            else None
        )
        row = EnterpriseSSOConnection(**values)
        self.db.add(row)
        self.db.flush()
        self.audit(
            company_id,
            actor_id,
            "enterprise.sso.created",
            "sso_connection",
            str(row.id),
            after={"name": row.name, "provider": row.provider.value, "domain": row.domain},
            commit=False,
        )
        self.db.commit()
        self.db.refresh(row)
        return row

    def update_sso(
        self,
        company_id: uuid.UUID,
        actor_id: uuid.UUID,
        connection_id: uuid.UUID,
        body: SSOConnectionUpdate,
    ) -> EnterpriseSSOConnection:
        row = self._owned(EnterpriseSSOConnection, connection_id, company_id)
        changes = body.model_dump(exclude_unset=True, exclude={"client_secret"})
        for key, value in changes.items():
            setattr(row, key, value)
        if body.client_secret:
            row.encrypted_client_secret = self._fernet().encrypt(
                body.client_secret.encode()
            ).decode()
        self.audit(
            company_id,
            actor_id,
            "enterprise.sso.updated",
            "sso_connection",
            str(row.id),
            after={"fields": sorted(body.model_fields_set)},
            commit=False,
        )
        self.db.commit()
        self.db.refresh(row)
        return row

    def initiate_sso(
        self, connection_id: uuid.UUID, redirect_uri: str
    ) -> SSOInitiateResponse:
        row = self.db.get(EnterpriseSSOConnection, connection_id)
        if not row or not row.is_active:
            raise HTTPException(status_code=404, detail="SSO connection not found")
        if row.allowed_redirect_uris and redirect_uri not in row.allowed_redirect_uris:
            raise HTTPException(status_code=400, detail="Redirect URI is not allow-listed")
        nonce = secrets.token_urlsafe(24)
        state = jwt.encode(
            {
                "type": "enterprise_sso_state",
                "connection_id": str(row.id),
                "redirect_hash": hashlib.sha256(redirect_uri.encode()).hexdigest(),
                "nonce": nonce,
                "exp": _now() + timedelta(minutes=10),
            },
            settings.JWT_SECRET_KEY,
            algorithm="HS256",
        )
        if row.provider == SSOProvider.SAML:
            params = urlencode({"RelayState": state})
            return SSOInitiateResponse(
                provider=row.provider,
                authorization_url=f"{row.sso_url}?{params}",
                state=state,
            )
        if not row.authorization_endpoint or not row.client_id:
            raise HTTPException(status_code=422, detail="SSO connection is incomplete")
        params = urlencode(
            {
                "client_id": row.client_id,
                "redirect_uri": redirect_uri,
                "response_type": "code",
                "scope": " ".join(row.scopes or ["openid", "profile", "email"]),
                "state": state,
                "nonce": nonce,
            }
        )
        return SSOInitiateResponse(
            provider=row.provider,
            authorization_url=f"{row.authorization_endpoint}?{params}",
            state=state,
        )

    async def complete_oidc(self, body: OIDCCallbackRequest):
        """Exchange and validate an OIDC authorization code, then issue existing JWTs."""
        try:
            state = jwt.decode(
                body.state, settings.JWT_SECRET_KEY, algorithms=["HS256"]
            )
        except JWTError as exc:
            raise HTTPException(status_code=400, detail="Invalid or expired SSO state") from exc
        if state.get("type") != "enterprise_sso_state":
            raise HTTPException(status_code=400, detail="Invalid SSO state type")
        if state.get("redirect_hash") != hashlib.sha256(body.redirect_uri.encode()).hexdigest():
            raise HTTPException(status_code=400, detail="SSO redirect URI mismatch")

        row = self.db.get(
            EnterpriseSSOConnection, uuid.UUID(str(state["connection_id"]))
        )
        if (
            not row
            or not row.is_active
            or row.provider == SSOProvider.SAML
            or not row.token_endpoint
            or not row.jwks_uri
            or not row.client_id
        ):
            raise HTTPException(status_code=400, detail="OIDC connection is incomplete")
        client_secret = (
            self._fernet().decrypt(row.encrypted_client_secret.encode()).decode()
            if row.encrypted_client_secret
            else None
        )
        token_payload = {
            "grant_type": "authorization_code",
            "code": body.code,
            "redirect_uri": body.redirect_uri,
            "client_id": row.client_id,
        }
        if client_secret:
            token_payload["client_secret"] = client_secret
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=False) as client:
            token_response = await client.post(row.token_endpoint, data=token_payload)
            if token_response.status_code >= 400:
                raise HTTPException(status_code=401, detail="Identity provider rejected the code")
            token_data = token_response.json()
            id_token = token_data.get("id_token")
            if not id_token:
                raise HTTPException(status_code=401, detail="Identity provider returned no ID token")
            jwks_response = await client.get(row.jwks_uri)
            jwks_response.raise_for_status()
            jwks = jwks_response.json()

        header = jwt.get_unverified_header(id_token)
        key = next(
            (item for item in jwks.get("keys", []) if item.get("kid") == header.get("kid")),
            None,
        )
        if not key:
            raise HTTPException(status_code=401, detail="No matching identity-provider key")
        try:
            claims = jwt.decode(
                id_token,
                key,
                algorithms=[header.get("alg", "RS256")],
                audience=row.client_id,
                issuer=row.issuer,
            )
        except JWTError as exc:
            raise HTTPException(status_code=401, detail="Invalid identity token") from exc
        if claims.get("nonce") != state.get("nonce"):
            raise HTTPException(status_code=401, detail="Identity token nonce mismatch")
        email = (claims.get("email") or claims.get("preferred_username") or "").lower()
        if not email or email.rsplit("@", 1)[-1] != row.domain:
            raise HTTPException(status_code=403, detail="Identity is outside the configured domain")

        user = self.db.scalar(
            select(User).where(
                User.company_id == row.company_id,
                User.email == email,
            )
        )
        if not user:
            if not row.jit_provisioning:
                raise HTTPException(status_code=403, detail="JIT provisioning is disabled")
            try:
                role = EnterpriseRole(row.default_role)
            except ValueError:
                role = EnterpriseRole.EMPLOYEE
            created = self.user_service.create_user(
                UserCreate(
                    email=email,
                    password=secrets.token_urlsafe(32),
                    company_id=row.company_id,
                    first_name=claims.get("given_name") or claims.get("name") or "SSO",
                    last_name=claims.get("family_name") or "User",
                    role=role,
                )
            )
            user = self.db.get(User, created.id)
        if not user or not user.is_active or user.status != UserStatus.ACTIVE:
            raise HTTPException(status_code=403, detail="Member is suspended or inactive")

        from app.auth.schema import TokenResponse
        from app.auth.service import ACCESS_TOKEN_EXPIRE_MINUTES, AuthService

        auth = AuthService(self.db)
        access_token = auth.create_access_token(str(user.id))
        refresh_token = auth.create_refresh_token(str(user.id))
        self.audit(
            row.company_id,
            user.id,
            "enterprise.sso.login",
            "sso_connection",
            str(row.id),
            metadata={"provider": row.provider.value, "domain": row.domain},
        )
        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )

    # ── Security: MFA policy, sessions, IP/API policy, trusted devices ───────

    def get_security_policy(self, company_id: uuid.UUID) -> EnterpriseSecurityPolicy:
        row = self.db.scalar(
            select(EnterpriseSecurityPolicy).where(
                EnterpriseSecurityPolicy.company_id == company_id
            )
        )
        if not row:
            row = EnterpriseSecurityPolicy(company_id=company_id)
            self.db.add(row)
            self.db.commit()
            self.db.refresh(row)
        return row

    def update_security_policy(
        self, company_id: uuid.UUID, actor_id: uuid.UUID, body: SecurityPolicyUpdate
    ) -> EnterpriseSecurityPolicy:
        row = self.get_security_policy(company_id)
        before = {
            "require_mfa": row.require_mfa,
            "ip_allow_list": row.ip_allow_list,
            "api_policies": row.api_policies,
        }
        for key, value in body.model_dump(exclude_unset=True).items():
            setattr(row, key, value)
        self.audit(
            company_id,
            actor_id,
            "enterprise.security_policy.updated",
            "security_policy",
            str(row.id),
            severity=AuditSeverity.WARNING,
            before=before,
            after=body.model_dump(exclude_unset=True),
            commit=False,
        )
        self.db.commit()
        self.db.refresh(row)
        return row

    def list_sessions(self, company_id: uuid.UUID, user_id: Optional[uuid.UUID] = None):
        stmt = (
            select(RefreshToken)
            .join(User, User.id == RefreshToken.user_id)
            .where(User.company_id == company_id)
            .order_by(RefreshToken.created_at.desc())
        )
        if user_id:
            self._user(user_id, company_id)
            stmt = stmt.where(RefreshToken.user_id == user_id)
        return list(self.db.scalars(stmt).all())

    def revoke_session(
        self, company_id: uuid.UUID, actor_id: uuid.UUID, session_id: uuid.UUID
    ) -> None:
        session = self.db.scalar(
            select(RefreshToken)
            .join(User, User.id == RefreshToken.user_id)
            .where(RefreshToken.id == session_id, User.company_id == company_id)
        )
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        if session.revoked_at is None:
            session.revoked_at = _now()
        self.audit(
            company_id,
            actor_id,
            "enterprise.session.revoked",
            "refresh_token",
            str(session.id),
            severity=AuditSeverity.WARNING,
            commit=False,
        )
        self.db.commit()

    def register_trusted_device(
        self,
        company_id: uuid.UUID,
        user_id: uuid.UUID,
        body: TrustedDeviceCreate,
        ip_address: Optional[str],
    ) -> EnterpriseTrustedDevice:
        self._user(user_id, company_id)
        policy = self.get_security_policy(company_id)
        digest = hashlib.sha256(body.fingerprint.encode()).hexdigest()
        row = self.db.scalar(
            select(EnterpriseTrustedDevice).where(
                EnterpriseTrustedDevice.user_id == user_id,
                EnterpriseTrustedDevice.fingerprint_hash == digest,
            )
        )
        if not row:
            row = EnterpriseTrustedDevice(
                company_id=company_id,
                user_id=user_id,
                fingerprint_hash=digest,
            )
            self.db.add(row)
        row.name = body.name
        row.last_ip = ip_address
        row.last_seen_at = _now()
        row.expires_at = _now() + timedelta(days=policy.trusted_device_days)
        row.revoked_at = None
        self.db.commit()
        self.db.refresh(row)
        return row

    def list_trusted_devices(
        self, company_id: uuid.UUID, user_id: uuid.UUID
    ) -> List[EnterpriseTrustedDevice]:
        self._user(user_id, company_id)
        return list(
            self.db.scalars(
                select(EnterpriseTrustedDevice)
                .where(
                    EnterpriseTrustedDevice.company_id == company_id,
                    EnterpriseTrustedDevice.user_id == user_id,
                )
                .order_by(EnterpriseTrustedDevice.last_seen_at.desc())
            ).all()
        )

    def revoke_trusted_device(
        self, company_id: uuid.UUID, actor_id: uuid.UUID, device_id: uuid.UUID
    ) -> None:
        row = self._owned(EnterpriseTrustedDevice, device_id, company_id)
        row.revoked_at = _now()
        self.audit(
            company_id,
            actor_id,
            "enterprise.trusted_device.revoked",
            "trusted_device",
            str(row.id),
            severity=AuditSeverity.WARNING,
            commit=False,
        )
        self.db.commit()

    # ── Audit / compliance ───────────────────────────────────────────────────

    def list_audit_logs(
        self,
        company_id: uuid.UUID,
        *,
        action: Optional[str] = None,
        actor_user_id: Optional[uuid.UUID] = None,
        severity: Optional[AuditSeverity] = None,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[EnterpriseAuditLog]:
        stmt = select(EnterpriseAuditLog).where(
            EnterpriseAuditLog.company_id == company_id
        )
        if action:
            stmt = stmt.where(EnterpriseAuditLog.action.ilike(f"%{action}%"))
        if actor_user_id:
            stmt = stmt.where(EnterpriseAuditLog.actor_user_id == actor_user_id)
        if severity:
            stmt = stmt.where(EnterpriseAuditLog.severity == severity)
        if start:
            stmt = stmt.where(EnterpriseAuditLog.created_at >= start)
        if end:
            stmt = stmt.where(EnterpriseAuditLog.created_at <= end)
        return list(
            self.db.scalars(
                stmt.order_by(EnterpriseAuditLog.created_at.desc())
                .offset(offset)
                .limit(min(limit, 1000))
            ).all()
        )

    def activity_timeline(
        self, company_id: uuid.UUID, resource_type: str, resource_id: str
    ) -> List[EnterpriseAuditLog]:
        return list(
            self.db.scalars(
                select(EnterpriseAuditLog)
                .where(
                    EnterpriseAuditLog.company_id == company_id,
                    EnterpriseAuditLog.resource_type == resource_type,
                    EnterpriseAuditLog.resource_id == resource_id,
                )
                .order_by(EnterpriseAuditLog.created_at.desc())
            ).all()
        )

    def upsert_retention(
        self, company_id: uuid.UUID, actor_id: uuid.UUID, body: RetentionPolicyCreate
    ) -> EnterpriseRetentionPolicy:
        row = self.db.scalar(
            select(EnterpriseRetentionPolicy).where(
                EnterpriseRetentionPolicy.company_id == company_id,
                EnterpriseRetentionPolicy.data_type == body.data_type,
            )
        )
        if not row:
            row = EnterpriseRetentionPolicy(company_id=company_id, data_type=body.data_type)
            self.db.add(row)
        for key, value in body.model_dump().items():
            setattr(row, key, value)
        self.audit(
            company_id,
            actor_id,
            "enterprise.retention_policy.updated",
            "retention_policy",
            str(row.id),
            after=body.model_dump(),
            commit=False,
        )
        self.db.commit()
        self.db.refresh(row)
        return row

    def list_retention(self, company_id: uuid.UUID) -> List[EnterpriseRetentionPolicy]:
        return list(
            self.db.scalars(
                select(EnterpriseRetentionPolicy)
                .where(EnterpriseRetentionPolicy.company_id == company_id)
                .order_by(EnterpriseRetentionPolicy.data_type)
            ).all()
        )

    def privacy_settings(
        self, company_id: uuid.UUID, body: Optional[PrivacySettingsUpdate] = None
    ) -> Dict[str, Any]:
        company = self._company(company_id)
        all_settings = dict(company.settings or {})
        privacy = dict(all_settings.get("privacy") or {})
        if body is not None:
            privacy.update(
                {
                    key: value
                    for key, value in body.model_dump(exclude_unset=True, mode="json").items()
                    if value is not None
                }
            )
            all_settings["privacy"] = privacy
            company.settings = all_settings
            self.db.add(company)
            self.db.commit()
        return privacy

    def record_consent(
        self,
        company_id: uuid.UUID,
        body: ConsentCreate,
        ip_address: Optional[str],
    ) -> EnterpriseConsentLog:
        row = EnterpriseConsentLog(
            company_id=company_id,
            subject_id=body.subject_id,
            purpose=body.purpose,
            granted=body.granted,
            policy_version=body.policy_version,
            source=body.source,
            ip_address=ip_address,
            metadata_=body.metadata,
            created_at=_now(),
        )
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def list_consents(
        self, company_id: uuid.UUID, subject_id: Optional[str] = None
    ) -> List[EnterpriseConsentLog]:
        stmt = select(EnterpriseConsentLog).where(
            EnterpriseConsentLog.company_id == company_id
        )
        if subject_id:
            stmt = stmt.where(EnterpriseConsentLog.subject_id == subject_id)
        return list(
            self.db.scalars(
                stmt.order_by(EnterpriseConsentLog.created_at.desc()).limit(1000)
            ).all()
        )

    def apply_retention_policies(self, company_id: uuid.UUID) -> Dict[str, int]:
        """Apply due tenant retention rules; legal holds always win."""
        result = {"deleted": 0, "anonymized": 0, "skipped_legal_hold": 0}
        for policy in self.list_retention(company_id):
            if policy.legal_hold:
                result["skipped_legal_hold"] += 1
                continue
            cutoff = _now() - timedelta(days=policy.retention_days)
            if policy.data_type == "audit":
                if policy.anonymize:
                    changed = self.db.execute(
                        update(EnterpriseAuditLog)
                        .where(
                            EnterpriseAuditLog.company_id == company_id,
                            EnterpriseAuditLog.created_at < cutoff,
                        )
                        .values(
                            actor_user_id=None,
                            ip_address=None,
                            user_agent=None,
                            before=None,
                            after=None,
                            metadata_={},
                        )
                    )
                    result["anonymized"] += int(changed.rowcount or 0)
                elif policy.auto_delete:
                    changed = self.db.execute(
                        delete(EnterpriseAuditLog).where(
                            EnterpriseAuditLog.company_id == company_id,
                            EnterpriseAuditLog.created_at < cutoff,
                        )
                    )
                    result["deleted"] += int(changed.rowcount or 0)
            elif policy.data_type == "consent":
                if policy.anonymize:
                    rows = self.db.scalars(
                        select(EnterpriseConsentLog).where(
                            EnterpriseConsentLog.company_id == company_id,
                            EnterpriseConsentLog.created_at < cutoff,
                        )
                    ).all()
                    for row in rows:
                        row.subject_id = hashlib.sha256(
                            f"{company_id}:{row.subject_id}".encode()
                        ).hexdigest()
                        row.ip_address = None
                        row.metadata_ = {}
                    result["anonymized"] += len(rows)
                elif policy.auto_delete:
                    changed = self.db.execute(
                        delete(EnterpriseConsentLog).where(
                            EnterpriseConsentLog.company_id == company_id,
                            EnterpriseConsentLog.created_at < cutoff,
                        )
                    )
                    result["deleted"] += int(changed.rowcount or 0)
            elif policy.data_type == "exports" and policy.auto_delete:
                changed = self.db.execute(
                    delete(EnterpriseExportJob).where(
                        EnterpriseExportJob.company_id == company_id,
                        EnterpriseExportJob.created_at < cutoff,
                    )
                )
                result["deleted"] += int(changed.rowcount or 0)
        self.db.commit()
        return result

    def apply_all_retention_policies(self) -> Dict[str, int]:
        totals = {"companies": 0, "deleted": 0, "anonymized": 0}
        company_ids = self.db.scalars(
            select(EnterpriseRetentionPolicy.company_id).distinct()
        ).all()
        for company_id in company_ids:
            result = self.apply_retention_policies(company_id)
            totals["companies"] += 1
            totals["deleted"] += result["deleted"]
            totals["anonymized"] += result["anonymized"]
        return totals

    # ── Dashboard and delegated reports ──────────────────────────────────────

    def dashboard(self, company_id: uuid.UUID) -> EnterpriseDashboardResponse:
        company = self._company(company_id)
        users = self.db.scalars(select(User).where(User.company_id == company_id)).all()
        units = self.list_units(company_id)
        policy = self.get_security_policy(company_id)
        mfa_enabled = self.db.scalar(
            select(func.count(MFASettings.id))
            .join(User, User.id == MFASettings.user_id)
            .where(User.company_id == company_id, MFASettings.enabled.is_(True))
        ) or 0
        active_sessions = self.db.scalar(
            select(func.count(RefreshToken.id))
            .join(User, User.id == RefreshToken.user_id)
            .where(
                User.company_id == company_id,
                RefreshToken.revoked_at.is_(None),
                RefreshToken.expires_at > _now(),
            )
        ) or 0
        try:
            usage = _jsonable(self.usage.dashboard(company_id))
        except Exception as exc:
            usage = {"unavailable": str(exc)}
        subscription = self.subscriptions.get_subscription(company_id)
        invoices = self.invoices.list_invoices(company_id, limit=5)
        try:
            brand = self.branding.get(company_id)
            branding = {
                "published": brand.is_published,
                "published_version": brand.published_version,
                "company_name": brand.company_name,
            }
        except Exception as exc:
            branding = {"unavailable": str(exc)}
        try:
            market = _jsonable(self.marketplace.dashboard(company_id))
        except Exception as exc:
            market = {"unavailable": str(exc)}
        from app.agent_platform.models.agent import AgentConfig

        published_agents = self.db.scalar(
            select(func.count(AgentConfig.id)).where(
                AgentConfig.company_id == company_id,
                AgentConfig.status == "PUBLISHED",
            )
        ) or 0
        return EnterpriseDashboardResponse(
            organization={
                "id": str(company.id),
                "name": company.display_name or company.name,
                "plan": _enum_value(company.plan),
                "status": _enum_value(company.status),
            },
            members={
                "total": len(users),
                "active": sum(1 for user in users if user.status == UserStatus.ACTIVE),
                "suspended": sum(1 for user in users if user.status == UserStatus.SUSPENDED),
                "pending": sum(1 for user in users if user.status == UserStatus.PENDING),
            },
            units={
                unit_type.value: sum(1 for unit in units if unit.unit_type == unit_type)
                for unit_type in UnitType
            },
            security={
                "require_mfa": policy.require_mfa,
                "mfa_enabled_users": int(mfa_enabled),
                "active_sessions": int(active_sessions),
                "ip_allow_list_count": len(policy.ip_allow_list or []),
                "sso_connections": len(self.list_sso(company_id)),
            },
            usage=usage,
            billing={
                "subscription": _jsonable(subscription) if subscription else None,
                "recent_invoices": [_jsonable(invoice) for invoice in invoices],
            },
            branding=branding,
            marketplace=market,
            published_agents=int(published_agents),
        )

    def report(self, company_id: uuid.UUID, report_type: str) -> ReportResponse:
        if report_type == "usage":
            data = {
                "dashboard": _jsonable(self.usage.dashboard(company_id)),
                "monthly": _jsonable(self.usage.monthly_summary(company_id)),
            }
        elif report_type == "billing":
            data = {
                "subscription": _jsonable(self.subscriptions.get_subscription(company_id)),
                "invoices": [
                    _jsonable(invoice)
                    for invoice in self.invoices.list_invoices(company_id, limit=100)
                ],
            }
        elif report_type == "security":
            policy = self.get_security_policy(company_id)
            data = {
                "policy": {
                    "require_mfa": policy.require_mfa,
                    "session_ttl_minutes": policy.session_ttl_minutes,
                    "ip_allow_list": policy.ip_allow_list,
                    "api_policies": policy.api_policies,
                },
                "active_sessions": len(
                    [
                        session
                        for session in self.list_sessions(company_id)
                        if not session.revoked_at and session.expires_at > _now()
                    ]
                ),
                "critical_events_30d": self.db.scalar(
                    select(func.count(EnterpriseAuditLog.id)).where(
                        EnterpriseAuditLog.company_id == company_id,
                        EnterpriseAuditLog.severity == AuditSeverity.CRITICAL,
                        EnterpriseAuditLog.created_at >= _now() - timedelta(days=30),
                    )
                )
                or 0,
            }
        else:
            raise HTTPException(status_code=404, detail="Unknown report")
        return ReportResponse(report_type=report_type, generated_at=_now(), data=data)

    # ── Exports (reuse StorageService) ───────────────────────────────────────

    async def create_export(
        self, company_id: uuid.UUID, actor_id: uuid.UUID, body: ExportRequest
    ) -> EnterpriseExportJob:
        job = EnterpriseExportJob(
            company_id=company_id,
            requested_by=actor_id,
            export_type=body.export_type,
            format=body.format,
            filters=body.filters,
            status=ExportStatus.PROCESSING,
        )
        self.db.add(job)
        self.db.commit()
        self.db.refresh(job)
        try:
            rows = self._export_rows(company_id, body.export_type, body.filters)
            content = self._encode_export(rows, body.format)
            content_type = "text/csv" if body.format == "csv" else "application/json"
            upload = UploadFile(
                file=io.BytesIO(content),
                size=len(content),
                filename=f"{body.export_type}-{job.id}.{body.format}",
                headers=Headers({"content-type": content_type}),
            )
            stored = await self.storage.upload_file(
                upload, company_id=company_id, user_id=actor_id
            )
            job.storage_file_id = stored.id
            job.download_url = self.storage.get_download_url(stored.id)
            job.row_count = len(rows)
            job.status = ExportStatus.COMPLETED
        except Exception as exc:
            job.status = ExportStatus.FAILED
            job.error = str(exc)[:2000]
        self.audit(
            company_id,
            actor_id,
            "enterprise.export.created",
            "export_job",
            str(job.id),
            after={"type": body.export_type, "status": job.status.value},
            commit=False,
        )
        self.db.commit()
        self.db.refresh(job)
        return job

    def list_exports(self, company_id: uuid.UUID) -> List[EnterpriseExportJob]:
        return list(
            self.db.scalars(
                select(EnterpriseExportJob)
                .where(EnterpriseExportJob.company_id == company_id)
                .order_by(EnterpriseExportJob.created_at.desc())
                .limit(500)
            ).all()
        )

    def _export_rows(
        self, company_id: uuid.UUID, export_type: str, filters: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        if export_type == "audit":
            return [
                {
                    "id": str(row.id),
                    "timestamp": row.created_at.isoformat(),
                    "actor_user_id": str(row.actor_user_id) if row.actor_user_id else "",
                    "action": row.action,
                    "resource_type": row.resource_type,
                    "resource_id": row.resource_id or "",
                    "severity": row.severity.value,
                    "ip_address": str(row.ip_address or ""),
                }
                for row in self.list_audit_logs(company_id, limit=1000)
            ]
        if export_type == "members":
            users = self.db.scalars(select(User).where(User.company_id == company_id)).all()
            return [
                {
                    "id": str(user.id),
                    "email": user.email,
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                    "role": _enum_value(user.role),
                    "status": _enum_value(user.status),
                }
                for user in users
            ]
        if export_type == "consent":
            return [
                {
                    "id": str(row.id),
                    "subject_id": row.subject_id,
                    "purpose": row.purpose,
                    "granted": row.granted,
                    "policy_version": row.policy_version,
                    "created_at": row.created_at.isoformat(),
                }
                for row in self.list_consents(company_id)
            ]
        report_type = "security" if export_type == "security" else export_type
        report = self.report(company_id, report_type)
        return [{"report_type": report.report_type, "data": json.dumps(report.data, default=str)}]

    @staticmethod
    def _encode_export(rows: List[Dict[str, Any]], format_value: str) -> bytes:
        if format_value == "json":
            return json.dumps(rows, default=str, indent=2).encode()
        if not rows:
            return b""
        stream = io.StringIO()
        writer = csv.DictWriter(stream, fieldnames=list(rows[0].keys()), extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
        return stream.getvalue().encode()
