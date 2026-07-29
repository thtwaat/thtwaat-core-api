"""
Copilot tool adapters — thin wrappers over existing platform services.
No business logic duplication.
"""
from __future__ import annotations

import logging
import re
from typing import Any, Dict
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.agent_platform.knowledge.schemas import KnowledgeBaseCreate
from app.agent_platform.knowledge.services import KnowledgeService
from app.agent_platform.models.agent import AgentConfig
from app.agent_platform.publish.service import PublishService
from app.branding.schemas import BrandingUpdate
from app.branding.service import BrandingService
from app.domains.schemas import DomainCreate
from app.domains.service import DomainService
from app.enterprise.models import UnitType
from app.enterprise.schemas import InviteMember, UnitCreate
from app.enterprise.service import EnterpriseService
from app.marketplace.schemas import InstallRequest
from app.marketplace.service import MarketplaceService
from app.monitoring.schemas import RetryJobRequest
from app.monitoring.service import MonitoringOpsService
from app.payments.subscriptions.schema import StripeCheckoutRequest
from app.payments.subscriptions.service import SubscriptionService
from app.product_generator.schemas import GenerateRequest
from app.product_generator.service import ProductGeneratorService
from app.usage.dimensions import UsageDimension
from app.usage.service import UsageService

logger = logging.getLogger(__name__)


