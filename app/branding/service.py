"""
White-label branding service.

Reuses:
  - StorageService for uploads / URLs
  - DomainService for custom domain + SSL status (no DNS/SSL duplication)
  - CompanyRepository for logo_url sync + company identity
  - PublishService widget defaults (cascade only — does not replace agent overrides)
"""
from __future__ import annotations

import hashlib
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.branding.assets import validate_brand_upload
from app.branding.defaults import (
    css_variables_from,
    default_branding_kwargs,
    snapshot_from_row,
)
from app.branding.models import BrandingAsset, BrandingAssetType, CompanyBranding
from app.branding.repository import BrandingRepository
from app.branding.schemas import (
    BrandingAssetResponse,
    BrandingPreviewResponse,
    BrandingPublishResponse,
    BrandingResponse,
    BrandingUpdate,
    PublicBrandingResponse,
)
from app.companies.repository import CompanyRepository
from app.domains.service import DomainService
from app.storage.service import StorageService

logger = logging.getLogger(__name__)

ASSET_URL_FIELD: Dict[BrandingAssetType, str] = {
    BrandingAssetType.LOGO: "logo_url",
    BrandingAssetType.DARK_LOGO: "dark_logo_url",
    BrandingAssetType.FAVICON: "favicon_url",
    BrandingAssetType.LOGIN_BACKGROUND: "login_background_url",
}


