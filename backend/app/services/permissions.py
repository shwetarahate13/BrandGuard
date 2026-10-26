"""Single source of truth for role permissions and submission-level access."""
from enum import Enum
from typing import Dict, Set, Tuple

from fastapi import HTTPException, status

from backend.app.models.models import (
    Finding,
    FindingCategory,
    FindingSeverity,
    Submission,
    User,
    UserRole,
)


class Action(str, Enum):
    SUBMISSION_CREATE = "submission:create"
    SUBMISSION_VIEW_OWN = "submission:view_own"
    SUBMISSION_VIEW_ALL = "submission:view_all"
    SUBMISSION_VIEW_ASSIGNED = "submission:view_assigned"
    SUBMISSION_ASSIGN = "submission:assign"
    SUBMISSION_REQUEST_REVIEW = "submission:request_review"
    SUBMISSION_APPROVE = "submission:approve"
    SUBMISSION_REQUEST_CHANGES = "submission:request_changes"
    SUBMISSION_REJECT = "submission:reject"
    SUBMISSION_COMMENT = "submission:comment"
    FINDINGS_DECIDE = "findings:decide"
    FINDINGS_ESCALATE_REVIEW = "findings:escalate_review"
    GUIDELINE_HEALTH_VIEW = "guidelines:health_view"
    GUIDELINE_REVISE = "guidelines:revise"
    SOURCES_READ = "sources:read"
    SOURCES_MANAGE = "sources:manage"
    USERS_MANAGE = "users:manage"
    SETTINGS_MANAGE = "settings:manage"
    SYSTEM_STATUS_VIEW = "system:status_view"
    AUDIT_LOG_VIEW = "audit_log:view"
    AUDIT_LOG_EXPORT = "audit_log:export"
    FEEDBACK_STATS_VIEW = "feedback:stats_view"
    FEEDBACK_RESET = "feedback:reset"
    PERSONAL_STATS_VIEW = "insights:personal"
    ORG_INSIGHTS_VIEW = "insights:org"


PERMISSION_MATRIX: Dict[UserRole, Set[Action]] = {
    UserRole.creator: {
        Action.SUBMISSION_CREATE,
        Action.SUBMISSION_VIEW_OWN,
        Action.SUBMISSION_REQUEST_REVIEW,
        Action.SUBMISSION_COMMENT,
        Action.FINDINGS_DECIDE,
        Action.PERSONAL_STATS_VIEW,
    },
    UserRole.manager: {
        Action.SUBMISSION_VIEW_ALL,
        Action.SUBMISSION_ASSIGN,
        Action.SUBMISSION_APPROVE,
        Action.SUBMISSION_REQUEST_CHANGES,
        Action.SUBMISSION_REJECT,
        Action.SUBMISSION_COMMENT,
        Action.GUIDELINE_HEALTH_VIEW,
        Action.GUIDELINE_REVISE,
        Action.SOURCES_READ,
        Action.FEEDBACK_STATS_VIEW,
        Action.ORG_INSIGHTS_VIEW,
    },
    UserRole.reviewer: {
        Action.SUBMISSION_VIEW_ASSIGNED,
        Action.SUBMISSION_APPROVE,
        Action.FINDINGS_ESCALATE_REVIEW,
        Action.SUBMISSION_COMMENT,
        Action.SOURCES_READ,
    },
    UserRole.admin: {
        Action.SUBMISSION_VIEW_ALL,
        Action.SOURCES_READ,
        Action.SOURCES_MANAGE,
        Action.GUIDELINE_HEALTH_VIEW,
        Action.GUIDELINE_REVISE,
        Action.USERS_MANAGE,
        Action.SETTINGS_MANAGE,
        Action.SYSTEM_STATUS_VIEW,
        Action.AUDIT_LOG_VIEW,
        Action.AUDIT_LOG_EXPORT,
        Action.FEEDBACK_STATS_VIEW,
        Action.FEEDBACK_RESET,
        Action.ORG_INSIGHTS_VIEW,
    },
}


def has_permission(role: UserRole, action: Action) -> bool:
    return action in PERMISSION_MATRIX.get(role, set())


def check_permission(user: User, action: Action) -> None:
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Inactive or unauthenticated user")
    if not has_permission(user.role, action):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Role '{user.role.value}' is forbidden from executing '{action.value}'",
        )


def has_escalated_risk(submission: Submission) -> bool:
    """Whether a submission includes any finding that requires compliance review."""
    findings = list(submission.findings or [])
    versions = list(submission.versions or [])
    if versions:
        latest_version_id = max(versions, key=lambda version: version.version_no).id
        findings = [finding for finding in findings if finding.version_id == latest_version_id]
    return any(
        finding.needs_human
        or finding.severity in (FindingSeverity.critical, FindingSeverity.major)
        or finding.category == FindingCategory.unsupported_claim
        for finding in findings
    )


def check_can_view_submission(user: User, submission: Submission) -> None:
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Inactive or unauthenticated user")
    if user.role in (UserRole.admin, UserRole.manager):
        check_permission(user, Action.SUBMISSION_VIEW_ALL)
        return
    if user.role == UserRole.creator:
        check_permission(user, Action.SUBMISSION_VIEW_OWN)
        if submission.creator_id != user.id:
            raise HTTPException(status_code=403, detail="Creators can only view their own submissions")
        return
    check_permission(user, Action.SUBMISSION_VIEW_ASSIGNED)
    assigned = submission.assigned_to_id == user.id
    if not assigned and not has_escalated_risk(submission):
        raise HTTPException(status_code=403, detail="Reviewers can only view assigned or escalated submissions")


def can_approve_submission(user: User, submission: Submission) -> Tuple[bool, str]:
    if not user or not user.is_active:
        return False, "Inactive or unauthenticated user"
    if submission.creator_id == user.id:
        return False, "Self-approval is forbidden: nobody can approve their own submission"
    if user.role in (UserRole.admin, UserRole.creator):
        return False, f"{user.role.value.title()} users cannot approve content"
    if not has_permission(user.role, Action.SUBMISSION_APPROVE):
        return False, f"Role '{user.role.value}' cannot approve content"

    high_risk = has_escalated_risk(submission)
    if user.role == UserRole.manager and high_risk:
        return False, "High-risk submissions require reviewer sign-off"
    if user.role == UserRole.reviewer:
        if submission.assigned_to_id != user.id:
            return False, "Reviewers can only sign off assigned submissions"
        if not high_risk:
            return False, "Reviewers sign off high-risk submissions only"
    return True, ""


def check_approval_allowed(user: User, submission: Submission) -> None:
    allowed, reason = can_approve_submission(user, submission)
    if not allowed:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=reason)


def finding_requires_reviewer_review(finding: Finding) -> bool:
    return bool(
        finding.needs_human
        or finding.severity in (FindingSeverity.critical, FindingSeverity.major)
        or finding.category == FindingCategory.unsupported_claim
    )
