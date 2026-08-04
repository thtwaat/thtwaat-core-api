"""Repository for marketplace templates, versions, and installations."""
from __future__ import annotations

from typing import List, Optional
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.marketplace.models import (
    InstallStatus,
    MarketplaceCategoryMeta,
    MarketplaceCollection,
    MarketplaceCollectionItem,
    MarketplaceTemplate,
    MarketplaceTemplateEvent,
    TemplateFavorite,
    TemplateInstallation,
    TemplateStatus,
    TemplateVersion,
)
from app.marketplace.search import apply_template_text_search


class MarketplaceRepository:
    def __init__(self, db: Session):
        self.db = db

    # ── Templates ─────────────────────────────────────────────────────────────

    def get_template(self, template_id: UUID) -> Optional[MarketplaceTemplate]:
        return self.db.query(MarketplaceTemplate).filter(MarketplaceTemplate.id == template_id).first()

    def get_by_slug(self, slug: str) -> Optional[MarketplaceTemplate]:
        return self.db.query(MarketplaceTemplate).filter(MarketplaceTemplate.slug == slug).first()

    def list_templates(
        self,
        *,
        q: Optional[str] = None,
        category: Optional[str] = None,
        featured: Optional[bool] = None,
        kind: Optional[str] = None,
        pricing_tier: Optional[str] = None,
        status: Optional[str] = TemplateStatus.PUBLISHED.value,
        is_public: Optional[bool] = True,
        sort: str = "featured",
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[List[MarketplaceTemplate], int]:
        query = self.db.query(MarketplaceTemplate)
        if status:
            query = query.filter(MarketplaceTemplate.status == status)
        if is_public is not None:
            query = query.filter(MarketplaceTemplate.is_public == is_public)
        if category:
            query = query.filter(MarketplaceTemplate.category == category)
        if kind:
            query = query.filter(MarketplaceTemplate.kind == kind)
        if pricing_tier:
            query = query.filter(MarketplaceTemplate.pricing_tier == pricing_tier)
        if featured is not None:
            query = query.filter(MarketplaceTemplate.is_featured == featured)

        dialect = self.db.get_bind().dialect.name
        query, rank_expr = apply_template_text_search(query, q, dialect_name=dialect)

        total = query.count()
        sort_key = (sort or "featured").lower()
        if sort_key in ("relevance", "rank") and rank_expr is not None:
            order = (rank_expr.desc(), MarketplaceTemplate.is_featured.desc(), MarketplaceTemplate.created_at.desc())
        elif sort_key in ("newest", "created", "created_at"):
            order = (MarketplaceTemplate.created_at.desc(),)
        elif sort_key in ("name", "alpha"):
            order = (MarketplaceTemplate.name.asc(),)
        elif sort_key in ("installs", "popular", "install_count"):
            order = (MarketplaceTemplate.install_count.desc(), MarketplaceTemplate.created_at.desc())
        elif sort_key in ("updated", "updated_at"):
            order = (MarketplaceTemplate.updated_at.desc(),)
        else:
            # featured (default)
            order = (
                MarketplaceTemplate.is_featured.desc(),
                MarketplaceTemplate.created_at.desc(),
            )
        items = query.order_by(*order).offset(offset).limit(limit).all()
        return items, total

    def category_counts(self) -> List[tuple[str, int]]:
        rows = (
            self.db.query(MarketplaceTemplate.category, func.count(MarketplaceTemplate.id))
            .filter(
                MarketplaceTemplate.status == TemplateStatus.PUBLISHED.value,
                MarketplaceTemplate.is_public.is_(True),
            )
            .group_by(MarketplaceTemplate.category)
            .all()
        )
        return [(str(cat.value if hasattr(cat, "value") else cat), int(count)) for cat, count in rows]

    def save_template(self, template: MarketplaceTemplate) -> MarketplaceTemplate:
        self.db.add(template)
        self.db.flush()
        return template

    # ── Versions ──────────────────────────────────────────────────────────────

    def get_version(self, version_id: UUID) -> Optional[TemplateVersion]:
        return self.db.query(TemplateVersion).filter(TemplateVersion.id == version_id).first()

    def get_version_by_number(self, template_id: UUID, version: str) -> Optional[TemplateVersion]:
        return (
            self.db.query(TemplateVersion)
            .filter(TemplateVersion.template_id == template_id, TemplateVersion.version == version)
            .first()
        )

    def get_latest_version(self, template_id: UUID) -> Optional[TemplateVersion]:
        return (
            self.db.query(TemplateVersion)
            .filter(TemplateVersion.template_id == template_id, TemplateVersion.is_latest.is_(True))
            .first()
        )

    def list_versions(self, template_id: UUID) -> List[TemplateVersion]:
        return (
            self.db.query(TemplateVersion)
            .filter(TemplateVersion.template_id == template_id)
            .order_by(TemplateVersion.created_at.desc())
            .all()
        )

    def clear_latest_flags(self, template_id: UUID) -> None:
        self.db.query(TemplateVersion).filter(TemplateVersion.template_id == template_id).update(
            {"is_latest": False},
            synchronize_session=False,
        )

    def save_version(self, version: TemplateVersion) -> TemplateVersion:
        self.db.add(version)
        self.db.flush()
        return version

    # ── Installations ─────────────────────────────────────────────────────────

    def get_install(self, install_id: UUID, company_id: UUID) -> Optional[TemplateInstallation]:
        return (
            self.db.query(TemplateInstallation)
            .filter(
                TemplateInstallation.id == install_id,
                TemplateInstallation.company_id == company_id,
            )
            .first()
        )

    def get_install_for_template(
        self, company_id: UUID, template_id: UUID
    ) -> Optional[TemplateInstallation]:
        return (
            self.db.query(TemplateInstallation)
            .filter(
                TemplateInstallation.company_id == company_id,
                TemplateInstallation.template_id == template_id,
                TemplateInstallation.status != InstallStatus.UNINSTALLED.value,
            )
            .first()
        )

    def list_installs(self, company_id: UUID) -> List[TemplateInstallation]:
        return (
            self.db.query(TemplateInstallation)
            .filter(
                TemplateInstallation.company_id == company_id,
                TemplateInstallation.status != InstallStatus.UNINSTALLED.value,
            )
            .order_by(TemplateInstallation.created_at.desc())
            .all()
        )

    def list_updates(self, company_id: UUID) -> List[TemplateInstallation]:
        return (
            self.db.query(TemplateInstallation)
            .filter(
                TemplateInstallation.company_id == company_id,
                TemplateInstallation.update_available.is_(True),
                TemplateInstallation.status != InstallStatus.UNINSTALLED.value,
            )
            .order_by(TemplateInstallation.updated_at.desc())
            .all()
        )

    def save_install(self, install: TemplateInstallation) -> TemplateInstallation:
        self.db.add(install)
        self.db.flush()
        return install

    # ── Favorites ─────────────────────────────────────────────────────────────

    def get_favorite(
        self, company_id: UUID, user_id: UUID, template_id: UUID
    ) -> Optional[TemplateFavorite]:
        return (
            self.db.query(TemplateFavorite)
            .filter(
                TemplateFavorite.company_id == company_id,
                TemplateFavorite.user_id == user_id,
                TemplateFavorite.template_id == template_id,
            )
            .first()
        )

    def list_favorites(self, company_id: UUID, user_id: UUID) -> List[MarketplaceTemplate]:
        return (
            self.db.query(MarketplaceTemplate)
            .join(TemplateFavorite, TemplateFavorite.template_id == MarketplaceTemplate.id)
            .filter(
                TemplateFavorite.company_id == company_id,
                TemplateFavorite.user_id == user_id,
                MarketplaceTemplate.status == TemplateStatus.PUBLISHED.value,
            )
            .order_by(TemplateFavorite.created_at.desc())
            .all()
        )

    def save_favorite(self, favorite: TemplateFavorite) -> TemplateFavorite:
        self.db.add(favorite)
        self.db.flush()
        return favorite

    def delete_favorite(self, favorite: TemplateFavorite) -> None:
        self.db.delete(favorite)
        self.db.flush()

    # ── Category meta / collections / events ───────────────────────────────────

    def list_category_meta(self) -> List[MarketplaceCategoryMeta]:
        return (
            self.db.query(MarketplaceCategoryMeta)
            .order_by(MarketplaceCategoryMeta.display_order.asc(), MarketplaceCategoryMeta.category_slug.asc())
            .all()
        )

    def get_category_meta(self, slug: str) -> Optional[MarketplaceCategoryMeta]:
        return (
            self.db.query(MarketplaceCategoryMeta)
            .filter(MarketplaceCategoryMeta.category_slug == slug)
            .first()
        )

    def upsert_category_meta(self, meta: MarketplaceCategoryMeta) -> MarketplaceCategoryMeta:
        self.db.add(meta)
        self.db.flush()
        return meta

    def list_collections(self, *, public_only: bool = True) -> List[MarketplaceCollection]:
        query = self.db.query(MarketplaceCollection)
        if public_only:
            query = query.filter(MarketplaceCollection.is_public.is_(True))
        return query.order_by(
            MarketplaceCollection.sort_order.asc(),
            MarketplaceCollection.name.asc(),
        ).all()

    def get_collection_by_slug(self, slug: str) -> Optional[MarketplaceCollection]:
        return (
            self.db.query(MarketplaceCollection)
            .filter(MarketplaceCollection.slug == slug)
            .first()
        )

    def get_collection(self, collection_id: UUID) -> Optional[MarketplaceCollection]:
        return (
            self.db.query(MarketplaceCollection)
            .filter(MarketplaceCollection.id == collection_id)
            .first()
        )

    def save_collection(self, collection: MarketplaceCollection) -> MarketplaceCollection:
        self.db.add(collection)
        self.db.flush()
        return collection

    def delete_collection(self, collection: MarketplaceCollection) -> None:
        self.db.delete(collection)
        self.db.flush()

    def list_collection_templates(self, collection_id: UUID) -> List[MarketplaceTemplate]:
        return (
            self.db.query(MarketplaceTemplate)
            .join(
                MarketplaceCollectionItem,
                MarketplaceCollectionItem.template_id == MarketplaceTemplate.id,
            )
            .filter(MarketplaceCollectionItem.collection_id == collection_id)
            .order_by(MarketplaceCollectionItem.position.asc())
            .all()
        )

    def replace_collection_items(
        self, collection_id: UUID, template_ids: List[UUID]
    ) -> None:
        self.db.query(MarketplaceCollectionItem).filter(
            MarketplaceCollectionItem.collection_id == collection_id
        ).delete(synchronize_session=False)
        for position, template_id in enumerate(template_ids):
            self.db.add(
                MarketplaceCollectionItem(
                    collection_id=collection_id,
                    template_id=template_id,
                    position=position,
                )
            )
        self.db.flush()

    def collection_item_counts(self) -> dict[UUID, int]:
        rows = (
            self.db.query(
                MarketplaceCollectionItem.collection_id,
                func.count(MarketplaceCollectionItem.id),
            )
            .group_by(MarketplaceCollectionItem.collection_id)
            .all()
        )
        return {cid: int(count) for cid, count in rows}

    def list_editors_choice(self, *, limit: int = 12) -> List[MarketplaceTemplate]:
        return (
            self.db.query(MarketplaceTemplate)
            .filter(
                MarketplaceTemplate.status == TemplateStatus.PUBLISHED.value,
                MarketplaceTemplate.is_public.is_(True),
                MarketplaceTemplate.is_editors_choice.is_(True),
            )
            .order_by(
                MarketplaceTemplate.is_featured.desc(),
                MarketplaceTemplate.install_count.desc(),
            )
            .limit(limit)
            .all()
        )

    def list_recent_install_templates(
        self, company_id: UUID, *, limit: int = 8
    ) -> List[MarketplaceTemplate]:
        return (
            self.db.query(MarketplaceTemplate)
            .join(
                TemplateInstallation,
                TemplateInstallation.template_id == MarketplaceTemplate.id,
            )
            .filter(
                TemplateInstallation.company_id == company_id,
                TemplateInstallation.status != InstallStatus.UNINSTALLED.value,
            )
            .order_by(TemplateInstallation.updated_at.desc())
            .limit(limit)
            .all()
        )

    def record_template_event(
        self,
        *,
        company_id: UUID,
        user_id: UUID,
        template_id: UUID,
        event_type: str = "view",
    ) -> MarketplaceTemplateEvent:
        event = MarketplaceTemplateEvent(
            company_id=company_id,
            user_id=user_id,
            template_id=template_id,
            event_type=event_type,
        )
        self.db.add(event)
        self.db.flush()
        return event

    def list_recently_viewed_templates(
        self,
        company_id: UUID,
        user_id: UUID,
        *,
        limit: int = 8,
    ) -> List[MarketplaceTemplate]:
        # Distinct by template, most recent view first
        subq = (
            self.db.query(
                MarketplaceTemplateEvent.template_id,
                func.max(MarketplaceTemplateEvent.created_at).label("last_seen"),
            )
            .filter(
                MarketplaceTemplateEvent.company_id == company_id,
                MarketplaceTemplateEvent.user_id == user_id,
                MarketplaceTemplateEvent.event_type == "view",
            )
            .group_by(MarketplaceTemplateEvent.template_id)
            .subquery()
        )
        return (
            self.db.query(MarketplaceTemplate)
            .join(subq, subq.c.template_id == MarketplaceTemplate.id)
            .filter(
                MarketplaceTemplate.status == TemplateStatus.PUBLISHED.value,
                MarketplaceTemplate.is_public.is_(True),
            )
            .order_by(subq.c.last_seen.desc())
            .limit(limit)
            .all()
        )

    def commit(self) -> None:
        self.db.commit()
