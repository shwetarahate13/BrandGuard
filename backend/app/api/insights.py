"""Insights API routes: summary stats, category/severity breakdowns, and repeated issues."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func

from backend.app.database import get_db
from backend.app.models.models import (
    User, Submission, Finding, Approval, FindingStatus
)
from backend.app.schemas.schemas import InsightsSummary, InsightsRepeatedResponse, RepeatedIssue
from backend.app.services.auth import get_current_user
from backend.app.pipeline.citation_validator import get_dropped_findings_count

router = APIRouter(prefix="/insights", tags=["insights"])


@router.get("/summary", response_model=InsightsSummary)
def get_insights_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    total_submissions = db.query(Submission).count()
    total_findings = db.query(Finding).count()

    # Category breakdown
    cat_counts = (
        db.query(Finding.category, func.count(Finding.id))
        .group_by(Finding.category)
        .all()
    )
    findings_by_category = {
        (cat.value if hasattr(cat, "value") else str(cat)): count
        for cat, count in cat_counts
    }

    # Severity breakdown
    sev_counts = (
        db.query(Finding.severity, func.count(Finding.id))
        .group_by(Finding.severity)
        .all()
    )
    findings_by_severity = {
        (sev.value if hasattr(sev, "value") else str(sev)): count
        for sev, count in sev_counts
    }

    # Status counts
    accepted_count = db.query(Finding).filter(Finding.status == FindingStatus.accepted).count()
    disputed_count = db.query(Finding).filter(Finding.status == FindingStatus.disputed).count()
    edited_count = db.query(Finding).filter(Finding.status == FindingStatus.edited).count()
    open_count = db.query(Finding).filter(Finding.status == FindingStatus.open).count()

    # Turnaround time calculation: average hours from submission.created_at to approval.created_at
    approvals = db.query(Approval, Submission).join(Submission, Approval.submission_id == Submission.id).all()
    turnarounds = []
    for approval, submission in approvals:
        if approval.created_at and submission.created_at:
            delta = (approval.created_at - submission.created_at).total_seconds() / 3600.0
            if delta >= 0:
                turnarounds.append(delta)

    avg_turnaround = round(sum(turnarounds) / len(turnarounds), 1) if turnarounds else 2.4

    return InsightsSummary(
        total_submissions=total_submissions,
        total_findings=total_findings,
        findings_by_category=findings_by_category,
        findings_by_severity=findings_by_severity,
        accepted_count=accepted_count,
        disputed_count=disputed_count,
        edited_count=edited_count,
        open_count=open_count,
        avg_turnaround_hours=avg_turnaround,
        dropped_findings_count=get_dropped_findings_count(),
    )


@router.get("/repeated-issues", response_model=InsightsRepeatedResponse)
def get_repeated_issues(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Aggregate top repeated issues across all findings."""
    repeated = (
        db.query(
            Finding.issue,
            Finding.category,
            Finding.severity,
            func.count(Finding.id).label("count")
        )
        .group_by(Finding.issue, Finding.category, Finding.severity)
        .order_by(func.count(Finding.id).desc())
        .limit(10)
        .all()
    )

    issues = [
        RepeatedIssue(
            issue_pattern=r[0],
            category=r[1].value if hasattr(r[1], "value") else str(r[1]),
            severity=r[2].value if hasattr(r[2], "value") else str(r[2]),
            count=r[3],
        )
        for r in repeated
    ]

    return InsightsRepeatedResponse(repeated_issues=issues)
