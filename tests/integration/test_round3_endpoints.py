"""Integration coverage for the new guideline, media, and feedback APIs."""
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.api import guidelines as guidelines_api
from backend.app.database import Base, get_db
from backend.app.main import app
from backend.app.models.models import (
    Decision,
    DecisionAction,
    Finding,
    FindingCategory,
    FindingConfidence,
    FindingSeverity,
    FindingStatus,
    GuidelineClause,
    GuidelineDoc,
    PreferenceModelState,
    SourceType,
    Submission,
    SubmissionStatus,
    SubmissionVersion,
    User,
    UserRole,
)
from backend.app.services.auth import get_current_user


@pytest.fixture
def api_client(monkeypatch):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
    )
    manager = User(
        id="manager-test",
        name="Test Manager",
        email="manager@example.test",
        password_hash="unused",
        role=UserRole.manager,
        is_active=True,
    )
    with session_factory.begin() as db:
        db.add(manager)

    def override_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    def override_user():
        return manager

    monkeypatch.setitem(app.dependency_overrides, get_db, override_db)
    monkeypatch.setitem(app.dependency_overrides, get_current_user, override_user)
    client = TestClient(app)
    yield client, session_factory, manager
    engine.dispose()


def _add_clause(db, clause_id="clause-test", text="Use clear approved language.", dfi=0.0):
    doc_id = f"doc-{clause_id}"
    db.add(GuidelineDoc(id=doc_id, title="Brand Guidelines"))
    clause = GuidelineClause(
        id=clause_id,
        doc_id=doc_id,
        code="VOICE-1",
        title="Voice and clarity",
        text=text,
        order_index=1,
        dispute_friction_index=dfi,
    )
    db.add(clause)
    return clause


def test_submission_visibility_and_role_routes_return_forbidden(api_client, monkeypatch):
    client, session_factory, manager = api_client
    creator = User(id="route-creator", name="Creator", email="c-route@example.test", password_hash="x", role=UserRole.creator, is_active=True)
    reviewer = User(id="route-reviewer", name="Reviewer", email="r-route@example.test", password_hash="x", role=UserRole.reviewer, is_active=True)
    submission = Submission(id="private-route-sub", creator_id=creator.id, title="Private draft", status=SubmissionStatus.in_review)
    with session_factory.begin() as db:
        db.add_all([creator, reviewer, submission])

    monkeypatch.setitem(app.dependency_overrides, get_current_user, lambda: reviewer)
    assert client.get(f"/api/submissions/{submission.id}").status_code == 403
    assert client.get("/api/submissions").json() == []
    assert client.get("/api/submissions/reviewers").status_code == 403
    assert client.get("/api/system/status").status_code == 403

    monkeypatch.setitem(app.dependency_overrides, get_current_user, lambda: creator)
    own_response = client.get(f"/api/submissions/{submission.id}")
    assert own_response.status_code == 200
    assert client.get("/api/submissions/reviewers").status_code == 403

    monkeypatch.setitem(app.dependency_overrides, get_current_user, lambda: manager)
    assert client.get("/api/submissions/reviewers").status_code == 200


def test_admin_is_the_only_role_with_detailed_system_status(api_client, monkeypatch):
    client, session_factory, _manager = api_client
    admin = User(id="route-admin", name="Admin", email="a-route@example.test", password_hash="x", role=UserRole.admin, is_active=True)
    with session_factory.begin() as db:
        db.add(admin)
    monkeypatch.setitem(app.dependency_overrides, get_current_user, lambda: admin)
    response = client.get("/api/system/status")
    assert response.status_code == 200
    assert "database_connected" in response.json()


def test_get_guideline_health_returns_real_clause_rows(api_client):
    client, session_factory, _ = api_client
    with session_factory.begin() as db:
        _add_clause(db, "clause-low", "Keep the wording clear.", 8.0)
        _add_clause(db, "clause-high", "Explain claims in detail.", 42.0)

    response = client.get("/api/guidelines/health")

    assert response.status_code == 200
    clauses = response.json()
    assert [clause["id"] for clause in clauses] == ["clause-high", "clause-low"]
    assert clauses[0]["dispute_friction_index"] == 42.0
    assert clauses[0]["proposed_revision"] is None


def test_patch_guideline_clause_applies_revision(api_client, monkeypatch):
    client, session_factory, _ = api_client
    with session_factory.begin() as db:
        _add_clause(db)
    monkeypatch.setattr(guidelines_api, "index_all_sources", lambda db: 1)

    response = client.patch(
        "/api/guidelines/clauses/clause-test",
        json={"text": "Use concise, approved wording."},
    )

    assert response.status_code == 200
    assert response.json()["text"] == "Use concise, approved wording."
    invalid = client.patch("/api/guidelines/clauses/clause-test", json={"text": "  "})
    assert invalid.status_code == 422


