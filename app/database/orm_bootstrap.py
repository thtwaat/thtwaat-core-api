"""Import ORM models so string relationships resolve outside FastAPI main.

Worker/scheduler/seed CLIs do not load ``main.py``. Importing a module that
touches ``Company`` (e.g. UsageService → CompanyRepository) without ``User``
leaves SQLAlchemy mappers half-configured:

  InvalidRequestError: expression 'User' failed to locate a name ('User')

Call ``register_orm_models()`` before opening a Session in any non-main entrypoint.
"""
from __future__ import annotations

_REGISTERED = False


def register_orm_models() -> None:
    """Idempotent — safe to call from worker / scheduler / seed / outbox helpers."""
    global _REGISTERED
    if _REGISTERED:
        return

    # Load relationship targets BEFORE Company so configure_mappers can resolve
    # Company.users → User and Company.apps → App without circular imports.
    import app.users.model  # noqa: F401  — class User
    import app.apps.model  # noqa: F401  — class App
    import app.companies.model  # noqa: F401  — class Company (refs User, App)
    import app.auth.model  # noqa: F401
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
    import app.studio.models  # noqa: F401
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

    from sqlalchemy.orm import configure_mappers

    configure_mappers()
    _REGISTERED = True
