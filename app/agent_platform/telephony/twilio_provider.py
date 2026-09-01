"""Twilio telephony adapter.

Deliberately does NOT depend on the ``twilio`` SDK — signature verification
is a well-documented HMAC-SHA1 scheme (https://www.twilio.com/docs/usage/security#validating-requests)
and call-control responses are plain TwiML XML strings, so this stays a
zero-new-dependency adapter, consistent with how the rest of this codebase's
webhook verification is hand-rolled (see app/static_sites/github_webhook.py,
app/payments/webhooks/router.py's Razorpay HMAC check).

Twilio speaks its own STT ("Gather input=speech") and TTS ("Say") at the
carrier edge — the caller's raw audio never reaches our servers. That keeps
telephony working without any WebSocket media-stream / audio-codec
infrastructure (none exists in this repo yet). The AI brain is still
AgentRuntime: Twilio's Gather produces text (SpeechResult), that text is the
``user_content`` fed into AgentRuntime.run_turn, and the text reply comes
back out through Twilio's <Say>.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import logging
from typing import Mapping, Optional
from xml.sax.saxutils import escape as xml_escape

from app.agent_platform.telephony.base import TelephonyProvider, TelephonyProviderRegistry
from app.config.settings import settings

logger = logging.getLogger(__name__)

# Twilio's <Gather>/<Say> "language" attribute wants a full locale tag, not a
# bare ISO-639-1 code — map the handful this platform already knows about
# (see agent_runtime._LOCALE_NAMES) and fall back to en-US.
_TWILIO_LOCALES = {
    "en": "en-US",
    "hi": "hi-IN",
    "es": "es-ES",
    "fr": "fr-FR",
    "de": "de-DE",
    "pt": "pt-BR",
    "ar": "en-US",  # Twilio's classic <Say> voice has no Arabic support; keep prompts audible.
    "ja": "ja-JP",
    "ko": "ko-KR",
    "zh": "zh-CN",
    "it": "it-IT",
    "nl": "nl-NL",
    "ru": "ru-RU",
}


def _twilio_locale(language: Optional[str]) -> str:
    return _TWILIO_LOCALES.get((language or "").lower(), "en-US")


def compute_twilio_signature(auth_token: str, url: str, params: Mapping[str, str]) -> str:
    """https://www.twilio.com/docs/usage/security#validating-requests"""
    buf = url
    for key in sorted(params.keys()):
        buf += key + params[key]
    mac = hmac.new(auth_token.encode("utf-8"), buf.encode("utf-8"), hashlib.sha1)
    return base64.b64encode(mac.digest()).decode("utf-8")


def verify_twilio_signature(
    auth_token: Optional[str],
    url: str,
    params: Mapping[str, str],
    signature_header: Optional[str],
) -> bool:
    """Constant-time verification. Returns False (never raises) on any
    missing/malformed input — the caller maps every False to the same 401."""
    if not auth_token or not signature_header or not url:
        return False
    try:
        expected = compute_twilio_signature(auth_token, url, dict(params))
        return hmac.compare_digest(expected, signature_header)
    except (TypeError, ValueError, UnicodeError):
        return False


class TwilioProvider(TelephonyProvider):
    name = "twilio"

    def verify_webhook(
        self,
        *,
        url: str,
        form_params: Mapping[str, str],
        signature_header: Optional[str],
    ) -> bool:
        return verify_twilio_signature(settings.TWILIO_AUTH_TOKEN, url, form_params, signature_header)

    def build_say_and_gather(
        self,
        *,
        text: str,
        gather_action_url: str,
        voice_id: Optional[str] = None,
        language: Optional[str] = None,
        fallback_text: Optional[str] = None,
    ) -> str:
        lang = _twilio_locale(language)
        fallback = fallback_text or "We didn't hear anything. Goodbye."
        return (
            '<?xml version="1.0" encoding="UTF-8"?>'
            "<Response>"
            f'<Gather input="speech" action="{xml_escape(gather_action_url)}" '
            f'method="POST" speechTimeout="auto" language="{xml_escape(lang)}">'
            f"<Say>{xml_escape(text)}</Say>"
            "</Gather>"
            f"<Say>{xml_escape(fallback)}</Say>"
            "<Hangup/>"
            "</Response>"
        )

    def build_say_and_hangup(self, *, text: str) -> str:
        return (
            '<?xml version="1.0" encoding="UTF-8"?>'
            "<Response>"
            f"<Say>{xml_escape(text)}</Say>"
            "<Hangup/>"
            "</Response>"
        )

    def build_say_and_dial(self, *, text: str, phone_number: str) -> str:
        return (
            '<?xml version="1.0" encoding="UTF-8"?>'
            "<Response>"
            f"<Say>{xml_escape(text)}</Say>"
            f"<Dial>{xml_escape(phone_number)}</Dial>"
            "</Response>"
        )

    def build_reject(self) -> str:
        return '<?xml version="1.0" encoding="UTF-8"?><Response><Reject/></Response>'


TelephonyProviderRegistry.register("twilio", TwilioProvider)
