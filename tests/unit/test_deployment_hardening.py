"""Small offline checks for deployment configuration and upload/auth guards."""
from io import BytesIO

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from backend.app.config import Settings
from backend.app.database import Base
from backend.app.models.models import UserRole
from backend.app.services.bootstrap import create_initial_admin
from backend.app.services.auth import (
    clear_login_failures,
    hash_password,
    login_lockout_remaining,
    record_login_failure,
    verify_password,
)
from backend.app.utils.text_extract import sanitize_upload_filename, sniff_upload_mime_type


def test_production_configuration_requires_stable_secret_and_postgres(monkeypatch):
    Settings(
        _env_file=None,
        ENVIRONMENT="production",
        JWT_SECRET="s" * 32,
        DATABASE_URL="postgresql://user:password@db.example.test/brandguard",
    )

    with pytest.raises(ValidationError, match="JWT_SECRET"):
        Settings(
            _env_file=None,
            ENVIRONMENT="production",
            DATABASE_URL="postgresql://user:password@db.example.test/brandguard",
        )
    with pytest.raises(ValidationError, match="PostgreSQL"):
        Settings(
            _env_file=None,
            ENVIRONMENT="production",
            JWT_SECRET="s" * 32,
            DATABASE_URL="sqlite:///./brandguard.db",
        )


def test_login_lockout_tracks_failures_per_ip_and_email():
    email = "lockout-test@example.test"
    client_ip = "192.0.2.145"
    clear_login_failures(email, client_ip)

    for attempt in range(5):
        record_login_failure(email, client_ip, now=100.0 + attempt)

    assert login_lockout_remaining(email, client_ip, now=104.0) == 900
    assert login_lockout_remaining(email, "192.0.2.146", now=104.0) == 0
    assert login_lockout_remaining(email, client_ip, now=1005.0) == 0
    clear_login_failures(email, client_ip)


def test_bcrypt_password_policy_does_not_truncate_long_input():
    with pytest.raises(ValueError, match="12 characters"):
        hash_password("short-pass")
    with pytest.raises(ValueError, match="72 UTF-8 bytes"):
        hash_password("x" * 73)

    password = "LongEnoughPassword2026!"
    assert verify_password(password, hash_password(password))
    assert not verify_password("x" * 73, hash_password(password))


def test_upload_filename_is_sanitized_and_pdf_signature_is_checked():
    assert sanitize_upload_filename("../../unsafe name.pdf") == "unsafe_name.pdf"
    assert sniff_upload_mime_type(b"%PDF-1.7\n%%EOF", "campaign.pdf") == "application/pdf"
    with pytest.raises(ValueError, match="do not match"):
        sniff_upload_mime_type(b"not a PDF", "campaign.pdf")


def test_docx_type_sniff_requires_a_real_word_document():
    archive = BytesIO()
    import zipfile

    with zipfile.ZipFile(archive, "w") as document:
        document.writestr("[Content_Types].xml", "<Types/>")
        document.writestr("word/document.xml", "<document/>")
    assert sniff_upload_mime_type(archive.getvalue(), "guideline.docx").endswith("wordprocessingml.document")


def test_first_admin_bootstrap_hashes_password_and_refuses_existing_users():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        admin = create_initial_admin(
            db,
            "  First Admin  ",
            "  ADMIN@example.test  ",
            "AdminBootstrapPassword2026!",
        )
        assert admin.name == "First Admin"
        assert admin.email == "admin@example.test"
        assert admin.role == UserRole.admin
        assert admin.password_hash != "AdminBootstrapPassword2026!"
        assert verify_password("AdminBootstrapPassword2026!", admin.password_hash)
        with pytest.raises(ValueError, match="database has no users"):
            create_initial_admin(db, "Second Admin", "second@example.test", "AnotherBootstrapPassword2026!")
    engine.dispose()
