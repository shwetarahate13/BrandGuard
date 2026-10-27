import pytest
from pydantic import ValidationError

from backend.app.config import Settings


def test_postgresql_psycopg_url_uses_installed_psycopg2_driver():
    settings = Settings(DATABASE_URL="postgresql+psycopg://user:pass@db.example.test/brandguard")

    assert settings.database_url_sync == "postgresql+psycopg2://user:pass@db.example.test/brandguard"


def test_postgres_legacy_scheme_normalizes_to_postgresql():
    settings = Settings(DATABASE_URL="postgres://user:pass@db.example.test/brandguard")

    assert settings.database_url_sync == "postgresql://user:pass@db.example.test/brandguard"


def test_lite_mode_always_disables_image_review():
    settings = Settings(_env_file=None, BRANDGUARD_LITE=True, IMAGE_REVIEW_ENABLED=True)

    assert settings.BRANDGUARD_LITE is True
    assert settings.IMAGE_REVIEW_ENABLED is False


def test_cors_configuration_requires_exact_origins_and_positive_jwt_expiry():
    settings = Settings(_env_file=None, CORS_ORIGINS="https://brandguard.example.test")
    assert settings.CORS_ORIGINS == "https://brandguard.example.test"

    with pytest.raises(ValidationError, match="explicit origin allowlist"):
        Settings(_env_file=None, CORS_ORIGINS="*")
    with pytest.raises(ValidationError, match="without paths"):
        Settings(_env_file=None, CORS_ORIGINS="https://brandguard.example.test/app")
    with pytest.raises(ValidationError, match="JWT_EXPIRE_MINUTES"):
        Settings(_env_file=None, JWT_EXPIRE_MINUTES=0)
