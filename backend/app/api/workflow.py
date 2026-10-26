"""Workflow API routes: comments, request review, approvals, rejections, and audit history."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.models.models import (
    User, UserRole, Submission, SubmissionVersion, SubmissionStatus,
    Comment, Approval, ApprovalDecision, AuditLog
)
from backend.app.schemas.schemas import (
    CommentCreate, CommentResponse, ApprovalCreate, ApprovalResponse,
    AuditLogResponse
)
from backend.app.services.auth import get_current_user
from backend.app.services.permissions import (
    Action,
    check_permission,
    check_approval_allowed,
    check_can_view_submission,
    has_escalated_risk,
)
from backend.app.utils.audit import log_action

router = APIRouter(prefix="/submissions", tags=["workflow"])


@router.post("/{submission_id}/comments", response_model=CommentResponse)
def add_comment(
    submission_id: str,
    payload: CommentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    check_permission(current_user, Action.SUBMISSION_COMMENT)
    submission = db.query(Submission).filter(Submission.id == submission_id).first()
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")

    check_can_view_submission(current_user, submission)

    comment = Comment(
        submission_id=submission.id,
        finding_id=payload.finding_id,
        user_id=current_user.id,
        body=payload.body.strip(),
    )
    db.add(comment)
    log_action(db, current_user.id, "add_comment", "submission", submission.id)
    db.commit()
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
        raise HTTPException(
            status_code=400,
            detail="Run a review on the latest content version before requesting manager review",
        )

    submission.status = SubmissionStatus.in_review
    log_action(db, current_user.id, "request_review", "submission", submission.id)
    db.commit()
    return {"status": "ok", "submission_status": submission.status.value}


@router.post("/{submission_id}/approve", response_model=ApprovalResponse)
def approve_submission(
    submission_id: str,
    payload: ApprovalCreate,
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

    approval = Approval(
        submission_id=submission.id,
        version_id=latest_version.id if latest_version else None,
        user_id=current_user.id,
        decision=ApprovalDecision.approved,
        note=payload.note,
    )
    db.add(approval)
    submission.status = SubmissionStatus.approved

    log_action(db, current_user.id, "approve_submission", "submission", submission.id, {"note": payload.note})
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

    approval = Approval(
        submission_id=submission.id,
        version_id=latest_version.id if latest_version else None,
        user_id=current_user.id,
        decision=ApprovalDecision(decision_val),
        note=payload.note,
    )
    db.add(approval)
    submission.status = target_status

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
        .filter(AuditLog.entity_id == submission_id)
        .order_by(AuditLog.created_at.asc())
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
