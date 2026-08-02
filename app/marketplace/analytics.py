"""Marketplace analytics aggregations (Phase 9)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import List
from uuid import UUID

from sqlalchemy import cast, Date, func
from sqlalchemy.orm import Session

from app.marketplace.models import (
    InstallStatus,
    MarketplaceTemplate,
    TemplateFavorite,
    TemplateInstallation,
    TemplateStatus,
)
from app.marketplace.schemas import (
    AnalyticsCountItem,
    AnalyticsDayPoint,
    AnalyticsTemplateRank,
    CatalogMarketplaceAnalytics,
    CompanyMarketplaceAnalytics,
    MarketplaceAnalytics,
)


def _label(key: str) -> str:
    return key.replace("_", " ").title()


def _enum_key(value) -> str:
    return str(value.value if hasattr(value, "value") else value)


def _fill_days(points: dict[str, int], days: int) -> List[AnalyticsDayPoint]:
    today = datetime.now(timezone.utc).date()
    out: List[AnalyticsDayPoint] = []
    for i in range(days - 1, -1, -1):
        d = (today - timedelta(days=i)).isoformat()
        out.append(AnalyticsDayPoint(day=d, installs=int(points.get(d, 0))))
    return out


def _count_rows(rows) -> List[AnalyticsCountItem]:
    items: List[AnalyticsCountItem] = []
    for key, count in rows:
        k = _enum_key(key) if key is not None else "unknown"
        items.append(AnalyticsCountItem(key=k, label=_label(k), count=int(count or 0)))
    items.sort(key=lambda x: (-x.count, x.label))
    return items


def company_analytics(db: Session, company_id: UUID, *, days: int = 30) -> CompanyMarketplaceAnalytics:
    active = (
        db.query(TemplateInstallation)
        .filter(
            TemplateInstallation.company_id == company_id,
            TemplateInstallation.status != InstallStatus.UNINSTALLED.value,
        )
        .all()
    )
    updates = sum(1 for i in active if i.update_available)
    favorites = (
        db.query(func.count(TemplateFavorite.id))
        .filter(TemplateFavorite.company_id == company_id)
        .scalar()
    ) or 0

    status_rows = (
        db.query(TemplateInstallation.status, func.count(TemplateInstallation.id))
        .filter(
            TemplateInstallation.company_id == company_id,
            TemplateInstallation.status != InstallStatus.UNINSTALLED.value,
        )
        .group_by(TemplateInstallation.status)
        .all()
    )

    cat_rows = (
        db.query(MarketplaceTemplate.category, func.count(TemplateInstallation.id))
        .join(TemplateInstallation, TemplateInstallation.template_id == MarketplaceTemplate.id)
        .filter(
            TemplateInstallation.company_id == company_id,
            TemplateInstallation.status != InstallStatus.UNINSTALLED.value,
        )
        .group_by(MarketplaceTemplate.category)
        .all()
    )
    kind_rows = (
        db.query(MarketplaceTemplate.kind, func.count(TemplateInstallation.id))
        .join(TemplateInstallation, TemplateInstallation.template_id == MarketplaceTemplate.id)
        .filter(
            TemplateInstallation.company_id == company_id,
            TemplateInstallation.status != InstallStatus.UNINSTALLED.value,
        )
        .group_by(MarketplaceTemplate.kind)
        .all()
    )

    since = datetime.now(timezone.utc) - timedelta(days=days)
    day_rows = (
        db.query(cast(TemplateInstallation.created_at, Date), func.count(TemplateInstallation.id))
        .filter(
            TemplateInstallation.company_id == company_id,
            TemplateInstallation.created_at >= since,
            TemplateInstallation.status != InstallStatus.UNINSTALLED.value,
        )
        .group_by(cast(TemplateInstallation.created_at, Date))
        .all()
    )
    day_map = {str(d): int(c) for d, c in day_rows if d is not None}

    recent: List[AnalyticsTemplateRank] = []
    for install in sorted(active, key=lambda i: i.created_at, reverse=True)[:8]:
        template = db.query(MarketplaceTemplate).filter(MarketplaceTemplate.id == install.template_id).first()
        if not template:
            continue
        recent.append(
            AnalyticsTemplateRank(
                template_id=template.id,
                slug=template.slug,
                name=template.name,
                kind=_enum_key(template.kind),
                category=_enum_key(template.category),
                install_count=int(template.install_count or 0),
                status=_enum_key(install.status),
            )
        )

    return CompanyMarketplaceAnalytics(
        installed_count=len(active),
        updates_available=updates,
        favorites_count=int(favorites),
        by_status=_count_rows(status_rows),
        by_category=_count_rows(cat_rows),
        by_kind=_count_rows(kind_rows),
        installs_over_time=_fill_days(day_map, days),
        recent_installs=recent,
    )


def catalog_analytics(db: Session, *, days: int = 30) -> CatalogMarketplaceAnalytics:
    templates_total = db.query(func.count(MarketplaceTemplate.id)).scalar() or 0
    status_counts = dict(
        (_enum_key(s), int(c))
        for s, c in db.query(MarketplaceTemplate.status, func.count(MarketplaceTemplate.id))
        .group_by(MarketplaceTemplate.status)
        .all()
    )
    kind_rows = (
        db.query(MarketplaceTemplate.kind, func.count(MarketplaceTemplate.id))
        .group_by(MarketplaceTemplate.kind)
        .all()
    )
    cat_rows = (
        db.query(MarketplaceTemplate.category, func.count(MarketplaceTemplate.id))
        .group_by(MarketplaceTemplate.category)
        .all()
    )
    tier_rows = (
        db.query(MarketplaceTemplate.pricing_tier, func.count(MarketplaceTemplate.id))
        .group_by(MarketplaceTemplate.pricing_tier)
        .all()
    )
    favorites_total = db.query(func.count(TemplateFavorite.id)).scalar() or 0
    active_installs = (
        db.query(func.count(TemplateInstallation.id))
        .filter(TemplateInstallation.status != InstallStatus.UNINSTALLED.value)
        .scalar()
    ) or 0

    top = (
        db.query(MarketplaceTemplate)
        .order_by(MarketplaceTemplate.install_count.desc(), MarketplaceTemplate.updated_at.desc())
        .limit(10)
        .all()
    )
    top_templates = [
        AnalyticsTemplateRank(
            template_id=t.id,
            slug=t.slug,
            name=t.name,
            kind=_enum_key(t.kind),
            category=_enum_key(t.category),
            install_count=int(t.install_count or 0),
            status=_enum_key(t.status),
        )
        for t in top
    ]

    since = datetime.now(timezone.utc) - timedelta(days=days)
    day_rows = (
        db.query(cast(TemplateInstallation.created_at, Date), func.count(TemplateInstallation.id))
        .filter(
            TemplateInstallation.created_at >= since,
            TemplateInstallation.status != InstallStatus.UNINSTALLED.value,
        )
        .group_by(cast(TemplateInstallation.created_at, Date))
        .all()
    )
    day_map = {str(d): int(c) for d, c in day_rows if d is not None}

    return CatalogMarketplaceAnalytics(
        templates_total=int(templates_total),
        published=status_counts.get(TemplateStatus.PUBLISHED.value, 0),
        draft=status_counts.get(TemplateStatus.DRAFT.value, 0),
        archived=status_counts.get(TemplateStatus.ARCHIVED.value, 0),
        favorites_total=int(favorites_total),
        active_installs=int(active_installs),
        by_kind=_count_rows(kind_rows),
        by_category=_count_rows(cat_rows),
        by_pricing_tier=_count_rows(tier_rows),
        top_templates=top_templates,
        installs_over_time=_fill_days(day_map, days),
    )


def build_marketplace_analytics(
    db: Session,
    company_id: UUID,
    *,
    days: int = 30,
    include_catalog: bool = False,
) -> MarketplaceAnalytics:
    days = max(1, min(int(days or 30), 90))
    return MarketplaceAnalytics(
        company=company_analytics(db, company_id, days=days),
        catalog=catalog_analytics(db, days=days) if include_catalog else None,
        days=days,
    )
