import logging
from typing import Optional

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

# Environments that must never boot with development-grade secrets.
HARDENED_ENVS = {"production", "prod", "staging"}

# Minimum secret length accepted in hardened environments.
# Kept in sync with deploy/validate-env.sh.
MIN_JWT_SECRET_LENGTH = 32

# Minimum number of distinct characters, so "aaaa...aaaa" (32 chars) is rejected.
MIN_JWT_SECRET_UNIQUE_CHARS = 12

# Lowercased substrings that indicate a placeholder / development secret.
WEAK_SECRET_MARKERS = (
    "devsecret",
    "changeme",
    "change-me",
    "change_me",
    "placeholder",
    "example",
    "insecure",
    "notsecret",
    "supersecret",
    "your-secret",
    "your_secret",
    "yoursecret",
    "secret123",
    "password",
    "testsecret",
    "dummy",
    "sample",
    "todo",
    "xxxx",
)

# Exact values that are never acceptable, regardless of environment rules.
WEAK_SECRET_EXACT = {
    "secret",
    "jwt_secret",
    "jwt_secret_key",
    "jwt-secret",
    "test",
    "dev",
    "development",
    "local",
}


def _describe_weakness(name: str, value: Optional[str]) -> Optional[str]:
    """Return a human-readable reason when a secret is not production-safe."""
    if not value or not value.strip():
        return f"{name} is empty"

    candidate = value.strip()
    lowered = candidate.lower()

    if lowered in WEAK_SECRET_EXACT:
        return f"{name} is a well-known placeholder value"
    for marker in WEAK_SECRET_MARKERS:
        if marker in lowered:
            return f"{name} contains the development marker '{marker}'"
    if len(candidate) < MIN_JWT_SECRET_LENGTH:
        return (
            f"{name} is {len(candidate)} characters long "
            f"(minimum {MIN_JWT_SECRET_LENGTH})"
        )
    if len(set(candidate)) < MIN_JWT_SECRET_UNIQUE_CHARS:
        return (
            f"{name} has only {len(set(candidate))} distinct characters "
            f"(minimum {MIN_JWT_SECRET_UNIQUE_CHARS})"
        )
    return None


