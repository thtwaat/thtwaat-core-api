"""Production agent runtime helpers — handoff, memory, locale, leads."""
from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from fastapi import HTTPException

HANDOFF_STATUSES = frozenset({"pending_human", "human"})
AI_BLOCKED_STATUSES = frozenset({"pending_human", "human", "closed"})

logger = logging.getLogger(__name__)

DEFAULT_PROVIDER = "openai"
DEFAULT_MODEL = "gpt-4o-mini"

# Provider -> model-name prefixes known to accept image content blocks via the
# standard chat-completions API. Minimal allowlist, not a full capability
# registry — extend as new vision-capable providers/models are verified.
VISION_CAPABLE_MODELS: Dict[str, Tuple[str, ...]] = {
    "openai": ("gpt-4o", "gpt-4.1", "gpt-5", "o4", "o3"),
}

_SYSTEM_PROMPT_TEMPLATE = """\
You are a helpful, accurate assistant. Answer the user's question using ONLY \
the context provided below. If the answer is not in the context, say \
"I don't have enough information to answer that."

Context:
{context}
"""

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
        # "knowledge" is the canonical key; "rag" is kept as a read fallback
        # since the agent builder UI has historically written that key.
        "knowledge": caps.get("knowledge", caps.get("rag", True)),
        "lead_capture": caps.get("lead_capture", True),
        "multilingual": caps.get("multilingual", True),
        "vision": caps.get("vision", False),
        # Voice (STT/TTS turns) and calling (telephony) — both default off so
        # existing agents (including Viral Awaaz) are unaffected until a
        # company explicitly opts in via web_config.capabilities.
        "voice": caps.get("voice", False),
        "calling": caps.get("calling", False),
        # Image generation (text prompt -> generated image). Default off so
        # existing agents are unaffected until a company explicitly opts in.
        "image_generation": caps.get("image_generation", False),
    }


DEFAULT_VOICE_PROVIDER = "openai"
DEFAULT_VOICE_ID = "alloy"
DEFAULT_TTS_SPEED = 1.0


def resolve_voice_config(agent: Any) -> Dict[str, Any]:
    """Read ``web_config.voice`` with safe defaults — mirrors ``resolve_provider_and_model``.

    Shape: ``{"provider": "openai", "voice_id": "alloy", "language": None, "speed": 1.0}``.
    """
    web_config = getattr(agent, "web_config", None) or {}
    raw = web_config.get("voice") if isinstance(web_config, dict) else None
    raw = raw if isinstance(raw, dict) else {}
    speed = raw.get("speed", DEFAULT_TTS_SPEED)
    try:
        speed = float(speed)
    except (TypeError, ValueError):
        speed = DEFAULT_TTS_SPEED
    return {
        "provider": str(raw.get("provider") or DEFAULT_VOICE_PROVIDER),
        "voice_id": str(raw.get("voice_id") or DEFAULT_VOICE_ID),
        "language": normalize_locale(raw.get("language")),
        "speed": speed,
    }


def resolve_calling_config(agent: Any) -> Dict[str, Any]:
    """Read ``web_config.calling`` with safe defaults.

    Shape: ``{"provider": "twilio", "phone_number": None, "voice_id": "alloy",
    "language": None, "greeting": <default>, "human_handoff": False,
    "human_handoff_number": None}``.
    """
    web_config = getattr(agent, "web_config", None) or {}
    raw = web_config.get("calling") if isinstance(web_config, dict) else None
    raw = raw if isinstance(raw, dict) else {}
    return {
        "provider": str(raw.get("provider") or "twilio"),
        "phone_number": raw.get("phone_number") or None,
        "voice_id": str(raw.get("voice_id") or DEFAULT_VOICE_ID),
        "language": normalize_locale(raw.get("language")),
        "greeting": str(raw.get("greeting") or "Hello! How can I help you today?"),
        "human_handoff": bool(raw.get("human_handoff", False)),
        "human_handoff_number": raw.get("human_handoff_number") or None,
    }


DEFAULT_IMAGE_PROVIDER = "openai"
DEFAULT_IMAGE_MODEL = "dall-e-3"
DEFAULT_IMAGE_SIZE = "1024x1024"
DEFAULT_IMAGE_QUALITY = "standard"

