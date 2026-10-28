from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from backend.app.database import Base
from backend.app.models.models import (
    Decision, DecisionAction, Finding, GuidelineClause, Submission, SubmissionStatus,
    User, UserRole,
)
from backend.app.pipeline.confidence import suppressed_span_combinations
from backend.app.seed import DEMO_USERS, ensure_demo_users, run_seed
from backend.app.services.auth import authenticate_user, hash_password
from backend.app.workers.dfi_worker import update_dispute_friction_index


def test_demo_accounts_stay_aligned_on_a_nonempty_database():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    try:
        with Session(engine) as db:
            stale_admin = User(
                id="existing-demo-admin",
                name="Existing Demo Admin",
                email="admin@nexora.dev",
                password_hash=hash_password("OldDemoPassword2026!"),
                role=UserRole.creator,
                is_active=True,
            )
            ordinary_user = User(
                id="ordinary-user",
                name="Workspace User",
                email="member@example.test",
                password_hash=hash_password("WorkspacePassword2026!"),
                role=UserRole.creator,
                is_active=True,
            )
            db.add_all([stale_admin, ordinary_user])
            db.commit()
            original_ordinary_hash = ordinary_user.password_hash

            ensure_demo_users(db)
            db.commit()

            for _name, email, password, role in DEMO_USERS:
                account = db.query(User).filter(User.email == email).one()
                assert account.role == role
                assert account.is_active is True
                assert authenticate_user(db, email, password) is account

            assert db.query(User).count() == 5
            assert ordinary_user.password_hash == original_ordinary_hash

            admin_hash = stale_admin.password_hash
            ensure_demo_users(db)
            db.commit()
            assert stale_admin.password_hash == admin_hash
    finally:
        engine.dispose()


def test_demo_seed_includes_high_friction_and_suppressed_feedback_history():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    try:
        with Session(engine) as db:
            run_seed(db)
            demo_submissions = db.query(Submission).filter(Submission.is_demo.is_(True)).all()
            assert len(demo_submissions) >= 15
            assert {submission.status for submission in demo_submissions} >= set(SubmissionStatus)
            assert all(submission.versions for submission in demo_submissions)
            media_submissions = [submission for submission in demo_submissions if submission.content_type.value in {"pdf", "image"}]
            assert {submission.content_type.value for submission in media_submissions} == {"pdf", "image"}
            assert all(submission.versions[0].source_file for submission in media_submissions)
            assert any(submission.assigned_to and submission.assigned_to.role == UserRole.reviewer for submission in demo_submissions)
            original_findings = db.query(Finding).count()
            original_submissions = len(demo_submissions)
            run_seed(db)
            assert db.query(Finding).count() == original_findings
            assert db.query(Submission).filter(Submission.is_demo.is_(True)).count() == original_submissions

            update_dispute_friction_index(db)
            clause = db.query(GuidelineClause).filter_by(code="VOICE-1").one()
            assert clause.dispute_friction_index > 30
            assert (clause.id, "our wording is unclear.") in suppressed_span_combinations(db)
            assert db.query(Decision).filter(Decision.action == DecisionAction.dispute).count() >= 3
    finally:
        engine.dispose()
