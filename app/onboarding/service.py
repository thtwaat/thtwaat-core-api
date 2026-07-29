"""
Onboarding wizard service.

Orchestrates existing platform services — does not re-implement billing,
marketplace, product generation, publish, domains, or branding logic.
"""
from __future__ import annotations

import logging
import secrets
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.agent_platform.knowledge.schemas import KnowledgeBaseCreate
from app.agent_platform.knowledge.services import KnowledgeService
from app.agent_platform.models.agent import AgentConfig
from app.agent_platform.publish.service import PublishService
from app.auth.schema import LoginRequest
from app.auth.service import AuthService
from app.branding.service import BrandingService
from app.companies.schema import CompanyCreate, CompanyUpdate
from app.companies.service import CompanyService
from app.domains.schemas import DomainCreate
from app.domains.service import DomainService
from app.marketplace.schemas import InstallRequest
from app.marketplace.service import MarketplaceService
from app.onboarding.models import OnboardingSession, OnboardingStepEvent
from app.onboarding.schemas import (
    AdminSessionListResponse,
    AdminSessionSummary,
    AutosaveRequest,
    ChecklistItem,
    CompleteStepRequest,
    DropOffBucket,
    FlowDefinitionResponse,
    GoLiveRequest,
    OnboardingAnalyticsResponse,
    OnboardingSessionResponse,
    ProgressTracker,
    SkipStepRequest,
    StartOnboardingRequest,
    StartOnboardingResponse,
    StepActionResponse,
    StepDefinition,
)
from app.onboarding.steps import (
    OPTIONAL_STEPS,
    STEP_META,
    STEP_ORDER,
    OnboardingStatus,
    OnboardingStep,
    StepEventType,
    build_checklist,
    estimated_minutes_remaining,
    flow_definition,
    next_incomplete_step,
    step_index,
    total_estimated_minutes,
)
from app.payments.subscriptions.schema import StripeCheckoutRequest
from app.payments.subscriptions.service import SubscriptionService
from app.product_generator.schemas import GenerateRequest
from app.product_generator.service import ProductGeneratorService
from app.rbac.enums import EnterpriseRole
from app.usage.dimensions import UsageDimension
from app.usage.service import UsageService
from app.users.schema import UserCreate
from app.users.service import UserService

logger = logging.getLogger(__name__)


