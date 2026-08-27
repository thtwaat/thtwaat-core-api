"""StaticSiteEnvVarService — THTWAAT Deploy Phase 4A.

CRUD + encryption-at-rest for per-site environment variables. Auth/company-
scoping/RBAC conventions are copied verbatim from app/static_sites/service.py
(itself copied from app/studio/service.py) rather than inventing a fourth
authorization mechanism — see can_manage_company_users()/_get_site() below.

Phase 4A stores and serves ENCRYPTED metadata only. No decrypted value is
ever returned from an API method here, logged, or placed in an exception
message — see app/static_sites/env_crypto.py. Build/runtime injection
(actually using the decrypted value) is Phase 4B and is not implemented here.
"""
from __future__ import annotations

import logging
from typing import Optional
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.schema import UserProfileResponse
from app.auth.tenant import can_manage_company_users
from app.static_sites.env_crypto import EnvVarCryptoError, encrypt_value
from app.static_sites.models import StaticSite, StaticSiteEnvironmentVariable
from app.static_sites.repository import StaticSiteRepository
from app.static_sites.schemas import (
    StaticSiteEnvVarCreateRequest,
    StaticSiteEnvVarListResponse,
    StaticSiteEnvVarResponse,
    StaticSiteEnvVarUpdateRequest,
    check_secret_public_prefix,
)

logger = logging.getLogger(__name__)

_GENERIC_FAILURE_MESSAGE = "Environment variable operation failed due to an internal error."
_NOT_FOUND_SITE = "Static site not found"
_NOT_FOUND_ENV_VAR = "Environment variable not found"
_DUPLICATE_KEY_MESSAGE = "An environment variable with this key already exists for this environment"


