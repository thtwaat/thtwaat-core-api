"""
app/notifications/events.py

In-process event bus for the notification system.

Usage:
    from app.notifications.events import NotificationEventBus
    NotificationEventBus.dispatch(
        event_type="user.registered",
        db=db,
        company_id=company.id,
        user_id=user.id,
        data={"user_name": user.name}
    )

Supported events:
    user.registered         — after user creation
    company.created         — after company creation
    document.indexed        — after RAG document indexing
    payment.success         — after successful payment webhook
    payment.failed          — after failed payment webhook
    subscription.created    — after subscription is created/activated
    subscription.renewed    — after subscription renewal (invoice paid)
    subscription.cancelled  — after subscription cancellation
    api_key.created         — after API key creation
    ai_quota.warning        — when AI credits drop below threshold
"""
import uuid
import logging
from typing import Optional
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


# ─── Event Templates ─────────────────────────────────────────────────────────────
# Each entry: (title_template, body_template)
# Placeholders are filled from the `data` dict passed to dispatch()
EVENT_TEMPLATES: dict[str, tuple[str, str]] = {
    "user.registered": (
        "Welcome to {company_name}!",
        "Your account has been created successfully. Start exploring the platform."
    ),
    "company.created": (
        "Company setup complete",
        "Your company '{company_name}' has been created and is ready to use."
    ),
    "enterprise.member_invited": (
        "You have been invited to {company_name}",
        "An administrator invited {email} to join {company_name}."
    ),
    "document.indexed": (
        "Document indexed",
        "Document '{document_name}' has been indexed and is ready for semantic search."
    ),
    "payment.success": (
        "Payment successful",
        "Your payment of {amount} {currency} was processed successfully."
    ),
    "payment.failed": (
        "Payment failed",
        "Your payment of {amount} {currency} could not be processed. Please update your payment method."
    ),
    "payment.refunded": (
        "Payment refunded",
        "Your payment of {amount} {currency} has been refunded successfully."
    ),
    "subscription.created": (
        "Subscription activated",
        "Your subscription to the '{plan_name}' plan is now active."
    ),
    "subscription.renewed": (
        "Subscription renewed",
        "Your '{plan_name}' subscription has been renewed successfully."
    ),
    "subscription.cancelled": (
        "Subscription cancelled",
        "Your subscription has been cancelled. Access continues until the end of the billing period."
    ),
    "api_key.created": (
        "New API key created",
        "A new API key '{key_name}' has been created for your account."
    ),
    "ai_quota.warning": (
        "AI credits running low",
        "Your AI credits balance is {credits} units. Top up to continue using AI features without interruption."
    ),
    "onboarding.started": (
        "Welcome — let's get you live",
        "Your onboarding wizard has started. Resume anytime with your saved progress."
    ),
    "onboarding.completed": (
        "You're live on THTWAAT",
        "Customer onboarding is complete. Your product is ready to serve customers."
    ),
    "ops.alert": (
        "Ops alert: {title}",
        "Severity {severity}. Alert id {alert_id}."
    ),
    "copilot.task_completed": (
        "Copilot task completed",
        "Your Copilot task ({intent}) finished successfully. Task id {task_id}.",
    ),
    "copilot.task_failed": (
        "Copilot task failed",
        "Your Copilot task ({intent}) failed. Open diagnostics for task {task_id}.",
    ),
    "agent_store.listing_submitted": (
        "Agent listing submitted",
        "Your listing '{listing_title}' was submitted for review.",
    ),
    "agent_store.listing_approved": (
        "Agent listing approved",
        "Your listing '{listing_title}' is now live in the Agent Store.",
    ),
    "agent_store.installed": (
        "Agent installed",
        "Agent '{listing_title}' was installed successfully.",
    ),
}


def _render_template(template: str, data: dict) -> str:
    """Simple template rendering — replaces {key} placeholders from data dict."""
    try:
        return template.format(**data)
    except (KeyError, ValueError):
        return template


class NotificationEventBus:
    """
    Synchronous, in-process event dispatcher.
    Creates an IN_APP notification record for the given event.
    """

    @staticmethod
    def dispatch(
        event_type: str,
        db: Session,
        company_id: uuid.UUID,
        user_id: Optional[uuid.UUID],
        data: Optional[dict] = None,
        actor_id: Optional[uuid.UUID] = None,
    ) -> None:
        """
        Dispatches an event by creating an in-app notification.

        Args:
            event_type: One of the supported event type strings (e.g. "payment.success")
            db: Active SQLAlchemy session
            company_id: Target company (tenant)
            user_id: Target user (None = broadcast to all company members)
            data: Template variables (e.g. {"amount": 99.0, "currency": "USD"})
            actor_id: UUID of the user/entity that triggered the event
        """
        if data is None:
            data = {}
        else:
            import decimal
            data = {k: (float(v) if isinstance(v, decimal.Decimal) else v) for k, v in data.items()}

        # Enrich with published white-label company name (reuse BrandingService — no template fork)
        if "company_name" not in data:
            try:
                from app.branding.service import BrandingService

                ctx = BrandingService(db).resolve_email_context(company_id)
                data = {**data, "company_name": ctx.get("company_name") or "THTWAAT"}
            except Exception:
                data = {**data, "company_name": data.get("company_name", "THTWAAT")}

        template = EVENT_TEMPLATES.get(event_type)
        if not template:
            logger.warning(f"[EventBus] Unknown event type: {event_type}")
            return

        title_template, body_template = template
        title = _render_template(title_template, data)
        body  = _render_template(body_template, data)

        try:
            from app.notifications.service import NotificationService
            service = NotificationService(db)
            service.create_in_app_notification(
                event_type=event_type,
                company_id=company_id,
                user_id=user_id,
                title=title,
                body=body,
                extra_data=data,
                actor_id=actor_id,
            )
            logger.info(f"[EventBus] Dispatched event '{event_type}' for company={company_id}")
        except Exception as e:
            # Never let notification failures break the main request
            logger.error(f"[EventBus] Failed to dispatch '{event_type}': {e}", exc_info=True)
