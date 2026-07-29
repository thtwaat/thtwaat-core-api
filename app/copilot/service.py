"""
AI Copilot service — NLU, planning, multi-step execution, memory, confirmations.

Delegates all domain work to existing services via CopilotToolRuntime.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.copilot.intents import (
    DESTRUCTIVE_TOOLS,
    TOOL_CATALOG,
    WORKFLOWS,
    CopilotIntent,
    MessageRole,
    StepStatus,
    TaskStatus,
)
from app.copilot.models import CopilotConversation, CopilotMessage, CopilotTask, CopilotTaskStep
from app.copilot.nlu import detect_intent, extract_slots, missing_required_slots
from app.copilot.schemas import (
    ChatRequest,
    ChatResponse,
    ConfirmTaskRequest,
    FailureDiagnostics,
    HistoryResponse,
    MessageResponse,
    StepProgress,
    TaskListResponse,
    TaskResponse,
    ToolInfo,
    ToolsResponse,
)
from app.copilot.tools import CopilotToolRuntime
from app.notifications.events import NotificationEventBus

logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _bool_str(value: bool) -> str:
    return "true" if value else "false"


class CopilotService:
    def __init__(self, db: Session) -> None:
        self.db = db

    # ── Public chat ───────────────────────────────────────────────────────────

    def chat(
        self,
        company_id: UUID,
        user_id: UUID,
        user_role: str,
        body: ChatRequest,
    ) -> ChatResponse:
        conversation = self._get_or_create_conversation(
            company_id, user_id, body.conversation_id
        )

        # Explicit confirm of pending destructive task
        if body.confirm:
            pending = self._pending_confirmation(conversation.id)
            if not pending:
                raise HTTPException(status_code=404, detail="No task awaiting confirmation")
            return self._confirm_and_respond(
                conversation, pending, user_role, company_id, user_id
            )

        intent, confidence, matched = detect_intent(body.message)
        slots = extract_slots(body.message, intent, conversation.memory or {})
        missing = missing_required_slots(intent, slots)

        self._add_message(
            conversation,
            MessageRole.USER,
            body.message,
            intent=intent.value,
            confidence=str(confidence),
            meta={"matched": matched, "slots": slots},
            user_id=user_id,
        )

        # Help / tools / unknown — conversational only
        if intent in (CopilotIntent.HELP, CopilotIntent.LIST_TOOLS, CopilotIntent.UNKNOWN):
            reply = self._help_reply(intent)
            assistant = self._add_message(
                conversation,
                MessageRole.ASSISTANT,
                reply,
                intent=intent.value,
                confidence=str(confidence),
                meta={"tools": [t["name"] for t in TOOL_CATALOG]},
                user_id=user_id,
            )
            self.db.commit()
            return ChatResponse(
                conversation_id=conversation.id,
                message=self._msg_response(assistant),
                intent=intent,
                confidence=confidence,
                matched_keywords=matched,
                missing_slots=missing,
            )

        if missing:
            reply = (
                f"I understood intent **{intent.value}**, but need: "
                + ", ".join(missing)
                + ". Please provide the missing details."
            )
            assistant = self._add_message(
                conversation,
                MessageRole.ASSISTANT,
                reply,
                intent=intent.value,
                confidence=str(confidence),
                meta={"missing_slots": missing},
                user_id=user_id,
            )
            self.db.commit()
            return ChatResponse(
                conversation_id=conversation.id,
                message=self._msg_response(assistant),
                intent=intent,
                confidence=confidence,
                matched_keywords=matched,
                missing_slots=missing,
            )

        task = self._create_task(conversation, intent, body.message, slots, user_id, company_id)
        needs_confirmation = self._plan_requires_confirmation(task.plan)

        if needs_confirmation and not body.confirm:
            task.status = TaskStatus.AWAITING_CONFIRMATION
            task.requires_confirmation = _bool_str(True)
            self._mark_destructive_steps_awaiting(task)
            reply = (
                f"Planned workflow **{intent.value}** with {len(task.plan)} step(s). "
                "This includes destructive actions. "
                "Confirm with `confirm: true` on the next chat message, "
                f"or `POST /api/v1/copilot/tasks/{task.id}/confirm`."
            )
            assistant = self._add_message(
                conversation,
                MessageRole.ASSISTANT,
                reply,
                intent=intent.value,
                confidence=str(confidence),
                meta={"task_id": str(task.id), "needs_confirmation": True},
                user_id=user_id,
            )
            self.db.commit()
            self.db.refresh(task)
            return ChatResponse(
                conversation_id=conversation.id,
                message=self._msg_response(assistant),
                intent=intent,
                confidence=confidence,
                matched_keywords=matched,
                task=self._task_response(task),
                needs_confirmation=True,
                progress=self._progress_payload(task),
            )

        if not body.auto_execute:
            task.status = TaskStatus.PLANNED
            reply = f"Planned **{intent.value}**. Call confirm/execute when ready."
            assistant = self._add_message(
                conversation,
                MessageRole.ASSISTANT,
                reply,
                intent=intent.value,
                confidence=str(confidence),
                meta={"task_id": str(task.id)},
                user_id=user_id,
            )
            self.db.commit()
            return ChatResponse(
                conversation_id=conversation.id,
                message=self._msg_response(assistant),
                intent=intent,
                confidence=confidence,
                matched_keywords=matched,
                task=self._task_response(task),
                progress=self._progress_payload(task),
            )

        task = self._execute_task(task, user_role)
        reply = self._summarize_task(task)
        assistant = self._add_message(
            conversation,
            MessageRole.ASSISTANT,
            reply,
            intent=intent.value,
            confidence=str(confidence),
            meta={"task_id": str(task.id), "status": task.status.value},
            user_id=user_id,
        )
        self._merge_memory(conversation, task)
        self.db.commit()
        self.db.refresh(task)

        try:
            NotificationEventBus.dispatch(
                event_type="copilot.task_completed"
                if task.status == TaskStatus.COMPLETED
                else "copilot.task_failed",
                db=self.db,
                company_id=company_id,
                user_id=user_id,
                data={"task_id": str(task.id), "intent": intent.value},
            )
        except Exception:
            pass

        return ChatResponse(
            conversation_id=conversation.id,
            message=self._msg_response(assistant),
            intent=intent,
            confidence=confidence,
            matched_keywords=matched,
            task=self._task_response(task),
            progress=self._progress_payload(task),
        )

    def confirm_task(
        self,
        task_id: UUID,
        company_id: UUID,
        user_id: UUID,
        user_role: str,
        body: ConfirmTaskRequest,
    ) -> TaskResponse:
        task = self._get_task(task_id, company_id)
        if task.status != TaskStatus.AWAITING_CONFIRMATION:
            raise HTTPException(status_code=409, detail=f"Task status is {task.status.value}")
        if not body.confirm:
            task.status = TaskStatus.CANCELLED
            task.completed_at = _now()
            self.db.commit()
            return self._task_response(task)

        task.confirmed_at = _now()
        task.requires_confirmation = _bool_str(False)
        # Reset awaiting steps to pending
        for step in self._steps(task.id):
            if step.status == StepStatus.AWAITING_CONFIRMATION:
                step.status = StepStatus.PENDING
        task = self._execute_task(task, user_role)
        conversation = self.db.get(CopilotConversation, task.conversation_id)
        if conversation:
            self._merge_memory(conversation, task)
            self._add_message(
                conversation,
                MessageRole.ASSISTANT,
                self._summarize_task(task),
                intent=task.intent,
                meta={"task_id": str(task.id), "confirmed": True},
                user_id=user_id,
            )
        self.db.commit()
        return self._task_response(task)

    def cancel_task(self, task_id: UUID, company_id: UUID) -> TaskResponse:
        task = self._get_task(task_id, company_id)
        if task.status in (TaskStatus.COMPLETED, TaskStatus.CANCELLED):
            raise HTTPException(status_code=400, detail="Task already finished")
        task.status = TaskStatus.CANCELLED
        task.completed_at = _now()
        for step in self._steps(task.id):
            if step.status in (StepStatus.PENDING, StepStatus.AWAITING_CONFIRMATION, StepStatus.RUNNING):
                step.status = StepStatus.SKIPPED
        self.db.commit()
        return self._task_response(task)

    def replay_task(
        self, task_id: UUID, company_id: UUID, user_id: UUID, user_role: str
    ) -> TaskResponse:
        original = self._get_task(task_id, company_id)
        conversation = self.db.get(CopilotConversation, original.conversation_id)
        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")
        intent = CopilotIntent(original.intent)
        slots = dict(original.slots or {})
        task = self._create_task(
            conversation, intent, original.prompt, slots, user_id, company_id
        )
        task.parent_task_id = original.id
        if self._plan_requires_confirmation(task.plan):
            task.status = TaskStatus.AWAITING_CONFIRMATION
            task.requires_confirmation = _bool_str(True)
            self._mark_destructive_steps_awaiting(task)
            self.db.commit()
            return self._task_response(task)
        task = self._execute_task(task, user_role)
        self._merge_memory(conversation, task)
        self.db.commit()
        return self._task_response(task)

    def list_tasks(
        self,
        company_id: UUID,
        user_id: Optional[UUID] = None,
        status: Optional[TaskStatus] = None,
        limit: int = 50,
    ) -> TaskListResponse:
        q = self.db.query(CopilotTask).filter(CopilotTask.company_id == company_id)
        if user_id:
            q = q.filter(CopilotTask.user_id == user_id)
        if status:
            q = q.filter(CopilotTask.status == status)
        total = q.count()
        rows = q.order_by(CopilotTask.created_at.desc()).limit(limit).all()
        return TaskListResponse(
            total=total, items=[self._task_response(t) for t in rows]
        )

    def get_task(self, task_id: UUID, company_id: UUID) -> TaskResponse:
        return self._task_response(self._get_task(task_id, company_id))

    def history(
        self,
        company_id: UUID,
        user_id: UUID,
        conversation_id: Optional[UUID] = None,
        limit: int = 50,
    ) -> HistoryResponse:
        if conversation_id:
            conversation = self._get_conversation(conversation_id, company_id, user_id)
        else:
            conversation = (
                self.db.query(CopilotConversation)
                .filter(
                    CopilotConversation.company_id == company_id,
                    CopilotConversation.user_id == user_id,
                )
                .order_by(CopilotConversation.updated_at.desc())
                .first()
            )
        if not conversation:
            return HistoryResponse()

        messages = (
            self.db.query(CopilotMessage)
            .filter(CopilotMessage.conversation_id == conversation.id)
            .order_by(CopilotMessage.created_at.asc())
            .limit(limit)
            .all()
        )
        tasks = (
            self.db.query(CopilotTask)
            .filter(CopilotTask.conversation_id == conversation.id)
            .order_by(CopilotTask.created_at.desc())
            .limit(limit)
            .all()
        )
        return HistoryResponse(
            conversation_id=conversation.id,
            messages=[self._msg_response(m) for m in messages],
            tasks=[self._task_response(t) for t in tasks],
        )

    def list_tools(self) -> ToolsResponse:
        tools = [
            ToolInfo(
                name=t["name"],
                integration=t["integration"],
                description=t["description"],
                destructive=bool(t.get("destructive")),
                platform_admin=bool(t.get("platform_admin")),
            )
            for t in TOOL_CATALOG
        ]
        workflows = [
            {
                "intent": intent.value,
                "steps": [
                    {"tool": s["tool"], "title": s["title"], "optional": s.get("optional", False)}
                    for s in steps
                ],
            }
            for intent, steps in WORKFLOWS.items()
            if steps
        ]
        return ToolsResponse(tools=tools, workflows=workflows)

    def diagnostics(self, task_id: UUID, company_id: UUID) -> FailureDiagnostics:
        task = self._get_task(task_id, company_id)
        steps = self._steps(task.id)
        failed = next((s for s in steps if s.status == StepStatus.FAILED), None)
        preceding = [s for s in steps if failed and s.step_index < failed.step_index]
        recommendations: List[str] = []
        if failed:
            recommendations.append(f"Inspect tool `{failed.tool_name}` input/output.")
            recommendations.append("Replay the task after fixing inputs: POST /copilot/tasks/{id}/replay")
            if failed.tool_name in DESTRUCTIVE_TOOLS:
                recommendations.append("Destructive tool — confirm required parameters carefully.")
            if "quota" in (failed.error or "").lower():
                recommendations.append("Check usage quotas / billing plan limits.")
            if failed.tool_name in ("retry_failed_job", "show_health", "show_monitoring"):
                recommendations.append("Check Redis worker heartbeat and dead-letter queue via /operations/jobs.")
        elif task.status == TaskStatus.FAILED:
            recommendations.append(task.error or "Task failed without step detail.")

        related: Dict[str, Any] = {}
        try:
            from app.monitoring import queue as queue_mod

            related["queue"] = queue_mod.queue_stats()
        except Exception as exc:
            related["queue_error"] = str(exc)

        return FailureDiagnostics(
            task_id=task.id,
            intent=task.intent,
            status=task.status,
            error=task.error or (failed.error if failed else None),
            failed_step=self._step_response(failed) if failed else None,
            preceding_steps=[self._step_response(s) for s in preceding],
            recommendations=recommendations,
            related_monitoring=related,
        )

    # ── Execution engine ──────────────────────────────────────────────────────

    def _execute_task(self, task: CopilotTask, user_role: str) -> CopilotTask:
        runtime = CopilotToolRuntime(
            self.db, task.company_id, task.user_id, user_role
        )
        task.status = TaskStatus.RUNNING
        task.started_at = task.started_at or _now()
        steps = self._steps(task.id)
        total = len(steps) or 1
        results: Dict[str, Any] = {"steps": []}
        slots = dict(task.slots or {})

        for step in steps:
            if step.status == StepStatus.SKIPPED:
                continue
            if step.status == StepStatus.AWAITING_CONFIRMATION:
                task.status = TaskStatus.AWAITING_CONFIRMATION
                self.db.flush()
                return task

            step.status = StepStatus.RUNNING
            step.started_at = _now()
            # Merge cumulative slots into args
            args = {**slots, **(step.input_args or {})}
            step.input_args = args
            self.db.flush()

            try:
                # Strip internal flags before tool call
                call_args = {k: v for k, v in args.items() if not str(k).startswith("_")}
                output = runtime.execute(step.tool_name, call_args)
                step.output = output if isinstance(output, dict) else {"value": output}
                step.status = StepStatus.COMPLETED
                step.completed_at = _now()
                # Promote useful ids into slots/memory
                for key in (
                    "agent_id",
                    "generation_id",
                    "knowledge_base_id",
                    "installation_id",
                    "domain_id",
                    "template_slug",
                    "unit_id",
                ):
                    if step.output.get(key):
                        slots[key] = step.output[key]
                results["steps"].append(
                    {"tool": step.tool_name, "status": "completed", "output": step.output}
                )
            except HTTPException as exc:
                optional = bool(args.get("_optional"))
                if optional and exc.status_code in (403, 404):
                    step.status = StepStatus.SKIPPED
                    step.error = str(exc.detail)
                    step.completed_at = _now()
                    results["steps"].append(
                        {"tool": step.tool_name, "status": "skipped", "error": str(exc.detail)}
                    )
                    task.progress_percent = int(100 * (step.step_index + 1) / total)
                    self.db.flush()
                    continue
                step.status = StepStatus.FAILED
                step.error = str(exc.detail)
                step.completed_at = _now()
                task.status = TaskStatus.FAILED
                task.error = str(exc.detail)
                task.completed_at = _now()
                task.slots = slots
                task.result = results
                task.progress_percent = int(100 * step.step_index / total)
                self.db.flush()
                return task
            except Exception as exc:
                logger.exception("copilot step failed")
                step.status = StepStatus.FAILED
                step.error = str(exc)
                step.completed_at = _now()
                task.status = TaskStatus.FAILED
                task.error = str(exc)
                task.completed_at = _now()
                task.slots = slots
                task.result = results
                self.db.flush()
                return task

            task.progress_percent = int(100 * (step.step_index + 1) / total)
            self.db.flush()

        task.status = TaskStatus.COMPLETED
        task.completed_at = _now()
        task.progress_percent = 100
        task.slots = slots
        task.result = results
        self.db.flush()
        return task

    def _create_task(
        self,
        conversation: CopilotConversation,
        intent: CopilotIntent,
        prompt: str,
        slots: Dict[str, Any],
        user_id: UUID,
        company_id: UUID,
    ) -> CopilotTask:
        plan = list(WORKFLOWS.get(intent) or [])
        # Branding: only include publish if requested
        if intent == CopilotIntent.CONFIGURE_BRANDING and not slots.get("publish"):
            plan = [s for s in plan if s["tool"] != "publish_branding"]
        # Reports: drop platform report for non-admins later at execute time (optional)
        if intent == CopilotIntent.SHOW_REPORTS:
            # Keep both; optional platform report may 403 and we can skip optional on failure
            pass

        # Publish: prefer publish_product if generation_id present
        if intent == CopilotIntent.PUBLISH_WEBSITE and slots.get("generation_id"):
            plan = [{"tool": "publish_product", "title": "Publish generated product"}]

        task = CopilotTask(
            conversation_id=conversation.id,
            company_id=company_id,
            user_id=user_id,
            intent=intent.value,
            status=TaskStatus.PLANNED,
            prompt=prompt,
            plan=plan,
            slots=slots,
            result={},
            requires_confirmation=_bool_str(False),
            progress_percent=0,
        )
        self.db.add(task)
        self.db.flush()

        for idx, step_def in enumerate(plan):
            step = CopilotTaskStep(
                task_id=task.id,
                step_index=idx,
                tool_name=step_def["tool"],
                title=step_def["title"],
                status=StepStatus.PENDING,
                input_args={**dict(slots), "_optional": bool(step_def.get("optional"))},
                output={},
            )
            self.db.add(step)
        self.db.flush()

        if not conversation.title:
            conversation.title = (prompt[:80] + "…") if len(prompt) > 80 else prompt
        return task

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _plan_requires_confirmation(self, plan: List[Dict[str, Any]]) -> bool:
        return any(s.get("tool") in DESTRUCTIVE_TOOLS for s in plan)

    def _mark_destructive_steps_awaiting(self, task: CopilotTask) -> None:
        for step in self._steps(task.id):
            if step.tool_name in DESTRUCTIVE_TOOLS:
                step.status = StepStatus.AWAITING_CONFIRMATION

    def _confirm_and_respond(
        self,
        conversation: CopilotConversation,
        task: CopilotTask,
        user_role: str,
        company_id: UUID,
        user_id: UUID,
    ) -> ChatResponse:
        task.confirmed_at = _now()
        task.requires_confirmation = _bool_str(False)
        for step in self._steps(task.id):
            if step.status == StepStatus.AWAITING_CONFIRMATION:
                step.status = StepStatus.PENDING
        task = self._execute_task(task, user_role)
        self._merge_memory(conversation, task)
        assistant = self._add_message(
            conversation,
            MessageRole.ASSISTANT,
            self._summarize_task(task),
            intent=task.intent,
            meta={"task_id": str(task.id), "confirmed": True},
            user_id=user_id,
        )
        self.db.commit()
        return ChatResponse(
            conversation_id=conversation.id,
            message=self._msg_response(assistant),
            intent=CopilotIntent(task.intent),
            confidence=1.0,
            matched_keywords=["confirm"],
            task=self._task_response(task),
            progress=self._progress_payload(task),
        )

    def _merge_memory(self, conversation: CopilotConversation, task: CopilotTask) -> None:
        memory = dict(conversation.memory or {})
        for key, value in (task.slots or {}).items():
            if value is not None:
                memory[key] = value
        memory["last_intent"] = task.intent
        memory["last_task_id"] = str(task.id)
        conversation.memory = memory

    def _summarize_task(self, task: CopilotTask) -> str:
        if task.status == TaskStatus.COMPLETED:
            parts = [f"Completed **{task.intent}** ({task.progress_percent}%)."]
            slots = task.slots or {}
            for key in ("agent_id", "generation_id", "preview_url", "domain_id", "hostname"):
                if slots.get(key):
                    parts.append(f"- {key}: `{slots[key]}`")
                elif isinstance(task.result, dict):
                    # peek last step outputs
                    pass
            # From last completed step outputs
            for step in self._steps(task.id):
                if step.status == StepStatus.COMPLETED and step.output:
                    if step.output.get("preview_url"):
                        parts.append(f"- preview: {step.output['preview_url']}")
                    if step.output.get("status") and step.tool_name == "show_health":
                        parts.append(f"- health: {step.output.get('status')}")
            return "\n".join(parts)
        if task.status == TaskStatus.FAILED:
            return f"Task **{task.intent}** failed: {task.error or 'unknown error'}. Use diagnostics endpoint for details."
        if task.status == TaskStatus.AWAITING_CONFIRMATION:
            return f"Task **{task.intent}** is awaiting confirmation."
        return f"Task **{task.intent}** status: {task.status.value}."

    def _help_reply(self, intent: CopilotIntent) -> str:
        if intent == CopilotIntent.LIST_TOOLS:
            names = ", ".join(t["name"] for t in TOOL_CATALOG)
            return f"Available Copilot tools: {names}"
        if intent == CopilotIntent.UNKNOWN:
            return (
                "I didn't catch that. Try: "
                "\"Create a customer support chatbot\", "
                "\"Publish my AI product\", "
                "\"Connect my domain example.com\", "
                "\"Show platform health\"."
            )
        return (
            "I'm the THTWAAT AI Copilot. I orchestrate Product Generator, Marketplace, "
            "Publish, Domains, Branding, Enterprise, Billing, and Monitoring — "
            "without duplicating their logic. Ask me to create agents, generate products, "
            "publish, connect domains, invite members, or show health/reports."
        )

    def _get_or_create_conversation(
        self, company_id: UUID, user_id: UUID, conversation_id: Optional[UUID]
    ) -> CopilotConversation:
        if conversation_id:
            return self._get_conversation(conversation_id, company_id, user_id)
        row = CopilotConversation(
            company_id=company_id,
            user_id=user_id,
            title=None,
            memory={},
            is_active="active",
        )
        self.db.add(row)
        self.db.flush()
        return row

    def _get_conversation(
        self, conversation_id: UUID, company_id: UUID, user_id: UUID
    ) -> CopilotConversation:
        row = self.db.get(CopilotConversation, conversation_id)
        if not row or row.company_id != company_id or row.user_id != user_id:
            raise HTTPException(status_code=404, detail="Conversation not found")
        return row

    def _get_task(self, task_id: UUID, company_id: UUID) -> CopilotTask:
        task = self.db.get(CopilotTask, task_id)
        if not task or task.company_id != company_id:
            raise HTTPException(status_code=404, detail="Task not found")
        return task

    def _pending_confirmation(self, conversation_id: UUID) -> Optional[CopilotTask]:
        return (
            self.db.query(CopilotTask)
            .filter(
                CopilotTask.conversation_id == conversation_id,
                CopilotTask.status == TaskStatus.AWAITING_CONFIRMATION,
            )
            .order_by(CopilotTask.created_at.desc())
            .first()
        )

    def _steps(self, task_id: UUID) -> List[CopilotTaskStep]:
        return (
            self.db.query(CopilotTaskStep)
            .filter(CopilotTaskStep.task_id == task_id)
            .order_by(CopilotTaskStep.step_index.asc())
            .all()
        )

    def _add_message(
        self,
        conversation: CopilotConversation,
        role: MessageRole,
        content: str,
        *,
        intent: Optional[str] = None,
        confidence: Optional[str] = None,
        meta: Optional[Dict[str, Any]] = None,
        user_id: Optional[UUID] = None,
    ) -> CopilotMessage:
        msg = CopilotMessage(
            conversation_id=conversation.id,
            company_id=conversation.company_id,
            user_id=user_id,
            role=role,
            content=content,
            intent=intent,
            confidence=confidence,
            meta=meta or {},
        )
        self.db.add(msg)
        self.db.flush()
        return msg

    def _msg_response(self, msg: CopilotMessage) -> MessageResponse:
        return MessageResponse(
            id=msg.id,
            conversation_id=msg.conversation_id,
            role=msg.role,
            content=msg.content,
            intent=msg.intent,
            confidence=msg.confidence,
            meta=msg.meta or {},
            created_at=msg.created_at,
        )

    def _step_response(self, step: CopilotTaskStep) -> StepProgress:
        return StepProgress(
            id=step.id,
            step_index=step.step_index,
            tool_name=step.tool_name,
            title=step.title,
            status=step.status,
            input_args=step.input_args or {},
            output=step.output or {},
            error=step.error,
        )

    def _task_response(self, task: CopilotTask) -> TaskResponse:
        steps = [self._step_response(s) for s in self._steps(task.id)]
        return TaskResponse(
            id=task.id,
            conversation_id=task.conversation_id,
            intent=task.intent,
            status=task.status,
            prompt=task.prompt,
            plan=task.plan or [],
            slots=task.slots or {},
            result=task.result or {},
            error=task.error,
            requires_confirmation=task.requires_confirmation == "true",
            progress_percent=task.progress_percent or 0,
            steps=steps,
            created_at=task.created_at,
            completed_at=task.completed_at,
            parent_task_id=task.parent_task_id,
        )

    def _progress_payload(self, task: CopilotTask) -> List[Dict[str, Any]]:
        return [
            {
                "step_index": s.step_index,
                "tool": s.tool_name,
                "title": s.title,
                "status": s.status.value,
            }
            for s in self._steps(task.id)
        ]
