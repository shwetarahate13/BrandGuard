"""BrandGuard application configuration."""
import secrets
import os
from functools import lru_cache
from pydantic import Field, model_validator
from pydantic_settings import BaseSettings
from typing import Literal, Optional
from urllib.parse import urlsplit


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # App
    APP_NAME: str = "BrandGuard"
    APP_VERSION: str = "1.0.0"
    ENVIRONMENT: str = "development"
    JWT_SECRET: str = ""
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = Field(default=480, ge=1)  # 8 hours

    # Database
    DATABASE_URL: str = "sqlite:///./brandguard.db"

    # ChromaDB
    CHROMA_PERSIST_DIR: str = "./data/chroma"
    ASSET_STORAGE_DIR: str = "./data/assets"

    # LLM
    LLM_PROVIDER: str = "mock"  # "anthropic" or "mock"
    LLM_MODEL: str = "claude-sonnet-4-20250514"
    LLM_API_KEY: Optional[str] = None
    LLM_TIMEOUT: int = 30
    LLM_MAX_RETRIES: int = 2

    # Upload limits
    MAX_UPLOAD_SIZE_MB: int = Field(default=5, ge=1, le=5)
    MAX_TEXT_WORDS: int = 5000
    # RapidOCR/ONNX can exceed small-instance memory budgets; opt in only on
    # instances sized for image processing. PDF text extraction stays enabled.
    IMAGE_REVIEW_ENABLED: bool = False
    OCR_BACKEND: Literal["rapidocr", "tesseract"] = "tesseract"

    # Demo users/data and demo-role switching are opt-in.
    DEMO_MODE: bool = False

    # Lightweight local mode deliberately omits image/OCR dependencies.
    BRANDGUARD_LITE: bool = False

    # Set this only when the frontend is hosted on a separate origin.
    CORS_ORIGINS: str = ""

    @model_validator(mode="after")
    def validate_runtime_configuration(self):
        if self.BRANDGUARD_LITE:
            self.IMAGE_REVIEW_ENABLED = False
        production = self.ENVIRONMENT.casefold() == "production" or os.getenv("RENDER", "").casefold() == "true"
        if production:
            if len(self.JWT_SECRET.encode("utf-8")) < 32:
                raise ValueError("JWT_SECRET must be set to at least 32 bytes in production")
            if not self.is_postgres:
                raise ValueError("DATABASE_URL must point to PostgreSQL in production")
            if self.LLM_PROVIDER.casefold() not in {"mock", "anthropic"}:
                raise ValueError("LLM_PROVIDER must be 'mock' or 'anthropic'")
            if self.LLM_PROVIDER.casefold() == "anthropic" and not self.LLM_API_KEY:
                raise ValueError("LLM_API_KEY is required when LLM_PROVIDER=anthropic")
        elif not self.JWT_SECRET:
            # A random per-process key is convenient for local development.
            self.JWT_SECRET = secrets.token_urlsafe(48)

        origins = [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]
        if any(origin == "*" for origin in origins):
            raise ValueError("CORS_ORIGINS must be an explicit origin allowlist; '*' is not allowed")
        for origin in origins:
            parsed = urlsplit(origin)
            if (
                parsed.scheme not in {"http", "https"}
                or not parsed.netloc
                or parsed.username is not None
                or parsed.password is not None
                or parsed.path != ""
                or parsed.query
                or parsed.fragment
            ):
                raise ValueError("CORS_ORIGINS must contain only HTTP(S) origins without paths or credentials")
        return self

    @property
    def database_url_sync(self) -> str:
        """Get a synchronous database URL using the installed PostgreSQL driver."""
        url = self.DATABASE_URL
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql://", 1)
        # This project installs psycopg2-binary. Some providers or copied
        # SQLAlchemy examples specify psycopg 3 explicitly; normalize that
        # driver name rather than failing at startup with ModuleNotFoundError.
        if url.startswith("postgresql+psycopg://"):
            url = url.replace("postgresql+psycopg://", "postgresql+psycopg2://", 1)
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
