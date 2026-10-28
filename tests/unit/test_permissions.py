"""Permission policy tests using an independent expected matrix."""
import pytest
from fastapi import HTTPException

from backend.app.models.models import (
    Finding,
    FindingCategory,
    FindingSeverity,
    Submission,
    SubmissionStatus,
    User,
    UserRole,
)
from backend.app.services.permissions import (
    Action,
    PERMISSION_MATRIX,
    can_approve_submission,
    check_approval_allowed,
    check_can_view_submission,
    check_permission,
    has_permission,
)


EXPECTED = {
    UserRole.creator: {
        Action.SUBMISSION_CREATE,
        Action.SUBMISSION_VIEW_OWN,
        Action.SUBMISSION_REQUEST_REVIEW,
        Action.SUBMISSION_COMMENT,
        Action.FINDINGS_DECIDE,
        Action.PERSONAL_STATS_VIEW,
        Action.CERTIFICATE_DOWNLOAD,
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
        Action.APPROVAL_REPORT_EXPORT,
        Action.CERTIFICATE_DOWNLOAD,
        Action.CERTIFICATE_REVOKE,
    },
    UserRole.reviewer: {
        Action.SUBMISSION_VIEW_ASSIGNED,
        Action.FINDINGS_ESCALATE_REVIEW,
        Action.SUBMISSION_COMMENT,
        Action.SOURCES_READ,
        Action.CERTIFICATE_DOWNLOAD,
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
        Action.AUDIT_INTEGRITY_VIEW,
        Action.CERTIFICATE_DOWNLOAD,
        Action.CERTIFICATE_REVOKE,
        Action.FEEDBACK_STATS_VIEW,
        Action.FEEDBACK_RESET,
        Action.ORG_INSIGHTS_VIEW,
        Action.APPROVAL_REPORT_EXPORT,
    },
}


@pytest.mark.parametrize("role", list(UserRole))
@pytest.mark.parametrize("action", list(Action))
def test_permission_matrix_cells(role: UserRole, action: Action):
    expected_allowed = action in EXPECTED[role]
    assert has_permission(role, action) is expected_allowed
    assert (action in PERMISSION_MATRIX[role]) is expected_allowed

    user = User(id="test-user", name="Test", email="test@example.com", role=role, is_active=True)
    if expected_allowed:
        check_permission(user, action)
    else:
        with pytest.raises(HTTPException) as exc:
            check_permission(user, action)
        assert exc.value.status_code == 403


def test_inactive_user_is_rejected():
    user = User(id="inactive", name="Inactive", email="inactive@example.com", role=UserRole.admin, is_active=False)
    with pytest.raises(HTTPException) as exc:
        check_permission(user, Action.USERS_MANAGE)
    assert exc.value.status_code == 401


def test_creators_cannot_view_another_creators_submission():
    creator = User(id="creator-1", name="Creator", email="c@example.com", role=UserRole.creator, is_active=True)
    submission = Submission(id="submission-1", creator_id="creator-2", title="Private", status=SubmissionStatus.draft)
    with pytest.raises(HTTPException) as exc:
        check_can_view_submission(creator, submission)
    assert exc.value.status_code == 403


def test_reviewers_can_view_only_assigned_or_escalated_submissions():
    reviewer = User(id="reviewer-1", name="Reviewer", email="r@example.com", role=UserRole.reviewer, is_active=True)
    unrelated = Submission(id="submission-1", creator_id="creator-1", title="Other", status=SubmissionStatus.in_review)
    with pytest.raises(HTTPException) as exc:
        check_can_view_submission(reviewer, unrelated)
    assert exc.value.status_code == 403

    unrelated.assigned_to_id = reviewer.id
    check_can_view_submission(reviewer, unrelated)


def test_approval_policy_restricts_self_approval_and_high_risk_signoff():
    manager = User(id="manager-1", name="Manager", email="m@example.com", role=UserRole.manager, is_active=True)
    reviewer = User(id="reviewer-1", name="Reviewer", email="r@example.com", role=UserRole.reviewer, is_active=True)
    admin = User(id="admin-1", name="Admin", email="a@example.com", role=UserRole.admin, is_active=True)
    own = Submission(id="own", creator_id=manager.id, title="Own", status=SubmissionStatus.in_review)
    assert can_approve_submission(manager, own)[0] is False
    with pytest.raises(HTTPException) as exc:
        check_approval_allowed(manager, own)
    assert exc.value.status_code == 403

    standard = Submission(id="standard", creator_id="creator-1", title="Standard", status=SubmissionStatus.in_review)
    assert can_approve_submission(manager, standard)[0] is True
    assert can_approve_submission(reviewer, standard)[0] is False

    high_risk = Submission(id="risky", creator_id="creator-1", title="Risky", status=SubmissionStatus.in_review)
    high_risk.findings = [Finding(category=FindingCategory.unsupported_claim, severity=FindingSeverity.major, needs_human=False)]
    assert can_approve_submission(manager, high_risk)[0] is False
    assert can_approve_submission(reviewer, high_risk)[0] is False
    high_risk.assigned_to_id = reviewer.id
    assert can_approve_submission(reviewer, high_risk)[0] is False
    assert can_approve_submission(admin, standard)[0] is False
