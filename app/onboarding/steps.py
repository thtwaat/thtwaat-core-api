"""Canonical 12-step onboarding definition (UX order + metadata)."""
from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List


class OnboardingStep(str, Enum):
    CREATE_ACCOUNT = "create_account"
    VERIFY_EMAIL = "verify_email"
    CREATE_COMPANY = "create_company"
    CHOOSE_PLAN = "choose_plan"
    CREATE_AI_AGENT = "create_ai_agent"
    UPLOAD_KNOWLEDGE = "upload_knowledge"
    CHOOSE_TEMPLATE = "choose_template"
    GENERATE_PRODUCT = "generate_product"
    PREVIEW = "preview"
    PUBLISH = "publish"
    CONNECT_DOMAIN = "connect_domain"
    GO_LIVE = "go_live"


class OnboardingStatus(str, Enum):
    IN_PROGRESS = "in_progress"
    PAUSED = "paused"
    COMPLETED = "completed"
    ABANDONED = "abandoned"


class StepEventType(str, Enum):
    ENTERED = "entered"
    AUTOSAVED = "autosaved"
    COMPLETED = "completed"
    SKIPPED = "skipped"
    FAILED = "failed"
    PAUSED = "paused"
    RESUMED = "resumed"


# Ordered flow — do not reorder without a migration note.
STEP_ORDER: List[OnboardingStep] = [
    OnboardingStep.CREATE_ACCOUNT,
    OnboardingStep.VERIFY_EMAIL,
    OnboardingStep.CREATE_COMPANY,
    OnboardingStep.CHOOSE_PLAN,
    OnboardingStep.CREATE_AI_AGENT,
    OnboardingStep.UPLOAD_KNOWLEDGE,
    OnboardingStep.CHOOSE_TEMPLATE,
    OnboardingStep.GENERATE_PRODUCT,
    OnboardingStep.PREVIEW,
    OnboardingStep.PUBLISH,
    OnboardingStep.CONNECT_DOMAIN,
    OnboardingStep.GO_LIVE,
]

# Optional steps may be skipped without blocking progress.
OPTIONAL_STEPS = {
    OnboardingStep.VERIFY_EMAIL,
    OnboardingStep.UPLOAD_KNOWLEDGE,
    OnboardingStep.CHOOSE_TEMPLATE,  # Product Generator can select a template
    OnboardingStep.CONNECT_DOMAIN,  # Can go live on platform subdomain
}

STEP_META: Dict[OnboardingStep, Dict[str, Any]] = {
    OnboardingStep.CREATE_ACCOUNT: {
        "title": "Create Account",
        "description": "Register your owner account (email + password).",
        "estimated_minutes": 2,
        "integration": "users",
        "optional": False,
    },
    OnboardingStep.VERIFY_EMAIL: {
        "title": "Verify Email",
        "description": "Email is confirmed automatically at signup (OTP removed).",
        "estimated_minutes": 0,
        "integration": "auth",
        "optional": True,
    },
    OnboardingStep.CREATE_COMPANY: {
        "title": "Create Company",
        "description": "Set up your tenant company profile.",
        "estimated_minutes": 3,
        "integration": "companies",
        "optional": False,
    },
    OnboardingStep.CHOOSE_PLAN: {
        "title": "Choose Plan",
        "description": "Select a billing plan or continue on Free.",
        "estimated_minutes": 3,
        "integration": "billing",
        "optional": False,
    },
    OnboardingStep.CREATE_AI_AGENT: {
        "title": "Create AI Agent",
        "description": "Provision your first draft AI agent.",
        "estimated_minutes": 4,
        "integration": "agent_platform",
        "optional": False,
    },
    OnboardingStep.UPLOAD_KNOWLEDGE: {
        "title": "Upload Knowledge",
        "description": "Attach a knowledge base / documents (optional).",
        "estimated_minutes": 5,
        "integration": "knowledge",
        "optional": True,
    },
    OnboardingStep.CHOOSE_TEMPLATE: {
        "title": "Choose Template",
        "description": "Install a marketplace template (optional if generating).",
        "estimated_minutes": 3,
        "integration": "marketplace",
        "optional": True,
    },
    OnboardingStep.GENERATE_PRODUCT: {
        "title": "Generate Product",
        "description": "Run the AI Product Generator for your use case.",
        "estimated_minutes": 8,
        "integration": "product_generator",
        "optional": False,
    },
    OnboardingStep.PREVIEW: {
        "title": "Preview",
        "description": "Review preview URL, widget snippet, and checklist.",
        "estimated_minutes": 3,
        "integration": "product_generator",
        "optional": False,
    },
    OnboardingStep.PUBLISH: {
        "title": "Publish",
        "description": "Publish the agent / product installation.",
        "estimated_minutes": 3,
        "integration": "publish",
        "optional": False,
    },
    OnboardingStep.CONNECT_DOMAIN: {
        "title": "Connect Domain",
        "description": "Attach a custom domain (optional).",
        "estimated_minutes": 5,
        "integration": "domains",
        "optional": True,
    },
    OnboardingStep.GO_LIVE: {
        "title": "Go Live",
        "description": "Finalize branding and mark onboarding complete.",
        "estimated_minutes": 2,
        "integration": "branding",
        "optional": False,
    },
}


def step_index(step: OnboardingStep) -> int:
    return STEP_ORDER.index(step)


def next_incomplete_step(
    completed: List[str],
    skipped: List[str],
) -> OnboardingStep | None:
    done = set(completed) | set(skipped)
    for step in STEP_ORDER:
        if step.value not in done:
            return step
    return None


def estimated_minutes_remaining(completed: List[str], skipped: List[str]) -> int:
    done = set(completed) | set(skipped)
    return sum(
        int(STEP_META[s]["estimated_minutes"])
        for s in STEP_ORDER
        if s.value not in done
    )


def total_estimated_minutes() -> int:
    return sum(int(STEP_META[s]["estimated_minutes"]) for s in STEP_ORDER)


def build_checklist(completed: List[str], skipped: List[str]) -> List[Dict[str, Any]]:
    done = set(completed)
    skipped_set = set(skipped)
    items: List[Dict[str, Any]] = []
    for step in STEP_ORDER:
        meta = STEP_META[step]
        status = "pending"
        if step.value in done:
            status = "completed"
        elif step.value in skipped_set:
            status = "skipped"
        items.append(
            {
                "step": step.value,
                "title": meta["title"],
                "optional": meta["optional"],
                "status": status,
                "estimated_minutes": meta["estimated_minutes"],
                "integration": meta["integration"],
            }
        )
    return items


def flow_definition() -> List[Dict[str, Any]]:
    return [
        {
            "order": i + 1,
            "step": step.value,
            **STEP_META[step],
        }
        for i, step in enumerate(STEP_ORDER)
    ]
