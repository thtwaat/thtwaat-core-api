"""Seed Store Home category meta + demo collections (idempotent)."""
from __future__ import annotations

from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.marketplace.models import (
    MarketplaceCategoryMeta,
    MarketplaceCollection,
    MarketplaceCollectionItem,
    MarketplaceTemplate,
    TemplateStatus,
)
from app.marketplace.service import CATEGORY_LABELS, DEFAULT_CATEGORY_ICONS

# Featured category slugs for the store home grid
FEATURED_CATEGORY_SLUGS = {
    "saas",
    "ai_agents",
    "marketing",
    "ecommerce",
    "helpdesk",
    "crm",
    "productivity",
    "automation",
    "startup",
    "security",
}

COLLECTION_SEEDS: List[Dict[str, Any]] = [
    {
        "slug": "best-for-smb",
        "name": "Best for SMB",
        "description": "Practical starters for small and mid-size teams.",
        "icon": "building",
        "is_featured": True,
        "sort_order": 10,
        "collection_type": "curated",
        "prefer_slugs": ["ai-saas-starter", "ai-website-starter", "ai-landing-starter"],
    },
    {
        "slug": "best-chatbots",
        "name": "Best Chatbots",
        "description": "Agent and helpdesk templates ready to embed.",
        "icon": "bot",
        "is_featured": True,
        "sort_order": 20,
        "collection_type": "curated",
        "prefer_categories": ["helpdesk", "ai_agents", "crm"],
    },
    {
        "slug": "free",
        "name": "Free",
        "description": "Install free templates with no purchase required.",
        "icon": "gift",
        "is_featured": True,
        "sort_order": 30,
        "collection_type": "computed",
        "computed_rule": {"pricing_tier": "free", "sort": "installs", "limit": 24},
    },
    {
        "slug": "premium",
        "name": "Premium",
        "description": "Pro and paid catalog picks.",
        "icon": "sparkles",
        "is_featured": True,
        "sort_order": 40,
        "collection_type": "computed",
        "computed_rule": {"pricing_tier": "pro", "sort": "featured", "limit": 24},
    },
    {
        "slug": "enterprise",
        "name": "Enterprise",
        "description": "Enterprise-ready packages and workflows.",
        "icon": "shield",
        "is_featured": True,
        "sort_order": 50,
        "collection_type": "computed",
        "computed_rule": {"pricing_tier": "enterprise", "sort": "featured", "limit": 24},
    },
    {
        "slug": "fastest-growing",
        "name": "Fastest Growing",
        "description": "Templates with the strongest install momentum.",
        "icon": "trending-up",
        "is_featured": True,
        "sort_order": 60,
        "collection_type": "computed",
        "computed_rule": {"sort": "installs", "limit": 24},
    },
]


def seed_category_meta(db: Session, *, dry_run: bool = False) -> int:
    """Upsert category meta rows for every known category slug."""
    existing = {
        row.category_slug: row
        for row in db.query(MarketplaceCategoryMeta).all()
    }
    created = 0
    order = 0
    for slug, name in CATEGORY_LABELS.items():
        order += 10
        meta = existing.get(slug)
        if meta is None:
            if dry_run:
                created += 1
                continue
            meta = MarketplaceCategoryMeta(category_slug=slug)
            db.add(meta)
            created += 1
        meta.display_name = meta.display_name or name
        meta.icon = meta.icon or DEFAULT_CATEGORY_ICONS.get(slug)
        meta.is_featured = slug in FEATURED_CATEGORY_SLUGS
        if not meta.popularity_score:
            meta.popularity_score = 100 if slug in FEATURED_CATEGORY_SLUGS else 10
        if meta.display_order == 100 or meta.display_order is None:
            meta.display_order = order if slug in FEATURED_CATEGORY_SLUGS else 500 + order
    if not dry_run:
        db.commit()
    return created