def _slugify(value: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", (value or "").lower()).strip("-")
    return s[:80] or "unit"


def _jsonable(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, dict):
        return {k: _jsonable(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_jsonable(v) for v in value]
    if isinstance(value, UUID):
        return str(value)
    return value


class CopilotToolRuntime:
    """Binds a DB session + tenant context to tool implementations."""

    def __init__(self, db: Session, company_id: UUID, user_id: UUID, user_role: str) -> None:
        self.db = db
        self.company_id = company_id
        self.user_id = user_id
        self.user_role = (user_role or "").lower()
        self.generator = ProductGeneratorService(db)
        self.marketplace = MarketplaceService(db)
        self.publish = PublishService(db)
        self.domains = DomainService(db)
        self.branding = BrandingService(db)
        self.enterprise = EnterpriseService(db)
        self.subscriptions = SubscriptionService(db)
        self.usage = UsageService(db)
        self.monitoring = MonitoringOpsService(db)

    def _require_platform_admin(self) -> None:
        if self.user_role != "super_admin":
            raise HTTPException(
                status_code=403,
                detail="This Copilot tool requires platform admin (super_admin).",
            )

    def execute(self, tool_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        handlers = {
            "create_agent": self.create_agent,
            "analyze_prompt": self.analyze_prompt,
            "generate_product": self.generate_product,
            "install_template": self.install_template,
            "create_knowledge_base": self.create_knowledge_base,
            "publish_agent": self.publish_agent,
            "publish_product": self.publish_product,
            "update_branding": self.update_branding,
            "publish_branding": self.publish_branding,
            "connect_domain": self.connect_domain,
            "create_organization": self.create_organization,
            "invite_member": self.invite_member,
            "show_platform_report": self.show_platform_report,
            "show_usage_dashboard": self.show_usage_dashboard,
            "show_health": self.show_health,
            "show_monitoring": self.show_monitoring,
            "retry_failed_job": self.retry_failed_job,
            "list_failed_jobs": self.list_failed_jobs,
            "billing_checkout": self.billing_checkout,
        }
        if tool_name not in handlers:
            raise HTTPException(status_code=400, detail=f"Unknown tool: {tool_name}")
        return handlers[tool_name](args or {})

    # ── Implementations ───────────────────────────────────────────────────────

    def create_agent(self, args: Dict[str, Any]) -> Dict[str, Any]:
        name = args.get("agent_name") or args.get("name") or "Copilot Agent"
        prompt = args.get("system_prompt_template") or (
            f"You are {name}, a helpful AI assistant for this company."
        )
        current_count = (
            self.db.query(AgentConfig).filter(AgentConfig.company_id == self.company_id).count()
        )
        try:
            self.usage.check_quota(
                self.company_id, UsageDimension.AGENTS_COUNT, quantity=current_count + 1
            )
        except HTTPException:
            raise
        except Exception:
            pass

        agent = AgentConfig(
            company_id=self.company_id,
            name=name,
            description=args.get("description") or "Created by AI Copilot",
            system_prompt_template=prompt,
            temperature=float(args.get("temperature", 0.7)),
            is_template=False,
            web_config=args.get("web_config") or {},
            status="DRAFT",
            version=1,
        )
        self.db.add(agent)
        self.db.flush()
        try:
            self.usage.record(
                self.company_id,
                UsageDimension.AGENTS_COUNT,
                current_count + 1,
                agent_id=agent.id,
                source="copilot",
            )
        except Exception:
            pass
        return {
            "agent_id": str(agent.id),
            "name": agent.name,
            "status": agent.status,
        }

    def analyze_prompt(self, args: Dict[str, Any]) -> Dict[str, Any]:
        prompt = args.get("prompt")
        if not prompt:
            raise HTTPException(status_code=422, detail="prompt is required")
        result = self.generator.analyze(prompt, self.company_id)
        return _jsonable(result)

    def generate_product(self, args: Dict[str, Any]) -> Dict[str, Any]:
        prompt = args.get("prompt")
        if not prompt:
            raise HTTPException(status_code=422, detail="prompt is required")
        payload = GenerateRequest(
            prompt=prompt,
            template_slug=args.get("template_slug"),
            config_overrides=args.get("config_overrides") or {},
            create_domain_hostname=args.get("hostname") or args.get("create_domain_hostname"),
            auto_publish=bool(args.get("auto_publish", False)),
            create_company=False,
        )
        generation = self.generator.generate(self.company_id, self.user_id, payload)
        out = _jsonable(generation)
        return {
            "generation_id": str(generation.id),
            "status": generation.status,
            "preview_url": generation.preview_url,
            "agent_id": str(generation.agent_id) if generation.agent_id else None,
            "template_slug": generation.template_slug,
            "installation_id": str(generation.installation_id) if generation.installation_id else None,
            "knowledge_base_id": str(generation.knowledge_base_id)
            if generation.knowledge_base_id
            else None,
            "result": out,
        }

    def install_template(self, args: Dict[str, Any]) -> Dict[str, Any]:
        slug = args.get("template_slug") or args.get("template_id_or_slug")
        if not slug:
            raise HTTPException(status_code=422, detail="template_slug is required")
        agent_id = args.get("agent_id")
        install = self.marketplace.install(
            self.company_id,
            self.user_id,
            str(slug),
            InstallRequest(
                version=args.get("version"),
                agent_id=UUID(str(agent_id)) if agent_id else None,
                create_api_key=bool(args.get("create_api_key", True)),
                config_overrides=args.get("config_overrides") or {},
            ),
        )
        return {
            "installation_id": str(install.id),
            "template_slug": install.template_slug,
            "status": install.status,
            "agent_id": str(install.agent_id) if install.agent_id else None,
        }

    def create_knowledge_base(self, args: Dict[str, Any]) -> Dict[str, Any]:
        name = args.get("name") or args.get("agent_name") or "Copilot Knowledge"
        kb = KnowledgeService.create_knowledge_base(
            self.db,
            self.company_id,
            KnowledgeBaseCreate(name=name, description=args.get("description")),
        )
        agent_id = args.get("agent_id")
        if agent_id:
            try:
                KnowledgeService.attach_knowledge_base_to_agent(
                    self.db, kb.id, UUID(str(agent_id))
                )
            except Exception as exc:
                logger.warning("KB attach via copilot: %s", exc)
        return {
            "knowledge_base_id": str(kb.id),
            "name": kb.name,
            "hint": "Upload files via /api/v1/v2/knowledge/upload or onboarding knowledge upload",
        }

    def publish_agent(self, args: Dict[str, Any]) -> Dict[str, Any]:
        agent_id = args.get("agent_id")
        if not agent_id:
            # Latest draft/published for company
            agent = (
                self.db.query(AgentConfig)
                .filter(AgentConfig.company_id == self.company_id)
                .order_by(AgentConfig.updated_at.desc())
                .first()
            )
            if not agent:
                raise HTTPException(status_code=404, detail="No agent found to publish")
            agent_id = agent.id
        result = self.publish.publish(UUID(str(agent_id)), self.company_id, self.user_id)
        return _jsonable(result)

    def publish_product(self, args: Dict[str, Any]) -> Dict[str, Any]:
        generation_id = args.get("generation_id")
        if not generation_id:
            raise HTTPException(status_code=422, detail="generation_id is required")
        published = self.generator.publish_product(
            self.company_id,
            self.user_id,
            UUID(str(generation_id)),
            hostname=args.get("hostname"),
        )
        return {
            "generation_id": str(published.id),
            "publish_status": published.publish_status,
            "preview_url": published.preview_url,
        }

    def update_branding(self, args: Dict[str, Any]) -> Dict[str, Any]:
        payload: Dict[str, Any] = {}
        if args.get("primary_color"):
            payload["primary_color"] = args["primary_color"]
        if args.get("company_name"):
            payload["company_name"] = args["company_name"]
        if args.get("secondary_color"):
            payload["secondary_color"] = args["secondary_color"]
        # Allow passthrough of known BrandingUpdate fields
        for key in ("accent_color", "font_family", "logo_url"):
            if args.get(key):
                payload[key] = args[key]
        if not payload:
            # Ensure branding row exists
            brand = self.branding.get(self.company_id)
            return _jsonable(brand)
        updated = self.branding.update(self.company_id, BrandingUpdate(**payload))
        return _jsonable(updated)

    def publish_branding(self, args: Dict[str, Any]) -> Dict[str, Any]:
        return _jsonable(self.branding.publish(self.company_id))

    def connect_domain(self, args: Dict[str, Any]) -> Dict[str, Any]:
        hostname = args.get("hostname")
        if not hostname:
            raise HTTPException(status_code=422, detail="hostname is required")
        agent_id = args.get("agent_id")
        domain = self.domains.create(
            self.company_id,
            DomainCreate(
                hostname=hostname,
                verification_method=args.get("verification_method") or "TXT",
                agent_id=UUID(str(agent_id)) if agent_id else None,
                is_primary=bool(args.get("is_primary", True)),
            ),
            self.user_id,
        )
        return _jsonable(domain)

    def create_organization(self, args: Dict[str, Any]) -> Dict[str, Any]:
        name = args.get("unit_name") or args.get("name") or "Organization"
        slug = args.get("slug") or _slugify(name)
        # Reuse existing org root if present
        existing = self.enterprise.list_units(self.company_id, UnitType.ORGANIZATION)
        if existing and not args.get("force_new"):
            row = existing[0]
            return {
                "unit_id": str(row.id),
                "name": row.name,
                "slug": row.slug,
                "unit_type": row.unit_type.value
                if hasattr(row.unit_type, "value")
                else row.unit_type,
                "already_existed": True,
            }
        unit = self.enterprise.create_unit(
            self.company_id,
            self.user_id,
            UnitCreate(
                name=name,
                slug=slug,
                unit_type=UnitType.ORGANIZATION,
                description=args.get("description") or "Created by AI Copilot",
            ),
        )
        return {
            "unit_id": str(unit.id),
            "name": unit.name,
            "slug": unit.slug,
            "unit_type": unit.unit_type.value
            if hasattr(unit.unit_type, "value")
            else unit.unit_type,
        }

    def invite_member(self, args: Dict[str, Any]) -> Dict[str, Any]:
        email = args.get("email")
        if not email:
            raise HTTPException(status_code=422, detail="email is required")
        first = args.get("first_name") or "Invited"
        last = args.get("last_name") or "User"
        result = self.enterprise.invite_member(
            self.company_id,
            self.user_id,
            InviteMember(
                email=email,
                first_name=first,
                last_name=last,
                builtin_role=args.get("role") or args.get("builtin_role") or "employee",
            ),
        )
        return _jsonable(result)

    def show_platform_report(self, args: Dict[str, Any]) -> Dict[str, Any]:
        self._require_platform_admin()
        period = args.get("period") or "daily"
        return _jsonable(self.monitoring.platform_report(period))

    def show_usage_dashboard(self, args: Dict[str, Any]) -> Dict[str, Any]:
        return _jsonable(self.usage.dashboard(self.company_id))

    async def show_health_async(self, args: Dict[str, Any]) -> Dict[str, Any]:
        self._require_platform_admin()
        return _jsonable(await self.monitoring.system_health())

    def show_health(self, args: Dict[str, Any]) -> Dict[str, Any]:
        self._require_platform_admin()
        # Sync wrapper using deploy health helpers
        from app.deploy import health as health_mod
        from app.monitoring import queue as queue_mod

        db_c = health_mod.check_database(self.db)
        workers = health_mod.check_workers()
        storage = health_mod.check_storage()
        q = queue_mod.queue_stats()
        return {
            "database": db_c,
            "workers": workers,
            "storage": storage,
            "queue": q,
            "status": "healthy"
            if db_c.get("ok") and storage.get("ok")
            else "degraded",
        }

    def show_monitoring(self, args: Dict[str, Any]) -> Dict[str, Any]:
        self._require_platform_admin()
        return _jsonable(self.monitoring.observability())

    def list_failed_jobs(self, args: Dict[str, Any]) -> Dict[str, Any]:
        self._require_platform_admin()
        jobs = self.monitoring.list_jobs(limit=int(args.get("limit") or 20))
        return {
            "dead_letter": jobs.dead_letter,
            "stats": jobs.stats,
            "diagnostics_hint": "Use retry_failed_job with index to requeue a dead-letter item",
        }

    def retry_failed_job(self, args: Dict[str, Any]) -> Dict[str, Any]:
        self._require_platform_admin()
        index = int(args.get("job_index") or args.get("index") or 0)
        return self.monitoring.retry_job(
            self.user_id, RetryJobRequest(index=index, dead=True)
        )

    def billing_checkout(self, args: Dict[str, Any]) -> Dict[str, Any]:
        plan_id = args.get("plan_id")
        success_url = args.get("success_url")
        cancel_url = args.get("cancel_url")
        if not plan_id or not success_url or not cancel_url:
            raise HTTPException(
                status_code=422,
                detail="plan_id, success_url, and cancel_url are required for checkout",
            )
        checkout = self.subscriptions.create_stripe_checkout_session(
            self.company_id,
            StripeCheckoutRequest(
                plan_id=UUID(str(plan_id)),
                success_url=success_url,
                cancel_url=cancel_url,
            ),
        )
        return _jsonable(checkout)
