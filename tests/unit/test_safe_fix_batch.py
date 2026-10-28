import uuid

import pytest
from fastapi import HTTPException

from backend.app.api.findings import apply_safe_fixes
from backend.app.database import get_session_factory
from backend.app.models.models import (
    Finding, FindingCategory, FindingConfidence, FindingSeverity, FindingStatus,
    Submission, SubmissionStatus, SubmissionVersion, User,
)
from backend.app.schemas.schemas import ApplySafeFixesRequest
from backend.app.seed import run_seed


def _fixture_submission(db, creator):
    submission = Submission(
        creator_id=creator.id, title=f"Batch fix {uuid.uuid4()}", intent="Correct the copy",
        status=SubmissionStatus.checked, content_type="text",
    )
    db.add(submission)
    db.flush()
    version = SubmissionVersion(submission_id=submission.id, version_no=1, text="teh patrons", created_by=creator.id)
    db.add(version)
    db.flush()
    first = Finding(
        submission_id=submission.id, version_id=version.id, span_start=0, span_end=3,
        category=FindingCategory.spelling, issue="Spelling", severity=FindingSeverity.minor,
        confidence=FindingConfidence.high, suggested_rewrite="the", needs_human=False, status=FindingStatus.open,
    )
    second = Finding(
        submission_id=submission.id, version_id=version.id, span_start=4, span_end=11,
        category=FindingCategory.grammar, issue="Grammar", severity=FindingSeverity.minor,
        confidence=FindingConfidence.high, suggested_rewrite="patrons.", needs_human=False, status=FindingStatus.open,
    )
    db.add_all([first, second])
    db.commit()
    return submission, [first, second]


def test_batch_grammar_fixes_create_one_version_and_decisions():
    db = get_session_factory()()
    try:
        run_seed(db)
        creator = db.query(User).filter_by(email="creator@nexora.dev").one()
        submission, findings = _fixture_submission(db, creator)
        result = apply_safe_fixes(
            submission.id,
            ApplySafeFixesRequest(finding_ids=[finding.id for finding in findings], mode="grammar"),
            db,
            creator,
        )
        versions = db.query(SubmissionVersion).filter_by(submission_id=submission.id).order_by(SubmissionVersion.version_no).all()
        assert result.applied_count == 2
        assert len(versions) == 2
        assert versions[-1].text == "the patrons."
        assert all(finding.status == FindingStatus.accepted for finding in findings)

        with pytest.raises(HTTPException) as error:
            apply_safe_fixes(
                submission.id,
                ApplySafeFixesRequest(finding_ids=[finding.id for finding in findings], mode="grammar"),
                db,
                creator,
            )
        assert error.value.status_code == 409
    finally:
        db.close()


def test_non_owner_cannot_apply_another_creators_safe_fixes():
    db = get_session_factory()()
    try:
        run_seed(db)
        creator = db.query(User).filter_by(email="creator@nexora.dev").one()
        manager = db.query(User).filter_by(email="manager@nexora.dev").one()
        submission, findings = _fixture_submission(db, creator)
        with pytest.raises(HTTPException) as error:
            apply_safe_fixes(
                submission.id,
                ApplySafeFixesRequest(finding_ids=[finding.id for finding in findings], mode="grammar"),
                db,
                manager,
            )
        assert error.value.status_code == 403
    finally:
        db.close()
