"""Integration coverage for certificate integrity, privacy, and role scope."""
from __future__ import annotations

import hashlib
import io
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
import pdfplumber
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.database import Base, get_db
from backend.app.main import app
from backend.app.models.models import (
    Approval,
    ApprovalCertificate,
    ApprovalDecision,
    Comment,
    Decision,
    DecisionAction,
    Finding,
    FindingCategory,
    FindingConfidence,
    FindingSeverity,
    FindingStatus,
    AuditChainHead,
    AuditLog,
    Submission,
    SubmissionStatus,
    SubmissionVersion,
    User,
    UserRole,
)
from backend.app.services.auth import get_current_user
from backend.app.services.certificates import approved_content_hash, create_certificate, render_certificate_pdf
from backend.app.utils.audit import log_action
from backend.app.utils.audit_chain import verify_all_chains, verify_submission_chain


@pytest.fixture
def certificate_app():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    with engine.begin() as connection:
        connection.exec_driver_sql("""
            CREATE TRIGGER audit_log_reject_update BEFORE UPDATE ON audit_log
            BEGIN SELECT RAISE(ABORT, 'audit_log is append-only'); END
        """)
        connection.exec_driver_sql("""
            CREATE TRIGGER audit_log_reject_delete BEFORE DELETE ON audit_log
            BEGIN SELECT RAISE(ABORT, 'audit_log is append-only'); END
        """)
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
    users = {
        "creator": User(id="cert-creator", name="Certificate Creator", email="cert-creator@example.test", password_hash="x", role=UserRole.creator, is_active=True),
        "manager": User(id="cert-manager", name="Certificate Manager", email="cert-manager@example.test", password_hash="x", role=UserRole.manager, is_active=True),
        "reviewer": User(id="cert-reviewer", name="Certificate Reviewer", email="cert-reviewer@example.test", password_hash="x", role=UserRole.reviewer, is_active=True),
        "unhandled_reviewer": User(id="cert-unhandled-reviewer", name="Unassigned Reviewer", email="cert-unhandled-reviewer@example.test", password_hash="x", role=UserRole.reviewer, is_active=True),
        "other_creator": User(id="cert-other-creator", name="Other Creator", email="cert-other@example.test", password_hash="x", role=UserRole.creator, is_active=True),
        "admin": User(id="cert-admin", name="Certificate Admin", email="cert-admin@example.test", password_hash="x", role=UserRole.admin, is_active=True),
    }
    submission_id = "certificate-submission"
    version_id = "certificate-version"
    approved_text = "Approved campaign copy contains a private approved phrase."
    with factory.begin() as db:
        db.add_all(users.values())
        submission = Submission(
            id=submission_id,
            creator_id=users["creator"].id,
            title="Certificate privacy campaign",
            status=SubmissionStatus.approved,
        )
        version = SubmissionVersion(
            id=version_id,
            submission_id=submission_id,
            version_no=1,
            text=approved_text,
            created_by=users["creator"].id,
        )
        db.add_all([submission, version])
        finding = Finding(
            id="certificate-finding",
            submission_id=submission_id,
            version_id=version_id,
            category=FindingCategory.terminology,
            issue="Avoid the informal term in the campaign.",
            severity=FindingSeverity.major,
            confidence=FindingConfidence.high,
            status=FindingStatus.accepted,
            needs_human=False,
        )
        db.add(finding)
        db.add(Decision(
            id="certificate-decision",
            finding_id=finding.id,
            user_id=users["creator"].id,
            action=DecisionAction.edit,
            original_span="cheap",
            human_edited_text="fairly priced",
            reason="Keeps the price point while following our brand voice.",
        ))
        db.add(Comment(
            id="certificate-reviewer-comment",
            submission_id=submission_id,
            finding_id=finding.id,
            user_id=users["reviewer"].id,
            body="[Compliance Confirmed]: The evidence does not support the high-risk claim.",
        ))
        approval = Approval(
            id="certificate-approval",
            submission_id=submission_id,
            version_id=version_id,
            user_id=users["manager"].id,
            decision=ApprovalDecision.approved,
            note="Approved after review.",
            content_hash=hashlib.sha256(approved_text.encode("utf-8")).hexdigest(),
        )
        db.add(approval)
        db.flush()
        event = log_action(
            db,
            users["manager"].id,
            "approve_submission",
            "submission",
            submission_id,
            {"content_hash": approval.content_hash, "note": approval.note},
            submission_id=submission_id,
        )
        approval.created_at = event.created_at
        cert = create_certificate(
            db,
            approval=approval,
            submission=submission,
            version=version,
            audit_head_hash=event.entry_hash,
            ai_engine="mock/offline",
            ai_mode="offline mock",
            base_url="http://testserver",
        )
        db.flush()
        certificate_id = cert.certificate_id

    selected_user = {"value": users["manager"]}

    def override_db():
        db = factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = lambda: selected_user["value"]
    client = TestClient(app)
    try:
        yield {
            "client": client,
            "factory": factory,
            "engine": engine,
            "users": users,
            "selected_user": selected_user,
            "submission_id": submission_id,
            "version_id": version_id,
            "certificate_id": certificate_id,
            "approved_text": approved_text,
        }
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_user, None)
        engine.dispose()


