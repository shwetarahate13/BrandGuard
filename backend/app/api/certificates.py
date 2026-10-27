"""Private certificate downloads and content-free public verification."""
from __future__ import annotations

import csv
import io
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.models.models import (
    Approval,
    ApprovalCertificate,
    ApprovalDecision,
    AuditLog,
    Submission,
    SubmissionVersion,
    User,
    UserRole,
)
from backend.app.services.auth import get_current_user
from backend.app.services.certificates import (
    approved_content_hash,
    certificate_access_allowed,
    certificate_metadata,
    check_certificate_access,
    get_or_create_certificate,
    render_certificate_pdf,
)
from backend.app.services.permissions import Action, check_permission
from backend.app.utils.audit import log_action
from backend.app.utils.audit_chain import canonical_timestamp, verify_all_chains, verify_submission_chain


router = APIRouter(tags=["certificates"])
admin_router = APIRouter(prefix="/admin", tags=["admin-integrity"])


class CertificateRevocationRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=5000)

    @field_validator("reason")
    @classmethod
    def reason_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("A reason is required to revoke a certificate")
        return value.strip()


class PublishedCopyRequest(BaseModel):
    text: str = Field(max_length=500000)


def _load_certificate(db: Session, certificate_id: str) -> tuple[ApprovalCertificate, Approval, Submission, SubmissionVersion]:
    certificate = db.query(ApprovalCertificate).filter(ApprovalCertificate.certificate_id == certificate_id).first()
    if not certificate:
        raise HTTPException(status_code=404, detail="Certificate not found")
    approval = db.query(Approval).filter(Approval.id == certificate.approval_id).first()
    submission = db.query(Submission).filter(Submission.id == certificate.submission_id).first()
    version = db.query(SubmissionVersion).filter(SubmissionVersion.id == certificate.version_id).first()
    if not approval or not submission or not version:
        raise HTTPException(status_code=404, detail="Certificate source records are unavailable")
    return certificate, approval, submission, version


def _newer_approved_version(db: Session, certificate: ApprovalCertificate) -> bool:
    return (
        db.query(Approval.id)
        .join(SubmissionVersion, SubmissionVersion.id == Approval.version_id)
        .filter(
            Approval.submission_id == certificate.submission_id,
            Approval.decision == ApprovalDecision.approved,
            SubmissionVersion.version_no > certificate.version_no,
        )
        .first()
        is not None
    )


def _same_timestamp(left, right) -> bool:
    try:
        return canonical_timestamp(left) == canonical_timestamp(right)
    except (TypeError, ValueError):
        return False