# Provider -> model names known to support image generation. Mirrors
# VISION_CAPABLE_MODELS's shape/spirit — minimal allowlist, not a full
# capability registry.
IMAGE_GENERATION_CAPABLE_MODELS: Dict[str, Tuple[str, ...]] = {
    "openai": ("dall-e-3", "dall-e-2", "gpt-image-1"),
}


def resolve_image_generation_config(agent: Any) -> Dict[str, Any]:
    """Read ``web_config.image_generation`` with safe defaults.

    Shape: ``{"provider": "openai", "model": "dall-e-3", "size": "1024x1024",
    "quality": "standard"}``. Deliberately independent of
    ``resolve_provider_and_model`` (the chat LLM's provider/model) — image
    generation is a distinct provider call, not a chat-completion capability.
    """
    web_config = getattr(agent, "web_config", None) or {}
    raw = web_config.get("image_generation") if isinstance(web_config, dict) else None
    raw = raw if isinstance(raw, dict) else {}
    return {
        "provider": str(raw.get("provider") or DEFAULT_IMAGE_PROVIDER),
        "model": str(raw.get("model") or DEFAULT_IMAGE_MODEL),
        "size": str(raw.get("size") or DEFAULT_IMAGE_SIZE),
        "quality": str(raw.get("quality") or DEFAULT_IMAGE_QUALITY),
    }


def provider_model_supports_image_generation(provider: str, model: str) -> bool:
    """Whether the given provider/model combo can generate images."""
    allowed = IMAGE_GENERATION_CAPABLE_MODELS.get((provider or "").lower(), ())
    return (model or "").lower() in {m.lower() for m in allowed}


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


def build_rag_system_prompt(
    agent: Any,
    *,
    locale: Optional[str],
    sources: Sequence[Any],
    caps: Mapping[str, Any],
) -> str:
    """Build the system prompt, injecting retrieved knowledge context when present.

    Extracted from the (previously duplicated) inline logic in
    ``ConversationService.send_message`` and ``chat_runtime.iter_public_chat_events``.
    """
    base_prompt = getattr(agent, "system_prompt_template", None) or "You are a helpful assistant."
    if not sources:
        system_prompt = base_prompt
        if caps.get("multilingual", True):
            system_prompt = system_prompt + language_system_instruction(locale)
        return system_prompt

    context_blocks = [
        f"[{i}] (Source: {src.document_name})\n{src.text}" for i, src in enumerate(sources, start=1)
    ]
    context = "\n\n---\n\n".join(context_blocks)
    system_prompt = _SYSTEM_PROMPT_TEMPLATE.format(context=context) + "\n\nOriginal Instructions: " + base_prompt
    if caps.get("multilingual", True):
        system_prompt = system_prompt + language_system_instruction(locale)
    return system_prompt


def build_gateway_messages(
    system_prompt: str,
    conv_messages: Sequence[Any],
    *,
    memory_enabled: bool,
    max_messages: int = 40,
) -> List[Dict[str, Any]]:
    """Build the ``{role, content}`` message list sent to the AI Gateway."""
    prior = memory_message_window(conv_messages, enabled=memory_enabled, max_messages=max_messages)
    messages: List[Dict[str, Any]] = [{"role": "system", "content": system_prompt}]
    for msg in prior:
        role = to_gateway_role(msg.role)
        if role in ("user", "assistant", "system", "tool"):
            messages.append({"role": role, "content": msg.content})
    return messages


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


def provider_model_supports_vision(provider: str, model: str) -> bool:
    """Whether the given provider/model combo accepts image content blocks."""
    prefixes = VISION_CAPABLE_MODELS.get((provider or "").lower(), ())
    m = (model or "").lower()
    return any(m.startswith(p) for p in prefixes)


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


