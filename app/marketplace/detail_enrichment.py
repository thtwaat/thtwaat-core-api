"""Additive template detail enrichment from config + capability flags.

Keeps catalog rows sparse: long-form store copy lives in default_config JSONB
(or agent_store listing bridge) without new breaking columns.

This module must never raise for catalog browse/home rails — malformed
``default_config`` is common on older rows.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

FEATURE_CATALOG = (
    ("ai_chat", "AI Chat", "Conversational agent experiences"),
    ("knowledge_base", "Knowledge Base", "RAG over company documents"),
    ("widget", "Widget", "Embeddable chat widget"),
    ("api", "API", "Programmatic access via API keys"),
    ("automation", "Automation", "Workflow and trigger automation"),
    ("analytics", "Analytics", "Usage and performance insights"),
    ("multilingual", "Multilingual", "Multi-language conversations"),
    ("rag", "RAG", "Retrieval-augmented generation"),
    ("human_handoff", "Human Handoff", "Escalate to a human agent"),
    ("webhooks", "Webhooks", "Outbound event delivery"),
)


def _as_dict(value: Any) -> Dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    return {}


def _as_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, str):
        text = value.strip()
        return [text] if text else []
    if isinstance(value, (list, tuple, set)):
        out: List[str] = []
        for item in value:
            if isinstance(item, dict):
                label = item.get("label") or item.get("name") or item.get("title") or item.get("key")
                if label:
                    out.append(str(label))
            else:
                s = str(item).strip()
                if s:
                    out.append(s)
        return out
    if isinstance(value, dict):
        # e.g. {"openai": true} or {"0": "en"}
        return [str(k) for k, v in value.items() if v not in (None, False, "")]
    return [str(value)]


def _as_str(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, (dict, list, tuple, set)):
        return None
    text = str(value).strip()
    return text or None


def derive_permissions(template: Any, cfg: Dict[str, Any]) -> List[str]:
    explicit = _as_list(cfg.get("permissions") or cfg.get("required_permissions"))
    if explicit:
        return explicit
    perms: List[str] = []
    tags = [str(t).lower() for t in (getattr(template, "tags", None) or [])]
    if getattr(template, "supports_agents", False):
        perms.append("Agents")
    if cfg.get("knowledge") or cfg.get("knowledge_base") or "knowledge" in tags:
        perms.append("Knowledge")
    if getattr(template, "supports_domains", False) or cfg.get("widget"):
        perms.append("Widget")
    if cfg.get("webhooks") or "webhooks" in tags or "webhook" in tags:
        perms.append("Webhooks")
    perms.append("API Keys")
    if getattr(template, "supports_billing", False) or cfg.get("analytics"):
        perms.append("Analytics")
    seen = set()
    ordered: List[str] = []
    for p in perms:
        if p not in seen:
            seen.add(p)
            ordered.append(p)
    return ordered


def derive_feature_keys(template: Any, cfg: Dict[str, Any]) -> List[str]:
    explicit = _as_list(cfg.get("feature_keys") or cfg.get("capabilities"))
    keys: List[str] = [k.lower().replace(" ", "_") for k in explicit]
    tags = {str(t).lower().replace(" ", "_") for t in (getattr(template, "tags", None) or [])}
    features_raw = cfg.get("features")
    if isinstance(features_raw, list):
        for item in features_raw:
            if isinstance(item, str):
                keys.append(item.lower().replace(" ", "_"))
            elif isinstance(item, dict) and item.get("key"):
                keys.append(str(item["key"]).lower().replace(" ", "_"))

    def add(key: str, cond: bool) -> None:
        if cond and key not in keys:
            keys.append(key)

    add("ai_chat", bool(getattr(template, "supports_agents", False) or "agent" in tags))
    add("knowledge_base", "knowledge" in tags or bool(cfg.get("knowledge") or cfg.get("prompt")))
    add("widget", bool(getattr(template, "supports_domains", False) or cfg.get("widget")))
    add("api", True)
    add("automation", "automation" in tags or bool(cfg.get("automation")))
    add("analytics", bool(getattr(template, "supports_billing", False) or cfg.get("analytics")))
    add("multilingual", "multilingual" in tags or bool(cfg.get("languages")))
    add("rag", "rag" in tags or bool(cfg.get("rag")))
    add("human_handoff", "handoff" in tags or bool(cfg.get("human_handoff")))
    add("webhooks", "webhook" in tags or "webhooks" in tags or bool(cfg.get("webhooks")))
    seen = set()
    out: List[str] = []
    for k in keys:
        if k not in seen:
            seen.add(k)
            out.append(k)
    return out


def feature_cards_for(keys: List[str]) -> List[Dict[str, str]]:
    by_key = {k: {"key": k, "title": title, "description": desc} for k, title, desc in FEATURE_CATALOG}
    cards: List[Dict[str, str]] = []
    for key in keys:
        if key in by_key:
            cards.append(by_key[key])
        else:
            title = key.replace("_", " ").title()
            cards.append({"key": key, "title": title, "description": title})
    if not cards:
        for k, title, desc in FEATURE_CATALOG[:4]:
            cards.append({"key": k, "title": title, "description": desc})
    return cards


def enrich_detail_fields(template: Any, bridge: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Return additive TemplateResponse field updates. Never raises."""
    try:
        return _enrich_detail_fields_unsafe(template, bridge)
    except Exception:
        logger.exception(
            "detail enrichment failed for template=%s",
            getattr(template, "slug", getattr(template, "id", "?")),
        )
        return {
            "listing_id": (bridge or {}).get("listing_id"),
            "what_it_does": _as_str(getattr(template, "description", None)),
            "best_for": [],
            "use_cases": [],
            "industries": [],
            "languages": [],
            "license": "THTWAAT Marketplace License",
            "permissions": ["API Keys"],
            "feature_cards": feature_cards_for(["api"]),
            "docs_markdown": None,
            "quick_start": None,
            "installation_docs": None,
            "configuration_docs": None,
            "examples_docs": None,
            "support_url": None,
            "website_url": None,
            "docs_url": None,
            "min_platform_version": None,
            "supported_providers": [],
            "dependencies": [],
            "compatibility": getattr(template, "compatibility", None),
            "publisher_bio": None,
            "publisher_website": None,
        }


