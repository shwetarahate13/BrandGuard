from backend.app.config import Settings


def test_postgresql_psycopg_url_uses_installed_psycopg2_driver():
    settings = Settings(DATABASE_URL="postgresql+psycopg://user:pass@db.example.test/brandguard")

    assert settings.database_url_sync == "postgresql+psycopg2://user:pass@db.example.test/brandguard"


def test_postgres_legacy_scheme_normalizes_to_postgresql():
    settings = Settings(DATABASE_URL="postgres://user:pass@db.example.test/brandguard")

    assert settings.database_url_sync == "postgresql://user:pass@db.example.test/brandguard"
