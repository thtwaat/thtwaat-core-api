"""Seed package templates into the marketplace registry.

Package starters live in `data/marketplace/seeds/packages/*.json` and are installed by
`python -m scripts.seed_marketplace` (packages + prompts by default).
"""
from __future__ import annotations

from typing import List

from sqlalchemy.orm import Session

from app.marketplace.schemas import TemplateCreate
from app.marketplace.seed_loader import (
    REQUIRED_PACKAGE_SLUGS,
    SeedStats,
    load_package_seed_payloads,
    merge_stats,
    seed_package_templates,
    seed_prompt_templates,
)


def get_seed_templates() -> List[TemplateCreate]:
    """Load package TemplateCreate payloads from the JSON catalog."""
    return load_package_seed_payloads()


# Eager snapshot for callers that iterate SEED_TEMPLATES at import time.
try:
    SEED_TEMPLATES: List[TemplateCreate] = get_seed_templates()
except FileNotFoundError:
    SEED_TEMPLATES = []


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
    _ = force
    parts = [
        seed_package_templates(db, upgrade=upgrade, dry_run=dry_run),
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
) -> SeedStats:
    """Full idempotent catalog seed with create/upgrade/refresh stats."""
    parts = []
    if include_packages:
        parts.append(
            seed_package_templates(
                db,
                upgrade=upgrade,
                refresh_same_version=refresh_same_version,
                dry_run=dry_run,
            )
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


__all__ = [
    "REQUIRED_PACKAGE_SLUGS",
    "SEED_TEMPLATES",
    "get_seed_templates",
    "seed_marketplace_catalog",
    "seed_marketplace_templates",
]
