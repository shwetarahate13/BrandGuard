"""Workflow API routes: comments, request review, approvals, rejections, and audit history."""
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError, OperationalError

from backend.app.database import get_db
from backend.app.models.models import (
    User, UserRole, Submission, SubmissionVersion, SubmissionStatus,
    Comment, Approval, ApprovalCertificate, ApprovalDecision, AuditLog, ReviewerSignoff, Finding, Decision, FindingStatus, Notification, gen_id,
)
from backend.app.llm.client import get_llm_mode
from backend.app.schemas.schemas import (
    CommentCreate, CommentResponse, ApprovalCreate, ApprovalResponse,
    AuditLogResponse, ReviewerSignoffRequest, ReviewerFollowupCreate
)
from backend.app.services.auth import get_current_user
from backend.app.services.permissions import (
    Action,
    check_permission,
    check_approval_allowed,
    check_can_view_submission,
    has_escalated_risk,
    finding_requires_reviewer_review,
)
from backend.app.utils.audit import log_action
from backend.app.services.notifications import add_notification
from backend.app.services.idempotency import find_idempotency_record, request_fingerprint, remember_request
from backend.app.services.certificates import approved_content_hash, create_certificate, render_certificate_pdf

router = APIRouter(prefix="/submissions", tags=["workflow"])


