"""Copilot intents, workflows, and tool catalog metadata."""
from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional


class CopilotIntent(str, Enum):
    CREATE_AGENT = "create_agent"
    GENERATE_PRODUCT = "generate_product"
    INSTALL_TEMPLATE = "install_template"
    UPLOAD_KNOWLEDGE = "upload_knowledge"
    PUBLISH_WEBSITE = "publish_website"
    CONFIGURE_BRANDING = "configure_branding"
    CONNECT_DOMAIN = "connect_domain"
    CREATE_ORGANIZATION = "create_organization"
    INVITE_MEMBERS = "invite_members"
    SHOW_REPORTS = "show_reports"
    VIEW_MONITORING = "view_monitoring"
    RETRY_FAILED_JOB = "retry_failed_job"
    SHOW_HEALTH = "show_health"
    LIST_TOOLS = "list_tools"
    HELP = "help"
    UNKNOWN = "unknown"


class TaskStatus(str, Enum):
    PLANNED = "planned"
    AWAITING_CONFIRMATION = "awaiting_confirmation"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class StepStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    AWAITING_CONFIRMATION = "awaiting_confirmation"


class MessageRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    TOOL = "tool"


# Tools that mutate production state and require explicit confirmation.
DESTRUCTIVE_TOOLS = {
    "publish_agent",
    "publish_product",
    "publish_branding",
    "connect_domain",
    "invite_member",
    "retry_failed_job",
    "cancel_job",
}


TOOL_CATALOG: List[Dict[str, Any]] = [
    {
        "name": "create_agent",
        "integration": "agents",
        "description": "Create a draft AI agent via AgentConfig",
        "destructive": False,
    },
    {
        "name": "generate_product",
        "integration": "product_generator",
        "description": "Run ProductGeneratorService.generate",
        "destructive": False,
    },
    {
        "name": "analyze_prompt",
        "integration": "product_generator",
        "description": "Analyze a product prompt",
        "destructive": False,
    },
    {
        "name": "install_template",
        "integration": "marketplace",
        "description": "Install a marketplace template",
        "destructive": False,
    },
    {
        "name": "create_knowledge_base",
        "integration": "knowledge",
        "description": "Create a knowledge base",
        "destructive": False,
    },
    {
        "name": "publish_agent",
        "integration": "publish",
        "description": "Publish an agent via PublishService",
        "destructive": True,
    },
    {
        "name": "publish_product",
        "integration": "product_generator",
        "description": "Publish a generated product",
        "destructive": True,
    },
    {
        "name": "update_branding",
        "integration": "branding",
        "description": "Update draft branding",
        "destructive": False,
    },
    {
        "name": "publish_branding",
        "integration": "branding",
        "description": "Publish branding live",
        "destructive": True,
    },
    {
        "name": "connect_domain",
        "integration": "domains",
        "description": "Register a custom domain",
        "destructive": True,
    },
    {
        "name": "create_organization",
        "integration": "enterprise",
        "description": "Create enterprise organization unit",
        "destructive": False,
    },
    {
        "name": "invite_member",
        "integration": "enterprise",
        "description": "Invite a team member",
        "destructive": True,
    },
    {
        "name": "show_platform_report",
        "integration": "monitoring",
        "description": "Platform growth/revenue report (admin)",
        "destructive": False,
        "platform_admin": True,
    },
    {
        "name": "show_usage_dashboard",
        "integration": "analytics",
        "description": "Company usage dashboard",
        "destructive": False,
    },
    {
        "name": "show_health",
        "integration": "monitoring",
        "description": "System health snapshot",
        "destructive": False,
        "platform_admin": True,
    },
    {
        "name": "show_monitoring",
        "integration": "monitoring",
        "description": "Observability links and signals",
        "destructive": False,
        "platform_admin": True,
    },
    {
        "name": "retry_failed_job",
        "integration": "monitoring",
        "description": "Retry a dead-letter ops job",
        "destructive": True,
        "platform_admin": True,
    },
    {
        "name": "list_failed_jobs",
        "integration": "monitoring",
        "description": "List dead-letter jobs",
        "destructive": False,
        "platform_admin": True,
    },
    {
        "name": "billing_checkout",
        "integration": "billing",
        "description": "Create Stripe checkout session",
        "destructive": False,
    },
]


