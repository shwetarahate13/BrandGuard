"""Findings API routes: view findings and make decisions (accept, edit, dispute)."""
from typing import List
import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.models.models import (
    User, Submission, SubmissionVersion, Finding, Decision,
    FindingStatus, DecisionAction
)
from backend.app.schemas.schemas import FindingResponse, DecisionCreate, DecisionRequest, DecisionResponse
from backend.app.services.auth import get_current_user
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


def _submit_decision(finding_id: str, payload: DecisionCreate, db: Session, current_user: User) -> Decision:
    finding = db.query(Finding).filter(Finding.id == finding_id).first()
    if not finding:
        raise HTTPException(status_code=404, detail="Finding not found")

    submission = db.query(Submission).filter(Submission.id == finding.submission_id).first()
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")

    action_lower = payload.action.strip().lower()
    if action_lower not in ("accept", "edit", "dispute"):
        raise HTTPException(status_code=400, detail="Action must be 'accept', 'edit', or 'dispute'")

    source_version = db.query(SubmissionVersion).filter(SubmissionVersion.id == finding.version_id).first()
    original_span = ""
    if source_version and finding.span_start is not None and finding.span_end is not None:
        start = max(0, finding.span_start)
        end = min(len(source_version.text), finding.span_end)
        original_span = source_version.text[start:end]

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

    # Model training is auxiliary to recording the human decision. A failed fit
    # rolls back only its savepoint and does not discard the decision itself.
    try:
        with db.begin_nested():
            partial_fit(db, decision)
    except Exception:
        logger.exception("Preference model update failed for decision %s", decision.id)

    # Update finding status
    if action_lower == "accept":
        finding.status = FindingStatus.accepted
    elif action_lower == "edit":
        finding.status = FindingStatus.edited
    elif action_lower == "dispute":
        finding.status = FindingStatus.disputed

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

    log_action(db, current_user.id, f"finding_{action_lower}", "finding", finding.id, {
        "submission_id": submission.id,
        "action": action_lower,
    })
    db.commit()
    db.refresh(decision)
    return decision


@router.post("/findings/{finding_id}/decision", response_model=DecisionResponse)
def submit_decision(
    finding_id: str,
    payload: DecisionCreate,
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