def _public_verification(db: Session, certificate_id: str) -> tuple[dict, SubmissionVersion]:
    certificate, approval, submission, version = _load_certificate(db, certificate_id)
    chain = verify_submission_chain(db, submission.id)
    approval_event = (
        db.query(AuditLog)
        .filter(
            AuditLog.submission_id == submission.id,
            AuditLog.entry_hash == certificate.audit_head_hash,
        )
        .first()
    )
    approval_event_valid = bool(
        approval_event
        and approval_event.action in {"approve_submission", "generate_certificate"}
        and (approval_event.meta or {}).get("content_hash") == certificate.content_hash
    )
    approval_event_detail = (approval_event.meta or {}) if approval_event else {}
    if approval_event and approval_event.action == "approve_submission":
        approval_event_valid = approval_event_valid and (
            approval_event.user_id == approval.user_id
            and approval_event_detail.get("note") == approval.note
            and _same_timestamp(approval_event.created_at, approval.created_at)
        )
    elif approval_event and approval_event.action == "generate_certificate":
        approval_event_valid = approval_event_valid and (
            approval_event_detail.get("approval_id") == approval.id
            and approval_event_detail.get("approval_actor") == approval.user_id
            and approval_event_detail.get("approval_note") == approval.note
            and _same_timestamp(approval_event_detail.get("approval_timestamp"), approval.created_at)
        )
    try:
        current_hash = approved_content_hash(submission, version)
    except ValueError:
        current_hash = ""
    content_hash_valid = (
        bool(current_hash)
        and current_hash == certificate.content_hash
        and approval.content_hash == certificate.content_hash
    )
    integrity_valid = (
        chain["valid"]
        and approval_event_valid
        and content_hash_valid
        and approval.decision == ApprovalDecision.approved
        and approval.submission_id == submission.id
        and approval.version_id == version.id
        and certificate.version_no == version.version_no
    )
    revoke_events = []
    if certificate.revocation_audit_head_hash:
        revoke_event = (
            db.query(AuditLog)
            .filter(
                AuditLog.submission_id == submission.id,
                AuditLog.entry_hash == certificate.revocation_audit_head_hash,
            )
            .first()
        )
        if (
            revoke_event
            and revoke_event.action == "revoke_certificate"
            and (revoke_event.meta or {}).get("certificate_id") == certificate.certificate_id
            and (revoke_event.meta or {}).get("reason") == certificate.revocation_reason
        ):
            revoke_events.append(revoke_event)
    any_revoke_event = (
        db.query(AuditLog)
        .filter(
            AuditLog.submission_id == submission.id,
            AuditLog.action == "revoke_certificate",
        )
        .all()
    )
    matching_revoke_events = [event for event in any_revoke_event if (event.meta or {}).get("certificate_id") == certificate.certificate_id]
    revoked_consistently = (
        certificate.status == "revoked"
        and len(revoke_events) == 1
        and len(matching_revoke_events) == 1
        and certificate.revoked_at is not None
        and certificate.revoked_by_id == revoke_events[0].user_id
        and _same_timestamp(certificate.revoked_at, revoke_events[0].created_at)
    )
    revoked_in_chain = bool(matching_revoke_events)
    newer_approved = _newer_approved_version(db, certificate)
    if certificate.status not in {"valid", "superseded", "revoked"}:
        integrity_valid = False
    if (certificate.status == "revoked") != revoked_in_chain or (revoked_in_chain and not revoked_consistently):
        integrity_valid = False
    if certificate.status == "superseded" and not newer_approved:
        integrity_valid = False
    if not integrity_valid:
        status = "tampered"
    elif revoked_consistently:
        status = "revoked"
    elif newer_approved:
        status = "superseded"
    else:
        status = "valid"
    metadata = certificate_metadata(certificate, approval, submission)
    metadata.pop("approval_comment", None)
    metadata.update({
        "status": status,
        "audit_chain_valid": chain["valid"] and approval_event_valid,
        "content_hash_valid": content_hash_valid,
        "revoked_at": certificate.revoked_at.isoformat() if certificate.revoked_at else None,
        "revocation_audit_head_hash": certificate.revocation_audit_head_hash,
    })
    return metadata, version


