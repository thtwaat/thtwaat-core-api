"""API schemas for the enterprise module."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.enterprise.models import (
    AuditSeverity,
    ExportStatus,
    InvitationStatus,
    SSOProvider,
    UnitType,
)


class UnitCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    slug: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$", max_length=100)
    unit_type: UnitType
    parent_id: Optional[UUID] = None
    description: Optional[str] = None
    manager_user_id: Optional[UUID] = None
    cost_center: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class UnitUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    parent_id: Optional[UUID] = None
    description: Optional[str] = None
    manager_user_id: Optional[UUID] = None
    cost_center: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None


class UnitResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    company_id: UUID
    parent_id: Optional[UUID]
    unit_type: UnitType
    name: str
    slug: str
    description: Optional[str]
    manager_user_id: Optional[UUID]
    cost_center: Optional[str]
    metadata: Dict[str, Any] = Field(validation_alias="metadata_")
    is_active: bool
    created_at: datetime
    updated_at: datetime


class MembershipCreate(BaseModel):
    user_id: UUID
    title: Optional[str] = None
    is_primary: bool = False


class MembershipResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    unit_id: UUID
    user_id: UUID
    title: Optional[str]
    is_primary: bool
    created_at: datetime


class InviteMember(BaseModel):
    email: EmailStr
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    builtin_role: str = "employee"
    custom_role_id: Optional[UUID] = None
    unit_ids: List[UUID] = Field(default_factory=list)
    expires_in_days: int = Field(default=7, ge=1, le=30)


class BulkInviteRequest(BaseModel):
    members: List[InviteMember] = Field(min_length=1, max_length=500)


class InviteAccept(BaseModel):
    token: str = Field(min_length=32)
    password: str = Field(min_length=8, max_length=128)


class InvitationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: EmailStr
    first_name: str
    last_name: str
    builtin_role: str
    custom_role_id: Optional[UUID]
    unit_ids: List[str]
    status: InvitationStatus
    expires_at: datetime
    accepted_at: Optional[datetime]
    created_at: datetime


class InviteResult(BaseModel):
    invitation: InvitationResponse
    invite_token: str = Field(description="Returned once; send through the existing notification provider")


class BulkInviteResult(BaseModel):
    invited: List[InviteResult] = Field(default_factory=list)
    rejected: List[Dict[str, str]] = Field(default_factory=list)


class MemberStatusUpdate(BaseModel):
    status: str

    @field_validator("status")
    @classmethod
    def valid_status(cls, value: str) -> str:
        if value not in {"active", "suspended", "inactive"}:
            raise ValueError("status must be active, suspended, or inactive")
        return value


class PermissionGroupCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: Optional[str] = None
    permissions: List[str] = Field(default_factory=list)


class PermissionGroupResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    description: Optional[str]
    permissions: List[str]
    is_system: bool


class CustomRoleCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: Optional[str] = None
    template_key: Optional[str] = None
    permissions: List[str] = Field(default_factory=list)
    permission_group_ids: List[UUID] = Field(default_factory=list)


class CustomRoleUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    permissions: Optional[List[str]] = None
    permission_group_ids: Optional[List[UUID]] = None
    is_active: Optional[bool] = None


class CustomRoleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    description: Optional[str]
    template_key: Optional[str]
    permissions: List[str]
    permission_group_ids: List[str]
    is_active: bool


class RoleAssignmentCreate(BaseModel):
    user_id: UUID
    role_id: UUID
    unit_id: Optional[UUID] = None


class EffectivePermissionsResponse(BaseModel):
    user_id: UUID
    builtin_role: str
    permissions: List[str]
    assignments: List[Dict[str, Any]] = Field(default_factory=list)


class SSOConnectionCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    provider: SSOProvider
    domain: str = Field(min_length=3, max_length=253)
    issuer: Optional[str] = None
    client_id: Optional[str] = None
    client_secret: Optional[str] = Field(None, min_length=8)
    authorization_endpoint: Optional[str] = None
    token_endpoint: Optional[str] = None
    jwks_uri: Optional[str] = None
    metadata_url: Optional[str] = None
    entity_id: Optional[str] = None
    sso_url: Optional[str] = None
    certificate: Optional[str] = None
    scopes: List[str] = Field(default_factory=lambda: ["openid", "profile", "email"])
    allowed_redirect_uris: List[str] = Field(default_factory=list)
    attribute_mapping: Dict[str, str] = Field(default_factory=dict)
    enforce_sso: bool = False
    jit_provisioning: bool = True
    default_role: str = "employee"


class SSOConnectionUpdate(BaseModel):
    name: Optional[str] = None
    client_secret: Optional[str] = Field(None, min_length=8)
    authorization_endpoint: Optional[str] = None
    token_endpoint: Optional[str] = None
    jwks_uri: Optional[str] = None
    metadata_url: Optional[str] = None
    entity_id: Optional[str] = None
    sso_url: Optional[str] = None
    certificate: Optional[str] = None
    scopes: Optional[List[str]] = None
    allowed_redirect_uris: Optional[List[str]] = None
    attribute_mapping: Optional[Dict[str, str]] = None
    enforce_sso: Optional[bool] = None
    jit_provisioning: Optional[bool] = None
    default_role: Optional[str] = None
    is_active: Optional[bool] = None


class SSOConnectionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    provider: SSOProvider
    domain: str
    issuer: Optional[str]
    client_id: Optional[str]
    authorization_endpoint: Optional[str]
    token_endpoint: Optional[str]
    jwks_uri: Optional[str]
    metadata_url: Optional[str]
    entity_id: Optional[str]
    sso_url: Optional[str]
    scopes: List[str]
    allowed_redirect_uris: List[str]
    attribute_mapping: Dict[str, str]
    enforce_sso: bool
    jit_provisioning: bool
    default_role: str
    is_active: bool


class SSOInitiateResponse(BaseModel):
    provider: SSOProvider
    authorization_url: str
    state: str


class OIDCCallbackRequest(BaseModel):
    code: str = Field(min_length=1)
    state: str = Field(min_length=20)
    redirect_uri: str = Field(min_length=8)


class SecurityPolicyUpdate(BaseModel):
    require_mfa: Optional[bool] = None
    session_ttl_minutes: Optional[int] = Field(None, ge=5, le=43200)
    idle_timeout_minutes: Optional[int] = Field(None, ge=5, le=1440)
    max_sessions_per_user: Optional[int] = Field(None, ge=1, le=100)
    ip_allow_list: Optional[List[str]] = None
    trusted_device_days: Optional[int] = Field(None, ge=1, le=365)
    api_policies: Optional[Dict[str, Any]] = None
    password_policy: Optional[Dict[str, Any]] = None


class SecurityPolicyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    require_mfa: bool
    session_ttl_minutes: int
    idle_timeout_minutes: int
    max_sessions_per_user: int
    ip_allow_list: List[str]
    trusted_device_days: int
    api_policies: Dict[str, Any]
    password_policy: Dict[str, Any]


class SessionResponse(BaseModel):
    id: UUID
    user_id: UUID
    created_at: datetime
    expires_at: datetime
    revoked_at: Optional[datetime]
    current: bool = False


class TrustedDeviceCreate(BaseModel):
    name: Optional[str] = None
    fingerprint: str = Field(min_length=16, max_length=1024)


class TrustedDeviceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    name: Optional[str]
    last_ip: Optional[str]
    last_seen_at: datetime
    expires_at: datetime
    revoked_at: Optional[datetime]


class AuditLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    actor_user_id: Optional[UUID]
    action: str
    resource_type: str
    resource_id: Optional[str]
    severity: AuditSeverity
    ip_address: Optional[str]
    user_agent: Optional[str]
    request_id: Optional[str]
    before: Optional[Dict[str, Any]]
    after: Optional[Dict[str, Any]]
    metadata: Dict[str, Any] = Field(validation_alias="metadata_")
    created_at: datetime


class RetentionPolicyCreate(BaseModel):
    data_type: str = Field(min_length=1, max_length=100)
    retention_days: int = Field(ge=1, le=36500)
    legal_hold: bool = False
    auto_delete: bool = False
    anonymize: bool = False


class RetentionPolicyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    data_type: str
    retention_days: int
    legal_hold: bool
    auto_delete: bool
    anonymize: bool


class ConsentCreate(BaseModel):
    subject_id: str = Field(min_length=1, max_length=255)
    purpose: str = Field(min_length=1, max_length=255)
    granted: bool
    policy_version: str = Field(min_length=1, max_length=64)
    source: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ConsentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    subject_id: str
    purpose: str
    granted: bool
    policy_version: str
    source: Optional[str]
    ip_address: Optional[str]
    metadata: Dict[str, Any] = Field(validation_alias="metadata_")
    created_at: datetime


class PrivacySettingsUpdate(BaseModel):
    data_processing_region: Optional[str] = None
    analytics_enabled: Optional[bool] = None
    marketing_enabled: Optional[bool] = None
    data_portability_enabled: Optional[bool] = None
    data_subject_request_email: Optional[EmailStr] = None


class ExportRequest(BaseModel):
    export_type: str = Field(pattern=r"^(audit|usage|security|billing|members|consent)$")
    format: str = Field(default="csv", pattern=r"^(csv|json)$")
    filters: Dict[str, Any] = Field(default_factory=dict)


class ExportResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    export_type: str
    format: str
    filters: Dict[str, Any]
    status: ExportStatus
    download_url: Optional[str]
    row_count: Optional[int]
    error: Optional[str]
    created_at: datetime


class EnterpriseDashboardResponse(BaseModel):
    organization: Dict[str, Any]
    members: Dict[str, int]
    units: Dict[str, int]
    security: Dict[str, Any]
    usage: Dict[str, Any]
    billing: Dict[str, Any]
    branding: Dict[str, Any]
    marketplace: Dict[str, Any]
    published_agents: int


class ReportResponse(BaseModel):
    report_type: str
    generated_at: datetime
    data: Dict[str, Any]