class BrandingService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = BrandingRepository(db)
        self.companies = CompanyRepository(db)
        self.storage = StorageService(db)
        self.domains = DomainService(db)

    # ── Read / ensure ─────────────────────────────────────────────────────────

    def get_or_create(self, company_id: uuid.UUID) -> CompanyBranding:
        row = self.repo.get_by_company(company_id)
        if row:
            return row
        company = self.companies.get_by_id(company_id)
        if not company:
            raise HTTPException(status_code=404, detail="Company not found")
        kwargs = default_branding_kwargs(company.display_name or company.name)
        if company.logo_url:
            kwargs["logo_url"] = company.logo_url
        row = CompanyBranding(company_id=company_id, **kwargs)
        return self.repo.create(row)

    def get(self, company_id: uuid.UUID) -> BrandingResponse:
        row = self.get_or_create(company_id)
        return self._to_response(row)

    def update(self, company_id: uuid.UUID, body: BrandingUpdate) -> BrandingResponse:
        row = self.get_or_create(company_id)
        data = body.model_dump(exclude_unset=True)

        for key in (
            "company_name",
            "copyright_text",
            "footer_text",
            "primary_color",
            "secondary_color",
            "accent_color",
            "font_family",
            "heading_font",
            "dashboard_theme",
            "login_background_url",
            "logo_url",
            "dark_logo_url",
            "favicon_url",
        ):
            if key in data:
                setattr(row, key, data[key])

        if "email" in data and data["email"] is not None:
            merged = dict(row.email or {})
            merged.update({k: v for k, v in data["email"].items() if v is not None})
            if "templates" in data["email"] and data["email"]["templates"] is not None:
                templates = dict(merged.get("templates") or {})
                templates.update(
                    {k: v for k, v in data["email"]["templates"].items() if v is not None}
                )
                merged["templates"] = templates
            row.email = merged

        if "mobile" in data and data["mobile"] is not None:
            merged = dict(row.mobile or {})
            merged.update({k: v for k, v in data["mobile"].items() if v is not None})
            row.mobile = merged

        if "widget" in data and data["widget"] is not None:
            merged = dict(row.widget or {})
            merged.update({k: v for k, v in data["widget"].items() if v is not None})
            row.widget = merged

        if "domain_roles" in data and data["domain_roles"] is not None:
            merged = dict(row.domain_roles or {})
            merged.update({k: v for k, v in data["domain_roles"].items() if v is not None})
            row.domain_roles = merged

        row.draft_version = int(row.draft_version or 0) + 1
        self.repo.save(row)
        return self._to_response(row)

    # ── Assets (reuse StorageService) ─────────────────────────────────────────

    async def upload_asset(
        self,
        company_id: uuid.UUID,
        user_id: uuid.UUID,
        asset_type: BrandingAssetType,
        file: UploadFile,
    ) -> BrandingAssetResponse:
        row = self.get_or_create(company_id)
        _, size, width, height = await validate_brand_upload(file, asset_type)

        # StorageService performs its own MIME allow-list; map ico → png-friendly types already validated
        stored = await self.storage.upload_file(
            file=file,
            company_id=company_id,
            user_id=user_id,
        )
        url = self.storage.get_download_url(stored.id)

        version = self.repo.next_asset_version(company_id, asset_type)
        self.repo.deactivate_active_assets(company_id, asset_type)

        checksum = hashlib.sha256()
        # Re-read not available; use size + filename fingerprint
        checksum.update(f"{stored.id}:{stored.storage_filename}:{size}".encode())

        asset = BrandingAsset(
            company_id=company_id,
            branding_id=row.id,
            asset_type=asset_type,
            storage_file_id=stored.id,
            url=url,
            mime_type=stored.mime_type,
            size_bytes=stored.size_bytes or size,
            version=version,
            width=width,
            height=height,
            is_active=True,
            checksum=checksum.hexdigest()[:32],
        )
        asset = self.repo.add_asset(asset)

        self._apply_asset_url(row, asset_type, url)
        row.draft_version = int(row.draft_version or 0) + 1
        self.repo.save(row)

        return BrandingAssetResponse(
            id=asset.id,
            asset_type=asset.asset_type.value,
            url=asset.url,
            mime_type=asset.mime_type,
            size_bytes=asset.size_bytes,
            version=asset.version,
            width=asset.width,
            height=asset.height,
            is_active=asset.is_active,
            created_at=asset.created_at,
        )

    def _apply_asset_url(
        self, row: CompanyBranding, asset_type: BrandingAssetType, url: str
    ) -> None:
        field = ASSET_URL_FIELD.get(asset_type)
        if field:
            setattr(row, field, url)
            return
        if asset_type == BrandingAssetType.EMAIL_LOGO:
            email = dict(row.email or {})
            email["logo_url"] = url
            row.email = email
        elif asset_type == BrandingAssetType.SPLASH:
            mobile = dict(row.mobile or {})
            mobile["splash_url"] = url
            row.mobile = mobile
        elif asset_type == BrandingAssetType.LAUNCHER_ICON:
            mobile = dict(row.mobile or {})
            mobile["launcher_icon_url"] = url
            row.mobile = mobile
        elif asset_type == BrandingAssetType.WIDGET_LAUNCHER:
            widget = dict(row.widget or {})
            widget["launcher_icon_url"] = url
            row.widget = widget
        elif asset_type == BrandingAssetType.WIDGET_HEADER:
            widget = dict(row.widget or {})
            widget["header_logo_url"] = url
            row.widget = widget

    # ── Preview / publish / reset ─────────────────────────────────────────────

    def preview(self, company_id: uuid.UUID) -> BrandingPreviewResponse:
        branding = self.get(company_id)
        row = self.get_or_create(company_id)
        snap = snapshot_from_row(row)

        domain_payload: List[Dict[str, Any]] = []
        try:
            for d in self.domains.list(company_id):
                domain_payload.append(
                    {
                        "id": str(d.id),
                        "hostname": d.hostname,
                        "status": d.status,
                        "ssl_status": d.ssl_status,
                        "is_primary": d.is_primary,
                    }
                )
        except Exception as exc:
            logger.warning("branding preview domains: %s", exc)

        roles = snap.get("domain_roles") or {}
        for role, host in roles.items():
            if host and not any(x.get("hostname") == host for x in domain_payload):
                domain_payload.append(
                    {
                        "id": None,
                        "hostname": host,
                        "status": "UNLINKED",
                        "ssl_status": None,
                        "role": role,
                        "hint": "Add this hostname via Domain Manager for SSL/verification",
                    }
                )

        email = snap.get("email") or {}
        company_name = snap.get("company_name") or "Company"
        templates = dict(email.get("templates") or {})
        email_preview = {
            "from": f"{email.get('sender_name') or company_name} <{email.get('sender_email') or 'noreply@example.com'}>",
            "logo_url": email.get("logo_url") or snap.get("logo_url"),
            "samples": {
                k: (v or "").replace("{{company_name}}", company_name) for k, v in templates.items()
            },
        }

        return BrandingPreviewResponse(
            branding=branding,
            published=row.published_snapshot if row.is_published else None,
            domains=domain_payload,
            css_variables=css_variables_from(snap),
            widget_preview=dict(snap.get("widget") or {}),
            email_preview=email_preview,
            mobile_preview=dict(snap.get("mobile") or {}),
        )

    def publish(self, company_id: uuid.UUID) -> BrandingPublishResponse:
        """
        Atomically publish draft → published_snapshot (zero downtime).
        Syncs company.logo_url and cascades widget defaults for agents without custom widget.
        Domain SSL remains DomainService / Deploy responsibility.
        """
        row = self.get_or_create(company_id)
        snap = snapshot_from_row(row)
        row.published_snapshot = snap
        row.published_version = int(row.draft_version or 1)
        row.published_at = datetime.now(timezone.utc)
        row.is_published = True
        self.repo.save(row)

        applied: Dict[str, Any] = {"company_logo": False, "widget_defaults": 0}

        company = self.companies.get_by_id(company_id)
        if company and snap.get("logo_url"):
            company.logo_url = snap["logo_url"]
            if snap.get("company_name") and not company.display_name:
                company.display_name = snap["company_name"]
            self.db.add(company)
            self.db.commit()
            applied["company_logo"] = True

        applied["widget_defaults"] = self._cascade_widget_defaults(company_id, snap.get("widget") or {})

        return BrandingPublishResponse(
            branding=self._to_response(row),
            published_version=row.published_version,
            applied=applied,
        )

    def reset(self, company_id: uuid.UUID) -> BrandingResponse:
        company = self.companies.get_by_id(company_id)
        if not company:
            raise HTTPException(status_code=404, detail="Company not found")
        row = self.get_or_create(company_id)
        defaults = default_branding_kwargs(company.display_name or company.name)
        for key, value in defaults.items():
            if key in ("draft_version", "published_version", "published_snapshot", "published_at", "is_published"):
                continue
            setattr(row, key, value)
        row.draft_version = int(row.draft_version or 0) + 1
        # Keep last published snapshot until next publish (no downtime for live tenants)
        self.repo.save(row)
        return self._to_response(row)

    def _cascade_widget_defaults(self, company_id: uuid.UUID, widget: Dict[str, Any]) -> int:
        """Fill empty agent widget keys from company branding — does not overwrite custom values."""
        try:
            from app.agent_platform.models.agent import AgentConfig
        except Exception:
            return 0

        agents = (
            self.db.query(AgentConfig)
            .filter(AgentConfig.company_id == company_id)
            .all()
        )
        updated = 0
        for agent in agents:
            web = dict(agent.web_config or {})
            current = dict(web.get("widget") or {})
            changed = False
            mapping = {
                "primary_color": widget.get("primary_color") or widget.get("bubble_color"),
                "theme": widget.get("chat_theme"),
                "logo": widget.get("header_logo_url") or widget.get("launcher_icon_url"),
                "avatar": widget.get("launcher_icon_url"),
                "font_family": widget.get("font_family"),
                "suggested_prompts": widget.get("suggested_prompts"),
            }
            for key, value in mapping.items():
                if value and not current.get(key):
                    current[key] = value
                    changed = True
            if changed:
                web["widget"] = current
                agent.web_config = web
                self.db.add(agent)
                updated += 1
        if updated:
            self.db.commit()
        return updated

    # ── Public resolve ────────────────────────────────────────────────────────

    def public_branding(
        self,
        *,
        company_id: Optional[uuid.UUID] = None,
        slug: Optional[str] = None,
        hostname: Optional[str] = None,
    ) -> PublicBrandingResponse:
        company = None
        if company_id:
            company = self.companies.get_by_id(company_id)
        elif slug:
            company = self.companies.get_by_slug(slug)
        elif hostname:
            from sqlalchemy import select

            from app.domains.models import CompanyDomain

            domain = self.db.scalar(
                select(CompanyDomain).where(CompanyDomain.hostname == hostname.lower())
            )
            if domain:
                company = self.companies.get_by_id(domain.company_id)

        if not company:
            raise HTTPException(status_code=404, detail="Branding not found")

        row = self.repo.get_by_company(company.id)
        if row and row.is_published and row.published_snapshot:
            branding = dict(row.published_snapshot)
            version = row.published_version
        elif row:
            branding = snapshot_from_row(row)
            version = row.draft_version
        else:
            raw = default_branding_kwargs(company.display_name or company.name)
            branding = {
                k: v
                for k, v in raw.items()
                if k
                not in (
                    "draft_version",
                    "published_version",
                    "published_snapshot",
                    "published_at",
                    "is_published",
                )
            }
            version = 0

        return PublicBrandingResponse(
            company_id=company.id,
            company_slug=company.slug,
            version=version,
            branding=branding,
            css_variables=css_variables_from(branding),
        )

    def resolve_email_context(self, company_id: uuid.UUID) -> Dict[str, Any]:
        """Used by notification/email layer — no duplicate template engine."""
        row = self.repo.get_by_company(company_id)
        if row and row.is_published and row.published_snapshot:
            snap = row.published_snapshot
        elif row:
            snap = snapshot_from_row(row)
        else:
            company = self.companies.get_by_id(company_id)
            name = (company.display_name or company.name) if company else "THTWAAT"
            snap = default_branding_kwargs(name)
        email = dict(snap.get("email") or {})
        return {
            "company_name": snap.get("company_name") or "THTWAAT",
            "logo_url": email.get("logo_url") or snap.get("logo_url"),
            "sender_name": email.get("sender_name") or snap.get("company_name"),
            "sender_email": email.get("sender_email"),
            "primary_color": snap.get("primary_color"),
            "templates": dict(email.get("templates") or {}),
            "footer": snap.get("footer_text"),
            "copyright": snap.get("copyright_text"),
        }

    def widget_defaults_for_company(self, company_id: uuid.UUID) -> Dict[str, Any]:
        row = self.repo.get_by_company(company_id)
        if row and row.is_published and row.published_snapshot:
            return dict((row.published_snapshot or {}).get("widget") or {})
        if row:
            return dict(row.widget or {})
        return {}

    # ── Mapping ───────────────────────────────────────────────────────────────

    def _to_response(self, row: CompanyBranding) -> BrandingResponse:
        assets = [
            BrandingAssetResponse(
                id=a.id,
                asset_type=a.asset_type.value if hasattr(a.asset_type, "value") else str(a.asset_type),
                url=a.url,
                mime_type=a.mime_type,
                size_bytes=a.size_bytes,
                version=a.version,
                width=a.width,
                height=a.height,
                is_active=a.is_active,
                created_at=a.created_at,
            )
            for a in self.repo.list_assets(row.company_id, active_only=True)
        ]
        return BrandingResponse(
            id=row.id,
            company_id=row.company_id,
            company_name=row.company_name,
            copyright_text=row.copyright_text,
            footer_text=row.footer_text,
            primary_color=row.primary_color,
            secondary_color=row.secondary_color,
            accent_color=row.accent_color,
            font_family=row.font_family,
            heading_font=row.heading_font,
            dashboard_theme=row.dashboard_theme,
            login_background_url=row.login_background_url,
            logo_url=row.logo_url,
            dark_logo_url=row.dark_logo_url,
            favicon_url=row.favicon_url,
            email=dict(row.email or {}),
            mobile=dict(row.mobile or {}),
            widget=dict(row.widget or {}),
            domain_roles=dict(row.domain_roles or {}),
            draft_version=row.draft_version,
            published_version=row.published_version,
            is_published=row.is_published,
            published_at=row.published_at,
            assets=assets,
        )
