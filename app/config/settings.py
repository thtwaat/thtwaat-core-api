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

    model_config = SettingsConfigDict(
        env_file=".env", 
        env_file_encoding="utf-8",
        extra="ignore" # Ignore extra env variables not defined in the model
    )

# Instantiate the settings object to be used across the application
settings = Settings()
