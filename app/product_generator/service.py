"""AI Product Generator orchestrator.

Reuses MarketplaceService, PublishService, KnowledgeService, DomainService,
and CompanyService — does NOT reimplement business logic.
"""
from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.agent_platform.knowledge.schemas import KnowledgeBaseCreate
from app.agent_platform.knowledge.services import KnowledgeService
from app.agent_platform.models.agent import AgentConfig
from app.agent_platform.publish.schemas import WidgetConfigUpdate
from app.agent_platform.publish.service import PublishService
from app.marketplace.schemas import ConnectRequest, InstallRequest
from app.marketplace.service import MarketplaceService
from app.product_generator.analyzer import (
    TYPE_TO_CATEGORY,
    analyze_prompt,
    build_product_config,
)
from app.product_generator.models import ProductGeneration, ProductGenerationStatus
from app.product_generator.schemas import (
    AnalysisResponse,
    GenerateRequest,
    ProductGenerationResponse,
    ProductGeneratorOutput,
)
from app.usage.dimensions import UsageDimension
from app.usage.service import UsageService

logger = logging.getLogger(__name__)

# Preferred marketplace slugs by category (seeded templates)
CATEGORY_TEMPLATE_SLUGS: Dict[str, List[str]] = {
    "website": ["ai-website-starter"],
    "landing": ["ai-landing-starter"],
    "saas": ["ai-saas-starter"],
    "crm": ["ai-saas-starter"],
    "helpdesk": ["ai-saas-starter"],
    "ecommerce": ["ai-website-starter"],
    "education": ["ai-saas-starter"],
    "healthcare": ["ai-saas-starter"],
    "real_estate": ["ai-landing-starter"],
    "restaurant": ["ai-website-starter"],
    "finance": ["ai-saas-starter"],
    "legal": ["ai-website-starter"],
}


