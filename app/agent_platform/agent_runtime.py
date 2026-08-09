"""Production agent runtime helpers — handoff, memory, locale, leads."""
from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

HANDOFF_STATUSES = frozenset({"pending_human", "human"})
AI_BLOCKED_STATUSES = frozenset({"pending_human", "human", "closed"})

logger = logging.getLogger(__name__)

DEFAULT_PROVIDER = "openai"
DEFAULT_MODEL = "gpt-4o-mini"

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


def slugify(value: str, fallback: str) -> str:
    """Lowercase, hyphenated slug from a name; falls back to ``fallback`` if empty."""
    base = re.sub(r"[^a-z0-9]+", "-", (value or "").lower()).strip("-")
    return base or fallback


def resolve_provider_and_model(agent: Any) -> Tuple[str, str]:
    """Prefer the first-class provider/model columns; fall back to web_config, then a default.

    Older agents (created before the ``provider``/``model`` columns existed) keep working
    unchanged via the ``web_config`` fallback.
    """
    web_config = getattr(agent, "web_config", None) or {}
    provider = getattr(agent, "provider", None) or web_config.get("provider") or DEFAULT_PROVIDER
    model = getattr(agent, "model", None) or web_config.get("model") or DEFAULT_MODEL
    return provider, model


def search_agent_knowledge(
    db: Any,
    agent_id: Any,
    query: str,
    company_id: Any,
    *,
    top_k: int = 5,
) -> List[Any]:
    """Search every knowledge base attached to an agent, merged and ranked by score.

    An agent can have more than one knowledge base attached (``KnowledgeBaseAgent`` is a
    many-to-many join table) — this searches all of them instead of only the first attachment.
    """
    from app.agent_platform.knowledge.models.knowledge_base import KnowledgeBaseAgent
    from app.agent_platform.knowledge.services import KnowledgeService

    attachments = (
        db.query(KnowledgeBaseAgent).filter(KnowledgeBaseAgent.agent_id == agent_id).all()
    )
    if not attachments:
        return []

    merged: List[Any] = []
    for attachment in attachments:
        try:
            merged.extend(
                KnowledgeService.search_knowledge_base(
                    db=db,
                    query=query,
                    top_k=top_k,
                    company_id=company_id,
                    kb_id=attachment.knowledge_base_id,
                )
            )
        except Exception as exc:
            logger.warning("Knowledge search failed for kb_id=%s: %s", attachment.knowledge_base_id, exc)

    merged.sort(key=lambda r: getattr(r, "score", 0.0), reverse=True)
    return merged[:top_k]


def build_tool_schemas(tool_names: Sequence[str]) -> List[Dict[str, Any]]:
    """Build OpenAI-style ``tools`` payloads for the given registered tool names."""
    from app.agent_platform.registries.tool_registry import ToolRegistry

    schemas = []
    for raw in ToolRegistry.get_schemas_for_tools(list(tool_names)):
        schemas.append(
            {
                "type": "function",
                "function": {
                    "name": raw["name"],
                    "description": raw["description"],
                    "parameters": raw["parameters"],
                },
            }
        )
    return schemas


async def maybe_execute_tool_calls(
    chat_request: Any,
    response: Any,
    *,
    db: Any,
    company_id: Any,
    agent_id: Any,
    usage_ctx: Optional[Dict[str, Any]] = None,
) -> Any:
    """If the model asked to call tools, execute them and issue one bounded follow-up call.

    Only wired for the OpenAI provider today (the only adapter that forwards ``tools`` /
    parses ``tool_calls`` — see ``app/agent_platform/providers/openai.py``). Other providers
    never populate ``response.tool_calls``, so this is a no-op for them — zero regression risk.
    Bounded to a single round: the follow-up request has ``tools=None``, so the model cannot
    trigger another round of tool calls.
    """
    if not getattr(response, "tool_calls", None):
        return response

    from app.agent_platform.gateway.service import AIGatewayService
    from app.agent_platform.registries.tool_registry import ToolRegistry

    tool_calls = response.tool_calls
    assistant_message: Dict[str, Any] = {
        "role": "assistant",
        "content": response.content or "",
        "tool_calls": tool_calls,
    }
    chat_request.messages.append(assistant_message)

    for call in tool_calls:
        function = call.get("function") or {}
        name = function.get("name")
        raw_args = function.get("arguments") or "{}"
        try:
            args = json.loads(raw_args) if isinstance(raw_args, str) else (raw_args or {})
        except (TypeError, ValueError):
            args = {}

        try:
            tool = ToolRegistry.get_tool(name)
            result = await tool.execute(db=db, company_id=company_id, agent_id=agent_id, **args)
            content = result if isinstance(result, str) else json.dumps(result, default=str)
        except Exception as exc:
            logger.warning("Tool execution failed for %s: %s", name, exc)
            content = f"Tool '{name}' failed: {exc}"

        chat_request.messages.append(
            {
                "role": "tool",
                "tool_call_id": call.get("id"),
                "content": content,
            }
        )

    chat_request.tools = None
    return await AIGatewayService.process_request(chat_request, db=db, **(usage_ctx or {}))
