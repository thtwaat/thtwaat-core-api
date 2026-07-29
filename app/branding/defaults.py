"""Default white-label branding payloads."""
from __future__ import annotations

from typing import Any, Dict


DEFAULT_EMAIL: Dict[str, Any] = {
    "sender_name": None,
    "sender_email": None,
    "logo_url": None,
    "templates": {
        "welcome": (
            "Welcome to {{company_name}}!\n\n"
            "Your account is ready. Sign in to get started."
        ),
        "password_reset": (
            "Reset your {{company_name}} password\n\n"
            "Use this code: {{code}}\n"
            "If you did not request a reset, ignore this email."
        ),
        "invoice": (
            "Invoice {{invoice_number}} from {{company_name}}\n\n"
            "Amount: {{amount}} {{currency}}\n"
            "Status: {{status}}"
        ),
        "notification": "{{title}}\n\n{{body}}\n\n— {{company_name}}",
    },
}

DEFAULT_MOBILE: Dict[str, Any] = {
    "app_name": None,
    "android_package": None,
    "ios_bundle_id": None,
    "splash_url": None,
    "launcher_icon_url": None,
    "primary_color": "#0F766E",
    "secondary_color": "#134E4A",
}

DEFAULT_WIDGET: Dict[str, Any] = {
    "launcher_icon_url": None,
    "chat_theme": "light",
    "bubble_color": "#0F766E",
    "header_logo_url": None,
    "suggested_prompts": ["Pricing?", "Book appointment", "Contact support"],
    "primary_color": "#0F766E",
    "font_family": "Inter, system-ui, sans-serif",
}

DEFAULT_DOMAIN_ROLES: Dict[str, Any] = {
    "app": None,
    "api": None,
    "chat": None,
}


def default_branding_kwargs(company_name: str | None = None) -> Dict[str, Any]:
    name = company_name or "THTWAAT"
    email = {**DEFAULT_EMAIL, "sender_name": name}
    email["templates"] = dict(DEFAULT_EMAIL["templates"])
    mobile = {**DEFAULT_MOBILE, "app_name": name}
    return {
        "company_name": name,
        "copyright_text": f"© {name}. All rights reserved.",
        "footer_text": name,
        "primary_color": "#0F766E",
        "secondary_color": "#134E4A",
        "accent_color": "#F59E0B",
        "font_family": "Inter, system-ui, sans-serif",
        "heading_font": None,
        "dashboard_theme": "system",
        "login_background_url": None,
        "logo_url": None,
        "dark_logo_url": None,
        "favicon_url": None,
        "email": email,
        "mobile": mobile,
        "widget": dict(DEFAULT_WIDGET),
        "domain_roles": dict(DEFAULT_DOMAIN_ROLES),
        "draft_version": 1,
        "published_version": 0,
        "published_snapshot": None,
        "published_at": None,
        "is_published": False,
    }


def css_variables_from(branding_dict: Dict[str, Any]) -> Dict[str, str]:
    return {
        "--brand-primary": branding_dict.get("primary_color") or "#0F766E",
        "--brand-secondary": branding_dict.get("secondary_color") or "#134E4A",
        "--brand-accent": branding_dict.get("accent_color") or "#F59E0B",
        "--brand-font": branding_dict.get("font_family") or "Inter, system-ui, sans-serif",
        "--brand-heading-font": branding_dict.get("heading_font")
        or branding_dict.get("font_family")
        or "Inter, system-ui, sans-serif",
    }


def snapshot_from_row(row) -> Dict[str, Any]:
    """Serialize ORM branding row to a publishable JSON snapshot."""
    return {
        "company_name": row.company_name,
        "copyright_text": row.copyright_text,
        "footer_text": row.footer_text,
        "primary_color": row.primary_color,
        "secondary_color": row.secondary_color,
        "accent_color": row.accent_color,
        "font_family": row.font_family,
        "heading_font": row.heading_font,
        "dashboard_theme": row.dashboard_theme,
        "login_background_url": row.login_background_url,
        "logo_url": row.logo_url,
        "dark_logo_url": row.dark_logo_url,
        "favicon_url": row.favicon_url,
        "email": dict(row.email or {}),
        "mobile": dict(row.mobile or {}),
        "widget": dict(row.widget or {}),
        "domain_roles": dict(row.domain_roles or {}),
    }