class StaticSiteEnvVarService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = StaticSiteRepository(db)

    # ---- auth helpers (mirrors app/static_sites/service.py exactly) ------

    def _require_env_manager(self, user: UserProfileResponse) -> None:
        # Env vars can hold secrets (API keys, DB URLs) — gate ALL
        # operations (including read of metadata) behind the same
        # owner/admin check used for deploy/rollback, not just mutations.
        if not can_manage_company_users(user):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only company owners and admins can manage environment variables",
            )

    def _get_site(self, user: UserProfileResponse, site_id: UUID) -> StaticSite:
        site = self.repo.get_site_for_workspace(site_id, UUID(str(user.company_id)))
        if not site:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=_NOT_FOUND_SITE)
        return site

    def _get_env_var(
        self, site: StaticSite, env_id: UUID
    ) -> StaticSiteEnvironmentVariable:
        row = self.repo.get_env_var(env_id)
        # Same not-found for "doesn't exist" and "belongs to a different
        # site/workspace" — never reveals whether another company's variable
        # exists (Phase 4A spec §11).
        if not row or row.site_id != site.id or row.workspace_id != site.workspace_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=_NOT_FOUND_ENV_VAR)
        return row

    def _audit(
        self, *, company_id: UUID, actor_id: Optional[UUID], action: str, resource_id: str, metadata: Optional[dict] = None
    ) -> None:
        try:
            from app.enterprise.models import AuditSeverity
            from app.enterprise.service import EnterpriseService

            # metadata deliberately carries only key/environment/site_id —
            # never a value or encrypted_value.
            EnterpriseService(self.db).audit(
                company_id,
                actor_id,
                action=action,
                resource_type="static_site_env_var",
                resource_id=resource_id,
                severity=AuditSeverity.INFO,
                metadata=metadata or {},
                commit=True,
            )
        except Exception:  # noqa: BLE001
            logger.warning("static_site_env_var_audit_failed action=%s", action)

    @staticmethod
    def _actor_id(user: UserProfileResponse) -> Optional[UUID]:
        return UUID(str(user.id)) if getattr(user, "id", None) else None

    # ---- CRUD ---------------------------------------------------------------

    def create_env_var(
        self, user: UserProfileResponse, site_id: UUID, payload: StaticSiteEnvVarCreateRequest
    ) -> StaticSiteEnvVarResponse:
        self._require_env_manager(user)
        site = self._get_site(user, site_id)

        # Checked here (service layer) rather than a schema model_validator —
        # a whole-model Pydantic validation failure makes FastAPI's default
        # 422 handler echo the ENTIRE request body, including `value`, back
        # in the response. A plain HTTPException never does that.
        try:
            check_secret_public_prefix(payload.key, payload.is_secret)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

        # Pre-flight check for a friendly error message — the UniqueConstraint
        # on (site_id, environment, key) is what actually guarantees
        # correctness under concurrent requests (see the IntegrityError
        # handling below), not this lookup.
        if self.repo.get_env_var_by_key(site.id, payload.environment, payload.key) is not None:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=_DUPLICATE_KEY_MESSAGE)

        try:
            encrypted = encrypt_value(payload.value)
        except EnvVarCryptoError as exc:
            logger.error("static_site_env_var_encrypt_failed site_id=%s key=%s", site.id, payload.key)
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc

        row = StaticSiteEnvironmentVariable(
            workspace_id=site.workspace_id,
            site_id=site.id,
            key=payload.key,
            encrypted_value=encrypted,
            environment=payload.environment,
            is_secret=payload.is_secret,
            created_by=self._actor_id(user),
        )
        try:
            row = self.repo.create_env_var(row)
        except IntegrityError as exc:
            self.db.rollback()
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=_DUPLICATE_KEY_MESSAGE) from exc
        except Exception as exc:  # noqa: BLE001
            self.db.rollback()
            logger.exception("static_site_env_var_create_failed site_id=%s", site.id)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=_GENERIC_FAILURE_MESSAGE
            ) from exc

        self._audit(
            company_id=site.workspace_id,
            actor_id=self._actor_id(user),
            action="static_site_env_var.create",
            resource_id=str(row.id),
            metadata={"site_id": str(site.id), "key": row.key, "environment": row.environment},
        )
        return StaticSiteEnvVarResponse.model_validate(row)

    def list_env_vars(
        self, user: UserProfileResponse, site_id: UUID, environment: Optional[str] = None
    ) -> StaticSiteEnvVarListResponse:
        self._require_env_manager(user)
        site = self._get_site(user, site_id)
        rows = self.repo.list_env_vars(site.id, site.workspace_id, environment=environment)
        return StaticSiteEnvVarListResponse(
            items=[StaticSiteEnvVarResponse.model_validate(r) for r in rows], total=len(rows)
        )

    def get_env_var(
        self, user: UserProfileResponse, site_id: UUID, env_id: UUID
    ) -> StaticSiteEnvVarResponse:
        self._require_env_manager(user)
        site = self._get_site(user, site_id)
        row = self._get_env_var(site, env_id)
        return StaticSiteEnvVarResponse.model_validate(row)

    def update_env_var(
        self,
        user: UserProfileResponse,
        site_id: UUID,
        env_id: UUID,
        payload: StaticSiteEnvVarUpdateRequest,
    ) -> StaticSiteEnvVarResponse:
        self._require_env_manager(user)
        site = self._get_site(user, site_id)
        row = self._get_env_var(site, env_id)

        resulting_is_secret = payload.is_secret if payload.is_secret is not None else row.is_secret
        try:
            check_secret_public_prefix(row.key, resulting_is_secret)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

        if payload.value is not None:
            try:
                row.encrypted_value = encrypt_value(payload.value)
            except EnvVarCryptoError as exc:
                logger.error("static_site_env_var_encrypt_failed site_id=%s env_id=%s", site.id, env_id)
                raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
        if payload.is_secret is not None:
            row.is_secret = payload.is_secret

        try:
            row = self.repo.save_env_var(row)
        except Exception as exc:  # noqa: BLE001
            self.db.rollback()
            logger.exception("static_site_env_var_update_failed site_id=%s env_id=%s", site.id, env_id)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=_GENERIC_FAILURE_MESSAGE
            ) from exc

        self._audit(
            company_id=site.workspace_id,
            actor_id=self._actor_id(user),
            action="static_site_env_var.update",
            resource_id=str(row.id),
            metadata={"site_id": str(site.id), "key": row.key, "environment": row.environment},
        )
        return StaticSiteEnvVarResponse.model_validate(row)

    def delete_env_var(self, user: UserProfileResponse, site_id: UUID, env_id: UUID) -> None:
        self._require_env_manager(user)
        site = self._get_site(user, site_id)
        row = self._get_env_var(site, env_id)

        key, environment = row.key, row.environment
        try:
            self.repo.delete_env_var(row)
        except Exception as exc:  # noqa: BLE001
            self.db.rollback()
            logger.exception("static_site_env_var_delete_failed site_id=%s env_id=%s", site.id, env_id)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=_GENERIC_FAILURE_MESSAGE
            ) from exc

        self._audit(
            company_id=site.workspace_id,
            actor_id=self._actor_id(user),
            action="static_site_env_var.delete",
            resource_id=str(env_id),
            metadata={"site_id": str(site.id), "key": key, "environment": environment},
        )