class Settings(BaseSettings):
    app_name: str = "THTWAAT Core API"
    app_env: str = "development"
    
    # Database connection parameters
    db_host: Optional[str] = None
    db_port: Optional[int] = 5432
    db_name: Optional[str] = None
    db_user: Optional[str] = None
    db_password: Optional[str] = None

    # Redis connection parameters
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379

    @property
    def database_url(self) -> str:
        """Construct the PostgreSQL database URL from individual components.

        Uses SQLAlchemy URL.create() so passwords with ``@``, ``#``, ``:``,
        ``/``, etc. are percent-encoded and never break host parsing.
        """
        import os

        from sqlalchemy.engine.url import URL

        if os.getenv("DATABASE_URL"):
            return os.getenv("DATABASE_URL")
        return URL.create(
            drivername="postgresql",
            username=self.db_user,
            password=self.db_password,
            host=self.db_host,
            port=self.db_port,
            database=self.db_name,
        ).render_as_string(hide_password=False)

    # Storage
    STORAGE_PROVIDER: str = "local"
    LOCAL_STORAGE_DIR: str = "data/uploads"

    # AI Gateway
    AI_PROVIDER: str = "openai"
    OPENAI_API_KEY: Optional[str] = None
    GEMINI_API_KEY: Optional[str] = None
    ANTHROPIC_API_KEY: Optional[str] = None
    OPENROUTER_API_KEY: Optional[str] = None
    OLLAMA_URL: Optional[str] = "http://localhost:11434"
    # OpenAI-compatible /v1 surface: stub (CI) or gateway (live providers)
    OPENAI_COMPAT_INFERENCE: str = "stub"
    # Sem03 Week 1 Day 2 — inference provider registry / default routing
    INFERENCE_DEFAULT_PROVIDER: str = "ollama"
    INFERENCE_ENABLE_OLLAMA: bool = True
    INFERENCE_ENABLE_OPENAI: bool = True
    INFERENCE_ENABLE_GEMINI: bool = True
    INFERENCE_ENABLE_ANTHROPIC: bool = True
    INFERENCE_ENABLE_VLLM: bool = False
    VLLM_BASE_URL: Optional[str] = None
    # Sem03 Week 1 Day 3 — inference router policies / health cache
    # Policies: default | cheapest | fastest | highest_quality | preferred_provider
    INFERENCE_ROUTING_POLICY: str = "default"
    INFERENCE_FALLBACK_PROVIDER: Optional[str] = "openai"
    INFERENCE_HEALTH_CACHE_TTL_SECONDS: int = 30
    # Optional comma list override for provider priority (first = highest)
    INFERENCE_PROVIDER_PRIORITY: Optional[str] = None
    # Sem03 Week 1 Day 4 — upstream timeout (Ollama chat HTTP)
    INFERENCE_OLLAMA_TIMEOUT_SECONDS: float = 120.0
    # Sem03 Week 1 Day 5 — prompt injection / model-exfil edge guard
    INFERENCE_PROMPT_GUARD_ENABLED: bool = True
    # block = 400 OpenAI-shaped error; log = allow but warn
    INFERENCE_PROMPT_GUARD_MODE: str = "block"
    # Sem03 Week 2 Day 1 — true provider SSE streaming
    STREAM_ENABLED: bool = True
    # When true and OPENAI_API_KEY set, use live OpenAI SSE; else synthetic incremental
    INFERENCE_STREAM_LIVE_OPENAI: bool = True
    # Week 2 Day 2 — Redis caching for openai_compat
    OPENAI_COMPAT_CACHE_ENABLED: bool = True
    OPENAI_COMPAT_MODEL_CACHE_TTL_SECONDS: int = 300
    OPENAI_COMPAT_RESPONSE_CACHE_TTL_SECONDS: int = 60
    OPENAI_COMPAT_CACHE_RESPONSES: bool = True
    # Week 2 Day 3 — Idempotency-Key for completions
    OPENAI_COMPAT_IDEMPOTENCY_ENABLED: bool = True
    OPENAI_COMPAT_IDEMPOTENCY_TTL_SECONDS: int = 86400
    # Week 2 Day 4 — tenant rate limits for openai_compat
    OPENAI_COMPAT_RATE_LIMIT_ENABLED: bool = True
    OPENAI_COMPAT_RATE_LIMIT_DEFAULT_PLAN: str = "free"
    # Optional global overrides (apply to completions scope when set)
    OPENAI_COMPAT_RATE_LIMIT_RPM: Optional[int] = None
    OPENAI_COMPAT_RATE_LIMIT_RPD: Optional[int] = None
    # Week 3 Day 1 — enqueue completion.* webhooks via Redis worker
    OPENAI_COMPAT_WEBHOOKS_ENABLED: bool = True
    # Week 3 Day 2 — delivery retries
    WEBHOOK_MAX_ATTEMPTS: int = 5
    WEBHOOK_BACKOFF_BASE_SECONDS: float = 2.0
    WEBHOOK_BACKOFF_CAP_SECONDS: float = 300.0
    # Week 3 Day 5 — reject receiver timestamps older/newer than this window
    WEBHOOK_SIGNATURE_TOLERANCE_SECONDS: int = 300
    # Week 4 Day 1 — dual-write webhook_deliveries outbox before Redis enqueue
    WEBHOOK_OUTBOX_ENABLED: bool = True
    # Week 4 Day 2 — redrive stuck pending/queued/failed rows
    WEBHOOK_OUTBOX_STALE_SECONDS: int = 120
    WEBHOOK_OUTBOX_REDRIVE_BATCH: int = 50
    # Week 4 Day 5 — block SSRF-ish webhook targets (localhost / private / link-local)
    WEBHOOK_URL_SSRF_GUARD_ENABLED: bool = True
    WEBHOOK_ALLOW_HTTP_URLS: bool = False
    WEBHOOK_URL_RESOLVE_DNS: bool = True

    # Marketplace catalog — idempotent seed of JSON package + prompt starters on boot.
    # Production Browse was empty because alembic creates schema only; without this
    # (or `python -m scripts.seed_marketplace`) the DB never receives the catalog.
    MARKETPLACE_AUTO_SEED_ON_STARTUP: bool = True
    MARKETPLACE_AUTO_SEED_REFRESH_SAME_VERSION: bool = False

    # Embeddings (RAG pipeline). Model names are configurable so a retired
    # provider model can be swapped without a code change.
    EMBEDDING_DIMENSIONS: int = 768
    EMBEDDING_OLLAMA_MODEL: str = "nomic-embed-text"
    EMBEDDING_GEMINI_MODEL: str = "models/gemini-embedding-001"
    EMBEDDING_OLLAMA_AUTO_PULL: bool = True
    
    # Auth & Security
    JWT_SECRET_KEY: str
    JWT_REFRESH_SECRET_KEY: str
    CORS_ORIGINS: list[str] = ["*"]
    
    MFA_ISSUER_NAME: str = "THTWAAT Enterprise"

    # Public publish / embed base URL (used in embed scripts & iframe URLs)
    PUBLIC_API_BASE_URL: str = "http://localhost:8000"
    # iframe embed JWT lifetime (seconds). Live API keys must never appear in iframe URLs.
    EMBED_TOKEN_TTL_SECONDS: int = 3600

    # Domain Manager / custom domains
    DOMAIN_CNAME_TARGET: str = "cname.thtwaat.com"
    DOMAIN_A_RECORDS: list[str] = []
    DOMAIN_AAAA_RECORDS: list[str] = []

    # SSL Manager
    SSL_MODE: str = "simulate"  # simulate | certbot
    SSL_ACME_EMAIL: Optional[str] = "ops@thtwaat.com"
    SSL_ACME_STAGING: bool = True
    SSL_CERTS_DIR: str = "nginx/ssl/domains"
    SSL_WEBROOT_DIR: str = "nginx/acme-webroot"
    NGINX_GENERATED_DIR: str = "nginx/conf.d/domains"
    NGINX_CERT_CONTAINER_PREFIX: Optional[str] = "/etc/nginx/ssl"

    # Backups / scheduler
    BACKUP_DIR: str = "data/backups"
    BACKUP_RETENTION_DAYS: int = 14
    BACKUP_HOUR_UTC: int = 3
    SCHEDULER_INTERVAL_SECONDS: int = 300

    # Observability (links only — Prometheus scrape remains Instrumentator /metrics)
    PROMETHEUS_URL: str = "http://localhost:9090"
    GRAFANA_URL: str = "http://localhost:3000"

    # /metrics exposure control.
    # In hardened environments the endpoint only answers internal scrapers or
    # callers presenting METRICS_TOKEN. See app/deploy/metrics_guard.py.
    METRICS_ENABLED: bool = True
    METRICS_TOKEN: Optional[str] = None
    METRICS_ALLOWED_NETWORKS: list[str] = [
        "127.0.0.0/8",
        "10.0.0.0/8",
        "172.16.0.0/12",
        "192.168.0.0/16",
        "::1/128",
        "fc00::/7",
    ]

    # Security
    TRUSTED_PROXIES: list[str] = ["nginx", "127.0.0.1"]
    CSP_POLICY: str = "default-src 'self'; frame-ancestors 'self'; object-src 'none'"

    # Payment Gateways
    STRIPE_SECRET_KEY: Optional[str] = None
    STRIPE_WEBHOOK_SECRET: Optional[str] = None
    STRIPE_CURRENCY: str = "usd"
    RAZORPAY_KEY_ID: Optional[str] = None
    RAZORPAY_KEY_SECRET: Optional[str] = None

    model_config = SettingsConfigDict(
        env_file=".env", 
        env_file_encoding="utf-8",
        extra="ignore" # Ignore extra env variables not defined in the model
    )

    @property
    def is_hardened_env(self) -> bool:
        return (self.app_env or "").strip().lower() in HARDENED_ENVS

    @model_validator(mode="after")
    def _enforce_production_secrets(self) -> "Settings":
        problems = [
            reason
            for reason in (
                _describe_weakness("JWT_SECRET_KEY", self.JWT_SECRET_KEY),
                _describe_weakness("JWT_REFRESH_SECRET_KEY", self.JWT_REFRESH_SECRET_KEY),
            )
            if reason
        ]
        if self.JWT_SECRET_KEY and self.JWT_SECRET_KEY == self.JWT_REFRESH_SECRET_KEY:
            problems.append(
                "JWT_SECRET_KEY and JWT_REFRESH_SECRET_KEY must be different values"
            )

        origins = [str(o).strip() for o in (self.CORS_ORIGINS or []) if str(o).strip()]
        if self.is_hardened_env:
            if not origins:
                problems.append(
                    "CORS_ORIGINS must list explicit frontend origins in production"
                )
            elif "*" in origins:
                problems.append(
                    "CORS_ORIGINS must not include '*' in production "
                    '(use e.g. ["https://app.thtwaat.com"])'
                )

        if not problems:
            return self

        if self.is_hardened_env:
            raise ValueError(
                "Refusing to start with unsafe configuration in "
                f"APP_ENV={self.app_env}:\n  - "
                + "\n  - ".join(problems)
                + "\nGenerate strong JWT secrets, e.g. "
                "`python -c \"import secrets; print(secrets.token_urlsafe(48))\"`, "
                "and set an explicit CORS_ORIGINS allowlist."
            )

        for problem in problems:
            logger.warning(
                "[Settings] Unsafe configuration (allowed in APP_ENV=%s only): %s",
                self.app_env,
                problem,
            )
        return self

# Instantiate the settings object to be used across the application
settings = Settings()
