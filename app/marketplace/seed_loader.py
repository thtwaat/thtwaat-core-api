"""Idempotent marketplace seed loader (packages + JSON prompt catalog).

Phase 5: create / upgrade / refresh without duplicates.
"""
from __future__ import annotations

import copy
import json
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, Iterable, List, Literal, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.marketplace.models import (
    MarketplaceTemplate,
    PricingTier,
    TemplateCategory,
    TemplateKind,
    TemplateStatus,
    TemplateVersion,
)
from app.marketplace.schemas import TemplateCreate, TemplateUpdate, TemplateVersionCreate

# NOTE: Do NOT import MarketplaceService at module level.
# MarketplaceService → UsageService → CompanyRepository → Company, which registers
# Company.relationship("User") before User is imported and breaks configure_mappers()
# in CLI/scripts that do not load main.py.


ROOT = Path(__file__).resolve().parents[2]
SEEDS_DIR = ROOT / "data" / "marketplace" / "seeds"
INDEX_PATH = SEEDS_DIR / "index.json"
PACKAGES_DIR = SEEDS_DIR / "packages"
PACKAGES_INDEX_PATH = PACKAGES_DIR / "index.json"

# Required production package starters (Product Generator assemble dependency).
REQUIRED_PACKAGE_SLUGS = frozenset(
    {
        "ai-website-starter",
        "ecommerce-starter",
        "hotel-website-starter",
        "restaurant-starter",
        "portfolio-starter",
        "blog-starter",
        "saas-starter",
        "crm-starter",
        "documentation-site",
        "landing-page-starter",
    }
)

SeedAction = Literal["created", "upgraded", "updated", "skipped"]


@dataclass
class SeedStats:
    created: int = 0
    upgraded: int = 0
    updated: int = 0
    skipped: int = 0
    actions: List[tuple[str, SeedAction]] = field(default_factory=list)

    def record(self, slug: str, action: SeedAction) -> None:
        self.actions.append((slug, action))
        setattr(self, action, getattr(self, action) + 1)

    @property
    def total_touched(self) -> int:
        return self.created + self.upgraded + self.updated


def prompt_default_config(doc: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "prompt": doc.get("prompt", ""),
        "variables": doc.get("variables") or [],
        "temperature": float(doc.get("temperature", 0.4)),
        "example_input": doc.get("example_input"),
        "example_output": doc.get("example_output"),
        "seed_id": doc.get("id"),
    }


def prompt_doc_to_create(doc: Dict[str, Any]) -> TemplateCreate:
    visibility = (doc.get("visibility") or "public").lower()
    return TemplateCreate(
        slug=doc["slug"],
        name=doc["name"],
        category=doc["category"],
        kind=doc.get("kind") or "prompt",
        pricing_tier=doc.get("pricing_tier") or "free",
        industry=doc.get("industry"),
        description=doc.get("description") or "",
        version=doc.get("version") or "1.0.0",
        thumbnail=doc.get("thumbnail"),
        icon=doc.get("icon") or "sparkles",
        tags=list(doc.get("tags") or []),
        author=doc.get("author") or "THTWAAT",
        price=Decimal(str(doc.get("price", "0"))),
        is_public=visibility == "public",
        is_featured=bool(doc.get("featured", False)),
        supports_agents=True,
        supports_domains=False,
        supports_billing=False,
        supports_mobile=False,
        package_path=None,
        default_config=prompt_default_config(doc),
        changelog=doc.get("changelog") or f"Seed {doc.get('version') or '1.0.0'}",
        publish=visibility == "public",
    )


def load_prompt_seed_docs(*, seeds_dir: Path = SEEDS_DIR) -> List[Dict[str, Any]]:
    index_path = seeds_dir / "index.json"
    if not index_path.exists():
        raise FileNotFoundError(f"Missing seed index: {index_path}")
    index = json.loads(index_path.read_text(encoding="utf-8"))
    docs: List[Dict[str, Any]] = []
    for entry in index.get("templates") or []:
        rel = entry.get("file")
        if not rel:
            continue
        path = seeds_dir / rel
        doc = json.loads(path.read_text(encoding="utf-8"))
        docs.append(doc)
    return docs


