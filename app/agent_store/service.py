"""AI Agent Store facade — discovery, monetization, publisher portal.

Install / update / rollback / uninstall delegate to MarketplaceService.
Paid installs gate through PaymentService before MarketplaceService.install.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import List, Optional, Tuple
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.agent_store.models import (
    AbuseReportStatus,
    AgentStoreAbuseReport,
    AgentStoreListing,
    AgentStorePublisher,
    AgentStorePurchase,
    AgentStoreReview,
    ListingStatus,
    PricingModel,
    PublisherStatus,
    PurchaseStatus,
)
from app.agent_store.schemas import (
    AbuseReportCreate,
    AbuseReportResponse,
    AbuseResolveRequest,
    ListingCreate,
    ListingDetailResponse,
    ListingResponse,
    ListingUpdate,
    ListingVersionCreate,
    ModerateListingRequest,
    PublisherAnalytics,
    PublisherResponse,
    PublisherUpsert,
    ReviewCreate,
    ReviewResponse,
    StoreAdminStats,
    StoreInstallRequest,
    StoreInstallResponse,
    StorefrontResponse,
)
from app.marketplace.schemas import InstallRequest, TemplateCreate, TemplateVersionCreate
from app.marketplace.service import MarketplaceService
from app.notifications.events import NotificationEventBus
from app.payments.model import Gateway, PaymentMethod, PaymentStatus
from app.payments.schema import PaymentCreate
from app.payments.service import PaymentService


def _now() -> datetime:
    return datetime.now(timezone.utc)


class AgentStoreService:
    def __init__(self, db: Session):
        self.db = db
        self.marketplace = MarketplaceService(db)
        self.payments = PaymentService(db)

    # ── Publisher portal ──────────────────────────────────────────────────────

    def upsert_publisher(self, company_id: UUID, payload: PublisherUpsert) -> PublisherResponse:
        existing = (
            self.db.query(AgentStorePublisher)
            .filter(AgentStorePublisher.company_id == company_id)
            .first()
        )
        slug_owner = (
            self.db.query(AgentStorePublisher)
            .filter(AgentStorePublisher.slug == payload.slug)
            .first()
        )
        if slug_owner and (not existing or slug_owner.id != existing.id):
            raise HTTPException(status_code=409, detail="Publisher slug already taken")

        if existing:
            existing.display_name = payload.display_name
            existing.slug = payload.slug
            existing.bio = payload.bio
            existing.website = payload.website
            existing.logo_url = payload.logo_url
            pub = existing
        else:
            pub = AgentStorePublisher(
                company_id=company_id,
                display_name=payload.display_name,
                slug=payload.slug,
                bio=payload.bio,
                website=payload.website,
                logo_url=payload.logo_url,
                status=PublisherStatus.ACTIVE,
            )
            self.db.add(pub)

        self.db.commit()
        self.db.refresh(pub)
        return PublisherResponse.model_validate(pub)

    def get_my_publisher(self, company_id: UUID) -> PublisherResponse:
        pub = self._require_publisher(company_id)
        return PublisherResponse.model_validate(pub)

    def create_listing(
        self,
        company_id: UUID,
        user_id: UUID,
        payload: ListingCreate,
    ) -> ListingResponse:
        pub = self._require_publisher(company_id)
        if pub.status != PublisherStatus.ACTIVE:
            raise HTTPException(status_code=403, detail="Publisher is not active")

        if self.db.query(AgentStoreListing).filter(AgentStoreListing.slug == payload.slug).first():
            raise HTTPException(status_code=409, detail="Listing slug already exists")

        if payload.pricing_model != PricingModel.FREE and payload.price_amount <= 0:
            raise HTTPException(status_code=400, detail="Paid listings require price_amount > 0")

        # Underlying installable template — reuse Marketplace create (no duplicate install logic)
        template = self.marketplace.create_template(
            TemplateCreate(
                slug=f"agent-store-{payload.slug}",
                name=payload.title,
                category=payload.marketplace_category,
                description=payload.short_description or payload.long_description[:500],
                version=payload.version,
                tags=payload.tags,
                author=pub.display_name,
                price=payload.price_amount if payload.pricing_model != PricingModel.FREE else Decimal("0"),
                is_public=False,
                is_featured=False,
                supports_agents=True,
                supports_domains=True,
                supports_billing=payload.pricing_model != PricingModel.FREE,
                default_config={
                    **(payload.default_config or {}),
                    "agent_store": True,
                    "listing_slug": payload.slug,
                    "source_agent_id": str(payload.source_agent_id) if payload.source_agent_id else None,
                },
                changelog=payload.release_notes or "Initial release",
                publish=False,
            )
        )

        listing = AgentStoreListing(
            publisher_id=pub.id,
            template_id=template.id,
            source_agent_id=payload.source_agent_id,
            slug=payload.slug,
            title=payload.title,
            short_description=payload.short_description,
            long_description=payload.long_description,
            screenshots=payload.screenshots or [],
            demo_url=payload.demo_url,
            supported_languages=payload.supported_languages or ["en"],
            knowledge_requirements=payload.knowledge_requirements,
            categories=payload.categories or [],
            tags=payload.tags or [],
            pricing_model=payload.pricing_model,
            price_amount=payload.price_amount,
            currency=payload.currency.upper(),
            status=ListingStatus.PENDING_REVIEW if payload.submit_for_review else ListingStatus.DRAFT,
            current_version=payload.version,
            release_notes=payload.release_notes,
            is_verified_badge=bool(pub.is_verified),
        )
        self.db.add(listing)
        self.db.commit()
        self.db.refresh(listing)

        if payload.submit_for_review:
            NotificationEventBus.dispatch(
                event_type="agent_store.listing_submitted",
                db=self.db,
                company_id=company_id,
                user_id=user_id,
                data={"listing_title": listing.title, "listing_id": str(listing.id)},
            )

        return self._listing_response(listing, company_id=company_id)

    def update_listing(
        self, company_id: UUID, listing_id: UUID, payload: ListingUpdate
    ) -> ListingResponse:
        listing = self._owned_listing(company_id, listing_id)
        data = payload.model_dump(exclude_unset=True)
        if "pricing_model" in data and data["pricing_model"] != PricingModel.FREE:
            amount = data.get("price_amount", listing.price_amount)
            if amount is not None and Decimal(str(amount)) <= 0:
                raise HTTPException(status_code=400, detail="Paid listings require price_amount > 0")
        if "currency" in data and data["currency"]:
            data["currency"] = data["currency"].upper()
        for key, value in data.items():
            setattr(listing, key, value)
        self.db.commit()
        self.db.refresh(listing)
        return self._listing_response(listing, company_id=company_id)

    def submit_listing(self, company_id: UUID, listing_id: UUID, user_id: UUID) -> ListingResponse:
        listing = self._owned_listing(company_id, listing_id)
        if listing.status not in (ListingStatus.DRAFT, ListingStatus.REJECTED):
            raise HTTPException(status_code=400, detail="Listing cannot be submitted from current status")
        listing.status = ListingStatus.PENDING_REVIEW
        listing.moderation_notes = None
        self.db.commit()
        self.db.refresh(listing)
        NotificationEventBus.dispatch(
            event_type="agent_store.listing_submitted",
            db=self.db,
            company_id=company_id,
            user_id=user_id,
            data={"listing_title": listing.title, "listing_id": str(listing.id)},
        )
        return self._listing_response(listing, company_id=company_id)

    def add_listing_version(
        self, company_id: UUID, listing_id: UUID, payload: ListingVersionCreate
    ) -> ListingResponse:
        listing = self._owned_listing(company_id, listing_id)
        self.marketplace.add_version(
            listing.template_id,
            TemplateVersionCreate(
                version=payload.version,
                changelog=payload.release_notes,
                config=payload.config or {},
                set_latest=True,
            ),
        )
        listing.current_version = payload.version
        if payload.release_notes is not None:
            listing.release_notes = payload.release_notes
        self.db.commit()
        self.db.refresh(listing)
        return self._listing_response(listing, company_id=company_id)

    def list_my_listings(self, company_id: UUID) -> List[ListingResponse]:
        pub = (
            self.db.query(AgentStorePublisher)
            .filter(AgentStorePublisher.company_id == company_id)
            .first()
        )
        if not pub:
            return []
        rows = (
            self.db.query(AgentStoreListing)
            .filter(AgentStoreListing.publisher_id == pub.id)
            .order_by(AgentStoreListing.updated_at.desc())
            .all()
        )
        return [self._listing_response(r, company_id=company_id) for r in rows]

    def publisher_analytics(self, company_id: UUID) -> PublisherAnalytics:
        pub = self._require_publisher(company_id)
        listings = (
            self.db.query(AgentStoreListing)
            .filter(AgentStoreListing.publisher_id == pub.id)
            .all()
        )
        listing_ids = [l.id for l in listings]
        purchases = []
        if listing_ids:
            purchases = (
                self.db.query(AgentStorePurchase)
                .filter(
                    AgentStorePurchase.listing_id.in_(listing_ids),
                    AgentStorePurchase.status == PurchaseStatus.COMPLETED,
                )
                .all()
            )
        gross = sum(Decimal(str(p.amount)) for p in purchases)
        publisher_rev = sum(Decimal(str(p.publisher_share)) for p in purchases)
        platform = sum(Decimal(str(p.platform_share)) for p in purchases)
        published = sum(1 for l in listings if l.status == ListingStatus.PUBLISHED)
        rating_count = sum(l.rating_count for l in listings)
        rating_sum = sum(float(l.rating_avg) * l.rating_count for l in listings)
        avg = (rating_sum / rating_count) if rating_count else 0.0
        return PublisherAnalytics(
            listings=len(listings),
            published_listings=published,
            total_installs=sum(l.install_count for l in listings),
            total_downloads=sum(l.download_count for l in listings),
            average_rating=round(avg, 2),
            review_count=rating_count,
            completed_purchases=len(purchases),
            gross_revenue=float(gross),
            publisher_revenue=float(publisher_rev),
            platform_fees=float(platform),
            currency=(listings[0].currency if listings else "USD"),
        )

    # ── Catalog / discovery ───────────────────────────────────────────────────

    def storefront(self, company_id: Optional[UUID] = None) -> StorefrontResponse:
        published = self._published_query().all()
        featured = [l for l in published if l.is_featured][:12]
        trending = sorted(published, key=lambda l: (l.install_count, float(l.rating_avg)), reverse=True)[:12]
        top_rated = sorted(
            [l for l in published if l.rating_count > 0],
            key=lambda l: (float(l.rating_avg), l.rating_count),
            reverse=True,
        )[:12]
        most_installed = sorted(published, key=lambda l: l.install_count, reverse=True)[:12]
        newest = sorted(
            [l for l in published if l.published_at],
            key=lambda l: l.published_at or l.created_at,
            reverse=True,
        )[:12]
        recently_updated = sorted(published, key=lambda l: l.updated_at, reverse=True)[:12]

        cat_counts: Dict[str, int] = {}
        for l in published:
            for c in l.categories or []:
                cat_counts[c] = cat_counts.get(c, 0) + 1
        categories = [{"slug": k, "name": k.replace("-", " ").title(), "count": v} for k, v in sorted(cat_counts.items())]

        return StorefrontResponse(
            featured=[self._listing_response(l, company_id) for l in featured],
            trending=[self._listing_response(l, company_id) for l in trending],
            top_rated=[self._listing_response(l, company_id) for l in top_rated],
            most_installed=[self._listing_response(l, company_id) for l in most_installed],
            newest=[self._listing_response(l, company_id) for l in newest],
            recently_updated=[self._listing_response(l, company_id) for l in recently_updated],
            categories=categories,
        )

    def search_listings(
        self,
        company_id: Optional[UUID] = None,
        q: Optional[str] = None,
        category: Optional[str] = None,
        pricing_model: Optional[str] = None,
        featured: Optional[bool] = None,
        verified: Optional[bool] = None,
        language: Optional[str] = None,
        min_rating: Optional[float] = None,
        sort: str = "trending",
        limit: int = 50,
    ) -> List[ListingResponse]:
        query = self._published_query()
        if q:
            like = f"%{q.strip()}%"
            query = query.filter(
                or_(
                    AgentStoreListing.title.ilike(like),
                    AgentStoreListing.short_description.ilike(like),
                    AgentStoreListing.long_description.ilike(like),
                    AgentStoreListing.slug.ilike(like),
                )
            )
        if pricing_model:
            try:
                query = query.filter(AgentStoreListing.pricing_model == PricingModel(pricing_model))
            except ValueError as exc:
                raise HTTPException(status_code=400, detail="Invalid pricing_model") from exc
        if featured is not None:
            query = query.filter(AgentStoreListing.is_featured.is_(featured))
        if verified is not None:
            query = query.filter(AgentStoreListing.is_verified_badge.is_(verified))
        if min_rating is not None:
            query = query.filter(AgentStoreListing.rating_avg >= min_rating)

        rows = query.all()
        if category:
            rows = [r for r in rows if category in (r.categories or [])]
        if language:
            rows = [r for r in rows if language in (r.supported_languages or [])]

        if sort == "newest":
            rows.sort(key=lambda l: l.published_at or l.created_at, reverse=True)
        elif sort == "top_rated":
            rows.sort(key=lambda l: (float(l.rating_avg), l.rating_count), reverse=True)
        elif sort == "most_installed":
            rows.sort(key=lambda l: l.install_count, reverse=True)
        elif sort == "price_asc":
            rows.sort(key=lambda l: Decimal(str(l.price_amount)))
        elif sort == "price_desc":
            rows.sort(key=lambda l: Decimal(str(l.price_amount)), reverse=True)
        else:  # trending
            rows.sort(key=lambda l: (l.install_count, float(l.rating_avg)), reverse=True)

        return [self._listing_response(r, company_id) for r in rows[:limit]]

    def get_listing(self, listing_id_or_slug: str, company_id: Optional[UUID] = None) -> ListingDetailResponse:
        listing = self._resolve_listing(listing_id_or_slug, allow_unpublished_for=company_id)
        versions = [
            v.model_dump() for v in self.marketplace.list_versions(listing.template_id)
        ]
        reviews = (
            self.db.query(AgentStoreReview)
            .filter(
                AgentStoreReview.listing_id == listing.id,
                AgentStoreReview.is_visible.is_(True),
            )
            .order_by(AgentStoreReview.created_at.desc())
            .limit(50)
            .all()
        )
        related = self._related(listing, limit=6)
        recommendations = self._recommendations(listing, company_id, limit=6)
        return ListingDetailResponse(
            listing=self._listing_response(listing, company_id),
            versions=versions,
            reviews=[ReviewResponse.model_validate(r) for r in reviews],
            related=[self._listing_response(r, company_id) for r in related],
            recommendations=[self._listing_response(r, company_id) for r in recommendations],
        )

    # ── Install / purchase / lifecycle ────────────────────────────────────────

    def install(
        self,
        company_id: UUID,
        user_id: UUID,
        listing_id_or_slug: str,
        payload: StoreInstallRequest,
    ) -> StoreInstallResponse:
        listing = self._resolve_listing(listing_id_or_slug)
        if listing.status != ListingStatus.PUBLISHED:
            raise HTTPException(status_code=400, detail="Listing is not published")

        publisher = self.db.get(AgentStorePublisher, listing.publisher_id)
        if publisher and publisher.company_id == company_id:
            raise HTTPException(status_code=400, detail="Cannot install your own listing")

        purchase_id: Optional[UUID] = None
        payment_id: Optional[UUID] = None

        if listing.pricing_model != PricingModel.FREE:
            existing = self._completed_purchase(listing.id, company_id)
            if not existing:
                payment_id, purchase_id = self._charge_and_record_purchase(
                    listing, publisher, company_id, user_id, payload
                )
            else:
                purchase_id = existing.id
                payment_id = existing.payment_id

        install_resp = self.marketplace.install(
            company_id,
            user_id,
            str(listing.template_id),
            InstallRequest(
                version=payload.version or listing.current_version,
                agent_id=payload.agent_id,
                create_api_key=payload.create_api_key,
                api_key_name=f"Agent Store: {listing.title}",
                config_overrides={
                    **(payload.config_overrides or {}),
                    "agent_store_listing_id": str(listing.id),
                    "agent_store_slug": listing.slug,
                },
            ),
        )

        listing.install_count = int(listing.install_count or 0) + 1
        listing.download_count = int(listing.download_count or 0) + 1

        if purchase_id:
            purchase = self.db.get(AgentStorePurchase, purchase_id)
            if purchase:
                purchase.installation_id = install_resp.id
                if purchase.status == PurchaseStatus.PENDING:
                    purchase.status = PurchaseStatus.COMPLETED

        publish_status = None
        if payload.publish_agent and install_resp.agent_id:
            try:
                pub_install = self.marketplace.publish_installation(company_id, install_resp.id)
                publish_status = pub_install.status
            except HTTPException:
                publish_status = "publish_skipped"

        self.db.commit()

        NotificationEventBus.dispatch(
            event_type="agent_store.installed",
            db=self.db,
            company_id=company_id,
            user_id=user_id,
            data={"listing_title": listing.title, "listing_id": str(listing.id)},
        )

        return StoreInstallResponse(
            listing_id=listing.id,
            installation_id=install_resp.id,
            purchase_id=purchase_id,
            payment_id=payment_id,
            agent_id=install_resp.agent_id,
            status=install_resp.status,
            publish_status=publish_status,
        )

    def update_install(
        self, company_id: UUID, installation_id: UUID, version: Optional[str] = None
    ) -> dict:
        resp = self.marketplace.update_installation(company_id, installation_id, version)
        return resp.model_dump()

    def rollback_install(self, company_id: UUID, installation_id: UUID) -> dict:
        resp = self.marketplace.rollback_installation(company_id, installation_id)
        return resp.model_dump()

    def uninstall(self, company_id: UUID, installation_id: UUID) -> dict:
        return self.marketplace.uninstall(company_id, installation_id)

    def list_installed(self, company_id: UUID) -> List[dict]:
        installs = self.marketplace.list_installed(company_id)
        out = []
        for inst in installs:
            listing = (
                self.db.query(AgentStoreListing)
                .filter(AgentStoreListing.template_id == inst.template_id)
                .first()
            )
            if not listing:
                continue
            data = inst.model_dump()
            data["listing_id"] = listing.id
            data["listing_slug"] = listing.slug
            data["listing_title"] = listing.title
            out.append(data)
        return out

    # ── Reviews ───────────────────────────────────────────────────────────────

    def add_review(
        self, company_id: UUID, user_id: UUID, listing_id: UUID, payload: ReviewCreate
    ) -> ReviewResponse:
        listing = self.db.get(AgentStoreListing, listing_id)
        if not listing or listing.status != ListingStatus.PUBLISHED:
            raise HTTPException(status_code=404, detail="Listing not found")

        # Prefer reviewers who installed (or purchased)
        installed = any(i.get("listing_id") == listing_id for i in self.list_installed(company_id))
        purchased = self._completed_purchase(listing_id, company_id) is not None
        if not installed and not purchased and listing.pricing_model != PricingModel.FREE:
            raise HTTPException(status_code=403, detail="Install or purchase required to review")

        existing = (
            self.db.query(AgentStoreReview)
            .filter(
                AgentStoreReview.listing_id == listing_id,
                AgentStoreReview.company_id == company_id,
                AgentStoreReview.user_id == user_id,
            )
            .first()
        )
        if existing:
            existing.rating = payload.rating
            existing.title = payload.title
            existing.body = payload.body
            review = existing
        else:
            review = AgentStoreReview(
                listing_id=listing_id,
                company_id=company_id,
                user_id=user_id,
                rating=payload.rating,
                title=payload.title,
                body=payload.body,
            )
            self.db.add(review)

        self.db.flush()
        self._recompute_rating(listing)
        self.db.commit()
        self.db.refresh(review)
        return ReviewResponse.model_validate(review)

    # ── Abuse ─────────────────────────────────────────────────────────────────

    def report_abuse(
        self, company_id: UUID, user_id: UUID, listing_id: UUID, payload: AbuseReportCreate
    ) -> AbuseReportResponse:
        listing = self.db.get(AgentStoreListing, listing_id)
        if not listing:
            raise HTTPException(status_code=404, detail="Listing not found")
        report = AgentStoreAbuseReport(
            listing_id=listing_id,
            reporter_company_id=company_id,
            reporter_user_id=user_id,
            reason=payload.reason,
            details=payload.details,
        )
        self.db.add(report)
        self.db.commit()
        self.db.refresh(report)
        return AbuseReportResponse.model_validate(report)

    # ── Admin moderation ──────────────────────────────────────────────────────

    def moderate_listing(
        self, admin_user_id: UUID, listing_id: UUID, payload: ModerateListingRequest
    ) -> ListingResponse:
        listing = self.db.get(AgentStoreListing, listing_id)
        if not listing:
            raise HTTPException(status_code=404, detail="Listing not found")
        listing.moderated_by = admin_user_id
        if payload.notes is not None:
            listing.moderation_notes = payload.notes

        action = payload.action
        if action == "approve":
            listing.status = ListingStatus.PUBLISHED
            listing.published_at = listing.published_at or _now()
            self.marketplace.publish_template(listing.template_id)
            pub = self.db.get(AgentStorePublisher, listing.publisher_id)
            if pub:
                NotificationEventBus.dispatch(
                    event_type="agent_store.listing_approved",
                    db=self.db,
                    company_id=pub.company_id,
                    user_id=None,
                    data={"listing_title": listing.title, "listing_id": str(listing.id)},
                )
        elif action == "reject":
            listing.status = ListingStatus.REJECTED
        elif action == "suspend":
            listing.status = ListingStatus.SUSPENDED
            listing.is_featured = False
        elif action == "feature":
            listing.is_featured = True
            if listing.status != ListingStatus.PUBLISHED:
                raise HTTPException(status_code=400, detail="Only published listings can be featured")
        elif action == "unfeature":
            listing.is_featured = False
        elif action == "verify":
            listing.is_verified_badge = True
            pub = self.db.get(AgentStorePublisher, listing.publisher_id)
            if pub:
                pub.is_verified = True

        self.db.commit()
        self.db.refresh(listing)
        return self._listing_response(listing)

    def list_pending_listings(self, limit: int = 50) -> List[ListingResponse]:
        rows = (
            self.db.query(AgentStoreListing)
            .filter(AgentStoreListing.status == ListingStatus.PENDING_REVIEW)
            .order_by(AgentStoreListing.created_at.asc())
            .limit(limit)
            .all()
        )
        return [self._listing_response(r) for r in rows]

    def list_abuse_reports(
        self, status_filter: Optional[str] = None, limit: int = 50
    ) -> List[AbuseReportResponse]:
        q = self.db.query(AgentStoreAbuseReport)
        if status_filter:
            try:
                q = q.filter(AgentStoreAbuseReport.status == AbuseReportStatus(status_filter))
            except ValueError as exc:
                raise HTTPException(status_code=400, detail="Invalid status") from exc
        rows = q.order_by(AgentStoreAbuseReport.created_at.desc()).limit(limit).all()
        return [AbuseReportResponse.model_validate(r) for r in rows]

    def resolve_abuse(self, report_id: UUID, payload: AbuseResolveRequest) -> AbuseReportResponse:
        report = self.db.get(AgentStoreAbuseReport, report_id)
        if not report:
            raise HTTPException(status_code=404, detail="Report not found")
        report.status = payload.status
        report.resolution_notes = payload.resolution_notes
        self.db.commit()
        self.db.refresh(report)
        return AbuseReportResponse.model_validate(report)

    def admin_stats(self) -> StoreAdminStats:
        total = self.db.query(func.count(AgentStoreListing.id)).scalar() or 0
        pending = (
            self.db.query(func.count(AgentStoreListing.id))
            .filter(AgentStoreListing.status == ListingStatus.PENDING_REVIEW)
            .scalar()
            or 0
        )
        published = (
            self.db.query(func.count(AgentStoreListing.id))
            .filter(AgentStoreListing.status == ListingStatus.PUBLISHED)
            .scalar()
            or 0
        )
        suspended = (
            self.db.query(func.count(AgentStoreListing.id))
            .filter(AgentStoreListing.status == ListingStatus.SUSPENDED)
            .scalar()
            or 0
        )
        open_abuse = (
            self.db.query(func.count(AgentStoreAbuseReport.id))
            .filter(AgentStoreAbuseReport.status == AbuseReportStatus.OPEN)
            .scalar()
            or 0
        )
        purchases = (
            self.db.query(AgentStorePurchase)
            .filter(AgentStorePurchase.status == PurchaseStatus.COMPLETED)
            .all()
        )
        gmv = float(sum(Decimal(str(p.amount)) for p in purchases))
        return StoreAdminStats(
            listings_total=int(total),
            pending_review=int(pending),
            published=int(published),
            suspended=int(suspended),
            open_abuse_reports=int(open_abuse),
            purchases_completed=len(purchases),
            gross_gmv=gmv,
        )

    # ── Internals ─────────────────────────────────────────────────────────────

    def _published_query(self):
        return self.db.query(AgentStoreListing).filter(
            AgentStoreListing.status == ListingStatus.PUBLISHED
        )

    def _require_publisher(self, company_id: UUID) -> AgentStorePublisher:
        pub = (
            self.db.query(AgentStorePublisher)
            .filter(AgentStorePublisher.company_id == company_id)
            .first()
        )
        if not pub:
            raise HTTPException(status_code=404, detail="Register as a publisher first")
        return pub

    def _owned_listing(self, company_id: UUID, listing_id: UUID) -> AgentStoreListing:
        pub = self._require_publisher(company_id)
        listing = self.db.get(AgentStoreListing, listing_id)
        if not listing or listing.publisher_id != pub.id:
            raise HTTPException(status_code=404, detail="Listing not found")
        return listing

    def _resolve_listing(
        self, listing_id_or_slug: str, allow_unpublished_for: Optional[UUID] = None
    ) -> AgentStoreListing:
        listing: Optional[AgentStoreListing] = None
        try:
            lid = UUID(listing_id_or_slug)
            listing = self.db.get(AgentStoreListing, lid)
        except ValueError:
            listing = (
                self.db.query(AgentStoreListing)
                .filter(AgentStoreListing.slug == listing_id_or_slug)
                .first()
            )
        if not listing:
            raise HTTPException(status_code=404, detail="Listing not found")
        if listing.status == ListingStatus.PUBLISHED:
            return listing
        if allow_unpublished_for:
            pub = self.db.get(AgentStorePublisher, listing.publisher_id)
            if pub and pub.company_id == allow_unpublished_for:
                return listing
        raise HTTPException(status_code=404, detail="Listing not found")

    def _completed_purchase(
        self, listing_id: UUID, company_id: UUID
    ) -> Optional[AgentStorePurchase]:
        return (
            self.db.query(AgentStorePurchase)
            .filter(
                AgentStorePurchase.listing_id == listing_id,
                AgentStorePurchase.buyer_company_id == company_id,
                AgentStorePurchase.status == PurchaseStatus.COMPLETED,
            )
            .first()
        )

    def _charge_and_record_purchase(
        self,
        listing: AgentStoreListing,
        publisher: Optional[AgentStorePublisher],
        company_id: UUID,
        user_id: UUID,
        payload: StoreInstallRequest,
    ) -> Tuple[UUID, UUID]:
        try:
            gateway = Gateway(payload.gateway)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Invalid payment gateway") from exc
        try:
            method = PaymentMethod(payload.payment_method)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Invalid payment method") from exc

        amount = Decimal(str(listing.price_amount))
        payment = self.payments.create_payment(
            PaymentCreate(
                amount=amount,
                currency=listing.currency,
                payment_method=method,
                gateway=gateway,
                invoice_number=f"ASTORE-{listing.slug[:40]}",
                payment_metadata={
                    "agent_store_listing_id": str(listing.id),
                    "pricing_model": listing.pricing_model.value,
                },
            ),
            company_id,
            user_id,
        )
        if payment.status != PaymentStatus.SUCCESS:
            purchase = AgentStorePurchase(
                listing_id=listing.id,
                buyer_company_id=company_id,
                buyer_user_id=user_id,
                payment_id=payment.id,
                amount=amount,
                currency=listing.currency,
                status=PurchaseStatus.FAILED,
                pricing_model=listing.pricing_model.value,
                meta={"payment_status": payment.status.value},
            )
            self.db.add(purchase)
            self.db.commit()
            raise HTTPException(status_code=402, detail="Payment failed for paid agent")

        bps = publisher.revenue_share_bps if publisher else 7000
        publisher_share = (amount * Decimal(bps) / Decimal(10000)).quantize(Decimal("0.01"))
        platform_share = (amount - publisher_share).quantize(Decimal("0.01"))

        purchase = AgentStorePurchase(
            listing_id=listing.id,
            buyer_company_id=company_id,
            buyer_user_id=user_id,
            payment_id=payment.id,
            amount=amount,
            currency=listing.currency,
            publisher_share=publisher_share,
            platform_share=platform_share,
            status=PurchaseStatus.COMPLETED,
            pricing_model=listing.pricing_model.value,
            meta={"payment_status": payment.status.value},
        )
        self.db.add(purchase)
        self.db.flush()
        return payment.id, purchase.id

    def _recompute_rating(self, listing: AgentStoreListing) -> None:
        agg = (
            self.db.query(
                func.avg(AgentStoreReview.rating),
                func.count(AgentStoreReview.id),
            )
            .filter(
                AgentStoreReview.listing_id == listing.id,
                AgentStoreReview.is_visible.is_(True),
            )
            .one()
        )
        avg, count = agg[0], agg[1]
        listing.rating_avg = Decimal(str(round(float(avg or 0), 2)))
        listing.rating_count = int(count or 0)

    def _related(self, listing: AgentStoreListing, limit: int = 6) -> List[AgentStoreListing]:
        cats = set(listing.categories or [])
        candidates = [
            l
            for l in self._published_query().filter(AgentStoreListing.id != listing.id).all()
            if cats.intersection(set(l.categories or []))
        ]
        candidates.sort(key=lambda l: (l.install_count, float(l.rating_avg)), reverse=True)
        if len(candidates) < limit:
            extras = [
                l
                for l in self._published_query().filter(AgentStoreListing.id != listing.id).all()
                if l not in candidates
            ]
            extras.sort(key=lambda l: l.install_count, reverse=True)
            candidates.extend(extras)
        return candidates[:limit]

    def _recommendations(
        self,
        listing: AgentStoreListing,
        company_id: Optional[UUID],
        limit: int = 6,
    ) -> List[AgentStoreListing]:
        # Simple: top-rated in overlapping categories, excluding already installed
        installed_template_ids = set()
        if company_id:
            for inst in self.marketplace.list_installed(company_id):
                installed_template_ids.add(inst.template_id)
        related = self._related(listing, limit=limit * 2)
        filtered = [l for l in related if l.template_id not in installed_template_ids]
        return filtered[:limit]

    def _listing_response(
        self, listing: AgentStoreListing, company_id: Optional[UUID] = None
    ) -> ListingResponse:
        pub = self.db.get(AgentStorePublisher, listing.publisher_id)
        installed = False
        purchased = False
        if company_id:
            purchased = self._completed_purchase(listing.id, company_id) is not None
            for inst in self.marketplace.list_installed(company_id):
                if inst.template_id == listing.template_id:
                    installed = True
                    break
        return ListingResponse(
            id=listing.id,
            publisher_id=listing.publisher_id,
            publisher_name=pub.display_name if pub else None,
            publisher_verified=bool(pub.is_verified) if pub else False,
            template_id=listing.template_id,
            source_agent_id=listing.source_agent_id,
            slug=listing.slug,
            title=listing.title,
            short_description=listing.short_description or "",
            long_description=listing.long_description or "",
            screenshots=listing.screenshots or [],
            demo_url=listing.demo_url,
            supported_languages=listing.supported_languages or [],
            knowledge_requirements=listing.knowledge_requirements,
            categories=listing.categories or [],
            tags=listing.tags or [],
            pricing_model=listing.pricing_model,
            price_amount=Decimal(str(listing.price_amount or 0)),
            currency=listing.currency,
            status=listing.status,
            is_featured=bool(listing.is_featured),
            is_verified_badge=bool(listing.is_verified_badge),
            install_count=int(listing.install_count or 0),
            download_count=int(listing.download_count or 0),
            rating_avg=Decimal(str(listing.rating_avg or 0)),
            rating_count=int(listing.rating_count or 0),
            current_version=listing.current_version,
            release_notes=listing.release_notes,
            published_at=listing.published_at,
            created_at=listing.created_at,
            updated_at=listing.updated_at,
            installed=installed,
            purchased=purchased,
        )
