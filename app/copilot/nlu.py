"""Deterministic NLU — intent detection + slot extraction (no duplicated LLM business logic)."""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from app.copilot.intents import INTENT_PATTERNS, CopilotIntent


def detect_intent(text: str) -> Tuple[CopilotIntent, float, List[str]]:
    """Return (intent, confidence 0..1, matched_keywords)."""
    lowered = (text or "").strip().lower()
    if not lowered:
        return CopilotIntent.UNKNOWN, 0.0, []

    best: Optional[CopilotIntent] = None
    best_score = 0
    matched: List[str] = []

    for rule in INTENT_PATTERNS:
        hits = [kw for kw in rule["keywords"] if kw in lowered]
        if not hits:
            continue
        score = len(hits) * int(rule["weight"])
        # Prefer longer keyword matches
        score += max(len(h) for h in hits)
        if score > best_score:
            best_score = score
            best = rule["intent"]
            matched = hits

    if best is None:
        # Soft heuristics for product-like prompts
        if any(w in lowered for w in ("chatbot", "assistant", "landing", "support bot")):
            return CopilotIntent.GENERATE_PRODUCT, 0.55, ["heuristic"]
        return CopilotIntent.UNKNOWN, 0.2, []

    # Normalize confidence
    confidence = min(0.99, 0.45 + (best_score / 40.0))
    return best, round(confidence, 2), matched


def extract_slots(text: str, intent: CopilotIntent, memory: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Pull structured args from natural language + conversation memory."""
    memory = memory or {}
    slots: Dict[str, Any] = {}
    raw = text or ""
    lowered = raw.lower()

    # Email
    email_m = re.search(r"[\w.+-]+@[\w-]+\.[\w.-]+", raw)
    if email_m:
        slots["email"] = email_m.group(0)

    # Hostname / domain — prefer explicit "domain <host>" then bare hostnames
    host = None
    host_m = re.search(
        r"\bdomain\s+[\"']?([a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)+)",
        lowered,
    )
    if host_m:
        host = host_m.group(1)
    else:
        bare = re.search(
            r"\b([a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)+)\b",
            lowered,
        )
        if bare and "@" not in bare.group(1):
            host = bare.group(1)
    if host:
        slots["hostname"] = host

    # Template slug after "template"
    tmpl = re.search(r"template\s+[\"']?([a-z0-9][a-z0-9-]{1,80})", lowered)
    if tmpl:
        slots["template_slug"] = tmpl.group(1)

    # Agent name
    agent_name = re.search(
        r"(?:named|called|name(?:d)?)\s+[\"']([^\"']{2,80})[\"']",
        raw,
        re.IGNORECASE,
    )
    if agent_name:
        slots["agent_name"] = agent_name.group(1)
    else:
        # "create agent Support Bot"
        m2 = re.search(r"create(?:\s+an?)?\s+agent\s+([A-Za-z0-9][\w\s-]{1,60})", raw, re.IGNORECASE)
        if m2 and intent == CopilotIntent.CREATE_AGENT:
            slots["agent_name"] = m2.group(1).strip()

    # UUIDs in text
    uuids = re.findall(
        r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b",
        lowered,
    )
    if uuids:
        slots["ids"] = uuids
        if intent == CopilotIntent.PUBLISH_WEBSITE:
            slots["agent_id"] = uuids[0]
        if intent == CopilotIntent.RETRY_FAILED_JOB:
            slots.setdefault("job_index", 0)

    # Branding color
    color = re.search(r"#([0-9a-fA-F]{6})\b", raw)
    if color:
        slots["primary_color"] = f"#{color.group(1)}"

    # Organization name
    org = re.search(
        r"(?:organization|org|department|team)\s+(?:named\s+)?[\"']?([A-Za-z0-9][\w\s-]{1,60})",
        raw,
        re.IGNORECASE,
    )
    if org and intent == CopilotIntent.CREATE_ORGANIZATION:
        slots["unit_name"] = org.group(1).strip()

    # Product prompt — use full user text for generator intents
    if intent in (CopilotIntent.GENERATE_PRODUCT,):
        slots["prompt"] = raw.strip()

    if intent == CopilotIntent.SHOW_REPORTS:
        if "weekly" in lowered:
            slots["period"] = "weekly"
        elif "monthly" in lowered:
            slots["period"] = "monthly"
        else:
            slots["period"] = "daily"

    if intent == CopilotIntent.CONFIGURE_BRANDING and "publish" in lowered:
        slots["publish"] = True

    # Inherit memory (agent_id, generation_id, knowledge_base_id, …)
    for key in (
        "agent_id",
        "generation_id",
        "knowledge_base_id",
        "installation_id",
        "domain_id",
        "template_slug",
        "agent_name",
    ):
        if key not in slots and memory.get(key):
            slots[key] = memory[key]

    return slots


def missing_required_slots(intent: CopilotIntent, slots: Dict[str, Any]) -> List[str]:
    required: Dict[CopilotIntent, List[str]] = {
        CopilotIntent.INSTALL_TEMPLATE: ["template_slug"],
        CopilotIntent.CONNECT_DOMAIN: ["hostname"],
        CopilotIntent.INVITE_MEMBERS: ["email"],
        CopilotIntent.PUBLISH_WEBSITE: [],  # can fall back to memory / latest agent
        CopilotIntent.GENERATE_PRODUCT: ["prompt"],
    }
    need = required.get(intent, [])
    return [k for k in need if not slots.get(k)]
