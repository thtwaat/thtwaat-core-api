"""Helpers to render white-label email bodies from BrandingService context."""
from __future__ import annotations

from typing import Any, Dict, Optional
from uuid import UUID

from sqlalchemy.orm import Session


def render_branded_email(
    db: Session,
    company_id: UUID,
    template_key: str,
    variables: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Render welcome / password_reset / invoice / notification email using
    company branding templates. Reuses BrandingService — no duplicate store.
    """
    from app.branding.service import BrandingService

    ctx = BrandingService(db).resolve_email_context(company_id)
    variables = dict(variables or {})
    variables.setdefault("company_name", ctx["company_name"])
    body_tpl = (ctx.get("templates") or {}).get(template_key) or ""
    body = body_tpl
    for key, value in variables.items():
        body = body.replace("{{" + key + "}}", str(value))
        body = body.replace("{" + key + "}", str(value))
    return {
        "sender_name": ctx.get("sender_name"),
        "sender_email": ctx.get("sender_email"),
        "logo_url": ctx.get("logo_url"),
        "primary_color": ctx.get("primary_color"),
        "footer": ctx.get("footer"),
        "copyright": ctx.get("copyright"),
        "subject": f"{ctx['company_name']} — {template_key.replace('_', ' ').title()}",
        "body": body,
    }
