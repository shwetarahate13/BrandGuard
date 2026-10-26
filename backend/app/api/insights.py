"""Insights API routes: summary stats, recent activity, repeated issues, and creator personal stats."""
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func

from backend.app.database import get_db
from backend.app.models.models import (
    User, Submission, Finding, Approval, FindingStatus, SubmissionStatus, Comment, AuditLog
)
from backend.app.schemas.schemas import (
    InsightsSummary, InsightsRepeatedResponse, RepeatedIssue, CreatorPersonalStats
)
from backend.app.services.auth import get_current_user
from backend.app.services.permissions import Action, check_permission
from backend.app.pipeline.citation_validator import get_dropped_findings_count

router = APIRouter(prefix="/insights", tags=["insights"])


@router.get("/summary", response_model=InsightsSummary)
def get_insights_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Organization-wide governance insights (Manager & Admin only)."""
    check_permission(current_user, Action.ORG_INSIGHTS_VIEW)
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

    avg_turnaround = round(sum(turnarounds) / len(turnarounds), 1) if turnarounds else None

    cutoff = (datetime.now(timezone.utc) - timedelta(days=6)).replace(tzinfo=None)
    submission_rows = (
        db.query(func.date(Submission.created_at), func.count(Submission.id))
        .filter(Submission.created_at >= cutoff)
        .group_by(func.date(Submission.created_at))
        .all()
    )
    finding_rows = (
        db.query(func.date(Finding.created_at), func.count(Finding.id))
        .filter(Finding.created_at >= cutoff)
        .group_by(func.date(Finding.created_at))
        .all()
    )

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
        submissions_by_day={str(day): count for day, count in submission_rows},
        findings_by_day={str(day): count for day, count in finding_rows},
    )


@router.get("/activity")
def get_recent_activity(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return a concise organization activity feed for managers and admins."""
    check_permission(current_user, Action.ORG_INSIGHTS_VIEW)
    events = db.query(AuditLog).order_by(AuditLog.created_at.desc()).limit(12).all()
    return [
        {
            "id": event.id,
            "action": event.action,
            "entity": event.entity,
            "created_at": event.created_at,
            "actor_name": event.user.name if event.user else "System",
        }
        for event in events
    ]


@router.get("/repeated-issues", response_model=InsightsRepeatedResponse)
def get_repeated_issues(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Aggregate top repeated issues across all findings (Manager & Admin only)."""
    check_permission(current_user, Action.ORG_INSIGHTS_VIEW)
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


@router.get("/personal", response_model=CreatorPersonalStats)
def get_personal_creator_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Personal insights for creators: acceptance rate, recurring mistakes, notifications."""
    check_permission(current_user, Action.PERSONAL_STATS_VIEW)
    total_submissions = db.query(Submission).filter(Submission.creator_id == current_user.id).count()

    creator_subs = db.query(Submission).filter(Submission.creator_id == current_user.id).all()
    creator_sub_ids = [s.id for s in creator_subs]

    acc_rate = 0.0
    recurring_mistakes = []
    pending_cnt = 0
    notifications = []

    if creator_sub_ids:
        accepted_cnt = db.query(Finding).filter(
            Finding.submission_id.in_(creator_sub_ids),
            Finding.status == FindingStatus.accepted
        ).count()
        total_decided = db.query(Finding).filter(
            Finding.submission_id.in_(creator_sub_ids),
            Finding.status.in_([FindingStatus.accepted, FindingStatus.edited, FindingStatus.disputed])
        ).count()
        acc_rate = round((accepted_cnt / total_decided * 100.0), 1) if total_decided else 0.0

        repeated = (
            db.query(Finding.issue, Finding.category, Finding.severity, func.count(Finding.id))
            .filter(Finding.submission_id.in_(creator_sub_ids))
            .group_by(Finding.issue, Finding.category, Finding.severity)
            .order_by(func.count(Finding.id).desc())
            .limit(5)
            .all()
        )
        recurring_mistakes = [
            RepeatedIssue(
                issue_pattern=r[0],
                category=r[1].value if hasattr(r[1], "value") else str(r[1]),
                severity=r[2].value if hasattr(r[2], "value") else str(r[2]),
                count=r[3],
            )
            for r in repeated
        ]

        pending_cnt = db.query(Submission).filter(
            Submission.creator_id == current_user.id,
            Submission.status.in_([SubmissionStatus.changes_requested, SubmissionStatus.checked])
        ).count()

        # Build notifications from recent approvals and comments
        approvals = (
            db.query(Approval, Submission)
            .join(Submission, Approval.submission_id == Submission.id)
            .filter(Submission.creator_id == current_user.id)
            .order_by(Approval.created_at.desc())
            .limit(5)
            .all()
        )
        for app, sub in approvals:
            dec_label = "approved" if app.decision.value == "approved" else "changes requested on"
            notifications.append(f"Submission '{sub.title}' was {dec_label} ({app.note or 'no note'})")

        comments = (
            db.query(Comment, Submission)
            .join(Submission, Comment.submission_id == Submission.id)
            .filter(Submission.creator_id == current_user.id, Comment.user_id != current_user.id)
            .order_by(Comment.created_at.desc())
            .limit(5)
            .all()
        )
        for comm, sub in comments:
            notifications.append(f"New review note on '{sub.title}': {comm.body[:60]}...")

    return CreatorPersonalStats(
        total_submissions=total_submissions,
        acceptance_rate=acc_rate,
        recurring_mistakes=recurring_mistakes,
        notifications=notifications[:10],
        pending_action_count=pending_cnt,
    )
