from logging.config import fileConfig

from sqlalchemy import pool

from alembic import context

# Import our settings and base metadata
from app.config.settings import settings
import app.users.model  # noqa: F401 — User before Company
import app.apps.model  # noqa: F401 — App before Company
import app.companies.model
import app.auth.model
import app.storage.model
import app.notifications.model
import app.payments.model
import app.ai.model
import app.products.model
import app.api_keys.model
import app.webhooks.model
import app.agent_platform.models
import app.agent_platform.knowledge.models  # noqa — registers all KB tables for autogenerate
import app.features.ai_platform.database.models  # noqa — registers ai_providers, ai_models, ai_agents, etc.
import app.usage.models  # noqa — usage_events, company_usage_meters, usage_daily_aggregates
import app.domains.models  # noqa — company_domains
import app.marketplace.models  # noqa — marketplace_templates, versions, installations
import app.product_generator.models  # noqa — product_generations
import app.branding.models  # noqa — company_branding, branding_assets
import app.enterprise.models  # noqa — enterprise administration and governance
import app.onboarding.models  # noqa — customer onboarding wizard
import app.monitoring.models  # noqa — monitoring & admin operations
import app.copilot.models  # noqa — AI Copilot orchestration
import app.agent_store.models  # noqa — AI Agent Marketplace & Store
import app.openai_compat.models  # noqa — openai_completion_logs
import app.payments.plans.model  # noqa
import app.payments.subscriptions.model  # noqa
import app.payments.invoices.model  # noqa
from app.models.base import Base

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Prefer the settings URL directly. When writing into alembic.ini via
# ConfigParser, percent-encoded passwords must escape "%" as "%%".
_db_url = str(settings.database_url)
config.set_main_option("sqlalchemy.url", _db_url.replace("%", "%%"))

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
target_metadata = Base.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = _db_url
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    # Bypass ConfigParser interpolation for encoded passwords (@, #, %, …).
    from sqlalchemy import create_engine

    connectable = create_engine(_db_url, poolclass=pool.NullPool)

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