def _pick_templates(
    db: Session,
    *,
    prefer_slugs: Optional[List[str]] = None,
    prefer_categories: Optional[List[str]] = None,
    limit: int = 8,
) -> List[MarketplaceTemplate]:
    picked: List[MarketplaceTemplate] = []
    seen: set[UUID] = set()
    if prefer_slugs:
        for slug in prefer_slugs:
            row = (
                db.query(MarketplaceTemplate)
                .filter(MarketplaceTemplate.slug == slug)
                .first()
            )
            if row and row.id not in seen:
                picked.append(row)
                seen.add(row.id)
    if prefer_categories and len(picked) < limit:
        rows = (
            db.query(MarketplaceTemplate)
            .filter(
                MarketplaceTemplate.status == TemplateStatus.PUBLISHED.value,
                MarketplaceTemplate.is_public.is_(True),
                MarketplaceTemplate.category.in_(prefer_categories),
            )
            .order_by(MarketplaceTemplate.install_count.desc())
            .limit(limit)
            .all()
        )
        for row in rows:
            if row.id not in seen:
                picked.append(row)
                seen.add(row.id)
            if len(picked) >= limit:
                break
    if len(picked) < limit:
        rows = (
            db.query(MarketplaceTemplate)
            .filter(
                MarketplaceTemplate.status == TemplateStatus.PUBLISHED.value,
                MarketplaceTemplate.is_public.is_(True),
            )
            .order_by(
                MarketplaceTemplate.is_featured.desc(),
                MarketplaceTemplate.install_count.desc(),
            )
            .limit(limit)
            .all()
        )
        for row in rows:
            if row.id not in seen:
                picked.append(row)
                seen.add(row.id)
            if len(picked) >= limit:
                break
    return picked[:limit]


def seed_collections(db: Session, *, dry_run: bool = False) -> int:
    """Create demo collections if missing; refresh curated item lists when empty."""
    created = 0
    for spec in COLLECTION_SEEDS:
        existing = (
            db.query(MarketplaceCollection)
            .filter(MarketplaceCollection.slug == spec["slug"])
            .first()
        )
        if existing is None:
            if dry_run:
                created += 1
                continue
            collection = MarketplaceCollection(
                slug=spec["slug"],
                name=spec["name"],
                description=spec.get("description") or "",
                icon=spec.get("icon"),
                is_public=True,
                is_featured=bool(spec.get("is_featured")),
                sort_order=int(spec.get("sort_order") or 100),
                collection_type=spec.get("collection_type") or "curated",
                computed_rule=dict(spec.get("computed_rule") or {}),
            )
            db.add(collection)
            db.flush()
            created += 1
        else:
            collection = existing
            collection.name = spec["name"]
            collection.description = spec.get("description") or collection.description
            collection.icon = spec.get("icon") or collection.icon
            collection.is_featured = bool(spec.get("is_featured"))
            collection.sort_order = int(spec.get("sort_order") or collection.sort_order)
            collection.collection_type = spec.get("collection_type") or collection.collection_type
            if spec.get("computed_rule"):
                collection.computed_rule = dict(spec["computed_rule"])

        if (collection.collection_type or "curated") == "curated":
            item_count = (
                db.query(MarketplaceCollectionItem)
                .filter(MarketplaceCollectionItem.collection_id == collection.id)
                .count()
            )
            if item_count == 0 and not dry_run:
                templates = _pick_templates(
                    db,
                    prefer_slugs=spec.get("prefer_slugs"),
                    prefer_categories=spec.get("prefer_categories"),
                    limit=8,
                )
                for position, tpl in enumerate(templates):
                    db.add(
                        MarketplaceCollectionItem(
                            collection_id=collection.id,
                            template_id=tpl.id,
                            position=position,
                        )
                    )

        # Mark a few featured editors' choice when empty
        if not dry_run and spec["slug"] == "best-for-smb":
            for tpl in _pick_templates(db, prefer_slugs=spec.get("prefer_slugs"), limit=3):
                tpl.is_editors_choice = True

    if not dry_run:
        db.commit()
    return created


def seed_store_home(db: Session, *, dry_run: bool = False) -> Dict[str, int]:
    """Seed category meta + collections for Store Home v1."""
    return {
        "category_meta_created": seed_category_meta(db, dry_run=dry_run),
        "collections_created": seed_collections(db, dry_run=dry_run),
    }