class OnboardingService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.companies = CompanyService(db)
        self.users = UserService(db)
        self.auth = AuthService(db)
        self.subscriptions = SubscriptionService(db)
        self.marketplace = MarketplaceService(db)
        self.generator = ProductGeneratorService(db)
        self.publish = PublishService(db)
        self.domains = DomainService(db)
        self.branding = BrandingService(db)
        self.usage = UsageService(db)

    # ── Public: start / resume ────────────────────────────────────────────────

    def start(self, body: StartOnboardingRequest) -> StartOnboardingResponse:
        company = self.companies.create_company(
            CompanyCreate(**body.company.model_dump())
        )
        user = self.users.create_user(
            UserCreate(
                email=body.account.email,
                password=body.account.password,
                first_name=body.account.first_name,
                last_name=body.account.last_name,
                company_id=company.id,
                role=EnterpriseRole.COMPANY_OWNER,
            )
        )

        now = datetime.now(timezone.utc)
        completed = [OnboardingStep.CREATE_ACCOUNT.value]
        session = OnboardingSession(
            resume_token=secrets.token_urlsafe(32),
            user_id=user.id,
            company_id=company.id,
            status=OnboardingStatus.IN_PROGRESS,
            current_step=OnboardingStep.VERIFY_EMAIL,
            completed_steps=completed,
            skipped_steps=[],
            draft_data={
                "account": {
                    "email": body.account.email,
                    "first_name": body.account.first_name,
                    "last_name": body.account.last_name,
                },
                "company": body.company.model_dump(),
            },
            resource_ids={},
            checklist=build_checklist(completed, []),
            estimated_minutes_total=total_estimated_minutes(),
            estimated_minutes_remaining=estimated_minutes_remaining(completed, []),
            started_at=now,
            last_active_at=now,
        )
        self.db.add(session)
        self.db.flush()
        self._record_event(session, OnboardingStep.CREATE_ACCOUNT, StepEventType.COMPLETED)
        self._record_event(session, OnboardingStep.VERIFY_EMAIL, StepEventType.ENTERED)
        self.db.commit()
        self.db.refresh(session)

        if body.send_verification:
            try:
                self.auth.send_email_verification(email=body.account.email)
            except Exception as exc:
                logger.warning("onboarding verification send skipped: %s", exc)

        tokens = self.auth.authenticate_user(
            LoginRequest(email=body.account.email, password=body.account.password)
        )
        # authenticate_user may return MFARequiredResponse — new accounts have MFA off
        if not hasattr(tokens, "access_token"):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Could not issue session tokens after signup",
            )

        try:
            from app.notifications.events import NotificationEventBus

            NotificationEventBus.dispatch(
                event_type="onboarding.started",
                db=self.db,
                company_id=company.id,
                user_id=user.id,
                data={"session_id": str(session.id)},
            )
        except Exception:
            pass

        return StartOnboardingResponse(
            session=self._to_response(session),
            access_token=tokens.access_token,
            refresh_token=tokens.refresh_token,
            expires_in=tokens.expires_in,
            next_actions=[
                "POST /api/v1/onboarding/me/steps/verify_email/complete",
                "GET /api/v1/onboarding/me",
            ],
        )

    def get_flow_definition(self) -> FlowDefinitionResponse:
        steps = [StepDefinition(**row) for row in flow_definition()]
        return FlowDefinitionResponse(
            steps=steps,
            total_estimated_minutes=total_estimated_minutes(),
            optional_steps=[s.value for s in OPTIONAL_STEPS],
            integrations=sorted({STEP_META[s]["integration"] for s in STEP_ORDER}),
        )

    def resume_by_token(self, resume_token: str) -> OnboardingSessionResponse:
        session = self._get_by_resume_token(resume_token)
        if session.status == OnboardingStatus.PAUSED:
            session.status = OnboardingStatus.IN_PROGRESS
            session.paused_at = None
            self._touch(session)
            self._record_event(session, session.current_step, StepEventType.RESUMED)
            self.db.commit()
            self.db.refresh(session)
        return self._to_response(session)

    def get_for_user(self, user_id: UUID, company_id: UUID) -> OnboardingSessionResponse:
        session = self._active_for_user(user_id, company_id)
        return self._to_response(session)

    # ── Autosave / pause / resume ─────────────────────────────────────────────

    def autosave(
        self,
        user_id: UUID,
        company_id: UUID,
        body: AutosaveRequest,
    ) -> OnboardingSessionResponse:
        session = self._active_for_user(user_id, company_id)
        self._assert_writable(session)
        step_key = (body.step or session.current_step).value
        drafts = dict(session.draft_data or {})
        step_draft = dict(drafts.get(step_key) or {})
        step_draft.update(body.draft)
        drafts[step_key] = step_draft
        session.draft_data = drafts
        self._touch(session)
        self._record_event(
            session,
            body.step or session.current_step,
            StepEventType.AUTOSAVED,
            payload={"keys": list(body.draft.keys())},
        )
        self.db.commit()
        self.db.refresh(session)
        return self._to_response(session)

    def pause(self, user_id: UUID, company_id: UUID) -> OnboardingSessionResponse:
        session = self._active_for_user(user_id, company_id)
        if session.status == OnboardingStatus.COMPLETED:
            raise HTTPException(status_code=400, detail="Onboarding already completed")
        session.status = OnboardingStatus.PAUSED
        session.paused_at = datetime.now(timezone.utc)
        self._touch(session)
        self._record_event(session, session.current_step, StepEventType.PAUSED)
        self.db.commit()
        self.db.refresh(session)
        return self._to_response(session)

    def resume(self, user_id: UUID, company_id: UUID) -> OnboardingSessionResponse:
        session = self._active_for_user(user_id, company_id, allow_paused=True)
        session.status = OnboardingStatus.IN_PROGRESS
        session.paused_at = None
        self._touch(session)
        self._record_event(session, session.current_step, StepEventType.RESUMED)
        self.db.commit()
        self.db.refresh(session)
        return self._to_response(session)

    # ── Complete / skip ───────────────────────────────────────────────────────

    def complete_step(
        self,
        user_id: UUID,
        company_id: UUID,
        step: OnboardingStep,
        body: CompleteStepRequest,
    ) -> StepActionResponse:
        session = self._active_for_user(user_id, company_id)
        self._assert_writable(session)
        self._assert_step_reachable(session, step)

        try:
            result = self._execute_step(session, step, body.data or {})
        except HTTPException as exc:
            session.last_error = str(exc.detail)
            self._record_event(
                session,
                step,
                StepEventType.FAILED,
                payload={"detail": exc.detail},
            )
            self.db.commit()
            raise

        completed = list(session.completed_steps or [])
        skipped = list(session.skipped_steps or [])
        if step.value not in completed:
            completed.append(step.value)
        if step.value in skipped:
            skipped = [s for s in skipped if s != step.value]

        session.completed_steps = completed
        session.skipped_steps = skipped
        session.last_error = None
        nxt = next_incomplete_step(completed, skipped)
        if nxt is None:
            session.current_step = OnboardingStep.GO_LIVE
            session.status = OnboardingStatus.COMPLETED
            session.completed_at = datetime.now(timezone.utc)
        else:
            session.current_step = nxt
            self._record_event(session, nxt, StepEventType.ENTERED)

        session.checklist = build_checklist(completed, skipped)
        session.estimated_minutes_remaining = estimated_minutes_remaining(completed, skipped)
        self._touch(session)
        self._record_event(session, step, StepEventType.COMPLETED, payload={"result_keys": list(result.keys())})
        self.db.commit()
        self.db.refresh(session)

        if session.status == OnboardingStatus.COMPLETED:
            try:
                from app.notifications.events import NotificationEventBus

                NotificationEventBus.dispatch(
                    event_type="onboarding.completed",
                    db=self.db,
                    company_id=company_id,
                    user_id=user_id,
                    data={"session_id": str(session.id)},
                )
            except Exception:
                pass

        return StepActionResponse(
            session=self._to_response(session),
            result=result,
            next_step=session.current_step if session.status != OnboardingStatus.COMPLETED else None,
        )

    def skip_step(
        self,
        user_id: UUID,
        company_id: UUID,
        step: OnboardingStep,
        body: SkipStepRequest,
    ) -> StepActionResponse:
        session = self._active_for_user(user_id, company_id)
        self._assert_writable(session)
        if step not in OPTIONAL_STEPS:
            raise HTTPException(
                status_code=400,
                detail=f"Step '{step.value}' is required and cannot be skipped",
            )
        self._assert_step_reachable(session, step)

        completed = list(session.completed_steps or [])
        skipped = list(session.skipped_steps or [])
        if step.value not in skipped and step.value not in completed:
            skipped.append(step.value)

        session.skipped_steps = skipped
        nxt = next_incomplete_step(completed, skipped)
        if nxt is None:
            session.status = OnboardingStatus.COMPLETED
            session.completed_at = datetime.now(timezone.utc)
            session.current_step = OnboardingStep.GO_LIVE
        else:
            session.current_step = nxt
            self._record_event(session, nxt, StepEventType.ENTERED)

        session.checklist = build_checklist(completed, skipped)
        session.estimated_minutes_remaining = estimated_minutes_remaining(completed, skipped)
        self._touch(session)
        self._record_event(
            session,
            step,
            StepEventType.SKIPPED,
            payload={"reason": body.reason},
        )
        self.db.commit()
        self.db.refresh(session)
        return StepActionResponse(
            session=self._to_response(session),
            result={"skipped": True, "reason": body.reason},
            next_step=session.current_step if session.status != OnboardingStatus.COMPLETED else None,
        )

    async def upload_knowledge_file(
        self,
        user_id: UUID,
        company_id: UUID,
        file: UploadFile,
        knowledge_base_id: Optional[UUID] = None,
    ) -> StepActionResponse:
        """Multipart helper for step 6 — delegates to KnowledgeService."""
        session = self._active_for_user(user_id, company_id)
        self._assert_writable(session)

        resources = dict(session.resource_ids or {})
        kb_id = knowledge_base_id or (
            UUID(resources["knowledge_base_id"]) if resources.get("knowledge_base_id") else None
        )
        if kb_id is None:
            agent_name = (resources.get("agent_name") or "Onboarding")
            kb = KnowledgeService.create_knowledge_base(
                self.db,
                company_id,
                KnowledgeBaseCreate(
                    name=f"{agent_name} Knowledge",
                    description="Created during customer onboarding",
                ),
            )
            kb_id = kb.id
            resources["knowledge_base_id"] = str(kb_id)
            agent_id = resources.get("agent_id")
            if agent_id:
                try:
                    KnowledgeService.attach_knowledge_base_to_agent(
                        self.db, kb_id, UUID(agent_id)
                    )
                except Exception as exc:
                    logger.warning("KB attach during onboarding: %s", exc)

        doc = await KnowledgeService.upload_document(
            db=self.db,
            company_id=company_id,
            file=file,
            knowledge_base_id=kb_id,
        )
        resources["last_document_id"] = str(doc.id)
        session.resource_ids = resources
        drafts = dict(session.draft_data or {})
        drafts[OnboardingStep.UPLOAD_KNOWLEDGE.value] = {
            "knowledge_base_id": str(kb_id),
            "last_document_id": str(doc.id),
        }
        session.draft_data = drafts
        self._touch(session)
        self.db.commit()
        self.db.refresh(session)
        return StepActionResponse(
            session=self._to_response(session),
            result={
                "knowledge_base_id": str(kb_id),
                "document_id": str(doc.id),
                "document_status": doc.status,
            },
            next_step=session.current_step,
        )

    # ── Step executors (delegate only) ────────────────────────────────────────

    def _execute_step(
        self,
        session: OnboardingSession,
        step: OnboardingStep,
        data: Dict[str, Any],
    ) -> Dict[str, Any]:
        handlers = {
            OnboardingStep.CREATE_ACCOUNT: self._step_create_account,
            OnboardingStep.VERIFY_EMAIL: self._step_verify_email,
            OnboardingStep.CREATE_COMPANY: self._step_create_company,
            OnboardingStep.CHOOSE_PLAN: self._step_choose_plan,
            OnboardingStep.CREATE_AI_AGENT: self._step_create_agent,
            OnboardingStep.UPLOAD_KNOWLEDGE: self._step_upload_knowledge,
            OnboardingStep.CHOOSE_TEMPLATE: self._step_choose_template,
            OnboardingStep.GENERATE_PRODUCT: self._step_generate_product,
            OnboardingStep.PREVIEW: self._step_preview,
            OnboardingStep.PUBLISH: self._step_publish,
            OnboardingStep.CONNECT_DOMAIN: self._step_connect_domain,
            OnboardingStep.GO_LIVE: self._step_go_live,
        }
        return handlers[step](session, data)

    def _step_create_account(self, session: OnboardingSession, data: Dict[str, Any]) -> Dict[str, Any]:
        # Already created during start(); allow idempotent complete.
        return {"user_id": str(session.user_id), "already_created": True}

    def _step_verify_email(self, session: OnboardingSession, data: Dict[str, Any]) -> Dict[str, Any]:
        email = data.get("email") or (session.draft_data or {}).get("account", {}).get("email")
        code = data.get("code")
        if not email or not code:
            raise HTTPException(status_code=422, detail="email and code are required")
        result = self.auth.verify_email(email=email, code=str(code))
        return {"detail": result.get("detail"), "email": email}

    def _step_create_company(self, session: OnboardingSession, data: Dict[str, Any]) -> Dict[str, Any]:
        # Company already exists from start — refine profile via CompanyService.
        update_fields = {
            k: v
            for k, v in data.items()
            if k
            in {
                "name",
                "display_name",
                "description",
                "website",
                "logo_url",
                "industry",
                "country",
                "timezone",
                "settings",
            }
            and v is not None
        }
        if update_fields:
            updated = self.companies.update_company(
                session.company_id, CompanyUpdate(**update_fields)
            )
            return {"company_id": str(updated.id), "name": updated.name, "updated": True}
        company = self.companies.get_company(session.company_id)
        return {"company_id": str(company.id), "name": company.name, "updated": False}

    def _step_choose_plan(self, session: OnboardingSession, data: Dict[str, Any]) -> Dict[str, Any]:
        plan_id = data.get("plan_id")
        stay_free = bool(data.get("stay_free", False))
        resources = dict(session.resource_ids or {})

        if stay_free or not plan_id:
            resources["plan"] = "free"
            session.resource_ids = resources
            return {"plan": "free", "checkout_url": None}

        provider = (data.get("provider") or "stripe").lower()
        if provider != "stripe":
            raise HTTPException(
                status_code=400,
                detail="Onboarding checkout currently supports provider=stripe; use payments APIs for Razorpay",
            )
        success_url = data.get("success_url")
        cancel_url = data.get("cancel_url")
        if not success_url or not cancel_url:
            raise HTTPException(
                status_code=422,
                detail="success_url and cancel_url are required for paid plan checkout",
            )
        checkout = self.subscriptions.create_stripe_checkout_session(
            session.company_id,
            StripeCheckoutRequest(
                plan_id=UUID(str(plan_id)),
                success_url=success_url,
                cancel_url=cancel_url,
            ),
        )
        resources["plan_id"] = str(plan_id)
        if checkout.subscription_id:
            resources["subscription_id"] = str(checkout.subscription_id)
        session.resource_ids = resources
        return {
            "plan_id": str(plan_id),
            "checkout_url": checkout.checkout_url,
            "subscription_id": str(checkout.subscription_id) if checkout.subscription_id else None,
            "provider": checkout.provider,
        }

    def _step_create_agent(self, session: OnboardingSession, data: Dict[str, Any]) -> Dict[str, Any]:
        name = data.get("name") or "My First Agent"
        description = data.get("description")
        system_prompt = data.get("system_prompt_template") or (
            "You are a helpful AI assistant for this company."
        )
        temperature = float(data.get("temperature", 0.7))

        company_id = session.company_id
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
            name=name,
            description=description,
            system_prompt_template=system_prompt,
            temperature=temperature,
            is_template=False,
            web_config=data.get("web_config") or {},
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
                source="onboarding",
            )
        except Exception:
            pass

        resources = dict(session.resource_ids or {})
        resources["agent_id"] = str(agent.id)
        resources["agent_name"] = agent.name
        session.resource_ids = resources
        return {"agent_id": str(agent.id), "name": agent.name, "status": agent.status}

    def _step_upload_knowledge(self, session: OnboardingSession, data: Dict[str, Any]) -> Dict[str, Any]:
        resources = dict(session.resource_ids or {})
        kb_id = data.get("knowledge_base_id") or resources.get("knowledge_base_id")
        if kb_id:
            kb = KnowledgeService.get_knowledge_base(self.db, UUID(str(kb_id)), session.company_id)
        else:
            name = data.get("name") or f"{resources.get('agent_name', 'Onboarding')} Knowledge"
            kb = KnowledgeService.create_knowledge_base(
                self.db,
                session.company_id,
                KnowledgeBaseCreate(name=name, description=data.get("description")),
            )
        resources["knowledge_base_id"] = str(kb.id)
        agent_id = resources.get("agent_id") or data.get("agent_id")
        if agent_id:
            try:
                KnowledgeService.attach_knowledge_base_to_agent(
                    self.db, kb.id, UUID(str(agent_id))
                )
            except Exception as exc:
                logger.warning("KB attach: %s", exc)
        session.resource_ids = resources
        return {
            "knowledge_base_id": str(kb.id),
            "hint": "Use POST /api/v1/onboarding/me/knowledge/upload for files",
        }

    def _step_choose_template(self, session: OnboardingSession, data: Dict[str, Any]) -> Dict[str, Any]:
        template = data.get("template_id_or_slug") or data.get("template_slug")
        if not template:
            raise HTTPException(status_code=422, detail="template_id_or_slug is required")
        resources = dict(session.resource_ids or {})
        agent_id = data.get("agent_id") or resources.get("agent_id")
        install = self.marketplace.install(
            session.company_id,
            session.user_id,
            str(template),
            InstallRequest(
                version=data.get("version"),
                agent_id=UUID(str(agent_id)) if agent_id else None,
                create_api_key=bool(data.get("create_api_key", True)),
                api_key_name=data.get("api_key_name") or "Onboarding install key",
                config_overrides=data.get("config_overrides") or {},
            ),
        )
        resources["installation_id"] = str(install.id)
        resources["template_id"] = str(install.template_id)
        resources["template_slug"] = install.template_slug
        if install.agent_id:
            resources["agent_id"] = str(install.agent_id)
        session.resource_ids = resources
        return {
            "installation_id": str(install.id),
            "template_slug": install.template_slug,
            "status": install.status,
        }

    def _step_generate_product(self, session: OnboardingSession, data: Dict[str, Any]) -> Dict[str, Any]:
        prompt = data.get("prompt")
        if not prompt:
            raise HTTPException(status_code=422, detail="prompt is required")
        resources = dict(session.resource_ids or {})
        payload = GenerateRequest(
            prompt=prompt,
            template_slug=data.get("template_slug") or resources.get("template_slug"),
            config_overrides=data.get("config_overrides") or {},
            create_domain_hostname=data.get("create_domain_hostname"),
            auto_publish=bool(data.get("auto_publish", False)),
            create_company=False,
        )
        generation = self.generator.generate(session.company_id, session.user_id, payload)
        resources["generation_id"] = str(generation.id)
        if generation.agent_id:
            resources["agent_id"] = str(generation.agent_id)
        if generation.knowledge_base_id:
            resources["knowledge_base_id"] = str(generation.knowledge_base_id)
        if generation.installation_id:
            resources["installation_id"] = str(generation.installation_id)
        if generation.domain_id:
            resources["domain_id"] = str(generation.domain_id)
        if generation.preview_url:
            resources["preview_url"] = generation.preview_url
        session.resource_ids = resources
        return {
            "generation_id": str(generation.id),
            "status": generation.status,
            "preview_url": generation.preview_url,
            "template_slug": generation.template_slug,
            "agent_id": str(generation.agent_id) if generation.agent_id else None,
        }

    def _step_preview(self, session: OnboardingSession, data: Dict[str, Any]) -> Dict[str, Any]:
        resources = dict(session.resource_ids or {})
        generation_id = data.get("generation_id") or resources.get("generation_id")
        if not generation_id:
            raise HTTPException(
                status_code=400,
                detail="No generation found — complete Generate Product first",
            )
        generation = self.generator.get(session.company_id, UUID(str(generation_id)))
        if not resources.get("preview_url") and generation.preview_url:
            resources["preview_url"] = generation.preview_url
            session.resource_ids = resources
        return {
            "generation_id": str(generation.id),
            "preview_url": generation.preview_url,
            "widget_snippet": generation.widget_snippet,
            "deployment_checklist": generation.deployment_checklist,
            "publish_status": generation.publish_status,
            "status": generation.status,
        }

    def _step_publish(self, session: OnboardingSession, data: Dict[str, Any]) -> Dict[str, Any]:
        resources = dict(session.resource_ids or {})
        generation_id = data.get("generation_id") or resources.get("generation_id")
        agent_id = data.get("agent_id") or resources.get("agent_id")

        if generation_id:
            published = self.generator.publish_product(
                session.company_id,
                session.user_id,
                UUID(str(generation_id)),
                hostname=data.get("hostname"),
            )
            resources["publish_status"] = published.publish_status
            if published.domain_id:
                resources["domain_id"] = str(published.domain_id)
            session.resource_ids = resources
            return {
                "mode": "product_generator",
                "generation_id": str(published.id),
                "publish_status": published.publish_status,
                "preview_url": published.preview_url,
            }

        if not agent_id:
            raise HTTPException(status_code=400, detail="agent_id or generation_id required to publish")

        result = self.publish.publish(
            UUID(str(agent_id)), session.company_id, session.user_id
        )
        resources["publish_status"] = getattr(result, "status", None) or "PUBLISHED"
        session.resource_ids = resources
        return {
            "mode": "agent_publish",
            "agent_id": str(agent_id),
            "result": result.model_dump() if hasattr(result, "model_dump") else dict(result),
        }

    def _step_connect_domain(self, session: OnboardingSession, data: Dict[str, Any]) -> Dict[str, Any]:
        hostname = data.get("hostname")
        if not hostname:
            raise HTTPException(status_code=422, detail="hostname is required")
        resources = dict(session.resource_ids or {})
        agent_id = data.get("agent_id") or resources.get("agent_id")
        domain = self.domains.create(
            session.company_id,
            DomainCreate(
                hostname=hostname,
                verification_method=data.get("verification_method") or "TXT",
                agent_id=UUID(str(agent_id)) if agent_id else None,
                widget_id=data.get("widget_id"),
                is_primary=bool(data.get("is_primary", True)),
            ),
            session.user_id,
        )
        resources["domain_id"] = str(domain.id)
        resources["domain_hostname"] = domain.hostname
        session.resource_ids = resources

        verify_now = bool(data.get("verify_now", False))
        verify_result = None
        if verify_now:
            verify_result = self.domains.verify(domain.id, session.company_id, session.user_id)
        return {
            "domain_id": str(domain.id),
            "hostname": domain.hostname,
            "status": domain.status,
            "dns_records": domain.dns_records if hasattr(domain, "dns_records") else None,
            "verify": verify_result.model_dump() if verify_result and hasattr(verify_result, "model_dump") else verify_result,
        }

    def _step_go_live(self, session: OnboardingSession, data: Dict[str, Any]) -> Dict[str, Any]:
        body = GoLiveRequest(**{k: v for k, v in data.items() if k in {"publish_branding", "notes"}})
        branding_result = None
        if body.publish_branding:
            try:
                branding_result = self.branding.publish(session.company_id)
            except Exception as exc:
                logger.warning("branding publish during go-live: %s", exc)

        # Bootstrap enterprise organization root when missing (best-effort).
        try:
            from app.enterprise.models import UnitType
            from app.enterprise.schemas import UnitCreate
            from app.enterprise.service import EnterpriseService

            ent = EnterpriseService(self.db)
            if not ent.list_units(session.company_id, UnitType.ORGANIZATION):
                company = self.companies.get_company(session.company_id)
                ent.create_unit(
                    session.company_id,
                    session.user_id,
                    UnitCreate(
                        name=company.name,
                        slug=company.slug,
                        unit_type=UnitType.ORGANIZATION,
                        description="Created during customer onboarding go-live",
                    ),
                )
        except Exception as exc:
            logger.warning("enterprise org bootstrap: %s", exc)

        resources = dict(session.resource_ids or {})
        resources["go_live_at"] = datetime.now(timezone.utc).isoformat()
        if body.notes:
            resources["go_live_notes"] = body.notes
        session.resource_ids = resources
        session.status = OnboardingStatus.COMPLETED
        session.completed_at = datetime.now(timezone.utc)
        return {
            "live": True,
            "branding": branding_result.model_dump()
            if branding_result and hasattr(branding_result, "model_dump")
            else branding_result,
            "resource_ids": resources,
        }

    # ── Admin analytics ───────────────────────────────────────────────────────

    def admin_list_sessions(
        self,
        page: int = 1,
        page_size: int = 20,
        status_filter: Optional[OnboardingStatus] = None,
        company_id: Optional[UUID] = None,
    ) -> AdminSessionListResponse:
        q = self.db.query(OnboardingSession)
        if status_filter:
            q = q.filter(OnboardingSession.status == status_filter)
        if company_id:
            q = q.filter(OnboardingSession.company_id == company_id)
        total = q.count()
        rows = (
            q.order_by(OnboardingSession.started_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        items = []
        for row in rows:
            completed = list(row.completed_steps or [])
            skipped = list(row.skipped_steps or [])
            done = len(completed) + len(skipped)
            items.append(
                AdminSessionSummary(
                    id=row.id,
                    company_id=row.company_id,
                    user_id=row.user_id,
                    status=row.status,
                    current_step=row.current_step,
                    completed_count=len(completed),
                    skipped_count=len(skipped),
                    percent_complete=round(100.0 * done / len(STEP_ORDER), 1),
                    started_at=row.started_at,
                    last_active_at=row.last_active_at,
                    completed_at=row.completed_at,
                )
            )
        return AdminSessionListResponse(
            total=total, page=page, page_size=page_size, items=items
        )

    def admin_get_session(self, session_id: UUID) -> OnboardingSessionResponse:
        session = self.db.get(OnboardingSession, session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Onboarding session not found")
        return self._to_response(session)

    def admin_analytics(self) -> OnboardingAnalyticsResponse:
        total = self.db.scalar(select(func.count()).select_from(OnboardingSession)) or 0

        def count_status(st: OnboardingStatus) -> int:
            return (
                self.db.scalar(
                    select(func.count()).select_from(OnboardingSession).where(
                        OnboardingSession.status == st
                    )
                )
                or 0
            )

        completed = count_status(OnboardingStatus.COMPLETED)
        in_progress = count_status(OnboardingStatus.IN_PROGRESS)
        paused = count_status(OnboardingStatus.PAUSED)
        abandoned = count_status(OnboardingStatus.ABANDONED)
        completion_rate = round((completed / total) * 100.0, 2) if total else 0.0

        avg_minutes = None
        if completed:
            rows = (
                self.db.query(OnboardingSession)
                .filter(
                    OnboardingSession.status == OnboardingStatus.COMPLETED,
                    OnboardingSession.completed_at.isnot(None),
                )
                .all()
            )
            deltas = [
                (r.completed_at - r.started_at).total_seconds() / 60.0
                for r in rows
                if r.completed_at and r.started_at
            ]
            if deltas:
                avg_minutes = round(sum(deltas) / len(deltas), 1)

        drop_off: List[DropOffBucket] = []
        funnel: List[Dict[str, Any]] = []
        for step in STEP_ORDER:
            stuck = (
                self.db.scalar(
                    select(func.count()).select_from(OnboardingSession).where(
                        OnboardingSession.current_step == step,
                        OnboardingSession.status.in_(
                            [OnboardingStatus.IN_PROGRESS, OnboardingStatus.PAUSED]
                        ),
                    )
                )
                or 0
            )
            entered = (
                self.db.scalar(
                    select(func.count()).select_from(OnboardingStepEvent).where(
                        OnboardingStepEvent.step == step,
                        OnboardingStepEvent.event_type == StepEventType.ENTERED,
                    )
                )
                or 0
            )
            step_completed = (
                self.db.scalar(
                    select(func.count()).select_from(OnboardingStepEvent).where(
                        OnboardingStepEvent.step == step,
                        OnboardingStepEvent.event_type == StepEventType.COMPLETED,
                    )
                )
                or 0
            )
            step_skipped = (
                self.db.scalar(
                    select(func.count()).select_from(OnboardingStepEvent).where(
                        OnboardingStepEvent.step == step,
                        OnboardingStepEvent.event_type == StepEventType.SKIPPED,
                    )
                )
                or 0
            )
            denom = max(entered, 1)
            drop_rate = round((stuck / denom) * 100.0, 2) if entered else (100.0 if stuck else 0.0)
            drop_off.append(
                DropOffBucket(
                    step=step.value,
                    title=STEP_META[step]["title"],
                    sessions_stuck=stuck,
                    entered_count=entered,
                    completed_count=step_completed,
                    skipped_count=step_skipped,
                    drop_off_rate=drop_rate,
                )
            )
            funnel.append(
                {
                    "step": step.value,
                    "order": step_index(step) + 1,
                    "entered": entered,
                    "completed": step_completed,
                    "skipped": step_skipped,
                    "stuck": stuck,
                }
            )

        return OnboardingAnalyticsResponse(
            sessions_total=total,
            in_progress=in_progress,
            paused=paused,
            completed=completed,
            abandoned=abandoned,
            completion_rate=completion_rate,
            avg_completion_minutes=avg_minutes,
            drop_off=drop_off,
            funnel=funnel,
        )

    # ── Internals ─────────────────────────────────────────────────────────────

    def _active_for_user(
        self,
        user_id: UUID,
        company_id: UUID,
        allow_paused: bool = False,
    ) -> OnboardingSession:
        statuses = [OnboardingStatus.IN_PROGRESS]
        if allow_paused:
            statuses.append(OnboardingStatus.PAUSED)
        session = (
            self.db.query(OnboardingSession)
            .filter(
                OnboardingSession.user_id == user_id,
                OnboardingSession.company_id == company_id,
                OnboardingSession.status.in_(statuses + [OnboardingStatus.COMPLETED]),
            )
            .order_by(OnboardingSession.started_at.desc())
            .first()
        )
        if not session:
            raise HTTPException(status_code=404, detail="No onboarding session for this user")
        if session.status == OnboardingStatus.PAUSED and not allow_paused:
            raise HTTPException(
                status_code=409,
                detail="Onboarding is paused — call POST /onboarding/me/resume",
            )
        return session

    def _get_by_resume_token(self, token: str) -> OnboardingSession:
        session = (
            self.db.query(OnboardingSession)
            .filter(OnboardingSession.resume_token == token)
            .first()
        )
        if not session:
            raise HTTPException(status_code=404, detail="Invalid resume token")
        return session

    def _assert_writable(self, session: OnboardingSession) -> None:
        if session.status == OnboardingStatus.COMPLETED:
            raise HTTPException(status_code=400, detail="Onboarding already completed")
        if session.status == OnboardingStatus.ABANDONED:
            raise HTTPException(status_code=400, detail="Onboarding abandoned")
        if session.status == OnboardingStatus.PAUSED:
            raise HTTPException(
                status_code=409,
                detail="Onboarding is paused — resume before continuing",
            )

    def _assert_step_reachable(self, session: OnboardingSession, step: OnboardingStep) -> None:
        completed = set(session.completed_steps or [])
        skipped = set(session.skipped_steps or [])
        if step.value in completed:
            raise HTTPException(status_code=400, detail=f"Step '{step.value}' already completed")
        # Allow completing current step or any previous incomplete optional left behind
        expected = next_incomplete_step(list(completed), list(skipped))
        if expected is None:
            raise HTTPException(status_code=400, detail="All steps already finished")
        if step != expected and step != session.current_step:
            # Allow re-entry of current only
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "step_out_of_order",
                    "expected": expected.value,
                    "requested": step.value,
                },
            )

    def _touch(self, session: OnboardingSession) -> None:
        session.last_active_at = datetime.now(timezone.utc)

    def _record_event(
        self,
        session: OnboardingSession,
        step: OnboardingStep,
        event_type: StepEventType,
        payload: Optional[Dict[str, Any]] = None,
        duration_ms: Optional[int] = None,
    ) -> None:
        self.db.add(
            OnboardingStepEvent(
                session_id=session.id,
                company_id=session.company_id,
                user_id=session.user_id,
                step=step,
                event_type=event_type,
                payload=payload or {},
                duration_ms=duration_ms,
            )
        )

    def _to_response(self, session: OnboardingSession) -> OnboardingSessionResponse:
        completed = list(session.completed_steps or [])
        skipped = list(session.skipped_steps or [])
        done = len(completed) + len(skipped)
        progress = ProgressTracker(
            current_step=session.current_step,
            current_order=step_index(session.current_step) + 1,
            total_steps=len(STEP_ORDER),
            completed_count=len(completed),
            skipped_count=len(skipped),
            percent_complete=round(100.0 * done / len(STEP_ORDER), 1),
            estimated_minutes_total=session.estimated_minutes_total
            or total_estimated_minutes(),
            estimated_minutes_remaining=session.estimated_minutes_remaining
            or estimated_minutes_remaining(completed, skipped),
            status=session.status,
        )
        checklist_raw = session.checklist or build_checklist(completed, skipped)
        checklist = [ChecklistItem(**item) if isinstance(item, dict) else item for item in checklist_raw]
        return OnboardingSessionResponse(
            id=session.id,
            resume_token=session.resume_token,
            user_id=session.user_id,
            company_id=session.company_id,
            status=session.status,
            current_step=session.current_step,
            completed_steps=completed,
            skipped_steps=skipped,
            draft_data=session.draft_data or {},
            resource_ids=session.resource_ids or {},
            checklist=checklist,
            progress=progress,
            started_at=session.started_at,
            last_active_at=session.last_active_at,
            paused_at=session.paused_at,
            completed_at=session.completed_at,
            last_error=session.last_error,
        )
