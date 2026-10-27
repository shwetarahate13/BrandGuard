"""Approval certificate creation, PDF rendering, and access policy."""
from __future__ import annotations

import hashlib
import uuid
from collections import Counter
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from backend.app.models.models import (
    Approval,
    ApprovalCertificate,
    ApprovalDecision,
    AuditLog,
    Comment,
    Finding,
    Submission,
    SubmissionVersion,
    User,
    UserRole,
    utcnow,
)
from backend.app.services.permissions import Action, check_permission
from backend.app.utils.audit_chain import canonical_timestamp


def approved_content_hash(submission: Submission, version: SubmissionVersion) -> str:
    """Hash approved text, or source file bytes for PDF/image approvals."""
    mime = (version.source_mime_type or "").lower()
    if mime == "application/pdf" or mime.startswith("image/"):
        if not version.source_file:
            raise ValueError("The approved PDF or image is missing its original file bytes")
        payload = bytes(version.source_file)
    else:
        payload = (version.text or "").encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def certificate_verification_url(base_url: str, certificate_id: str) -> str:
    return f"{str(base_url).rstrip('/')}/verify?certificate_id={certificate_id}"


def create_certificate(
    db: Session,
    *,
    approval: Approval,
    submission: Submission,
    version: SubmissionVersion,
    audit_head_hash: str,
    ai_engine: str,
    ai_mode: str,
    base_url: str,
) -> ApprovalCertificate:
    existing = db.query(ApprovalCertificate).filter(ApprovalCertificate.approval_id == approval.id).first()
    if existing:
        return existing
    if approval.decision != ApprovalDecision.approved:
        raise ValueError("Only an approved decision can receive a certificate")
    digest = approved_content_hash(submission, version)
    approval.content_hash = digest
    certificate_id = f"BG-{uuid.uuid4().hex[:20].upper()}"
    certificate = ApprovalCertificate(
        certificate_id=certificate_id,
        approval_id=approval.id,
        submission_id=submission.id,
        version_id=version.id,
        version_no=version.version_no,
        content_hash=digest,
        audit_head_hash=audit_head_hash,
        ai_engine=ai_engine,
        ai_mode=ai_mode,
        verification_url=certificate_verification_url(base_url, certificate_id),
        status="valid",
        created_at=utcnow(),
    )
    newer_approved = (
        db.query(Approval.id)
        .join(SubmissionVersion, SubmissionVersion.id == Approval.version_id)
        .filter(
            Approval.submission_id == submission.id,
            Approval.decision == ApprovalDecision.approved,
            SubmissionVersion.version_no > version.version_no,
        )
        .first()
    )
    if newer_approved:
        certificate.status = "superseded"
    db.add(certificate)
    db.flush()
    db.query(ApprovalCertificate).filter(
        ApprovalCertificate.submission_id == submission.id,
        ApprovalCertificate.version_no < version.version_no,
        ApprovalCertificate.status == "valid",
    ).update({ApprovalCertificate.status: "superseded"}, synchronize_session=False)
    return certificate


def get_or_create_certificate(
    db: Session,
    *,
    approval: Approval,
    base_url: str,
    actor_id: str,
) -> ApprovalCertificate:
    existing = db.query(ApprovalCertificate).filter(ApprovalCertificate.approval_id == approval.id).first()
    if existing:
        return existing
    submission = db.query(Submission).filter(Submission.id == approval.submission_id).first()
    version = db.query(SubmissionVersion).filter(SubmissionVersion.id == approval.version_id).first()
    if not submission or not version:
        raise ValueError("The approved submission version is unavailable")
    digest = approved_content_hash(submission, version)
    from backend.app.utils.audit import log_action

    generation_event = log_action(
        db,
        actor_id,
        "generate_certificate",
        "submission",
        submission.id,
        {
            "content_hash": digest,
            "version_no": version.version_no,
            "approval_id": approval.id,
            "approval_actor": approval.user_id,
            "approval_timestamp": canonical_timestamp(approval.created_at) if approval.created_at else None,
            "approval_note": approval.note,
        },
        submission_id=submission.id,
    )
    from backend.app.llm.client import get_llm_mode

    engine = get_llm_mode()
    mode = "offline mock" if engine == "mock/offline" else "live provider"
    return create_certificate(
        db,
        approval=approval,
        submission=submission,
        version=version,
        audit_head_hash=generation_event.entry_hash,
        ai_engine=engine,
        ai_mode=mode,
        base_url=base_url,
    )


