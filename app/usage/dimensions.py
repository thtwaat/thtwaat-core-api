"""Usage dimension constants and default plan limits."""
from __future__ import annotations

from enum import Enum
from typing import Dict


class UsageDimension(str, Enum):
    AI_MESSAGES = "ai_messages"
    CONVERSATIONS = "conversations"
    PROMPT_TOKENS = "prompt_tokens"
    COMPLETION_TOKENS = "completion_tokens"
    TOTAL_TOKENS = "total_tokens"
    API_REQUESTS = "api_requests"
    WIDGET_REQUESTS = "widget_requests"
    KNOWLEDGE_SEARCHES = "knowledge_searches"
    KNOWLEDGE_UPLOAD_BYTES = "knowledge_upload_bytes"
    STORAGE_BYTES = "storage_bytes"
    AGENTS_COUNT = "agents_count"
    ACTIVE_USERS = "active_users"
    API_KEYS = "api_keys"
    DOMAINS = "domains"
    TEMPLATES_PUBLISHED = "templates_published"
    # THTWAAT Deploy Phase 6A — Preview Deployments.
    PREVIEW_DEPLOYMENTS = "preview_deployments"
    # Part 3 — Voice AI + AI Calling. No CompanyUsageMeter columns / plan
    # limits yet (see UsageService.record) — recorded as raw UsageEvent /
    # daily-aggregate rows for analytics/billing today, not yet quota-enforced.
    AUDIO_INPUT_SECONDS = "audio_input_seconds"
    AUDIO_OUTPUT_SECONDS = "audio_output_seconds"
    CALL_COUNT = "call_count"
    CALL_MINUTES = "call_minutes"
    # Part 4 — Image Generation. Same "raw event, not yet quota-enforced"
    # treatment as the Part 3 dimensions above.
    IMAGES_GENERATED = "images_generated"


# Gauge dimensions are set absolute (not incremented) when syncing inventory
GAUGE_DIMENSIONS = {
    UsageDimension.AGENTS_COUNT,
    UsageDimension.ACTIVE_USERS,
    UsageDimension.API_KEYS,
    UsageDimension.DOMAINS,
    UsageDimension.TEMPLATES_PUBLISHED,
    UsageDimension.STORAGE_BYTES,
    UsageDimension.PREVIEW_DEPLOYMENTS,
}


class PlanTier:
    FREE = "free"
    STARTER = "starter"
    PRO = "pro"
    BUSINESS = "business"
    ENTERPRISE = "enterprise"


# Canonical limits used when Plan row lacks explicit columns / for FREE defaults
DEFAULT_PLAN_LIMITS: Dict[str, Dict[str, int]] = {
    PlanTier.FREE: {
        "max_agents": 1,
        "max_messages": 100,
        "max_tokens": 50_000,
        "max_storage": 100 * 1024 * 1024,  # 100MB
        # Allow one custom domain so Domains UI works on trial/free without upgrade.
        "max_domains": 1,
        "max_team_members": 5,
        "max_api_keys": 1,
        "max_templates": 0,
        "max_apps": 1,
        "max_users": 5,
        "max_preview_deployments": 1,
    },
    PlanTier.STARTER: {
        "max_agents": 5,
        "max_messages": 5_000,
        "max_tokens": 1_000_000,
        "max_storage": 1 * 1024 * 1024 * 1024,
        "max_domains": 1,
        "max_team_members": 25,
        "max_api_keys": 5,
        "max_templates": 3,
        "max_apps": 5,
        "max_users": 25,
        "max_preview_deployments": 3,
    },
    PlanTier.PRO: {
        "max_agents": 25,
        "max_messages": 50_000,
        "max_tokens": 10_000_000,
        "max_storage": 10 * 1024 * 1024 * 1024,
        "max_domains": 5,
        "max_team_members": 100,
        "max_api_keys": 25,
        "max_templates": 20,
        "max_apps": 25,
        "max_users": 100,
        "max_preview_deployments": 10,
    },
    "growth": {  # alias → Pro
        "max_agents": 25,
        "max_messages": 50_000,
        "max_tokens": 10_000_000,
        "max_storage": 10 * 1024 * 1024 * 1024,
        "max_domains": 5,
        "max_team_members": 100,
        "max_api_keys": 25,
        "max_templates": 20,
        "max_apps": 25,
        "max_users": 100,
        "max_preview_deployments": 10,
    },
    PlanTier.BUSINESS: {
        "max_agents": 100,
        "max_messages": 250_000,
        "max_tokens": 50_000_000,
        "max_storage": 50 * 1024 * 1024 * 1024,
        "max_domains": 25,
        "max_team_members": 500,
        "max_api_keys": 100,
        "max_templates": 100,
        "max_apps": 100,
        "max_users": 500,
        "max_preview_deployments": 50,
    },
    PlanTier.ENTERPRISE: {
        "max_agents": 10_000,
        "max_messages": 10_000_000,
        "max_tokens": 1_000_000_000,
        "max_storage": 500 * 1024 * 1024 * 1024,
        "max_domains": 1_000,
        "max_team_members": 10_000,
        "max_api_keys": 1_000,
        "max_templates": 10_000,
        "max_apps": 1_000,
        "max_users": 10_000,
        "max_preview_deployments": 1_000,
    },
}

DIMENSION_TO_LIMIT = {
    UsageDimension.AI_MESSAGES: "max_messages",
    UsageDimension.TOTAL_TOKENS: "max_tokens",
    UsageDimension.PROMPT_TOKENS: "max_tokens",
    UsageDimension.COMPLETION_TOKENS: "max_tokens",
    UsageDimension.STORAGE_BYTES: "max_storage",
    UsageDimension.KNOWLEDGE_UPLOAD_BYTES: "max_storage",
    UsageDimension.AGENTS_COUNT: "max_agents",
    UsageDimension.DOMAINS: "max_domains",
    UsageDimension.ACTIVE_USERS: "max_team_members",
    UsageDimension.API_KEYS: "max_api_keys",
    UsageDimension.TEMPLATES_PUBLISHED: "max_templates",
    UsageDimension.PREVIEW_DEPLOYMENTS: "max_preview_deployments",
}


def resolve_plan_key(name: str | None) -> str:
    if not name:
        return PlanTier.FREE
    key = name.strip().lower()
    if key in DEFAULT_PLAN_LIMITS:
        return key
    if key in ("pro", "professional"):
        return PlanTier.PRO
    return PlanTier.FREE


def limits_for_plan(name: str | None) -> Dict[str, int]:
    return dict(DEFAULT_PLAN_LIMITS[resolve_plan_key(name)])