def package_doc_to_create(doc: Dict[str, Any]) -> TemplateCreate:
    visibility = (doc.get("visibility") or "public").lower()
    return TemplateCreate(
        slug=doc["slug"],
        name=doc["name"],
        category=doc["category"],
        kind=doc.get("kind") or "package",
        pricing_tier=doc.get("pricing_tier") or "free",
        industry=doc.get("industry"),
        description=doc.get("description") or "",
        version=doc.get("version") or "1.0.0",
        thumbnail=doc.get("thumbnail"),
        icon=doc.get("icon") or "package",
        tags=list(doc.get("tags") or []),
        author=doc.get("author") or "THTWAAT",
        price=Decimal(str(doc.get("price", "0"))),
        is_public=visibility == "public",
        is_featured=bool(doc.get("featured", False)),
        supports_agents=bool(doc.get("supports_agents", True)),
        supports_domains=bool(doc.get("supports_domains", True)),
        supports_billing=bool(doc.get("supports_billing", False)),
        supports_mobile=bool(doc.get("supports_mobile", False)),
        package_path=doc.get("package_path"),
        default_config=copy.deepcopy(doc.get("default_config") or {}),
        changelog=doc.get("changelog") or f"Seed {doc.get('version') or '1.0.0'}",
        publish=bool(doc.get("publish", visibility == "public")),
    )


def load_package_seed_docs(*, packages_dir: Path = PACKAGES_DIR) -> List[Dict[str, Any]]:
    index_path = packages_dir / "index.json"
    if not index_path.exists():
        raise FileNotFoundError(f"Missing package seed index: {index_path}")
    index = json.loads(index_path.read_text(encoding="utf-8"))
    docs: List[Dict[str, Any]] = []
    for entry in index.get("templates") or []:
        rel = entry.get("file")
        if not rel:
            continue
        path = packages_dir / rel
        doc = json.loads(path.read_text(encoding="utf-8"))
        docs.append(doc)
    return docs


def load_package_seed_payloads(*, packages_dir: Path = PACKAGES_DIR) -> List[TemplateCreate]:
    return [package_doc_to_create(doc) for doc in load_package_seed_docs(packages_dir=packages_dir)]


def _parse_enum(enum_cls, value: str, field_name: str):
    try:
        return enum_cls(value)
    except ValueError as exc:
        raise ValueError(f"Invalid {field_name}: {value}") from exc


def _create_with_stable_id(service: Any, doc: Dict[str, Any], payload: TemplateCreate) -> None:
    template = MarketplaceTemplate(
        id=UUID(str(doc["id"])),
        slug=payload.slug,
        name=payload.name,
        category=_parse_enum(TemplateCategory, payload.category, "category"),
        kind=_parse_enum(TemplateKind, payload.kind, "kind"),
        pricing_tier=_parse_enum(PricingTier, payload.pricing_tier, "pricing_tier"),
        industry=payload.industry,
        description=payload.description,
        version=payload.version,
        thumbnail=payload.thumbnail,
        icon=payload.icon,
        tags=payload.tags or [],
        author=payload.author,
        price=payload.price or Decimal("0"),
        is_public=payload.is_public,
        is_featured=payload.is_featured,
        supports_agents=payload.supports_agents,
        supports_domains=payload.supports_domains,
        supports_billing=payload.supports_billing,
        supports_mobile=payload.supports_mobile,
        package_path=payload.package_path,
        default_config=copy.deepcopy(payload.default_config or {}),
        status=TemplateStatus.PUBLISHED if payload.publish else TemplateStatus.DRAFT,
    )
    service.repo.save_template(template)
    from datetime import datetime, timezone

    version = TemplateVersion(
        template_id=template.id,
        version=payload.version,
        changelog=payload.changelog or "Initial release",
        config=copy.deepcopy(payload.default_config or {}),
        is_latest=True,
        published_at=datetime.now(timezone.utc) if payload.publish else None,
    )
    service.repo.save_version(version)
    service.repo.commit()


def _metadata_update(payload: TemplateCreate) -> TemplateUpdate:
    return TemplateUpdate(
        name=payload.name,
        category=payload.category,
        kind=payload.kind,
        pricing_tier=payload.pricing_tier,
        industry=payload.industry,
        description=payload.description,
        thumbnail=payload.thumbnail,
        icon=payload.icon,
        tags=payload.tags,
        author=payload.author,
        price=payload.price,
        is_public=payload.is_public,
        is_featured=payload.is_featured,
        supports_agents=payload.supports_agents,
        supports_domains=payload.supports_domains,
        supports_billing=payload.supports_billing,
        supports_mobile=payload.supports_mobile,
        package_path=payload.package_path,
        default_config=payload.default_config,
        status=TemplateStatus.PUBLISHED.value if payload.publish else TemplateStatus.DRAFT.value,
    )


def _marketplace_service(db: Session) -> "MarketplaceService":
    from app.marketplace.service import MarketplaceService

    return MarketplaceService(db)