def certificate_access_allowed(db: Session, user: User, submission: Submission) -> bool:
    """Apply the requested creator/handled-reviewer/admin certificate scope."""
    if user.role == UserRole.admin:
        return True
    if user.role == UserRole.creator:
        return submission.creator_id == user.id
    if user.role not in (UserRole.manager, UserRole.reviewer):
        return False
    handled_approval = db.query(Approval.id).filter(
        Approval.submission_id == submission.id,
        Approval.user_id == user.id,
    ).first()
    handled_comment = db.query(Comment.id).filter(
        Comment.submission_id == submission.id,
        Comment.user_id == user.id,
    ).first()
    handled_audit = db.query(AuditLog.id).filter(
        AuditLog.submission_id == submission.id,
        AuditLog.user_id == user.id,
    ).first()
    return bool(handled_approval or handled_comment or handled_audit)


def check_certificate_access(db: Session, user: User, submission: Submission) -> None:
    check_permission(user, Action.CERTIFICATE_DOWNLOAD)
    if not certificate_access_allowed(db, user, submission):
        raise PermissionError("Certificate access is limited to your own or handled submissions")


def _pdf_text(value: Any) -> str:
    text = str(value or "")
    transliterate = str.maketrans({
        "—": "-",
        "–": "-",
        "’": "'",
        "‘": "'",
        "“": '"',
        "”": '"',
        "…": "...",
    })
    return text.translate(transliterate).encode("latin-1", "replace").decode("latin-1")


def _date(value: datetime | None) -> str:
    if not value:
        return "Not recorded"
    normalized = value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)
    return normalized.isoformat(timespec="seconds")


