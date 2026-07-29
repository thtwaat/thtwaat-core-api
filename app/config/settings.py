from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict

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

# Instantiate the settings object to be used across the application
settings = Settings()
