"""Production agent runtime helpers — handoff, memory, locale, leads."""
from __future__ import annotations

import re
from typing import Any, Dict, List, Mapping, Optional, Sequence

HANDOFF_STATUSES = frozenset({"pending_human", "human"})
AI_BLOCKED_STATUSES = frozenset({"pending_human", "human", "closed"})

_HANDOFF_PATTERNS = (
    r"\btalk to (a )?human\b",
    r"\bspeak to (a )?(human|agent|person)\b",
    r"\breal person\b",
    r"\bhuman (please|agent|support)\b",
    r"\bcustomer (support|service)\b",
    r"\bhand ?off\b",
    r"\blive agent\b",
    r"\bagent please\b",
)

_HANDOFF_RE = re.compile("|".join(_HANDOFF_PATTERNS), re.IGNORECASE)

# Common locale → reply language instruction
_LOCALE_NAMES = {
    "en": "English",
    "hi": "Hindi",
    "es": "Spanish",
    "fr": "French",
    "de": "German",
    "pt": "Portuguese",
    "ar": "Arabic",
    "ja": "Japanese",
    "ko": "Korean",
    "zh": "Chinese",
    "it": "Italian",
    "nl": "Dutch",
    "tr": "Turkish",
    "ru": "Russian",
}


def agent_capabilities(web_config: Optional[Mapping[str, Any]]) -> Dict[str, bool]:
    caps = {}
    if isinstance(web_config, dict):
        raw = web_config.get("capabilities") or {}
        if isinstance(raw, dict):
            caps = {str(k): bool(v) for k, v in raw.items()}
    return {
        "memory": caps.get("memory", True),
        "handoff": caps.get("handoff", True),
        "tools": caps.get("tools", False),
        "lead_capture": caps.get("lead_capture", True),
        "multilingual": caps.get("multilingual", True),
    }


def detect_handoff_intent(message: str) -> bool:
    text = (message or "").strip()
    if not text:
        return False
    return bool(_HANDOFF_RE.search(text))


def normalize_locale(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    raw = str(value).strip().replace("_", "-")
    if not raw:
        return None
    primary = raw.split("-")[0].lower()
    return primary[:8] if primary else None


def resolve_locale(
    *,
    metadata: Optional[Mapping[str, Any]] = None,
    web_config: Optional[Mapping[str, Any]] = None,
) -> Optional[str]:
    meta = metadata or {}
    for key in ("locale", "language", "lang"):
        code = normalize_locale(meta.get(key) if isinstance(meta, Mapping) else None)
        if code:
            return code
    if isinstance(web_config, dict):
        for key in ("locale", "language", "default_locale"):
            code = normalize_locale(web_config.get(key))
            if code:
                return code
    return None


def language_system_instruction(locale: Optional[str]) -> str:
    code = normalize_locale(locale)
    if not code:
        return ""
    name = _LOCALE_NAMES.get(code, code)
    return (
        f"\n\nLanguage policy: Reply in {name} ({code}). "
        "Match the visitor's language when they write in another language."
    )


def handoff_wait_message(locale: Optional[str] = None) -> str:
    code = normalize_locale(locale) or "en"
    messages = {
        "en": "Connecting you with a human teammate. Please wait — they can see this chat.",
        "hi": "आपको एक मानव प्रतिनिधि से जोड़ा जा रहा है। कृपया प्रतीक्षा करें।",
        "es": "Te estamos conectando con un compañero humano. Por favor espera.",
        "fr": "Nous vous mettons en relation avec un conseiller humain. Veuillez patienter.",
        "de": "Wir verbinden Sie mit einem menschlichen Mitarbeiter. Bitte warten.",
        "ar": "نقوم بتوصيلك بمندوب بشري. يرجى الانتظار.",
    }
    return messages.get(code, messages["en"])


def conversation_closed_message(locale: Optional[str] = None) -> str:
    code = normalize_locale(locale) or "en"
    messages = {
        "en": "This conversation is closed. Start a new chat if you still need help.",
        "hi": "यह बातचीत बंद है। मदद के लिए नई चैट शुरू करें।",
        "es": "Esta conversación está cerrada. Inicia un nuevo chat si aún necesitas ayuda.",
    }
    return messages.get(code, messages["en"])


def extract_lead(metadata: Optional[Mapping[str, Any]]) -> Optional[Dict[str, Any]]:
    """Normalize lead payload from public metadata."""
    if not metadata:
        return None
    raw = metadata.get("lead") if isinstance(metadata, Mapping) else None
    if not isinstance(raw, dict):
        # Flat identifyUser style
        email = metadata.get("email") if isinstance(metadata, Mapping) else None
        name = metadata.get("name") if isinstance(metadata, Mapping) else None
        phone = metadata.get("phone") if isinstance(metadata, Mapping) else None
        if not any([email, name, phone]):
            return None
        raw = {"email": email, "name": name, "phone": phone}

    lead: Dict[str, Any] = {}
    for key in ("name", "email", "phone", "company", "message", "source"):
        val = raw.get(key)
        if val is not None and str(val).strip():
            lead[key] = str(val).strip()[:500]
    if not lead.get("email") and not lead.get("phone") and not lead.get("name"):
        return None
    lead.setdefault("source", "widget")
    return lead


def merge_lead_into_metadata(
    existing: Optional[Mapping[str, Any]],
    lead: Dict[str, Any],
) -> Dict[str, Any]:
    out = dict(existing or {})
    prev = dict(out.get("lead") or {}) if isinstance(out.get("lead"), dict) else {}
    prev.update(lead)
    out["lead"] = prev
    # Mirror common fields for inbox search
    if prev.get("email"):
        out["email"] = prev["email"]
    if prev.get("name"):
        out["name"] = prev["name"]
    return out


def memory_message_window(
    messages: Sequence[Any],
    *,
    enabled: bool = True,
    max_messages: int = 40,
) -> List[Any]:
    """Return prior messages for the model (role user/assistant/human/system/tool)."""
    allowed = {"user", "assistant", "human", "system", "tool"}
    filtered = [m for m in messages if getattr(m, "role", None) in allowed]
    if not enabled:
        # Still include the latest user turn if present
        return list(filtered[-2:]) if filtered else []
    if max_messages > 0 and len(filtered) > max_messages:
        return list(filtered[-max_messages:])
    return list(filtered)


def to_gateway_role(role: str) -> str:
    """Map stored roles onto OpenAI-compatible roles."""
    if role == "human":
        return "assistant"
    return role
