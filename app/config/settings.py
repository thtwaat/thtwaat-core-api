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
    INFERENCE_ENABLE_OPENROUTER: bool = True
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
    # Sem03 Week 2 Day 2 — production streaming reliability
    # provider=auto|ollama|openai|gemini|anthropic (request body; default auto)
    STREAM_DEFAULT_PROVIDER: str = "auto"
    # Comma list — tried after primary fails before first token
    STREAM_FALLBACK_ORDER: str = "ollama,openai,gemini,anthropic,openrouter"
    # Enterprise gateway retry / timeout defaults (additive)
    GATEWAY_RETRY_MAX_ATTEMPTS: int = 2
    GATEWAY_RETRY_BACKOFF_MS: int = 200
    GATEWAY_REQUEST_TIMEOUT_SECONDS: float = 60.0
    STREAM_CONNECT_TIMEOUT: float = 10.0
    STREAM_FIRST_TOKEN_TIMEOUT: float = 30.0
    STREAM_IDLE_TIMEOUT: float = 60.0
    # Max SSE frames buffered for a slow client before disconnect
    STREAM_MAX_QUEUED_EVENTS: int = 256
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

    # Consumer Google OAuth (email + password launch auth; not enterprise Workspace SSO)
    GOOGLE_OAUTH_CLIENT_ID: Optional[str] = None
    GOOGLE_OAUTH_CLIENT_SECRET: Optional[str] = None
    GOOGLE_OAUTH_REDIRECT_URI: str = "http://localhost:8000/api/v1/auth/google/callback"
    # SaaS web app origin for post-login / password-reset redirects
    PUBLIC_APP_BASE_URL: str = "http://localhost:3300"
    PASSWORD_RESET_TOKEN_TTL_MINUTES: int = 60

    # THTWAAT Phase 6C-1 — Coding AI / AgentRuntime service-to-service auth.
    # Core mints a short-lived HS256 token (app/coding_agent/service.py)
    # identifying (company_id, user_id) to the separately-deployed AI_Project
    # API (dashboard.thtwaat.com), which verifies it with the SAME secret
    # configured out-of-band on its own side. Deliberately its OWN secret —
    # never JWT_SECRET_KEY/JWT_REFRESH_SECRET_KEY — so a leaked/rotated
    # service secret can never forge a user session or vice versa.
    CODING_AGENT_SERVICE_JWT_SECRET: Optional[str] = None
    CODING_AGENT_JWT_AUDIENCE: str = "coding-agent"
    CODING_AGENT_JWT_ISSUER: str = "thtwaat-core-api"
    CODING_AGENT_SERVICE_TOKEN_TTL_SECONDS: int = 120

    # THTWAAT Phase 6C-2 — task-creation proxy. Base URL of the
    # separately-deployed AI_Project API (dashboard.thtwaat.com in
    # production); empty means the integration is not wired up yet, in
    # which case app.coding_agent.client fails closed with 503 rather
    # than attempting a request to an empty URL.
    CODING_AGENT_API_BASE_URL: Optional[str] = None
    CODING_AGENT_REQUEST_TIMEOUT_SECONDS: float = 30.0

    # THTWAAT Deploy Phase 5 — GitHub Connect (GitHub App, not OAuth App).
    # The app authenticates itself via an RS256 JWT signed with
    # GITHUB_APP_PRIVATE_KEY to mint short-lived installation access tokens
    # on demand (see app/static_sites/github_client.py) — no GitHub user
    # access/refresh token is ever requested or stored, so there is no
    # client_secret here either.
    GITHUB_APP_ID: Optional[str] = None
    GITHUB_APP_SLUG: Optional[str] = None
    GITHUB_APP_PRIVATE_KEY: Optional[str] = None
    GITHUB_OAUTH_STATE_TTL_MINUTES: int = 15

    # THTWAAT Deploy Phase 5C — Git Push -> Auto Deploy. Server-side-only
    # webhook secret used to verify GitHub's X-Hub-Signature-256 HMAC over
    # the raw webhook body (app/static_sites/github_webhook.py). Never
    # accepted from a request; configured once on the GitHub App's own
    # "Webhook secret" field in github.com settings.
    GITHUB_APP_WEBHOOK_SECRET: Optional[str] = None
    # Hard cap on a fetched repository archive (zipball) size, enforced
    # while streaming the download — mirrors STATIC_SITE_MAX_ARCHIVE_BYTES
    # for uploads so a malicious/huge repo can't exhaust disk on the box
    # fetching it.
    GITHUB_ARCHIVE_MAX_BYTES: int = 50 * 1024 * 1024

    # THTWAAT Deploy Phase 6A — Preview Deployments. Kill switch, expiry
    # backstop (a preview is torn down on PR-close regardless; this bounds
    # how long an abandoned/never-closed PR's preview can live), and the
    # deterministic hostname prefix (see app/static_sites/preview_hostname.py).
    PREVIEW_DEPLOYMENTS_ENABLED: bool = True
    PREVIEW_DEPLOYMENT_TTL_HOURS: int = 72
    PREVIEW_SUBDOMAIN_PREFIX: str = "pr"

    # Public publish / embed base URL (used in embed scripts & iframe URLs)
    PUBLIC_API_BASE_URL: str = "http://localhost:8000"
    # iframe embed JWT lifetime (seconds). Live API keys must never appear in iframe URLs.
    EMBED_TOKEN_TTL_SECONDS: int = 3600

    # Domain Manager / custom domains
    DOMAIN_CNAME_TARGET: str = "cname.thtwaat.com"
    DOMAIN_A_RECORDS: list[str] = []
    DOMAIN_AAAA_RECORDS: list[str] = []
    # Studio free deploy hostnames: {slug}-{id8}.thtwaat.com
    STUDIO_FREE_SUBDOMAIN_ZONE: str = "thtwaat.com"

    # SSL Manager
    SSL_MODE: str = "simulate"  # simulate | certbot
    SSL_ACME_EMAIL: Optional[str] = "ops@thtwaat.com"
    SSL_ACME_STAGING: bool = True
    SSL_CERTS_DIR: str = "nginx/ssl/domains"
    SSL_WEBROOT_DIR: str = "nginx/acme-webroot"
    NGINX_GENERATED_DIR: str = "nginx/conf.d/domains"
    NGINX_CERT_CONTAINER_PREFIX: Optional[str] = "/etc/nginx/ssl"

    # THTWAAT Deploy (app/static_sites) — isolated static-site content root.
    # Mirrors the SSL_CERTS_DIR / NGINX_CERT_CONTAINER_PREFIX pattern: api/worker
    # write extracted deployments under STATIC_SITES_DIR; nginx mounts the same
    # host directory read-only at STATIC_SITES_CONTAINER_PREFIX.
    STATIC_SITES_DIR: str = "data/static-sites"
    STATIC_SITES_CONTAINER_PREFIX: Optional[str] = "/etc/nginx/static-sites"
    STATIC_SITE_MAX_ARCHIVE_BYTES: int = 50 * 1024 * 1024
    STATIC_SITE_MAX_EXTRACTED_BYTES: int = 200 * 1024 * 1024
    STATIC_SITE_MAX_FILE_BYTES: int = 20 * 1024 * 1024
    STATIC_SITE_MAX_FILE_COUNT: int = 5000

    # THTWAAT Deploy — Vite build sandbox (app/static_sites/vite_build.py).
    # The build ALWAYS runs in an ephemeral, non-root, resource-capped
    # `docker run` against VITE_BUILD_IMAGE — never on the api/worker host,
    # never with the Docker socket, host filesystem, or any secret mounted
    # into it. VITE_BUILD_ENABLED lets ops disable this entirely (e.g. on a
    # host where the docker CLI / socket isn't available to this process).
    VITE_BUILD_ENABLED: bool = False
    VITE_BUILD_IMAGE: str = "thtwaat-vite-build:20"
    # Dedicated network, deliberately separate from thtwaat_net (db/redis/api/
    # nginx) — the build container is never attached to the network that can
    # reach internal services. See docker-compose.prod.yml.
    VITE_BUILD_NETWORK: str = "thtwaat_vite_build_net"
    VITE_MAX_BUILD_TIME_SECONDS: int = 300
    VITE_MAX_BUILD_MEMORY_MB: int = 1536
    VITE_MAX_BUILD_CPU: float = 1.0
    VITE_BUILD_TMPFS_MB: int = 512
    VITE_MAX_SOURCE_BYTES: int = 50 * 1024 * 1024
    VITE_MAX_OUTPUT_BYTES: int = 100 * 1024 * 1024
    VITE_MAX_OUTPUT_FILE_COUNT: int = 20000
    VITE_MAX_NODE_MODULES_BYTES: int = 1024 * 1024 * 1024
    VITE_MAX_LOG_BYTES: int = 200_000

    # THTWAAT Deploy — build-orchestrator (recommended production mode; see
    # orchestrator/README.md and the Phase 2 staging validation report §1).
    # When VITE_BUILD_ORCHESTRATOR_URL is set, run_vite_build() calls this
    # service over HTTP instead of shelling out to `docker` itself — api/
    # worker then never need Docker socket access at all. Empty (the
    # default) keeps the original direct-`docker run` fallback below, which
    # requires this process to have docker.sock access and is intended for
    # local/dev only (docker-compose.yml), never for docker-compose.prod.yml.
    VITE_BUILD_ORCHESTRATOR_URL: str = ""
    VITE_BUILD_ORCHESTRATOR_SHARED_SECRET: str = ""
    VITE_BUILD_ORCHESTRATOR_TIMEOUT_SECONDS: int = 320

    # THTWAAT Deploy — Next.js standalone build + isolated Node runtime
    # (Phase 3). Reuses the SAME build-orchestrator service/shared-secret/URL
    # as Vite above (VITE_BUILD_ORCHESTRATOR_URL/_SHARED_SECRET) — it is one
    # process with a narrow UUID-only schema; this just adds two more
    # endpoints to it (/v1/nextjs-builds, /v1/nextjs-runtimes) rather than
    # standing up a second Docker-control-plane service. Gated by its own
    # flag because a deployment may want Vite builds without ever running a
    # persistent Node runtime container (a materially different risk/cost
    # profile — long-lived process vs. one-shot build).
    NEXTJS_BUILD_ENABLED: bool = False
    NEXTJS_BUILD_IMAGE: str = "thtwaat-nextjs-build:20"
    # Defaults to the SAME network as Vite builds (no path to db/redis/api;
    # open egress for the npm registry) — a distinct setting so ops can split
    # them later without a code change, but nothing forces a second network
    # to exist just for this phase.
    NEXTJS_BUILD_NETWORK: str = "thtwaat_vite_build_net"
    NEXTJS_MAX_BUILD_TIME_SECONDS: int = 600
    NEXTJS_MAX_BUILD_MEMORY_MB: int = 2048
    NEXTJS_MAX_BUILD_CPU: float = 1.5
    NEXTJS_BUILD_TMPFS_MB: int = 512
    NEXTJS_MAX_SOURCE_BYTES: int = 50 * 1024 * 1024
    # Bigger than Vite's static-dist cap — the standalone artifact includes a
    # traced, pruned node_modules subset, not just HTML/CSS/JS.
    NEXTJS_MAX_OUTPUT_BYTES: int = 300 * 1024 * 1024
    NEXTJS_MAX_OUTPUT_FILE_COUNT: int = 40000
    NEXTJS_MAX_NODE_MODULES_BYTES: int = 1536 * 1024 * 1024
    NEXTJS_MAX_LOG_BYTES: int = 200_000

    # Runtime container (one per live Next.js deployment version). No host
    # port is ever published — nginx reaches it by its fixed container name
    # over NEXTJS_RUNTIME_NETWORK using Docker's embedded DNS (see
    # app/ssl/nginx_gen.py RUNTIME_PROXY_LOCATION_BLOCK), so there is no
    # host-port allocator to run or collide.
    NEXTJS_RUNTIME_IMAGE: str = "thtwaat-nextjs-runtime:20"
    NEXTJS_RUNTIME_NETWORK: str = "thtwaat_nextjs_runtime_net"
    NEXTJS_RUNTIME_PORT: int = 3000
    NEXTJS_RUNTIME_MEMORY_MB: int = 512
    NEXTJS_RUNTIME_CPU: float = 0.5
    NEXTJS_RUNTIME_PIDS: int = 128
    NEXTJS_RUNTIME_TMPFS_MB: int = 64
    NEXTJS_HEALTH_STARTUP_TIMEOUT_SECONDS: int = 60
    NEXTJS_HEALTH_RETRY_COUNT: int = 10
    NEXTJS_HEALTH_RETRY_INTERVAL_SECONDS: float = 2.0
    NEXTJS_HEALTH_REQUEST_TIMEOUT_SECONDS: float = 3.0
    # Per-company cap on simultaneously LIVE Next.js runtime containers — a
    # single tenant must not be able to start unbounded persistent processes
    # on the VPS (unlike static files, these hold memory/CPU/PIDs 24/7).
    NEXTJS_MAX_RUNTIMES_PER_COMPANY: int = 10

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
    RAZORPAY_WEBHOOK_SECRET: Optional[str] = None
    # Feature flags — either provider can be enabled independently
    BILLING_ENABLE_STRIPE: bool = True
    BILLING_ENABLE_RAZORPAY: bool = True
    BILLING_DEFAULT_PROVIDER: str = "auto"  # auto|stripe|razorpay

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

        if self.CODING_AGENT_SERVICE_JWT_SECRET:
            weakness = _describe_weakness(
                "CODING_AGENT_SERVICE_JWT_SECRET", self.CODING_AGENT_SERVICE_JWT_SECRET
            )
            if weakness:
                problems.append(weakness)
            if self.CODING_AGENT_SERVICE_JWT_SECRET in (
                self.JWT_SECRET_KEY,
                self.JWT_REFRESH_SECRET_KEY,
            ):
                problems.append(
                    "CODING_AGENT_SERVICE_JWT_SECRET must not reuse "
                    "JWT_SECRET_KEY or JWT_REFRESH_SECRET_KEY"
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
