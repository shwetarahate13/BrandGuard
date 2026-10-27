import pytest
from pydantic import ValidationError

from backend.app.config import Settings


def test_postgresql_psycopg_url_uses_installed_psycopg2_driver():
    settings = Settings(DATABASE_URL="postgresql+psycopg://user:pass@db.example.test/brandguard")

    assert settings.database_url_sync == "postgresql+psycopg2://user:pass@db.example.test/brandguard"


def test_postgres_legacy_scheme_normalizes_to_postgresql():
    settings = Settings(DATABASE_URL="postgres://user:pass@db.example.test/brandguard")

    assert settings.database_url_sync == "postgresql://user:pass@db.example.test/brandguard"


def test_full_local_runtime_uses_requested_caps_and_pip_ocr_by_default():
    settings = Settings(_env_file=None)

    assert settings.MAX_UPLOAD_SIZE_MB == 25
    assert settings.MAX_TEXT_WORDS == 20_000
    assert settings.IMAGE_REVIEW_ENABLED is True
    assert settings.OCR_BACKEND == "rapidocr"
    assert settings.RETRIEVAL_TOP_K >= 10

    with pytest.raises(ValidationError, match="MAX_UPLOAD_SIZE_MB"):
        Settings(_env_file=None, MAX_UPLOAD_SIZE_MB=26)


def test_cors_configuration_requires_exact_origins_and_positive_jwt_expiry():
    settings = Settings(_env_file=None, CORS_ORIGINS="https://brandguard.example.test")
    assert settings.CORS_ORIGINS == "https://brandguard.example.test"

    with pytest.raises(ValidationError, match="explicit origin allowlist"):
        Settings(_env_file=None, CORS_ORIGINS="*")
    with pytest.raises(ValidationError, match="without paths"):
        Settings(_env_file=None, CORS_ORIGINS="https://brandguard.example.test/app")
    with pytest.raises(ValidationError, match="JWT_EXPIRE_MINUTES"):
        Settings(_env_file=None, JWT_EXPIRE_MINUTES=0)