def test_audit_chain_verifies_and_detects_a_changed_entry(certificate_app):
    env = certificate_app
    with env["factory"]() as db:
        initial = verify_submission_chain(db, env["submission_id"])
        assert initial["valid"] is True
        assert initial["entry_count"] == 1
        log_id = db.query(AuditLog.id).filter(AuditLog.submission_id == env["submission_id"]).scalar()
        db.execute(text("DROP TRIGGER audit_log_reject_update"))
        db.execute(text("UPDATE audit_log SET action='tampered_approval' WHERE id=:id"), {"id": log_id})
        db.commit()
        checked = verify_submission_chain(db, env["submission_id"])
        assert checked["valid"] is False
        assert any("hash mismatch" in error for error in checked["errors"])
    public = env["client"].get(f"/api/certificates/verify/{env['certificate_id']}")
    assert public.status_code == 200
    assert public.json()["status"] == "tampered"


def test_sqlite_audit_triggers_reject_update_and_delete(certificate_app):
    env = certificate_app
    with env["factory"]() as db:
        log_id = db.query(AuditLog.id).filter(AuditLog.submission_id == env["submission_id"]).scalar()
        with pytest.raises(IntegrityError, match="audit_log is append-only"):
            db.execute(text("UPDATE audit_log SET action='changed' WHERE id=:id"), {"id": log_id})
        db.rollback()
        with pytest.raises(IntegrityError, match="audit_log is append-only"):
            db.execute(text("DELETE FROM audit_log WHERE id=:id"), {"id": log_id})
        db.rollback()


def test_certificate_pdf_and_public_verify_do_not_expose_content(certificate_app):
    env = certificate_app
    with env["factory"]() as db:
        certificate = db.get(ApprovalCertificate, env["certificate_id"])
        pdf = render_certificate_pdf(db, certificate)
        assert pdf.startswith(b"%PDF")
        assert env["approved_text"].encode() not in pdf
        with pdfplumber.open(io.BytesIO(pdf)) as document:
            pdf_text = "\n".join(page.extract_text() or "" for page in document.pages)
        assert certificate.certificate_id in pdf_text
        assert "Certificate Manager (manager)" in pdf_text
        assert "Approved after review." in pdf_text
        assert "Terminology" in pdf_text
        assert "edited by Certificate Creator" in pdf_text
        assert "Keeps the price point" in pdf_text
        assert "escalated confirmed by Certificate Reviewer" in pdf_text
        assert "mock/offline" in pdf_text and "offline mock" in pdf_text
        assert verify_all_chains(db)[0]["valid"] is True
    response = env["client"].get(f"/api/certificates/verify/{env['certificate_id']}")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "valid"
    assert body["content_hash_valid"] is True
    assert env["approved_text"] not in response.text
    assert "approval_comment" not in body
    matching = env["client"].post(
        f"/api/certificates/verify/{env['certificate_id']}/copy",
        json={"text": env["approved_text"]},
    )
    differing = env["client"].post(
        f"/api/certificates/verify/{env['certificate_id']}/copy",
        json={"text": "A different published version."},
    )
    assert matching.json()["copy_result"] == "Match"
    assert differing.json()["copy_result"] == "Differs"
    assert env["approved_text"] not in matching.text


def test_content_hash_mismatch_and_missing_chain_head_are_tampered(certificate_app):
    env = certificate_app
    client = env["client"]
    with env["factory"]() as db:
        version = db.get(SubmissionVersion, env["version_id"])
        version.text += " changed"
        db.commit()
    assert client.get(f"/api/certificates/verify/{env['certificate_id']}").json()["status"] == "tampered"

    with env["factory"]() as db:
        db.delete(db.get(AuditChainHead, env["submission_id"]))
        db.commit()
    checked = client.get(f"/api/certificates/verify/{env['certificate_id']}").json()
    assert checked["status"] == "tampered"
    assert checked["audit_chain_valid"] is False


@pytest.mark.parametrize("mime", ["application/pdf", "image/png"])
def test_pdf_and_image_hashes_use_exact_original_bytes(mime):
    original = b"\x00\xffexact source-file bytes\n"
    version = SimpleNamespace(source_mime_type=mime, source_file=original, text="extracted text is not the file hash")
    digest = approved_content_hash(SimpleNamespace(), version)
    assert digest == hashlib.sha256(original).hexdigest()
    assert digest != hashlib.sha256(version.text.encode("utf-8")).hexdigest()