def test_get_submission_source_returns_authorized_uploaded_bytes(api_client):
    client, session_factory, manager = api_client
    submission_id = str(uuid.uuid4())
    version_id = str(uuid.uuid4())
    with session_factory.begin() as db:
        db.add(Submission(
            id=submission_id,
            creator_id=manager.id,
            title="Uploaded creative",
            status=SubmissionStatus.draft,
        ))
        db.add(SubmissionVersion(
            id=version_id,
            submission_id=submission_id,
            version_no=1,
            text="Recognized creative copy",
            source_file=b"actual-test-image-bytes",
            source_mime_type="image/png",
            source_filename="creative.png",
            source_layout={"media": "image", "width": 2, "height": 2, "regions": []},
            created_by=manager.id,
        ))

    response = client.get(f"/api/submissions/{submission_id}/versions/{version_id}/source")

    assert response.status_code == 200
    assert response.content == b"actual-test-image-bytes"
    assert response.headers["content-type"].startswith("image/png")
    assert response.headers["cache-control"] == "private, no-store"


def test_post_decisions_snapshots_pair_and_updates_model(api_client, monkeypatch):
    client, session_factory, manager = api_client
    creator = User(
        id="creator-test",
        name="Test Creator",
        email="creator@example.test",
        password_hash="unused",
        role=UserRole.creator,
        is_active=True,
    )
    submission_id = str(uuid.uuid4())
    version_id = str(uuid.uuid4())
    finding_id = str(uuid.uuid4())
    with session_factory.begin() as db:
        db.add(creator)
        db.add(Submission(
            id=submission_id,
            creator_id=creator.id,
            title="Copy under review",
            status=SubmissionStatus.draft,
        ))
        db.add(SubmissionVersion(
            id=version_id,
            submission_id=submission_id,
            version_no=1,
            text="Cheap oat drink",
            created_by=creator.id,
        ))

        db.add(Finding(
            id=finding_id,
            submission_id=submission_id,
            version_id=version_id,
            span_start=0,
            span_end=5,
            category=FindingCategory.messaging,
            issue="Avoid the low-value term.",
            severity=FindingSeverity.minor,
            confidence=FindingConfidence.high,
            suggested_rewrite="Fairly priced oat drink",
            status=FindingStatus.open,
        ))

    monkeypatch.setitem(app.dependency_overrides, get_current_user, lambda: creator)

    response = client.post(
        "/api/decisions",
        json={"finding_id": finding_id, "action": "accept"},
    )

    assert response.status_code == 200
    with session_factory() as db:
        decision = db.query(Decision).filter(Decision.finding_id == finding_id).one()
        assert decision.original_span == "Cheap"
        assert decision.suggested_rewrite == "Fairly priced oat drink"
        assert decision.human_edited_text is None
        assert db.query(PreferenceModelState).one().sample_count == 1
        assert db.query(SubmissionVersion).filter(SubmissionVersion.submission_id == submission_id).count() == 2
        assert decision.suggested_rewrite in db.query(SubmissionVersion).filter_by(submission_id=submission_id, version_no=2).one().text

    invalid = client.post("/api/decisions", json={"finding_id": finding_id, "action": "unknown"})
    assert invalid.status_code == 422


def test_get_feedback_stats_reports_category_rates_and_suppression(api_client):
    client, session_factory, manager = api_client
    with session_factory.begin() as db:
        clause = _add_clause(db, "clause-repeat")
        for index in range(3):
            submission_id = f"sub-repeat-{index}"
            version_id = f"ver-repeat-{index}"
            finding_id = f"finding-repeat-{index}"
            db.add(Submission(
                id=submission_id,
                creator_id=manager.id,
                title=f"Copy {index}",
                status=SubmissionStatus.draft,
            ))
            db.add(SubmissionVersion(
                id=version_id,
                submission_id=submission_id,
                version_no=1,
                text="Claim text",
                created_by=manager.id,
            ))
            db.add(Finding(
                id=finding_id,
                submission_id=submission_id,
                version_id=version_id,
                span_start=0,
                span_end=10,
                category=FindingCategory.messaging,
                issue="Clarify the claim.",
                source_type=SourceType.guideline_clause,
                source_id=clause.id,
                severity=FindingSeverity.minor,
                confidence=FindingConfidence.high,
                status=FindingStatus.disputed,
            ))
            db.add(Decision(
                id=f"decision-repeat-{index}",
                finding_id=finding_id,
                user_id=manager.id,
                action=DecisionAction.dispute,
                original_span="Claim text",
                reason="The guideline is unclear.",
            ))

    response = client.get("/api/feedback/stats")

    assert response.status_code == 200
    messaging = next(item for item in response.json()["categories"] if item["category"] == "messaging")
    assert messaging["decisions_count"] == 3
    assert messaging["acceptance_rate"] == 0.0
    assert messaging["edit_rate"] == 0.0
    assert messaging["suppression_count"] == 1
