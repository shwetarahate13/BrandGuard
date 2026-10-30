"""Findings API routes: view findings and make decisions (accept, edit, dispute)."""
from typing import List
import re
import logging
from fastapi import APIRouter, Depends, HTTPException, Path as APIPath
from sqlalchemy.orm import Session
from sqlalchemy.exc import OperationalError

from backend.app.database import get_db
from backend.app.models.models import (
    User, UserRole, Submission, SubmissionVersion, Finding, Decision, Comment,
    FindingStatus, DecisionAction, SubmissionStatus, GuidelineClause, SourceType, Notification,
    FindingCategory, FindingConfidence, WritingRuleDispute,
)
from backend.app.schemas.schemas import (
    FindingResponse, DecisionCreate, DecisionRequest, DecisionResponse,
    EscalatedReviewRequest, ApplySafeFixesRequest, ApplySafeFixesResponse,
)
from backend.app.services.auth import get_current_user
from backend.app.services.permissions import (
    Action,
    check_can_view_submission,
    check_permission,
    finding_requires_reviewer_review,
)
from backend.app.utils.audit import log_action
from backend.app.pipeline.preference_model import partial_fit

logger = logging.getLogger(__name__)

router = APIRouter(tags=["findings"])


@router.get("/submissions/{submission_id}/findings", response_model=List[FindingResponse])
def get_submission_findings(
    submission_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retrieve findings for the latest version of a submission."""
    submission = db.query(Submission).filter(Submission.id == submission_id).first()
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")

    check_can_view_submission(current_user, submission)

    latest_version = (
        db.query(SubmissionVersion)
        .filter(SubmissionVersion.submission_id == submission_id)
        .order_by(SubmissionVersion.version_no.desc())
        .first()
    )
    if not latest_version:
        return []

    findings = (
        db.query(Finding)
        .filter(Finding.version_id == latest_version.id)
        .order_by(
            Finding.acceptance_probability.desc().nullslast(),
            Finding.span_start.asc().nullslast(),
        )
        .all()
    )
    return findings


@router.post("/submissions/{submission_id}/findings/apply-safe-fixes", response_model=ApplySafeFixesResponse)
def apply_safe_fixes(
    submission_id: str,
    payload: ApplySafeFixesRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Accept a batch of eligible safe edits and create one immutable next version."""
    check_permission(current_user, Action.FINDINGS_DECIDE)
    submission = db.query(Submission).filter(Submission.id == submission_id).first()
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")
    if submission.creator_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the creator can apply these fixes")
    latest = (
        db.query(SubmissionVersion)
        .filter(SubmissionVersion.submission_id == submission_id)
        .order_by(SubmissionVersion.version_no.desc())
        .first()
    )
    if not latest:
        raise HTTPException(status_code=404, detail="Submission has no content version")

    query = db.query(Finding).filter(
        Finding.id.in_(set(payload.finding_ids)),
        Finding.submission_id == submission_id,
        Finding.version_id == latest.id,
        Finding.status == FindingStatus.open,
        Finding.needs_human.is_(False),
        Finding.confidence == FindingConfidence.high,
        Finding.suggested_rewrite.isnot(None),
    )
    eligible_categories = {FindingCategory.spelling, FindingCategory.grammar}
    if payload.mode == "safe":
        eligible_categories |= {FindingCategory.terminology, FindingCategory.accessibility}
    eligible = query.filter(Finding.category.in_(eligible_categories)).order_by(Finding.span_start.asc()).all()

    # Keep the first non-overlapping high-confidence edits in source order.
    selected = []
    last_end = -1
    for finding in eligible:
        if finding.span_start is None or finding.span_end is None:
            continue
        if finding.span_start < last_end:
            continue
        selected.append(finding)
        last_end = finding.span_end
    if not selected:
        raise HTTPException(status_code=409, detail="No open high-confidence safe fixes are available")

    new_text = latest.text
    for finding in reversed(selected):
        start, end = finding.span_start, finding.span_end
        new_text = new_text[:start] + finding.suggested_rewrite + new_text[end:]
    if len(new_text.split()) > 20_000:
        raise HTTPException(status_code=422, detail="The revised content exceeds the 20,000-word limit")

    decisions = []
    for finding in selected:
        claimed = db.query(Finding).filter(
            Finding.id == finding.id, Finding.status == FindingStatus.open
        ).update({Finding.status: FindingStatus.accepted}, synchronize_session=False)
        if claimed != 1:
            db.rollback()
            raise HTTPException(status_code=409, detail="A finding was decided concurrently; refresh before retrying")
        original = latest.text[finding.span_start:finding.span_end]
        decision = Decision(
            finding_id=finding.id,
            user_id=current_user.id,
            action=DecisionAction.accept,
            original_span=original,
            suggested_rewrite=finding.suggested_rewrite,
        )
        db.add(decision)
        db.flush()
        decisions.append(decision)
        try:
            with db.begin_nested():
                partial_fit(db, decision)
        except Exception:
            logger.exception("Preference model update failed for safe-fix decision %s", decision.id)

    next_version = SubmissionVersion(
        submission_id=submission.id,
        version_no=latest.version_no + 1,
        text=new_text,
        source_file=latest.source_file,
        source_mime_type=latest.source_mime_type,
        source_filename=latest.source_filename,
        source_layout=latest.source_layout,
        created_by=current_user.id,
    )
    db.add(next_version)
    db.flush()
    submission.status = SubmissionStatus.draft
    log_action(db, current_user.id, "apply_safe_fixes", "submission_version", next_version.id, {
        "submission_id": submission.id,
        "finding_ids": [finding.id for finding in selected],
        "mode": payload.mode,
    })
    db.commit()
    return ApplySafeFixesResponse(
        submission_id=submission.id,
        version_no=next_version.version_no,
        applied_finding_ids=[finding.id for finding in selected],
        applied_count=len(selected),
    )


def _submit_decision(finding_id: str, payload: DecisionCreate, db: Session, current_user: User) -> Decision:
    check_permission(current_user, Action.FINDINGS_DECIDE)
    finding = db.query(Finding).filter(Finding.id == finding_id).first()
    if not finding:
        raise HTTPException(status_code=404, detail="Finding not found")

    submission = db.query(Submission).filter(Submission.id == finding.submission_id).first()
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")

    check_can_view_submission(current_user, submission)

    action_lower = payload.action.strip().lower()
    if action_lower not in ("accept", "edit", "dispute"):
        raise HTTPException(status_code=400, detail="Action must be 'accept', 'edit', or 'dispute'")

    source_version = db.query(SubmissionVersion).filter(SubmissionVersion.id == finding.version_id).first()
    latest_version = (
        db.query(SubmissionVersion)
        .filter(SubmissionVersion.submission_id == submission.id)
        .order_by(SubmissionVersion.version_no.desc())
        .first()
    )
    if not source_version or not latest_version or source_version.id != latest_version.id:
        raise HTTPException(status_code=409, detail="This finding belongs to an older version; review the latest version instead")
    if finding.status != FindingStatus.open:
        raise HTTPException(status_code=409, detail="This finding has already been decided")
    if action_lower == "edit" and not (payload.edited_text or "").strip():
        raise HTTPException(status_code=422, detail="Edited wording cannot be empty")
    original_span = ""
    if source_version and finding.span_start is not None and finding.span_end is not None:
        start = max(0, finding.span_start)
        end = min(len(source_version.text), finding.span_end)
        original_span = source_version.text[start:end]

    # Claim an open finding in the database before writing the decision. The
    # conditional update makes concurrent duplicate actions a clean 409.
    decision_status = {
        "accept": FindingStatus.accepted,
        "edit": FindingStatus.edited,
        "dispute": FindingStatus.disputed,
    }[action_lower]
    try:
        claimed = (
            db.query(Finding)
            .filter(Finding.id == finding.id, Finding.status == FindingStatus.open)
            .update({Finding.status: decision_status}, synchronize_session=False)
        )
    except OperationalError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Another decision is being saved. Refresh to see the result.") from exc
    if claimed != 1:
        db.rollback()
        raise HTTPException(status_code=409, detail="This finding has already been decided")
    finding.status = decision_status

    # Capture an immutable snapshot of the text pair used for online training.
    decision = Decision(
        finding_id=finding.id,
        user_id=current_user.id,
        action=DecisionAction(action_lower),
        edited_text=payload.edited_text,
        original_span=original_span,
        suggested_rewrite=finding.suggested_rewrite,
        human_edited_text=payload.edited_text,
        reason=payload.reason,
    )
    db.add(decision)
    db.flush()

    if action_lower == "dispute" and finding.category == FindingCategory.grammar:
        rule_match = re.match(r"^(GRAM-\d+):", finding.issue)
        if rule_match:
            db.add(WritingRuleDispute(rule_id=rule_match.group(1), finding_id=finding.id))

    if action_lower == "dispute" and finding.source_type == SourceType.guideline_clause and finding.source_id:
        clause = db.query(GuidelineClause).filter(GuidelineClause.id == finding.source_id).first()
        if clause:
            clause.dfi_computed_at = None

    # Model training is auxiliary to recording the human decision. A failed fit
    # rolls back only its savepoint and does not discard the decision itself.
    try:
        with db.begin_nested():
            partial_fit(db, decision)
    except Exception:
        logger.exception("Preference model update failed for decision %s", decision.id)

    # Update finding status
    # If accept or edit: generate next version with the replacement applied
    replacement_text = None
    if action_lower == "accept" and finding.suggested_rewrite:
        replacement_text = finding.suggested_rewrite
    elif action_lower == "edit" and payload.edited_text is not None:
        replacement_text = payload.edited_text

    if replacement_text is not None and finding.span_start is not None and finding.span_end is not None:
        latest_version = (
            db.query(SubmissionVersion)
            .filter(SubmissionVersion.submission_id == submission.id)
            .order_by(SubmissionVersion.version_no.desc())
            .first()
        )
        if latest_version and latest_version.id == finding.version_id:
            old_text = latest_version.text
            start = max(0, finding.span_start)
            end = min(len(old_text), finding.span_end)
            
            # Apply replacement to text
            new_text = old_text[:start] + replacement_text + old_text[end:]

            # Create next version
            new_version = SubmissionVersion(
                submission_id=submission.id,
                version_no=latest_version.version_no + 1,
                text=new_text,
                source_file=latest_version.source_file,
                source_mime_type=latest_version.source_mime_type,
                source_filename=latest_version.source_filename,
                source_layout=latest_version.source_layout,
                created_by=current_user.id,
            )
            db.add(new_version)
            db.flush()
            submission.status = SubmissionStatus.draft

    log_action(db, current_user.id, f"finding_{action_lower}", "finding", finding.id, {
        "submission_id": submission.id,
        "action": action_lower,
    })
    db.commit()
    db.refresh(decision)
    return decision


@router.post("/findings/{finding_id}/decision", response_model=DecisionResponse)
def submit_decision(
    payload: DecisionCreate,
    finding_id: str = APIPath(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9-]+$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Submit a decision through the established finding-scoped API route."""
    return _submit_decision(finding_id, payload, db, current_user)


@router.post("/decisions", response_model=DecisionResponse)
def create_decision(
    payload: DecisionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Record a reviewer decision and update the online rewrite preference model."""
    return _submit_decision(payload.finding_id, payload, db, current_user)


@router.post("/findings/{finding_id}/escalate-review")
def review_escalated_finding(
    payload: EscalatedReviewRequest,
    finding_id: str = APIPath(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9-]+$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Assigned reviewer confirms or dismisses an escalated finding with required justification."""
    check_permission(current_user, Action.FINDINGS_ESCALATE_REVIEW)
    finding = db.query(Finding).filter(Finding.id == finding_id).first()
    if not finding:
        raise HTTPException(status_code=404, detail="Finding not found")

    submission = db.query(Submission).filter(Submission.id == finding.submission_id).first()
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")

    check_can_view_submission(current_user, submission)
    if current_user.role != UserRole.reviewer or submission.assigned_to_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only a reviewer assigned to this submission can resolve escalated findings")
    if not finding_requires_reviewer_review(finding):
        raise HTTPException(status_code=400, detail="This finding is not escalated for compliance review")
    latest_version = (
        db.query(SubmissionVersion)
        .filter(SubmissionVersion.submission_id == submission.id)
        .order_by(SubmissionVersion.version_no.desc())
        .first()
    )
    if not latest_version or latest_version.id != finding.version_id:
        raise HTTPException(status_code=409, detail="This finding belongs to an older version; review the latest version instead")
    if db.query(Decision).filter_by(finding_id=finding.id, user_id=current_user.id).first():
        raise HTTPException(status_code=409, detail="You have already recorded a compliance decision for this finding")

    if payload.action == "confirm":
        finding.needs_human = False
        finding.status = FindingStatus.accepted
        note_body = f"[Compliance Confirmed]: {payload.justification.strip()}"
        submission.status = SubmissionStatus.changes_requested
        db.add(Notification(
            user_id=submission.creator_id,
            submission_id=submission.id,
            kind="reviewer_violation_confirmed",
            title="Compliance reviewer confirmed a violation",
            message=note_body,
        ))
        start = max(0, finding.span_start or 0)
        end = min(len(latest_version.text), finding.span_end or start)
        db.add(Decision(finding_id=finding.id, user_id=current_user.id, action=DecisionAction.accept,
            original_span=latest_version.text[start:end], reason=payload.justification.strip()))
    else:
        finding.needs_human = False
        finding.status = FindingStatus.disputed
        note_body = f"[Compliance Dismissed]: {payload.justification.strip()}"
        start = max(0, finding.span_start or 0)
        end = min(len(latest_version.text), finding.span_end or start)
        decision = Decision(
            finding_id=finding.id,
            user_id=current_user.id,
            action=DecisionAction.dispute,
            original_span=latest_version.text[start:end],
            suggested_rewrite=finding.suggested_rewrite,
            reason=payload.justification.strip(),
        )
        db.add(decision)
        db.flush()
        if finding.source_type == SourceType.guideline_clause and finding.source_id:
            clause = db.query(GuidelineClause).filter(GuidelineClause.id == finding.source_id).first()
            if clause:
                clause.dfi_computed_at = None
        try:
            with db.begin_nested():
                partial_fit(db, decision)
        except Exception:
            logger.exception("Preference model update failed for reviewer dismissal %s", decision.id)

    comment = Comment(
        submission_id=submission.id,
        finding_id=finding.id,
        user_id=current_user.id,
        body=note_body,
    )
    db.add(comment)
    log_action(db, current_user.id, f"escalate_{payload.action}", "finding", finding.id, {
        "justification": payload.justification,
    })
    db.commit()
    return {"status": "ok", "action": payload.action, "finding_id": finding.id}