def test_certificate_permissions_follow_creator_handling_and_admin_scope(certificate_app):
    env = certificate_app
    client = env["client"]
    certificate_path = f"/api/certificates/{env['certificate_id']}/download"
    env["selected_user"]["value"] = env["users"]["creator"]
    assert client.get(certificate_path).status_code == 200
    env["selected_user"]["value"] = env["users"]["manager"]
    assert client.get(certificate_path).status_code == 200
    env["selected_user"]["value"] = env["users"]["other_creator"]
    assert client.get(certificate_path).status_code == 403
    env["selected_user"]["value"] = env["users"]["unhandled_reviewer"]
    assert client.get(certificate_path).status_code == 403
    env["selected_user"]["value"] = env["users"]["reviewer"]
    assert client.get(certificate_path).status_code == 200
    env["selected_user"]["value"] = env["users"]["admin"]
    assert client.get(certificate_path).status_code == 200


def test_manager_admin_revoke_requires_reason_and_is_chained(certificate_app):
    env = certificate_app
    client = env["client"]
    env["selected_user"]["value"] = env["users"]["manager"]
    endpoint = f"/api/certificates/{env['certificate_id']}/revoke"
    assert client.post(endpoint, json={"reason": "   "}).status_code == 422
    revoked = client.post(endpoint, json={"reason": "The approved product claim was withdrawn."})
    assert revoked.status_code == 200, revoked.text
    public = client.get(f"/api/certificates/verify/{env['certificate_id']}")
    assert public.json()["status"] == "revoked"
    assert public.json()["audit_chain_valid"] is True
    env["selected_user"]["value"] = env["users"]["admin"]
    assert client.post(endpoint, json={"reason": "duplicate revocation attempt"}).status_code == 409
    env["selected_user"]["value"] = env["users"]["reviewer"]
    assert client.post(endpoint, json={"reason": "not allowed"}).status_code == 403


def test_later_approved_version_marks_older_certificate_superseded(certificate_app):
    env = certificate_app
    with env["factory"]() as db:
        submission = db.get(Submission, env["submission_id"])
        version = SubmissionVersion(
            id="certificate-version-2",
            submission_id=submission.id,
            version_no=2,
            text="A newer approved campaign copy.",
            created_by=env["users"]["creator"].id,
        )
        db.add(version)
        approval = Approval(
            id="certificate-approval-2",
            submission_id=submission.id,
            version_id=version.id,
            user_id=env["users"]["manager"].id,
            decision=ApprovalDecision.approved,
            content_hash=hashlib.sha256(version.text.encode("utf-8")).hexdigest(),
        )
        db.add(approval)
        db.flush()
        event = log_action(
            db,
            env["users"]["manager"].id,
            "approve_submission",
            "submission",
            submission.id,
            {"content_hash": approval.content_hash, "note": approval.note},
            submission_id=submission.id,
        )
        approval.created_at = event.created_at
        create_certificate(
            db,
            approval=approval,
            submission=submission,
            version=version,
            audit_head_hash=event.entry_hash,
            ai_engine="mock/offline",
            ai_mode="offline mock",
            base_url="http://testserver",
        )
        db.commit()
    response = env["client"].get(f"/api/certificates/verify/{env['certificate_id']}")
    assert response.status_code == 200
    assert response.json()["status"] == "superseded"


def test_approved_submission_certificate_can_be_generated_on_demand(certificate_app):
    env = certificate_app
    with env["factory"]() as db:
        db.delete(db.get(ApprovalCertificate, env["certificate_id"]))
        db.commit()
    env["selected_user"]["value"] = env["users"]["creator"]
    response = env["client"].get(f"/api/submissions/{env['submission_id']}/certificate")
    assert response.status_code == 200, response.text
    assert response.headers["content-type"] == "application/pdf"
    assert response.content.startswith(b"%PDF")
    with env["factory"]() as db:
        generated = db.query(AuditLog).filter(AuditLog.action == "generate_certificate").first()
        assert generated is not None
        assert verify_submission_chain(db, env["submission_id"])["valid"] is True


def test_admin_integrity_page_api_is_admin_only(certificate_app):
    env = certificate_app
    client = env["client"]
    env["selected_user"]["value"] = env["users"]["admin"]
    response = client.get("/api/admin/integrity-check")
    assert response.status_code == 200
    assert response.json()["invalid_chains"] == 0
    exported = client.get("/api/admin/integrity-check/export")
    assert exported.status_code == 200
    assert "text/csv" in exported.headers["content-type"]
    env["selected_user"]["value"] = env["users"]["manager"]
    assert client.get("/api/admin/integrity-check").status_code == 403