@router.get("/certificates")
def list_certificates(
    limit: int = Query(200, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    check_permission(current_user, Action.CERTIFICATE_DOWNLOAD)
    query = db.query(ApprovalCertificate).join(Submission, Submission.id == ApprovalCertificate.submission_id)
    if current_user.role == UserRole.creator:
        query = query.filter(Submission.creator_id == current_user.id)
    elif current_user.role in (UserRole.manager, UserRole.reviewer):
        handled_ids = {
            row[0]
            for row in db.query(Approval.submission_id).filter(Approval.user_id == current_user.id).all()
        }
        from backend.app.models.models import AuditLog, Comment
        handled_ids.update(row[0] for row in db.query(Comment.submission_id).filter(Comment.user_id == current_user.id).all())
        handled_ids.update(row[0] for row in db.query(AuditLog.submission_id).filter(AuditLog.user_id == current_user.id).all() if row[0])
        from sqlalchemy import false
        query = query.filter(Submission.id.in_(handled_ids)) if handled_ids else query.filter(false())
    certificates = query.order_by(ApprovalCertificate.created_at.desc()).limit(limit).all()
    results = []
    for certificate in certificates:
        submission = db.query(Submission).filter(Submission.id == certificate.submission_id).first()
        if not submission or not certificate_access_allowed(db, current_user, submission):
            continue
        approval = db.query(Approval).filter(Approval.id == certificate.approval_id).first()
        if approval:
            results.append(certificate_metadata(certificate, approval, submission))
    return results


@router.get("/submissions/{submission_id}/certificate")
def download_submission_certificate(
    submission_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    submission = db.query(Submission).filter(Submission.id == submission_id).first()
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")
    try:
        check_certificate_access(db, current_user, submission)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    approval = (
        db.query(Approval)
        .filter(Approval.submission_id == submission.id, Approval.decision == ApprovalDecision.approved)
        .order_by(Approval.created_at.desc(), Approval.id.desc())
        .first()
    )
    if not approval:
        raise HTTPException(status_code=409, detail="This submission has no approved version to certify")
    try:
        certificate = get_or_create_certificate(
            db,
            approval=approval,
            base_url=str(request.base_url),
            actor_id=current_user.id,
        )
        db.commit()
        pdf = render_certificate_pdf(db, certificate)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    filename = f"brandguard-certificate-{certificate.certificate_id}.pdf"
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"', "Cache-Control": "private, no-store"},
    )


@router.get("/certificates/{certificate_id}/download")
def download_certificate(
    certificate_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    certificate, _approval, submission, _version = _load_certificate(db, certificate_id)
    try:
        check_certificate_access(db, current_user, submission)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    pdf = render_certificate_pdf(db, certificate)
    filename = f"brandguard-certificate-{certificate.certificate_id}.pdf"
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"', "Cache-Control": "private, no-store"},
    )


@router.post("/certificates/{certificate_id}/revoke")
def revoke_certificate(
    certificate_id: str,
    payload: CertificateRevocationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    check_permission(current_user, Action.CERTIFICATE_REVOKE)
    certificate, _approval, submission, _version = _load_certificate(db, certificate_id)
    if certificate.status == "revoked":
        raise HTTPException(status_code=409, detail="Certificate is already revoked")
    reason = payload.reason.strip()
    if not reason:
        raise HTTPException(status_code=422, detail="A reason is required to revoke a certificate")
    event = log_action(
        db,
        current_user.id,
        "revoke_certificate",
        "submission",
        submission.id,
        {"certificate_id": certificate.certificate_id, "reason": reason},
        submission_id=submission.id,
    )
    certificate.status = "revoked"
    certificate.revoked_by_id = current_user.id
    certificate.revoked_at = event.created_at
    certificate.revocation_reason = reason
    certificate.revocation_audit_head_hash = event.entry_hash
    db.commit()
    return {"certificate_id": certificate.certificate_id, "status": certificate.status, "revoked_at": certificate.revoked_at}


@router.get("/certificates/verify/{certificate_id}")
def verify_certificate(
    certificate_id: str,
    db: Session = Depends(get_db),
):
    """Public metadata-only certificate verification; never returns approved content."""
    metadata, _version = _public_verification(db, certificate_id)
    return metadata


@router.post("/certificates/verify/{certificate_id}/copy")
def verify_published_copy(
    certificate_id: str,
    payload: PublishedCopyRequest,
    db: Session = Depends(get_db),
):
    metadata, version = _public_verification(db, certificate_id)
    mime = (version.source_mime_type or "").lower()
    file_based = mime == "application/pdf" or mime.startswith("image/")
    if file_based:
        matches = payload.text == (version.text or "")
        scope = "extracted_text"
        message = "Compared the pasted copy to the text extracted from the approved file; file-byte integrity is checked separately."
    else:
        matches = hashlib_sha256(payload.text.encode("utf-8")) == metadata["content_hash"]
        scope = "approved_text_bytes"
        message = "Compared the pasted copy byte-for-byte with the approved UTF-8 text."
    if metadata["status"] == "tampered":
        matches = False
    return {
        "certificate_id": certificate_id,
        "status": metadata["status"],
        "copy_result": "Match" if matches else "Differs",
        "comparison_scope": scope,
        "message": message,
        "content_hash_valid": metadata["content_hash_valid"],
    }


def hashlib_sha256(payload: bytes) -> str:
    import hashlib
    return hashlib.sha256(payload).hexdigest()


@admin_router.get("/integrity-check")
def admin_integrity_check(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    check_permission(current_user, Action.AUDIT_INTEGRITY_VIEW)
    chains = verify_all_chains(db)
    return {
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "total_chains": len(chains),
        "valid_chains": sum(1 for chain in chains if chain["valid"]),
        "invalid_chains": sum(1 for chain in chains if not chain["valid"]),
        "total_entries": sum(chain["entry_count"] for chain in chains),
        "chains": chains,
    }


@admin_router.get("/integrity-check/export")
def export_integrity_check(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = admin_integrity_check(db, current_user)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["scope", "submission_id", "entry_count", "valid", "head_hash", "errors"])
    for chain in result["chains"]:
        writer.writerow([
            chain["scope_id"],
            chain["submission_id"] or "",
            chain["entry_count"],
            chain["valid"],
            chain["head_hash"] or "",
            "; ".join(chain["errors"]),
        ])
    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="brandguard_integrity_check.csv"'},
    )
