"""BrandGuard application configuration."""
import os
from pathlib import Path
from functools import lru_cache
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # App
    APP_NAME: str = "BrandGuard"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    SECRET_KEY: str = "dev-secret-key-change-in-production"
    JWT_SECRET: str = "dev-jwt-secret-change-in-production"
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

    # Embeddings
    EMBEDDING_BACKEND: str = "tfidf"  # "tfidf" or "sentence_transformer"

    # Upload limits
    MAX_UPLOAD_SIZE_MB: int = 5
    MAX_TEXT_WORDS: int = 5000

    # Seeding
    AUTO_SEED: bool = False

    # CORS (local dev only)
    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:3000"

    # Rate limiting
    RATE_LIMIT_AUTH: str = "10/minute"
    RATE_LIMIT_CHECK: str = "20/minute"

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
