"""Safe HTML + plaintext email bodies for auth OTP / verification / reset."""
from __future__ import annotations

import re
from html import escape
from typing import Tuple


def render_security_code_email(
    code: str,
    *,
    purpose: str = "verification",
) -> Tuple[str, str, str]:
    """
    Return ``(subject, html_body, text_body)``.

    ``code`` is embedded in the message only — callers must never log it.
    """
    purpose_l = (purpose or "verification").lower()
    if "password" in purpose_l or "reset" in purpose_l:
        subject = "Reset your password"
        headline = "Password reset code"
        intro = "Use this code to reset your password. It expires in a few minutes."
    elif "email" in purpose_l or "verify" in purpose_l:
        subject = "Verify your email"
        headline = "Email verification code"
        intro = "Use this code to verify your email address. It expires in a few minutes."
    else:
        subject = "Your verification code"
        headline = "Verification code"
        intro = "Use this one-time code to continue. It expires in a few minutes."

    safe_code = escape(str(code))
    text = (
        f"{headline}\n\n"
        f"{intro}\n\n"
        f"Code: {code}\n\n"
        "If you did not request this, you can ignore this email.\n"
    )
    html = f"""<!DOCTYPE html>
<html><body style="font-family:system-ui,sans-serif;line-height:1.5;color:#111">
  <h2 style="margin-bottom:8px">{escape(headline)}</h2>
  <p>{escape(intro)}</p>
  <p style="font-size:28px;letter-spacing:4px;font-weight:700">{safe_code}</p>
  <p style="color:#666;font-size:13px">If you did not request this, you can ignore this email.</p>
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