class AgentRuntime:
    """Shared execution core for a single agent turn.

    Resolves provider/model, runs RAG retrieval, builds the system prompt and
    memory-windowed message list, calls the AI Gateway, and runs the bounded
    tool-call follow-up. Both ``ConversationService`` (dashboard) and
    ``chat_runtime`` (public widget) delegate the "compute the reply" step to
    this — everything path-specific (session resumption, lead capture, keyword
    handoff, SSE shaping, as_human) stays in the caller.
    """

    @staticmethod
    def resolve_context(db: Any, agent: Any, company_id: Any, query: str, *, top_k: int = 5) -> List[Any]:
        return search_agent_knowledge(db, agent.id, query, company_id, top_k=top_k)

    @staticmethod
    def check_voice_request(caps: Mapping[str, Any]) -> None:
        """Raise HTTPException(400) if the agent's voice capability isn't enabled."""
        if not caps.get("voice", False):
            raise HTTPException(
                status_code=400,
                detail="This agent does not have the voice capability enabled.",
            )

    @staticmethod
    def check_calling_request(caps: Mapping[str, Any]) -> None:
        """Raise HTTPException(400) if the agent's calling capability isn't enabled."""
        if not caps.get("calling", False):
            raise HTTPException(
                status_code=400,
                detail="This agent does not have the calling capability enabled.",
            )

    @staticmethod
    def check_image_generation_request(caps: Mapping[str, Any], provider: str, model: str) -> None:
        """Raise HTTPException(400) if image generation isn't enabled, or the
        configured provider/model can't generate images."""
        if not caps.get("image_generation", False):
            raise HTTPException(
                status_code=400,
                detail="This agent does not have the image generation capability enabled.",
            )
        if not provider_model_supports_image_generation(provider, model):
            raise HTTPException(
                status_code=400,
                detail=f"Model '{provider}/{model}' does not support image generation.",
            )

    @staticmethod
    def check_vision_request(agent: Any, caps: Mapping[str, Any], has_image: bool) -> None:
        """Raise HTTPException(400) if an image was sent but the agent/model
        combo can't handle it. No-op when ``has_image`` is False."""
        if not has_image:
            return
        if not caps.get("vision", False):
            raise HTTPException(
                status_code=400,
                detail="This agent does not have the vision capability enabled.",
            )
        provider, model = resolve_provider_and_model(agent)
        if not provider_model_supports_vision(provider, model):
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Model '{provider}/{model}' does not support image input. "
                    "Vision requires an OpenAI GPT-4o-class model."
                ),
            )

    @staticmethod
    async def run_turn(
        db: Any,
        *,
        agent: Any,
        company_id: Any,
        conv_messages: Sequence[Any],
        user_content: str,
        locale: Optional[str],
        provider: str,
        model: str,
        temperature: float,
        max_tokens: int = 1024,
        image_blocks: Optional[List[Dict[str, Any]]] = None,
        usage_ctx: Optional[Dict[str, Any]] = None,
    ) -> Tuple[Any, List[Any]]:
        """Run one agent turn and return ``(UnifiedChatResponse, sources)``.

        ``user_content`` is the current turn's raw message text, used as the RAG
        query (matches prior behavior exactly). ``conv_messages`` must already
        include the current turn's persisted user message (both callers
        persist-then-refresh before calling this) — the image blocks, when
        present, are spliced onto its content rather than requiring a separate
        parameter for that.
        """
        from app.agent_platform.gateway.service import AIGatewayService
        from app.agent_platform.schemas import UnifiedChatRequest

        caps = agent_capabilities(getattr(agent, "web_config", None))
        AgentRuntime.check_vision_request(agent, caps, bool(image_blocks))

        try:
            sources = AgentRuntime.resolve_context(db, agent, company_id, user_content)
        except Exception as exc:
            logger.warning("Knowledge retrieval failed for agent_id=%s: %s", agent.id, exc)
            sources = []

        system_prompt = build_rag_system_prompt(agent, locale=locale, sources=sources, caps=caps)
        messages = build_gateway_messages(
            system_prompt, conv_messages, memory_enabled=caps.get("memory", True)
        )

        if image_blocks and messages and messages[-1]["role"] == "user":
            text_content = messages[-1]["content"]
            messages[-1] = {
                "role": "user",
                "content": [{"type": "text", "text": text_content}, *image_blocks],
            }

        allowed_tools = getattr(agent, "allowed_tools", None) or []
        chat_request = UnifiedChatRequest(
            company_id=str(company_id),
            agent_id=str(agent.id),
            provider=provider,
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            tools=build_tool_schemas(allowed_tools) if allowed_tools else None,
        )

        response = await AIGatewayService.process_request(chat_request, db=db, **(usage_ctx or {}))
        if getattr(response, "tool_calls", None):
            response = await maybe_execute_tool_calls(
                chat_request,
                response,
                db=db,
                company_id=company_id,
                agent_id=agent.id,
                usage_ctx=usage_ctx,
            )
        return response, sources