def render_certificate_pdf(db: Session, certificate: ApprovalCertificate) -> bytes:
    """Render a compact text-only certificate PDF with fpdf2."""
    from fpdf import FPDF

    submission = db.query(Submission).filter(Submission.id == certificate.submission_id).first()
    version = db.query(SubmissionVersion).filter(SubmissionVersion.id == certificate.version_id).first()
    approval = db.query(Approval).filter(Approval.id == certificate.approval_id).first()
    if not submission or not version or not approval:
        raise ValueError("Certificate source records are unavailable")

    pdf = FPDF(format="A4")
    pdf.set_auto_page_break(auto=True, margin=16)
    pdf.set_title(_pdf_text(f"BrandGuard Certificate {certificate.certificate_id}"))
    pdf.set_author("BrandGuard")
    pdf.add_page()

    def section(title: str) -> None:
        pdf.ln(2)
        pdf.set_font("Helvetica", "B", 12)
        pdf.set_x(pdf.l_margin)
        pdf.multi_cell(0, 7, _pdf_text(title))
        pdf.set_draw_color(180, 180, 180)
        y = pdf.get_y()
        pdf.line(10, y, 200, y)
        pdf.ln(2)
        pdf.set_font("Helvetica", size=9)

    def line(label: str, value: Any) -> None:
        pdf.set_x(pdf.l_margin)
        pdf.set_font("Helvetica", "B", 9)
        pdf.write(5, _pdf_text(f"{label}: "))
        pdf.set_font("Helvetica", size=9)
        pdf.multi_cell(0, 5, _pdf_text(value))

    pdf.set_font("Helvetica", "B", 20)
    pdf.set_text_color(45, 64, 50)
    pdf.set_x(pdf.l_margin)
    pdf.multi_cell(0, 11, "BrandGuard Approval Certificate")
    pdf.set_text_color(30, 30, 30)
    pdf.set_font("Helvetica", size=9)
    pdf.set_x(pdf.l_margin)
    pdf.multi_cell(0, 5, "Human-approved brand copy with a verifiable audit trail.")

    section("Certificate")
    line("Certificate ID", certificate.certificate_id)
    line("Title", submission.title)
    line("Approved version", f"v{certificate.version_no}")
    line("Status", certificate.status.title())
    line("Approved at", _date(approval.created_at))
    line("SHA-256 content hash", certificate.content_hash)
    line("AI engine", certificate.ai_engine)
    line("AI mode", certificate.ai_mode)
    line("Audit chain head hash", certificate.audit_head_hash)
    line("Verification URL", certificate.verification_url)
    if certificate.status == "revoked":
        revoker = certificate.revoked_by
        line("Revoked at", _date(certificate.revoked_at))
        line("Revoked by", f"{revoker.name} ({revoker.role.value})" if revoker else "Unknown")
        line("Revocation reason", certificate.revocation_reason or "No reason recorded")

    approvals = (
        db.query(Approval)
        .filter(
            Approval.submission_id == submission.id,
            Approval.version_id == version.id,
            Approval.decision == ApprovalDecision.approved,
        )
        .order_by(Approval.created_at.asc())
        .all()
    ) or [approval]
    section("Approvers")
    for signed in approvals:
        approver = signed.user
        line("Approver", f"{approver.name if approver else 'Unknown'} ({approver.role.value if approver else 'unknown role'})")
        line("Signed at", _date(signed.created_at))
        line("Comment", signed.note or "No comment recorded")

    findings = (
        db.query(Finding)
        .filter(Finding.submission_id == submission.id, Finding.version_id == version.id)
        .order_by(Finding.category.asc(), Finding.created_at.asc(), Finding.id.asc())
        .all()
    )
    category_counts = Counter(finding.category.value for finding in findings)
    category_labels = {
        "tone": "Tone",
        "terminology": "Terminology",
        "messaging": "Messaging",
        "factual_accuracy": "Factual accuracy",
        "unsupported_claim": "Unsupported claim",
        "accessibility": "Accessibility",
    }
    section("Findings summary by category")
    if not findings:
        pdf.set_x(pdf.l_margin)
        pdf.multi_cell(0, 5, "No findings were recorded for the approved version.")
    for category, count in sorted(category_counts.items()):
        line(category_labels.get(category, category), f"{count} finding(s)")

    section("Finding resolutions and reviewer justifications")
    for finding in findings:
        pdf.set_font("Helvetica", "B", 9)
        pdf.set_x(pdf.l_margin)
        pdf.multi_cell(0, 5, _pdf_text(f"[{category_labels.get(finding.category.value, finding.category.value)}] {finding.issue}"))
        decisions = sorted(finding.decisions, key=lambda decision: (decision.created_at or datetime.min, decision.id))
        comments = (
            db.query(Comment)
            .filter(Comment.finding_id == finding.id)
            .order_by(Comment.created_at.asc(), Comment.id.asc())
            .all()
        )
        resolutions = []
        for decision in decisions:
            action = {"accept": "accepted", "edit": "edited", "dispute": "disputed"}.get(decision.action.value, decision.action.value)
            actor = decision.user
            detail = f"{action} by {actor.name if actor else 'Unknown'} on {_date(decision.created_at)}"
            if decision.reason:
                detail += f" — {decision.reason}"
            resolutions.append(detail)
        for comment in comments:
            body = comment.body or ""
            if body.startswith("[Compliance Confirmed]:"):
                actor = comment.user
                resolutions.append(f"escalated confirmed by {actor.name if actor else 'Reviewer'}: {body.split(':', 1)[1].strip()}")
            elif body.startswith("[Compliance Dismissed]:"):
                actor = comment.user
                resolutions.append(f"escalated dismissed by {actor.name if actor else 'Reviewer'}: {body.split(':', 1)[1].strip()}")
        if not resolutions:
            resolutions.append(f"Current finding status: {finding.status.value}")
        pdf.set_font("Helvetica", size=8)
        for resolution in resolutions:
            pdf.set_x(pdf.l_margin)
            pdf.multi_cell(0, 4.5, _pdf_text(f"- {resolution}"))
        pdf.ln(1)

    output = pdf.output()
    return bytes(output)


def certificate_metadata(certificate: ApprovalCertificate, approval: Approval, submission: Submission) -> dict[str, Any]:
    approver = approval.user
    return {
        "certificate_id": certificate.certificate_id,
        "title": submission.title,
        "status": certificate.status,
        "approved_version": certificate.version_no,
        "content_hash": certificate.content_hash,
        "approved_at": approval.created_at.isoformat() if approval.created_at else None,
        "approver": {
            "name": approver.name if approver else "Unknown",
            "role": approver.role.value if approver else "unknown",
        },
        "approval_comment": approval.note,
        "ai_engine": certificate.ai_engine,
        "ai_mode": certificate.ai_mode,
        "audit_chain_head_hash": certificate.audit_head_hash,
        "verification_url": certificate.verification_url,
    }
