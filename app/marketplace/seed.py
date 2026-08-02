"""Seed Website / Landing / SaaS templates into the marketplace registry."""
from __future__ import annotations

from decimal import Decimal

from sqlalchemy.orm import Session

from app.marketplace.schemas import TemplateCreate


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


def seed_marketplace_templates(
    db: Session,
    *,
    force: bool = False,
    include_prompts: bool = False,
    upgrade: bool = True,
    dry_run: bool = False,
) -> int:
    """Idempotently seed core package templates. Returns number created.

    Prompt catalog is opt-in here for backward-compatible tests; use
    `seed_marketplace_catalog` (CLI default) for packages + prompts.
    """
    from app.marketplace.seed_loader import merge_stats, seed_package_templates, seed_prompt_templates

    _ = force
    parts = [
        seed_package_templates(db, SEED_TEMPLATES, upgrade=upgrade, dry_run=dry_run),
    ]
    if include_prompts:
        parts.append(
            seed_prompt_templates(
                db,
                upgrade=upgrade,
                refresh_same_version=False,
                dry_run=dry_run,
            )
        )
    return merge_stats(*parts).created


def seed_marketplace_catalog(
    db: Session,
    *,
    include_packages: bool = True,
    include_prompts: bool = True,
    upgrade: bool = True,
    refresh_same_version: bool = True,
    dry_run: bool = False,
):
    """Phase 5 entry: full idempotent catalog seed with create/upgrade/refresh stats."""
    from app.marketplace.seed_loader import SeedStats, merge_stats, seed_package_templates, seed_prompt_templates

    parts = []
    if include_packages:
        parts.append(
            seed_package_templates(db, SEED_TEMPLATES, upgrade=upgrade, dry_run=dry_run)
        )
    if include_prompts:
        parts.append(
            seed_prompt_templates(
                db,
                upgrade=upgrade,
                refresh_same_version=refresh_same_version,
                dry_run=dry_run,
            )
        )
    return merge_stats(*parts) if parts else SeedStats()