def _slugify(value: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return s[:80] or "product"


class ProductGeneratorService:
    def __init__(self, db: Session):
        self.db = db
        self.marketplace = MarketplaceService(db)
        self.publish = PublishService(db)
        self.usage = UsageService(db)

    # ── Step 1–2: Analyze + recommend template ────────────────────────────────

    def analyze(self, prompt: str, company_id: Optional[UUID] = None) -> AnalysisResponse:
        analysis = analyze_prompt(prompt)
        template = self._pick_template(analysis.category, company_id)
        return AnalysisResponse(
            **analysis.to_dict(),
            recommended_template_slug=template.slug if template else None,
            recommended_template_name=template.name if template else None,
        )

    # ── Full generate (Steps 1–6, optional 7) ──────────────────────────────────

    def generate(
        self,
        company_id: UUID,
        user_id: UUID,
        payload: GenerateRequest,
    ) -> ProductGenerationResponse:
        job = ProductGeneration(
            company_id=company_id,
            user_id=user_id,
            prompt=payload.prompt,
            status=ProductGenerationStatus.ANALYZING,
            analysis={},
            product_config={},
            result={},
            deployment_checklist=[],
        )
        self.db.add(job)
        self.db.flush()

        try:
            # Optional factory-mode company create
            if payload.create_company:
                company_id = self._maybe_create_company(payload, company_id)
                job.company_id = company_id

            # STEP 1 — Analyze
            analysis = analyze_prompt(payload.prompt)
            job.analysis = analysis.to_dict()
            self.db.flush()

            # STEP 2 — Choose template
            job.status = ProductGenerationStatus.TEMPLATE_SELECTED
            template = None
            if payload.template_slug:
                template = self.marketplace.repo.get_by_slug(payload.template_slug)
            if not template:
                template = self._pick_template(analysis.category, company_id)
            if not template:
                raise HTTPException(
                    status_code=404,
                    detail=f"No marketplace template for category '{analysis.category}'. Seed marketplace first.",
                )
            job.template_id = template.id
            job.template_slug = template.slug
            self.db.flush()

            # STEP 4 config early (needed for agent prompt)
            config = build_product_config(analysis, payload.config_overrides)
            job.product_config = config

            # STEP 3 — Provision resources
            job.status = ProductGenerationStatus.PROVISIONING
            self.db.flush()

            agent = self._create_agent(company_id, config)
            job.agent_id = agent.id

            kb = KnowledgeService.create_knowledge_base(
                self.db,
                company_id,
                KnowledgeBaseCreate(
                    name=f"{config['name']} Knowledge",
                    description=f"Auto-created for {config['name']} ({analysis.industry})",
                ),
            )
            job.knowledge_base_id = kb.id
            try:
                KnowledgeService.attach_knowledge_base_to_agent(self.db, kb.id, agent.id)
            except Exception as exc:
                logger.warning("KB attach skipped: %s", exc)

            # STEP 4 — Configure widget theme on agent
            job.status = ProductGenerationStatus.CONFIGURING
            self.db.flush()
            self._configure_widget(agent, config)

            # Install marketplace template (clone config + connect company)
            install = self.marketplace.install(
                company_id,
                user_id,
                template.slug,
                InstallRequest(
                    agent_id=agent.id,
                    create_api_key=False,
                    config_overrides={
                        **config,
                        "generated_by": "product_generator",
                        "generation_id": str(job.id),
                    },
                ),
            )
            job.installation_id = install.id

            # Create API key via PublishService
            key_resp = self.publish.create_api_key(
                agent.id,
                company_id,
                name=f"{config['name']} Product Key",
            )
            job.api_key_id = key_resp.id
            job.api_key_prefix = key_resp.key_prefix
            job.ephemeral_api_key = key_resp.api_key

            # Ensure widget_id exists (publish will also set it)
            if not agent.widget_id:
                from app.agent_platform.publish.service import generate_widget_id

                agent.widget_id = generate_widget_id()
                self.db.add(agent)
                self.db.flush()
            job.widget_id = agent.widget_id

            # STEP 5 — Bind agent / knowledge / widget / billing flags / domain
            job.status = ProductGenerationStatus.BINDING
            self.db.flush()

            self.marketplace.connect(
                company_id,
                install.id,
                ConnectRequest(agent_id=agent.id, create_api_key=False),
            )

            if payload.create_domain_hostname:
                domain_id = self._create_domain(
                    company_id, user_id, payload.create_domain_hostname, agent
                )
                job.domain_id = domain_id

            # Mark billing support in config when template supports it
            config["bindings"] = {
                "agent_id": str(agent.id),
                "knowledge_base_id": str(kb.id),
                "widget_id": agent.widget_id,
                "installation_id": str(install.id),
                "api_key_id": str(key_resp.id),
                "supports_billing": bool(template.supports_billing),
                "supports_domains": bool(template.supports_domains),
                "domain_id": str(job.domain_id) if job.domain_id else None,
            }
            job.product_config = config

            # STEP 6 — Preview
            embed = self.publish.get_embed_snippets(
                agent.id, company_id, api_key_placeholder=key_resp.api_key
            )
            job.preview_url = embed.preview_url or self.publish.build_public_chat_url()
            job.widget_snippet = embed.script
            job.publish_status = "preview_ready"
            job.deployment_checklist = self._checklist(job, published=False)
            job.status = ProductGenerationStatus.PREVIEW_READY
            job.result = {
                "preview_url": job.preview_url,
                "publish_status": job.publish_status,
                "widget": {
                    "widget_id": job.widget_id,
                    "snippet": job.widget_snippet,
                    "iframe_url": self.publish.build_iframe_url() if job.widget_id else None,
                },
                "api_key_prefix": job.api_key_prefix,
            }
            self.db.commit()
            self.db.refresh(job)

            if payload.auto_publish:
                return self.publish_product(company_id, user_id, job.id)

            return self._to_response(job, include_api_key=True)

        except HTTPException as exc:
            job.status = ProductGenerationStatus.FAILED
            job.failure_reason = str(exc.detail)
            self.db.commit()
            raise
        except Exception as exc:
            logger.exception("Product generation failed")
            job.status = ProductGenerationStatus.FAILED
            job.failure_reason = str(exc)
            self.db.commit()
            raise HTTPException(status_code=500, detail=f"Product generation failed: {exc}") from exc

    # ── Step 7 — Publish ──────────────────────────────────────────────────────

    def publish_product(
        self,
        company_id: UUID,
        user_id: UUID,
        generation_id: UUID,
        hostname: Optional[str] = None,
    ) -> ProductGenerationResponse:
        job = self._get(generation_id, company_id)
        if job.status not in (
            ProductGenerationStatus.PREVIEW_READY,
            ProductGenerationStatus.PUBLISHED,
            ProductGenerationStatus.FAILED,
        ):
            if job.status != ProductGenerationStatus.PUBLISHING:
                raise HTTPException(
                    status_code=400,
                    detail=f"Cannot publish from status '{job.status}'",
                )

        if not job.agent_id:
            raise HTTPException(status_code=400, detail="No agent provisioned")

        job.status = ProductGenerationStatus.PUBLISHING
        self.db.flush()

        try:
            if hostname and not job.domain_id:
                agent = (
                    self.db.query(AgentConfig)
                    .filter(AgentConfig.id == job.agent_id, AgentConfig.company_id == company_id)
                    .first()
                )
                if agent:
                    job.domain_id = self._create_domain(company_id, user_id, hostname, agent)

            pub = self.publish.publish(job.agent_id, company_id, user_id)
            if pub.api_key:
                job.ephemeral_api_key = pub.api_key
                job.api_key_prefix = (pub.api_key or "")[:16] or job.api_key_prefix
            job.widget_id = pub.widget_id
            job.widget_snippet = pub.embed_script
            job.preview_url = pub.public_chat_url or job.preview_url
            job.publish_status = pub.status

            if job.installation_id:
                try:
                    self.marketplace.publish_installation(company_id, job.installation_id)
                except HTTPException:
                    # Agent may already satisfy ready — ignore soft failures
                    pass

            job.status = ProductGenerationStatus.PUBLISHED
            job.deployment_checklist = self._checklist(job, published=True)
            job.result = {
                "preview_url": job.preview_url,
                "publish_status": job.publish_status,
                "widget": {
                    "widget_id": job.widget_id,
                    "snippet": job.widget_snippet,
                    "iframe_url": pub.iframe_url,
                    "public_chat_url": pub.public_chat_url,
                },
                "api_key_prefix": job.api_key_prefix,
                "agent_id": str(job.agent_id),
                "installation_id": str(job.installation_id) if job.installation_id else None,
            }
            self.db.commit()
            self.db.refresh(job)
            return self._to_response(job, include_api_key=True)
        except HTTPException as exc:
            job.status = ProductGenerationStatus.FAILED
            job.failure_reason = str(exc.detail)
            job.publish_status = "failed"
            self.db.commit()
            raise
        except Exception as exc:
            job.status = ProductGenerationStatus.FAILED
            job.failure_reason = str(exc)
            job.publish_status = "failed"
            self.db.commit()
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    def get(self, company_id: UUID, generation_id: UUID) -> ProductGenerationResponse:
        job = self._get(generation_id, company_id)
        return self._to_response(job, include_api_key=True)

    def list(self, company_id: UUID, limit: int = 50) -> List[ProductGenerationResponse]:
        rows = (
            self.db.query(ProductGeneration)
            .filter(ProductGeneration.company_id == company_id)
            .order_by(ProductGeneration.created_at.desc())
            .limit(limit)
            .all()
        )
        return [self._to_response(r, include_api_key=False) for r in rows]

    def output(self, company_id: UUID, generation_id: UUID) -> ProductGeneratorOutput:
        job = self._get(generation_id, company_id)
        api_key = job.ephemeral_api_key
        if api_key:
            job.ephemeral_api_key = None
            self.db.commit()
        widget = (job.result or {}).get("widget") or {
            "widget_id": job.widget_id,
            "snippet": job.widget_snippet,
        }
        return ProductGeneratorOutput(
            generation_id=job.id,
            preview_url=job.preview_url,
            publish_status=job.publish_status or job.status.value,
            widget=widget,
            api_key=api_key,
            deployment_checklist=list(job.deployment_checklist or []),
            agent_id=job.agent_id,
            template_slug=job.template_slug,
            installation_id=job.installation_id,
        )

    # ── Internals ─────────────────────────────────────────────────────────────

    def _get(self, generation_id: UUID, company_id: UUID) -> ProductGeneration:
        job = (
            self.db.query(ProductGeneration)
            .filter(
                ProductGeneration.id == generation_id,
                ProductGeneration.company_id == company_id,
            )
            .first()
        )
        if not job:
            raise HTTPException(status_code=404, detail="Product generation not found")
        return job

    def _pick_template(self, category: str, company_id: Optional[UUID]):
        cat = TYPE_TO_CATEGORY.get(category, category)
        preferred = CATEGORY_TEMPLATE_SLUGS.get(cat, [])
        for slug in preferred:
            t = self.marketplace.repo.get_by_slug(slug)
            if t and getattr(t.status, "value", t.status) == "published":
                return t
        # Fallback: first published in category
        items = self.marketplace.repo.list_templates(category=cat, limit=5)
        if items:
            return items[0]
        # Absolute fallback: any featured
        featured = self.marketplace.repo.list_templates(featured=True, limit=1)
        return featured[0] if featured else None

    def _create_agent(self, company_id: UUID, config: Dict[str, Any]) -> AgentConfig:
        current_count = (
            self.db.query(AgentConfig).filter(AgentConfig.company_id == company_id).count()
        )
        try:
            self.usage.check_quota(
                company_id, UsageDimension.AGENTS_COUNT, quantity=current_count + 1
            )
        except HTTPException:
            raise
        except Exception:
            pass

        agent = AgentConfig(
            company_id=company_id,
            name=config.get("name") or "Generated Agent",
            description=f"Auto-generated for {config.get('industry')} {config.get('product_type')}",
            system_prompt_template=config.get("system_prompt") or "You are a helpful assistant.",
            temperature=0.7,
            is_template=False,
            web_config={},
            status="DRAFT",
            version=1,
        )
        self.db.add(agent)
        self.db.flush()
        try:
            self.usage.record(
                company_id,
                UsageDimension.AGENTS_COUNT,
                current_count + 1,
                agent_id=agent.id,
                source="product_generator",
            )
        except Exception:
            pass
        return agent

    def _configure_widget(self, agent: AgentConfig, config: Dict[str, Any]) -> None:
        colors = config.get("colors") or {}
        update = WidgetConfigUpdate(
            theme=config.get("theme") or "light",
            primary_color=colors.get("primary") or "#111827",
            welcome_message=config.get("welcome_message") or "Hi! How can I help?",
            logo=config.get("logo_placeholder"),
            suggested_prompts=list(config.get("suggested_prompts") or []),
            agent_name=config.get("name"),
            position="bottom-right",
        )
        # update_widget_config expects agent already flushable
        self.publish.update_widget_config(agent.id, agent.company_id, update)

    def _create_domain(
        self, company_id: UUID, user_id: UUID, hostname: str, agent: AgentConfig
    ) -> Optional[UUID]:
        try:
            from app.domains.schemas import DomainCreate
            from app.domains.service import DomainService

            domain = DomainService(self.db).create(
                company_id,
                DomainCreate(
                    hostname=hostname,
                    verification_method="TXT",
                    agent_id=agent.id,
                    widget_id=agent.widget_id,
                    is_primary=True,
                ),
                user_id,
            )
            return domain.id
        except HTTPException:
            raise
        except Exception as exc:
            logger.warning("Domain create skipped: %s", exc)
            return None

    def _maybe_create_company(self, payload: GenerateRequest, fallback: UUID) -> UUID:
        if not payload.create_company:
            return fallback
        from app.companies.schema import CompanyCreate
        from app.companies.service import CompanyService

        name = payload.company_name or (payload.prompt[:40] + " Co")
        slug = payload.company_slug or _slugify(name)
        company = CompanyService(self.db).create_company(
            CompanyCreate(name=name, slug=slug, industry=None)
        )
        return company.id

    def _checklist(self, job: ProductGeneration, *, published: bool) -> List[Dict[str, Any]]:
        def item(key: str, label: str, done: bool, href: Optional[str] = None):
            return {"key": key, "label": label, "done": done, "href": href}

        return [
            item("analyze", "Analyze product prompt", bool(job.analysis)),
            item("template", "Select marketplace template", bool(job.template_slug)),
            item("agent", "Create AI agent", bool(job.agent_id), "/app/agents"),
            item("knowledge", "Create knowledge base", bool(job.knowledge_base_id), "/app/knowledge"),
            item("api_key", "Issue API key", bool(job.api_key_prefix)),
            item("widget", "Configure widget", bool(job.widget_id)),
            item("install", "Install template", bool(job.installation_id), "/app/templates"),
            item("bind", "Bind agent + knowledge + widget", bool(job.product_config.get("bindings"))),
            item("preview", "Generate preview", bool(job.preview_url)),
            item("domain", "Attach custom domain", bool(job.domain_id), "/app/domains"),
            item("publish", "Publish via Publish Service", published and job.publish_status == "PUBLISHED"),
            item("billing", "Confirm billing plan", False, "/app/billing"),
        ]

    def _to_response(
        self, job: ProductGeneration, *, include_api_key: bool
    ) -> ProductGenerationResponse:
        api_key = None
        if include_api_key and job.ephemeral_api_key:
            api_key = job.ephemeral_api_key
            # Keep ephemeral until explicit output() clear, or clear on list=False get once
        return ProductGenerationResponse(
            id=job.id,
            company_id=job.company_id,
            prompt=job.prompt,
            status=job.status.value if hasattr(job.status, "value") else str(job.status),
            analysis=dict(job.analysis or {}),
            template_id=job.template_id,
            template_slug=job.template_slug,
            installation_id=job.installation_id,
            agent_id=job.agent_id,
            knowledge_base_id=job.knowledge_base_id,
            api_key_id=job.api_key_id,
            api_key_prefix=job.api_key_prefix,
            api_key=api_key,
            widget_id=job.widget_id,
            domain_id=job.domain_id,
            product_config=dict(job.product_config or {}),
            preview_url=job.preview_url,
            widget_snippet=job.widget_snippet,
            publish_status=job.publish_status,
            deployment_checklist=list(job.deployment_checklist or []),
            result=dict(job.result or {}),
            failure_reason=job.failure_reason,
            created_at=job.created_at,
            updated_at=job.updated_at,
        )