# Intent → ordered tool steps. Args are resolved from NLU slots + memory.
WORKFLOWS: Dict[CopilotIntent, List[Dict[str, Any]]] = {
    CopilotIntent.CREATE_AGENT: [
        {"tool": "create_agent", "title": "Create AI agent"},
    ],
    CopilotIntent.GENERATE_PRODUCT: [
        {"tool": "analyze_prompt", "title": "Analyze product prompt"},
        {"tool": "generate_product", "title": "Generate AI product"},
    ],
    CopilotIntent.INSTALL_TEMPLATE: [
        {"tool": "install_template", "title": "Install marketplace template"},
    ],
    CopilotIntent.UPLOAD_KNOWLEDGE: [
        {"tool": "create_knowledge_base", "title": "Create knowledge base"},
    ],
    CopilotIntent.PUBLISH_WEBSITE: [
        {"tool": "publish_agent", "title": "Publish AI agent / website"},
    ],
    CopilotIntent.CONFIGURE_BRANDING: [
        {"tool": "update_branding", "title": "Update branding draft"},
        {"tool": "publish_branding", "title": "Publish branding", "optional": True},
    ],
    CopilotIntent.CONNECT_DOMAIN: [
        {"tool": "connect_domain", "title": "Connect custom domain"},
    ],
    CopilotIntent.CREATE_ORGANIZATION: [
        {"tool": "create_organization", "title": "Create organization unit"},
    ],
    CopilotIntent.INVITE_MEMBERS: [
        {"tool": "invite_member", "title": "Invite team member"},
    ],
    CopilotIntent.SHOW_REPORTS: [
        {"tool": "show_usage_dashboard", "title": "Usage analytics"},
        {"tool": "show_platform_report", "title": "Platform report", "optional": True},
    ],
    CopilotIntent.VIEW_MONITORING: [
        {"tool": "show_monitoring", "title": "Observability overview"},
        {"tool": "show_health", "title": "System health"},
    ],
    CopilotIntent.RETRY_FAILED_JOB: [
        {"tool": "list_failed_jobs", "title": "List failed jobs"},
        {"tool": "retry_failed_job", "title": "Retry failed job"},
    ],
    CopilotIntent.SHOW_HEALTH: [
        {"tool": "show_health", "title": "System health"},
    ],
    CopilotIntent.LIST_TOOLS: [],
    CopilotIntent.HELP: [],
    CopilotIntent.UNKNOWN: [],
}


# Keyword / phrase rules for deterministic NLU (order matters — first match wins by score).
INTENT_PATTERNS: List[Dict[str, Any]] = [
    {
        "intent": CopilotIntent.GENERATE_PRODUCT,
        "keywords": [
            "generate product",
            "build a landing",
            "landing page",
            "customer support chatbot",
            "hr assistant",
            "create a chatbot",
            "generate an hr",
            "build me a",
            "product generator",
        ],
        "weight": 10,
    },
    {
        "intent": CopilotIntent.CREATE_AGENT,
        "keywords": ["create agent", "create an agent", "new agent", "make an agent", "ai agent"],
        "weight": 8,
    },
    {
        "intent": CopilotIntent.INSTALL_TEMPLATE,
        "keywords": ["install template", "marketplace template", "use template", "install from marketplace"],
        "weight": 9,
    },
    {
        "intent": CopilotIntent.UPLOAD_KNOWLEDGE,
        "keywords": ["upload knowledge", "knowledge base", "add documents", "create knowledge"],
        "weight": 8,
    },
    {
        "intent": CopilotIntent.PUBLISH_WEBSITE,
        "keywords": ["publish my", "publish agent", "publish product", "go live", "publish website", "publish ai"],
        "weight": 9,
    },
    {
        "intent": CopilotIntent.CONFIGURE_BRANDING,
        "keywords": ["branding", "brand colors", "logo", "white label", "white-label"],
        "weight": 8,
    },
    {
        "intent": CopilotIntent.CONNECT_DOMAIN,
        "keywords": [
            "connect domain",
            "connect my domain",
            "custom domain",
            "add domain",
            "attach domain",
        ],
        "weight": 9,
    },
    {
        "intent": CopilotIntent.CREATE_ORGANIZATION,
        "keywords": ["create organization", "create org", "business unit", "department", "enterprise unit"],
        "weight": 8,
    },
    {
        "intent": CopilotIntent.INVITE_MEMBERS,
        "keywords": ["invite member", "invite user", "invite team", "add teammate", "invite colleagues"],
        "weight": 8,
    },
    {
        "intent": CopilotIntent.SHOW_REPORTS,
        "keywords": ["show report", "analytics", "usage report", "revenue", "growth report", "show usage"],
        "weight": 7,
    },
    {
        "intent": CopilotIntent.VIEW_MONITORING,
        "keywords": ["monitoring", "observability", "grafana", "prometheus", "error rate", "why did deployment fail"],
        "weight": 9,
    },
    {
        "intent": CopilotIntent.RETRY_FAILED_JOB,
        "keywords": ["retry failed", "retry job", "dead letter", "failed job", "deployment fail"],
        "weight": 9,
    },
    {
        "intent": CopilotIntent.SHOW_HEALTH,
        "keywords": ["platform health", "system health", "show health", "is the api healthy", "health check"],
        "weight": 9,
    },
    {
        "intent": CopilotIntent.LIST_TOOLS,
        "keywords": ["list tools", "what can you do", "capabilities", "available tools"],
        "weight": 6,
    },
    {
        "intent": CopilotIntent.HELP,
        "keywords": ["help", "how do i", "what is copilot"],
        "weight": 3,
    },
]


def tool_by_name(name: str) -> Optional[Dict[str, Any]]:
    for t in TOOL_CATALOG:
        if t["name"] == name:
            return t
    return None
