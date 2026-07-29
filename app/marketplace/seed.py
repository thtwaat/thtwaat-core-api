"""Seed Website / Landing / SaaS templates into the marketplace registry."""
from __future__ import annotations

from decimal import Decimal

from sqlalchemy.orm import Session

from app.marketplace.schemas import TemplateCreate
from app.marketplace.service import MarketplaceService


SEED_TEMPLATES = [
    TemplateCreate(
        slug="ai-website-starter",
        name="AI Website Starter",
        category="website",
        industry="general",
        description="Multi-page AI website with chat, knowledge search, blog, and lead capture.",
        version="1.0.0",
        thumbnail="/templates/website.png",
        icon="globe",
        tags=["website", "seo", "chat", "leads"],
        author="THTWAAT",
        price=Decimal("0"),
        is_public=True,
        is_featured=True,
        supports_agents=True,
        supports_domains=True,
        supports_billing=False,
        supports_mobile=False,
        package_path="apps/templates/website",
        default_config={
            "stack": ["nextjs15", "tailwind", "shadcn"],
            "env": ["NEXT_PUBLIC_API_URL", "NEXT_PUBLIC_AGENT_API_KEY"],
            "pages": ["home", "about", "services", "pricing", "blog", "contact", "chat"],
            "features": ["widget", "streaming_chat", "knowledge_search", "leads"],
        },
        changelog="Initial Website Starter release",
        publish=True,
    ),
    TemplateCreate(
        slug="ai-landing-starter",
        name="AI Landing Page Starter",
        category="landing",
        industry="growth",
        description="High-converting single-page landing with inline AI assistant and demo booking.",
        version="1.0.0",
        thumbnail="/templates/landing.png",
        icon="sparkles",
        tags=["landing", "conversion", "demo", "faq"],
        author="THTWAAT",
        price=Decimal("0"),
        is_public=True,
        is_featured=True,
        supports_agents=True,
        supports_domains=True,
        supports_billing=True,
        supports_mobile=False,
        package_path="apps/templates/landing",
        default_config={
            "stack": ["nextjs15", "tailwind", "shadcn"],
            "env": ["NEXT_PUBLIC_API_URL", "NEXT_PUBLIC_AGENT_API_KEY"],
            "sections": [
                "hero",
                "ai_chat_cta",
                "features",
                "benefits",
                "pricing",
                "testimonials",
                "faq",
                "book_demo",
                "contact",
            ],
            "features": ["widget", "inline_assistant", "streaming", "leads"],
        },
        changelog="Initial Landing Starter release",
        publish=True,
    ),
    TemplateCreate(
        slug="ai-saas-starter",
        name="AI SaaS Starter",
        category="saas",
        industry="b2b",
        description="Full SaaS dashboard: auth, agents, knowledge, domains, billing, analytics.",
        version="1.0.0",
        thumbnail="/templates/saas.png",
        icon="layout-dashboard",
        tags=["saas", "dashboard", "billing", "auth"],
        author="THTWAAT",
        price=Decimal("0"),
        is_public=True,
        is_featured=True,
        supports_agents=True,
        supports_domains=True,
        supports_billing=True,
        supports_mobile=False,
        package_path="apps/templates/saas",
        default_config={
            "stack": ["nextjs15", "tailwind", "tanstack-query", "rhf", "zod"],
            "env": ["NEXT_PUBLIC_API_URL", "NEXT_PUBLIC_AGENT_API_KEY"],
            "modules": [
                "auth",
                "dashboard",
                "agents",
                "knowledge",
                "domains",
                "billing",
                "analytics",
                "settings",
                "marketplace",
            ],
            "features": ["jwt", "otp", "usage_meter", "publish"],
        },
        changelog="Initial SaaS Starter release",
        publish=True,
    ),
]


def seed_marketplace_templates(db: Session, *, force: bool = False) -> int:
    """Idempotently seed core templates. Returns number created."""
    service = MarketplaceService(db)
    created = 0
    for payload in SEED_TEMPLATES:
        existing = service.repo.get_by_slug(payload.slug)
        if existing and not force:
            continue
        if existing and force:
            continue
        service.create_template(payload)
        created += 1
    return created