def _enrich_detail_fields_unsafe(
    template: Any, bridge: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    raw_cfg = getattr(template, "default_config", None)
    cfg = _as_dict(raw_cfg)
    store = _as_dict(cfg.get("store") or cfg.get("marketplace"))
    bridge = bridge or {}

    languages = _as_list(
        store.get("languages")
        or cfg.get("languages")
        or bridge.get("supported_languages")
    )
    use_cases = _as_list(store.get("use_cases") or cfg.get("use_cases"))
    best_for = _as_list(store.get("best_for") or cfg.get("best_for"))
    industries = _as_list(
        store.get("industries")
        or cfg.get("industries")
        or ([template.industry] if getattr(template, "industry", None) else [])
    )

    what_it_does = _as_str(store.get("what_it_does") or cfg.get("what_it_does") or cfg.get("summary"))
    if not what_it_does:
        what_it_does = _as_str(getattr(template, "description", None))

    docs_markdown = _as_str(
        store.get("docs_markdown")
        or cfg.get("docs_markdown")
        or cfg.get("docs")
        or cfg.get("readme")
    )
    quick_start = _as_str(store.get("quick_start") or cfg.get("quick_start"))
    installation_docs = _as_str(store.get("installation") or cfg.get("installation"))
    configuration_docs = _as_str(store.get("configuration") or cfg.get("configuration"))
    examples_docs = _as_str(store.get("examples") or cfg.get("examples") or cfg.get("example_output"))

    requirements = store.get("requirements") or cfg.get("requirements") or {}
    if not isinstance(requirements, dict):
        requirements = {"notes": str(requirements)} if requirements not in (None, "") else {}

    supported_providers = _as_list(
        requirements.get("supported_providers")
        or store.get("supported_providers")
        or cfg.get("supported_providers")
        or cfg.get("model_hint")
    )
    min_platform_version = _as_str(
        requirements.get("min_platform_version")
        or store.get("min_platform_version")
        or cfg.get("min_platform_version")
    )
    dependencies = _as_list(requirements.get("dependencies") or store.get("dependencies"))

    license_name = _as_str(store.get("license") or cfg.get("license") or "THTWAAT Marketplace License")
    support_url = _as_str(store.get("support_url") or cfg.get("support_url") or bridge.get("support_url"))
    website_url = _as_str(store.get("website") or cfg.get("website") or bridge.get("website"))
    docs_url = _as_str(store.get("docs_url") or cfg.get("docs_url"))

    merged = {**cfg, **store}
    feature_keys = derive_feature_keys(template, merged)
    compatibility = _as_str(
        getattr(template, "compatibility", None)
        or store.get("compatibility")
        or cfg.get("compatibility")
        or (", ".join(supported_providers) if supported_providers else None)
    )

    return {
        "listing_id": bridge.get("listing_id"),
        "what_it_does": what_it_does,
        "best_for": best_for,
        "use_cases": use_cases,
        "industries": industries,
        "languages": languages,
        "license": license_name,
        "permissions": derive_permissions(template, merged),
        "feature_cards": feature_cards_for(feature_keys),
        "docs_markdown": docs_markdown,
        "quick_start": quick_start,
        "installation_docs": installation_docs,
        "configuration_docs": configuration_docs,
        "examples_docs": examples_docs,
        "support_url": support_url,
        "website_url": website_url,
        "docs_url": docs_url,
        "min_platform_version": min_platform_version,
        "supported_providers": supported_providers,
        "dependencies": dependencies,
        "compatibility": compatibility or getattr(template, "compatibility", None),
        "publisher_bio": _as_str(bridge.get("publisher_bio")),
        "publisher_website": _as_str(bridge.get("publisher_website") or website_url),
    }
