from backend.app.api.admin import reset_writing_rule_disputes
from backend.app.api.findings import submit_decision
from backend.app.database import get_session_factory
from backend.app.models.models import (
    Finding, FindingCategory, FindingConfidence, FindingSeverity, FindingStatus,
    Submission, SubmissionStatus, SubmissionVersion, User, GuidelineClause, SourceType,
)
from backend.app.schemas.schemas import DecisionCreate
from backend.app.pipeline.writing_rule_feedback import suppressed_writing_rules, writing_rule_dispute_counts
from backend.app.seed import run_seed


def test_grammar_rule_suppresses_after_three_disputes_and_admin_can_reset():
    db = get_session_factory()()
    try:
        run_seed(db)
        creator = db.query(User).filter_by(email="creator@nexora.dev").one()
        admin = db.query(User).filter_by(email="admin@nexora.dev").one()
        submission = Submission(creator_id=creator.id, title="Grammar feedback", intent="Test rule feedback", status=SubmissionStatus.checked, content_type="text")
        db.add(submission)
        db.flush()
        version = SubmissionVersion(submission_id=submission.id, version_no=1, text="abc", created_by=creator.id)
        db.add(version)
        db.flush()
        style_clause = db.query(GuidelineClause).filter_by(code="STYLE-1").one()
        for index in range(3):
            finding = Finding(
                submission_id=submission.id, version_id=version.id, span_start=index, span_end=index + 1,
                category=FindingCategory.grammar, issue="GRAM-3: subject agreement", severity=FindingSeverity.minor,
                source_type=SourceType.guideline_clause, source_id=style_clause.id,
                confidence=FindingConfidence.high, status=FindingStatus.open,
            )
            db.add(finding)
            db.flush()
            submit_decision(DecisionCreate(action="dispute", reason="This rule needs review."), finding.id, db, creator)

        assert writing_rule_dispute_counts(db)["GRAM-3"] == 3
        assert suppressed_writing_rules(db) == {"GRAM-3"}
        result = reset_writing_rule_disputes(db, admin)
        assert result["deleted_count"] == 3
        assert suppressed_writing_rules(db) == set()
    finally:
        db.close()