@router.post("/{submission_id}/reviewer-followups")
def create_reviewer_followup(
    submission_id: str,
    payload: ReviewerFollowupCreate,
    idempotency_key: str = Header(..., alias="Idempotency-Key", min_length=8, max_length=128),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    check_permission(current_user, Action.FINDINGS_ESCALATE_REVIEW)
    submission = db.query(Submission).filter_by(id=submission_id).first()
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")
    check_can_view_submission(current_user, submission)
    if current_user.role != UserRole.reviewer or submission.assigned_to_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the assigned reviewer can create compliance follow-up tasks")
    if submission.status != SubmissionStatus.in_review:
        raise HTTPException(status_code=409, detail="Reviewer follow-up tasks require a submission that is in review")

    finding = db.query(Finding).filter_by(id=payload.finding_id, submission_id=submission.id).first()
    if not finding:
        raise HTTPException(status_code=404, detail="Finding not found")
    if finding.status != FindingStatus.open:
        raise HTTPException(status_code=409, detail="Follow-up tasks can only be created for open findings")
    if not finding_requires_reviewer_review(finding):
        raise HTTPException(status_code=400, detail="Follow-up tasks require an escalated finding")

    fingerprint = request_fingerprint({
        "submission_id": submission.id,
        "finding_id": finding.id,
        "action": payload.action,
        "message": payload.message,
    })
    scope = f"reviewer-followup:{submission.id}"
    existing = find_idempotency_record(db, current_user.id, scope, idempotency_key, fingerprint)
    if existing:
        return {"status": "already_created", "action": payload.action, "finding_id": finding.id}

    if payload.action == "request_evidence":
        recipients = [submission.creator_id]
        title = "Evidence requested by compliance reviewer"
        kind = "evidence_requested"
        task_label = "Evidence requested"
    else:
        recipients = [
            user.id for user in db.query(User).filter_by(role=UserRole.admin, is_active=True).all()
        ]
        if not recipients:
            raise HTTPException(status_code=409, detail="No active admin is available to review a fact proposal")
        title = "Approved fact proposal needs review"
        kind = "fact_proposed"
        task_label = "Approved fact proposal"

    comment = Comment(
        id=gen_id(),
        submission_id=submission.id,
        finding_id=finding.id,
        user_id=current_user.id,
        body=f"{task_label}: {payload.message}",
    )
    db.add(comment)
    for recipient_id in recipients:
        db.add(Notification(
            user_id=recipient_id,
            submission_id=submission.id,
            kind=kind,
            title=title,
            message=f"{payload.message} Finding: {finding.issue}",
        ))
    remember_request(db, current_user.id, scope, idempotency_key, fingerprint, comment.id)
    log_action(db, current_user.id, f"reviewer_{payload.action}", "finding", finding.id)
    try:
        db.commit()
    except (IntegrityError, OperationalError) as exc:
        db.rollback()
        existing = find_idempotency_record(db, current_user.id, scope, idempotency_key, fingerprint)
        if existing:
            return {"status": "already_created", "action": payload.action, "finding_id": finding.id}
        raise HTTPException(status_code=409, detail="The reviewer task may have been saved at the same time. Refresh before retrying.") from exc
    return {"status": "created", "action": payload.action, "finding_id": finding.id}


@router.post("/{submission_id}/reviewer-signoff")
def reviewer_signoff(submission_id: str, payload: ReviewerSignoffRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Record compliance sign-off for a high-risk version; this never gives final approval."""
    check_permission(current_user, Action.FINDINGS_ESCALATE_REVIEW)
    submission = db.query(Submission).filter(Submission.id == submission_id).first()
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")
    check_can_view_submission(current_user, submission)
    if current_user.role != UserRole.reviewer or submission.assigned_to_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the assigned reviewer can sign off")
    if submission.status != SubmissionStatus.in_review or not has_escalated_risk(submission):
        raise HTTPException(status_code=409, detail="Reviewer sign-off applies to high-risk submissions in review")
    required = {"claims_verified", "facts_current", "accessibility_reviewed", "legal_wording_reviewed"}
    if set(payload.checklist) != required or not all(payload.checklist.values()):
        raise HTTPException(status_code=400, detail="Complete every required reviewer checklist item")
    latest = db.query(SubmissionVersion).filter_by(submission_id=submission.id).order_by(SubmissionVersion.version_no.desc()).first()
    if not latest:
        raise HTTPException(status_code=409, detail="There is no version available to sign off")
    pending = db.query(Finding).filter_by(submission_id=submission.id, version_id=latest.id).all()
    for finding in pending:
        if finding_requires_reviewer_review(finding):
            reviewed = db.query(Decision).filter_by(finding_id=finding.id, user_id=current_user.id).first()
            if not reviewed:
                raise HTTPException(status_code=409, detail="Review and confirm or dismiss each escalated finding before sign-off")
    existing = db.query(ReviewerSignoff).filter_by(submission_id=submission.id, version_id=latest.id).first()
    if existing:
        raise HTTPException(status_code=409, detail="This version already has reviewer sign-off")
    record = ReviewerSignoff(submission_id=submission.id, version_id=latest.id, reviewer_id=current_user.id,
        checklist=payload.checklist, evidence_notes=payload.evidence_notes.strip(), justification=payload.justification.strip())
    db.add(record)
    log_action(db, current_user.id, "reviewer_signoff", "submission", submission.id,
        {"version_id": latest.id, "checklist": payload.checklist, "evidence_notes": payload.evidence_notes.strip()}, submission_id=submission.id)
    db.commit()
    return {"status": "ok", "reviewer_signoff_id": record.id, "version_id": latest.id}


@router.get("/{submission_id}/reviewer-signoff")
def get_reviewer_signoff(submission_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    submission = db.query(Submission).filter_by(id=submission_id).first()
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")
    check_can_view_submission(current_user, submission)
    latest = db.query(SubmissionVersion).filter_by(submission_id=submission.id).order_by(SubmissionVersion.version_no.desc()).first()
    signoff = db.query(ReviewerSignoff).filter_by(submission_id=submission.id, version_id=latest.id).first() if latest else None
    return {"signed_off": bool(signoff), "reviewer_id": signoff.reviewer_id if signoff else None,
        "created_at": signoff.created_at.isoformat() if signoff else None,
        "checklist": signoff.checklist if signoff else {}, "evidence_notes": signoff.evidence_notes if signoff else ""}


@router.get("/reviewer-metrics")
def reviewer_metrics(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    check_permission(current_user, Action.FINDINGS_ESCALATE_REVIEW)
    from backend.app.models.models import DecisionAction
    decisions = db.query(Decision).filter(Decision.user_id == current_user.id,
        Decision.action.in_([DecisionAction.accept, DecisionAction.dispute])).all()
    confirmed = sum(1 for item in decisions if item.action == DecisionAction.accept)
    dismissed = sum(1 for item in decisions if item.action == DecisionAction.dispute)
    reviewed_finding_ids = {item.finding_id for item in decisions}
    overturned = 0
    if reviewed_finding_ids:
        later_decisions = db.query(Decision).filter(Decision.finding_id.in_(reviewed_finding_ids), Decision.user_id != current_user.id).all()
        reviewer_times = {}
        for item in decisions:
            reviewer_times[item.finding_id] = max(reviewer_times.get(item.finding_id, item.created_at), item.created_at)
        overturned = sum(1 for item in later_decisions if item.created_at > reviewer_times.get(item.finding_id, item.created_at))
    signoffs = db.query(ReviewerSignoff).filter_by(reviewer_id=current_user.id).all()
    durations = []
    for signoff in signoffs:
        submission = db.query(Submission).filter_by(id=signoff.submission_id).first()
        if submission:
            durations.append(max(0, (signoff.created_at - submission.created_at).total_seconds() / 3600))
    return {"average_turnaround_hours": round(sum(durations) / len(durations), 2) if durations else None,
        "confirmed": confirmed, "dismissed": dismissed,
        "overturned_rate": round(100 * overturned / len(reviewed_finding_ids), 1) if reviewed_finding_ids else 0}


@router.post("/{submission_id}/comments", response_model=CommentResponse)
def add_comment(
    submission_id: str,
    payload: CommentCreate,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    check_permission(current_user, Action.SUBMISSION_COMMENT)
    submission = db.query(Submission).filter(Submission.id == submission_id).first()
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")

    check_can_view_submission(current_user, submission)

    fingerprint = request_fingerprint({
        "submission_id": submission.id,
        "body": payload.body,
        "finding_id": payload.finding_id,
    })
    scope = f"submission-comment:{submission.id}"
    existing = find_idempotency_record(db, current_user.id, scope, idempotency_key, fingerprint)
    if existing:
        comment = db.query(Comment).filter(Comment.id == existing.resource_id).first()
        if comment:
            return comment
        db.delete(existing)
        db.commit()

    comment = Comment(
        id=gen_id(),
        submission_id=submission.id,
        finding_id=payload.finding_id,
        user_id=current_user.id,
        body=payload.body.strip(),
    )
    db.add(comment)
    remember_request(db, current_user.id, scope, idempotency_key, fingerprint, comment.id)
    try:
        log_action(db, current_user.id, "add_comment", "submission", submission.id)
        db.commit()
    except (IntegrityError, OperationalError) as exc:
        db.rollback()
        existing = find_idempotency_record(db, current_user.id, scope, idempotency_key, fingerprint)
        if existing:
            saved_comment = db.query(Comment).filter(Comment.id == existing.resource_id).first()
            if saved_comment:
                return saved_comment
        raise HTTPException(status_code=409, detail="The comment may have been saved at the same time. Refresh before retrying.") from exc
    db.refresh(comment)
    return comment


@router.post("/{submission_id}/request-review")
def request_review(
    submission_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Creator submits content for manager/reviewer approval."""
    check_permission(current_user, Action.SUBMISSION_REQUEST_REVIEW)
    submission = db.query(Submission).filter(Submission.id == submission_id).first()
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")

    if submission.creator_id != current_user.id:
        raise HTTPException(status_code=403, detail="Creators can only request review for their own submissions")

    if submission.status != SubmissionStatus.checked:
        if submission.status == SubmissionStatus.in_review:
            raise HTTPException(status_code=409, detail="This submission is already in review")
        raise HTTPException(
            status_code=400,
            detail="Run a review on the latest content version before requesting manager review",
        )

    try:
        transitioned = (
            db.query(Submission)
            .filter(Submission.id == submission.id, Submission.status == SubmissionStatus.checked)
            .update({Submission.status: SubmissionStatus.in_review}, synchronize_session=False)
        )
    except OperationalError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Another review request is being saved. Refresh to see the result.") from exc
    if transitioned != 1:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Only a checked submission can be routed for review; refresh its current status",
        )
    submission.status = SubmissionStatus.in_review
    log_action(db, current_user.id, "request_review", "submission", submission.id)
    db.commit()
    return {"status": "ok", "submission_status": submission.status.value}


@router.post("/{submission_id}/approve", response_model=ApprovalResponse)
def approve_submission(
    submission_id: str,
    payload: ApprovalCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Manager or Reviewer gives sign-off on a submission. Enforces self-approval guard."""
    submission = db.query(Submission).filter(Submission.id == submission_id).first()
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")

    check_can_view_submission(current_user, submission)
    if submission.status != SubmissionStatus.in_review:
        raise HTTPException(status_code=409, detail="Only submissions in review can be signed off")

    # Invariant: check role, assignment, risk level, and ensure no self-approval.
    check_approval_allowed(current_user, submission)

    latest_version = (
        db.query(SubmissionVersion)
        .filter(SubmissionVersion.submission_id == submission.id)
        .order_by(SubmissionVersion.version_no.desc())
        .first()
    )
    if not latest_version:
        raise HTTPException(status_code=409, detail="There is no version available to approve")
    content_hash = approved_content_hash(submission, latest_version)

    try:
        transitioned = (
            db.query(Submission)
            .filter(Submission.id == submission.id, Submission.status == SubmissionStatus.in_review)
            .update({Submission.status: SubmissionStatus.approved}, synchronize_session=False)
        )
    except OperationalError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Another decision is being saved. Refresh to see the result.") from exc
    if transitioned != 1:
        db.rollback()
        raise HTTPException(status_code=409, detail="This submission has already received a decision")
    submission.status = SubmissionStatus.approved

    approval = Approval(
        submission_id=submission.id,
        version_id=latest_version.id if latest_version else None,
        user_id=current_user.id,
        decision=ApprovalDecision.approved,
        note=payload.note,
        content_hash=content_hash,
    )
    db.add(approval)
    message = f"{current_user.name} approved ‘{submission.title}’."
    if payload.note and payload.note.strip():
        message += f" Review note: {payload.note.strip()}"
    add_notification(
        db,
        user_id=submission.creator_id,
        submission_id=submission.id,
        kind="workflow_decision",
        title="Submission approved",
        message=message,
    )

    audit_event = log_action(
        db,
        current_user.id,
        "approve_submission",
        "submission",
        submission.id,
        {"note": payload.note, "content_hash": content_hash},
        submission_id=submission.id,
    )
    approval.created_at = audit_event.created_at
    engine = get_llm_mode()
    create_certificate(
        db,
        approval=approval,
        submission=submission,
        version=latest_version,
        audit_head_hash=audit_event.entry_hash,
        ai_engine=engine,
        ai_mode="offline mock" if engine == "mock/offline" else "live provider",
        base_url=str(request.base_url),
    )
    db.flush()
    latest_certificate = db.query(ApprovalCertificate).filter_by(approval_id=approval.id).one()
    render_certificate_pdf(db, latest_certificate)
    db.commit()
    db.refresh(approval)
    return approval


@router.post("/{submission_id}/reject", response_model=ApprovalResponse)
def reject_or_request_changes(
    submission_id: str,
    payload: ApprovalCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Manager or Reviewer requests changes or rejects content."""
    submission = db.query(Submission).filter(Submission.id == submission_id).first()
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")

    check_can_view_submission(current_user, submission)
    if submission.status != SubmissionStatus.in_review:
        raise HTTPException(status_code=409, detail="Only submissions in review can be rejected or returned")
    if has_escalated_risk(submission):
        raise HTTPException(status_code=403, detail="High-risk submissions require reviewer compliance sign-off")

    if submission.creator_id == current_user.id:
        raise HTTPException(status_code=403, detail="Cannot reject or request changes on your own submission")

    decision_val = payload.decision.strip().lower()
    if decision_val not in ("changes_requested", "rejected"):
        decision_val = "changes_requested"

    if decision_val == "rejected":
        check_permission(current_user, Action.SUBMISSION_REJECT)
    else:
        check_permission(current_user, Action.SUBMISSION_REQUEST_CHANGES)

    target_status = (
        SubmissionStatus.rejected if decision_val == "rejected" else SubmissionStatus.changes_requested
    )

    latest_version = (
        db.query(SubmissionVersion)
        .filter(SubmissionVersion.submission_id == submission.id)
        .order_by(SubmissionVersion.version_no.desc())
        .first()
    )

    try:
        transitioned = (
            db.query(Submission)
            .filter(Submission.id == submission.id, Submission.status == SubmissionStatus.in_review)
            .update({Submission.status: target_status}, synchronize_session=False)
        )
    except OperationalError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Another decision is being saved. Refresh to see the result.") from exc
    if transitioned != 1:
        db.rollback()
        raise HTTPException(status_code=409, detail="This submission has already received a decision")
    submission.status = target_status

    approval = Approval(
        submission_id=submission.id,
        version_id=latest_version.id if latest_version else None,
        user_id=current_user.id,
        decision=ApprovalDecision(decision_val),
        note=payload.note,
    )
    db.add(approval)
    decision_label = "requested changes on" if decision_val == "changes_requested" else "rejected"
    message = f"{current_user.name} {decision_label} ‘{submission.title}’."
    if payload.note and payload.note.strip():
        message += f" Review note: {payload.note.strip()}"
    add_notification(
        db,
        user_id=submission.creator_id,
        submission_id=submission.id,
        kind="workflow_decision",
        title="Changes requested" if decision_val == "changes_requested" else "Submission rejected",
        message=message,
    )

    log_action(db, current_user.id, f"{decision_val}_submission", "submission", submission.id, {"note": payload.note})
    db.commit()
    db.refresh(approval)
    return approval


@router.get("/{submission_id}/history")
def get_submission_history(
    submission_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return version history, approvals, and audit trail for this submission."""
    submission = db.query(Submission).filter(Submission.id == submission_id).first()
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")

    check_can_view_submission(current_user, submission)

    versions = (
        db.query(SubmissionVersion)
        .filter(SubmissionVersion.submission_id == submission_id)
        .order_by(SubmissionVersion.version_no.asc())
        .all()
    )
    approvals = (
        db.query(Approval)
        .filter(Approval.submission_id == submission_id)
        .order_by(Approval.created_at.asc())
        .all()
    )
    audit_logs = (
        db.query(AuditLog)
        .filter(AuditLog.submission_id == submission_id)
        .order_by(AuditLog.sequence_no.asc())
        .all()
    )
    comments = (
        db.query(Comment)
        .filter(Comment.submission_id == submission_id)
        .order_by(Comment.created_at.asc())
        .all()
    )

    return {
        "submission_id": submission_id,
        "title": submission.title,
        "current_status": submission.status.value,
        "versions": [
            {
                "id": v.id,
                "version_no": v.version_no,
                "text": v.text,
                "created_at": v.created_at.isoformat(),
                "created_by": v.created_by,
                "creator_name": v.creator.name if v.creator else "User",
            }
            for v in versions
        ],
        "approvals": [
            {
                "id": a.id,
                "decision": a.decision.value,
                "note": a.note,
                "created_at": a.created_at.isoformat(),
                "user_name": a.user.name if a.user else "User",
                "user_role": a.user.role.value if a.user else "",
            }
            for a in approvals
        ],
        "comments": [
            {
                "id": c.id,
                "body": c.body,
                "finding_id": c.finding_id,
                "created_at": c.created_at.isoformat(),
                "user_name": c.user.name if c.user else "User",
            }
            for c in comments
        ],
        "audit_logs": [
            {
                "id": al.id,
                "action": al.action,
                "created_at": al.created_at.isoformat(),
                "user_id": al.user_id,
                "user_name": al.user.name if al.user else "System",
                "meta": al.meta,
            }
            for al in audit_logs
        ],
    }