def upsert_prompt_doc(
    service: "MarketplaceService",
    doc: Dict[str, Any],
    *,
    upgrade: bool = True,
    refresh_same_version: bool = True,
) -> SeedAction:
    payload = prompt_doc_to_create(doc)
    existing = service.repo.get_by_slug(payload.slug)
    if not existing:
        _create_with_stable_id(service, doc, payload)
        return "created"

    if existing.version != payload.version:
        if not upgrade:
            return "skipped"
        service.update_template(existing.id, _metadata_update(payload))
        service.add_version(
            existing.id,
            TemplateVersionCreate(
                version=payload.version,
                changelog=payload.changelog or f"Upgrade to {payload.version}",
                config=copy.deepcopy(payload.default_config or {}),
                set_latest=True,
            ),
        )
        return "upgraded"

    if not refresh_same_version:
        return "skipped"

    # Same version: refresh catalog metadata + latest config snapshot.
    service.update_template(existing.id, _metadata_update(payload))
    latest = service.repo.get_latest_version(existing.id)
    if latest and latest.version == payload.version:
        latest.changelog = payload.changelog or latest.changelog
        latest.config = copy.deepcopy(payload.default_config or {})
        service.repo.commit()
    return "updated"


def seed_prompt_templates(
    db: Session,
    *,
    upgrade: bool = True,
    refresh_same_version: bool = True,
    seeds_dir: Path = SEEDS_DIR,
    dry_run: bool = False,
) -> SeedStats:
    service = _marketplace_service(db)
    stats = SeedStats()
    for doc in load_prompt_seed_docs(seeds_dir=seeds_dir):
        if dry_run:
            existing = service.repo.get_by_slug(doc["slug"])
            if not existing:
                action: SeedAction = "created"
            elif existing.version != (doc.get("version") or "1.0.0"):
                action = "upgraded" if upgrade else "skipped"
            else:
                action = "updated" if refresh_same_version else "skipped"
            stats.record(doc["slug"], action)
            continue
        action = upsert_prompt_doc(
            service,
            doc,
            upgrade=upgrade,
            refresh_same_version=refresh_same_version,
        )
        stats.record(doc["slug"], action)
    return stats


def seed_package_templates(
    db: Session,
    packages: Optional[Iterable[TemplateCreate]] = None,
    *,
    upgrade: bool = True,
    dry_run: bool = False,
    packages_dir: Path = PACKAGES_DIR,
    refresh_same_version: bool = False,
) -> SeedStats:
    """Idempotently seed package starters from JSON catalog (or explicit payloads)."""
    service = _marketplace_service(db)
    stats = SeedStats()
    payloads = list(packages) if packages is not None else load_package_seed_payloads(packages_dir=packages_dir)
    docs_by_slug = {
        d["slug"]: d for d in load_package_seed_docs(packages_dir=packages_dir)
    } if packages is None else {}

    for payload in payloads:
        existing = service.repo.get_by_slug(payload.slug)
        if dry_run:
            if not existing:
                stats.record(payload.slug, "created")
            elif existing.version != payload.version:
                stats.record(payload.slug, "upgraded" if upgrade else "skipped")
            elif refresh_same_version:
                stats.record(payload.slug, "updated")
            else:
                stats.record(payload.slug, "skipped")
            continue
        if not existing:
            doc = docs_by_slug.get(payload.slug)
            if doc and doc.get("id"):
                _create_with_stable_id(service, doc, payload)
            else:
                service.create_template(payload)
            stats.record(payload.slug, "created")
            continue
        if existing.version != payload.version:
            if not upgrade:
                stats.record(payload.slug, "skipped")
                continue
            service.update_template(existing.id, _metadata_update(payload))
            service.add_version(
                existing.id,
                TemplateVersionCreate(
                    version=payload.version,
                    changelog=payload.changelog or f"Upgrade to {payload.version}",
                    config=copy.deepcopy(payload.default_config or {}),
                    set_latest=True,
                ),
            )
            stats.record(payload.slug, "upgraded")
            continue
        if refresh_same_version:
            service.update_template(existing.id, _metadata_update(payload))
            latest = service.repo.get_latest_version(existing.id)
            if latest and latest.version == payload.version:
                latest.changelog = payload.changelog or latest.changelog
                latest.config = copy.deepcopy(payload.default_config or {})
                service.repo.commit()
            stats.record(payload.slug, "updated")
            continue
        stats.record(payload.slug, "skipped")
    return stats


def merge_stats(*parts: SeedStats) -> SeedStats:
    out = SeedStats()
    for part in parts:
        out.created += part.created
        out.upgraded += part.upgraded
        out.updated += part.updated
        out.skipped += part.skipped
        out.actions.extend(part.actions)
    return out
