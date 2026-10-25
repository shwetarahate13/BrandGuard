"""BrandGuard application configuration."""
import secrets
from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # App
    APP_NAME: str = "BrandGuard"
    APP_VERSION: str = "1.0.0"
    # Use a fresh local-only key when no environment secret is configured.
    # Production deployments should provide JWT_SECRET so tokens remain valid
    # across restarts and multiple application instances.
    JWT_SECRET: str = Field(default_factory=lambda: secrets.token_urlsafe(48))
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 480  # 8 hours

    # Database
    DATABASE_URL: str = "sqlite:///./brandguard.db"

    # ChromaDB
    CHROMA_PERSIST_DIR: str = "./data/chroma"

    # LLM
    LLM_PROVIDER: str = "mock"  # "anthropic" or "mock"
    LLM_MODEL: str = "claude-sonnet-4-20250514"
    LLM_API_KEY: Optional[str] = None
    LLM_TIMEOUT: int = 30
    LLM_MAX_RETRIES: int = 2

    # Upload limits
    MAX_UPLOAD_SIZE_MB: int = 5
    MAX_TEXT_WORDS: int = 5000

    # Seeding
    AUTO_SEED: bool = False

    # Set this only when the frontend is hosted on a separate origin.
    CORS_ORIGINS: str = ""

    @property
    def database_url_sync(self) -> str:
        """Get sync database URL, normalizing postgres:// to postgresql://."""
        url = self.DATABASE_URL
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql://", 1)
        return url

    @property
    def is_sqlite(self) -> bool:
        return self.DATABASE_URL.startswith("sqlite")

    @property
    def is_postgres(self) -> bool:
        return "postgres" in self.DATABASE_URL.lower()

    @property
    def llm_available(self) -> bool:
        return self.LLM_PROVIDER != "mock" and bool(self.LLM_API_KEY)

    model_config = {"env_file": ".env", "extra": "ignore"}


@lru_cache()
def get_settings() -> Settings:
    return Settings()
