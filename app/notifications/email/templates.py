"""Safe HTML + plaintext email bodies for auth (password reset / welcome)."""
from __future__ import annotations

import re
from html import escape
from typing import Tuple


def render_password_reset_link_email(reset_url: str) -> Tuple[str, str, str]:
    """Return ``(subject, html_body, text_body)`` for a password-reset link."""
    subject = "Reset your password"
    intro = "Click the link below to choose a new password. It expires in about an hour."
    safe_url = escape(str(reset_url))
    text = (
        "Reset your password\n\n"
        f"{intro}\n\n"
        f"{reset_url}\n\n"
        "If you did not request this, you can ignore this email.\n"
    )
    html = f"""<!DOCTYPE html>
<html><body style="font-family:system-ui,sans-serif;line-height:1.5;color:#111">
  <h2 style="margin-bottom:8px">Reset your password</h2>
  <p>{escape(intro)}</p>
  <p><a href="{safe_url}" style="color:#0f766e;font-weight:600">Choose a new password</a></p>
  <p style="color:#666;font-size:13px">If you did not request this, you can ignore this email.</p>
</body></html>"""
    return subject, html, text


def render_welcome_email(*, first_name: str = "") -> Tuple[str, str, str]:
    """Optional welcome email after email signup (no verification OTP)."""
    name = (first_name or "").strip() or "there"
    subject = "Welcome to THTWAAT"
    intro = f"Hi {name}, your account is ready. Sign in anytime with your email and password."
    text = f"{subject}\n\n{intro}\n"
    html = f"""<!DOCTYPE html>
<html><body style="font-family:system-ui,sans-serif;line-height:1.5;color:#111">
  <h2 style="margin-bottom:8px">{escape(subject)}</h2>
  <p>{escape(intro)}</p>
</body></html>"""
    return subject, html, text


def html_to_plaintext_fallback(html: str) -> str:
    """Minimal HTML → text fallback when only HTML is supplied."""
    text = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", html)
    text = re.sub(r"(?is)<br\s*/?>", "\n", text)
    text = re.sub(r"(?is)</p>", "\n\n", text)
    text = re.sub(r"(?is)<[^>]+>", " ", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()
