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
        """Construct the PostgreSQL database URL from individual components."""
        import os
        if os.getenv("DATABASE_URL"):
            return os.getenv("DATABASE_URL")
        return f"postgresql://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}"

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

        if not problems:
            return self

        if self.is_hardened_env:
            raise ValueError(
                "Refusing to start with development-grade JWT configuration in "
                f"APP_ENV={self.app_env}:\n  - "
                + "\n  - ".join(problems)
                + "\nGenerate strong secrets, e.g. "
                "`python -c \"import secrets; print(secrets.token_urlsafe(48))\"`."
            )

        for problem in problems:
            logger.warning(
                "[Settings] Weak JWT configuration (allowed in APP_ENV=%s only): %s",
                self.app_env,
                problem,
            )
        return self

# Instantiate the settings object to be used across the application
settings = Settings()
