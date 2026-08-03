"""Import ORM models so string relationships resolve outside FastAPI main.

Worker/scheduler do not load ``main.py``; querying Webhook/Company without
registering ``User``/``App``/etc. leaves SQLAlchemy mappers half-configured.
"""
from __future__ import annotations

_REGISTERED = False


def register_orm_models() -> None:
    """Idempotent — safe to call from worker loop / outbox helpers."""
    global _REGISTERED
    if _REGISTERED:
        return

    import app.companies.model  # noqa: F401
    import app.users.model  # noqa: F401
    import app.auth.model  # noqa: F401
    import app.apps.model  # noqa: F401
    import app.storage.model  # noqa: F401
    import app.notifications.model  # noqa: F401
    import app.payments.model  # noqa: F401
    import app.ai.model  # noqa: F401
    import app.products.model  # noqa: F401
    import app.api_keys.model  # noqa: F401
    import app.webhooks.model  # noqa: F401
    import app.features.ai_platform.database.models  # noqa: F401
    import app.agent_platform.models  # noqa: F401
    import app.agent_platform.knowledge.models  # noqa: F401
    import app.usage.models  # noqa: F401
    import app.domains.models  # noqa: F401
    import app.marketplace.models  # noqa: F401
    import app.product_generator.models  # noqa: F401
    import app.branding.models  # noqa: F401
    import app.enterprise.models  # noqa: F401
    import app.onboarding.models  # noqa: F401
    import app.monitoring.models  # noqa: F401
    import app.copilot.models  # noqa: F401
    import app.agent_store.models  # noqa: F401
    import app.openai_compat.models  # noqa: F401
    import app.payments.plans.model  # noqa: F401
    import app.payments.invoices.model  # noqa: F401
    import app.payments.subscriptions.model  # noqa: F401

    _REGISTERED = True
