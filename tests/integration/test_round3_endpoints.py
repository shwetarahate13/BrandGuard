"""Integration coverage for the new guideline, media, and feedback APIs."""
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.api import guidelines as guidelines_api
from backend.app.api import auth as auth_api
from backend.app.api import submissions as submissions_api
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
from backend.app.pipeline.confidence import should_suppress_finding, suppressed_span_combinations
from backend.app.services.rate_limit import endpoint_rate_limiter
from backend.app.workers.dfi_worker import dfi_scores_are_stale


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
        dfi_computed_at=datetime.now(timezone.utc),
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


def test_health_headers_and_demo_login_gate(api_client, monkeypatch):
    client, _session_factory, _manager = api_client
    monkeypatch.setattr(auth_api, "get_settings", lambda: SimpleNamespace(DEMO_MODE=False))

    health = client.get("/healthz", headers={"X-Request-ID": "phase6-test-123"})
    assert health.status_code == 200
    assert health.headers["x-request-id"] == "phase6-test-123"
    assert health.headers["x-content-type-options"] == "nosniff"
    assert health.headers["x-frame-options"] == "DENY"
    assert "frame-ancestors 'none'" in health.headers["content-security-policy"]

    demo = client.post("/api/auth/demo-login", json={"role": "creator"})
    assert demo.status_code == 404


def test_demo_login_switches_only_to_seeded_active_role_accounts(api_client, monkeypatch):
    client, session_factory, _manager = api_client
    creator = User(
        id="demo-switch-creator",
        name="Demo Creator",
        email="creator@nexora.dev",
        password_hash="unused",
        role=UserRole.creator,
        is_active=True,
    )
    with session_factory.begin() as db:
        db.add(creator)
    monkeypatch.setattr(auth_api, "get_settings", lambda: SimpleNamespace(DEMO_MODE=True))

    response = client.post("/api/auth/demo-login", json={"role": "creator"})

    assert response.status_code == 200
    assert response.json()["token_type"] == "bearer"
    assert response.json()["access_token"]
    assert client.post("/api/auth/demo-login", json={"role": "manager"}).status_code == 503


def test_login_route_locks_out_repeated_invalid_password_attempts(api_client):
    client, _session_factory, _manager = api_client
    email = "lockout-route@example.test"
    from backend.app.services.auth import clear_login_failures
    clear_login_failures(email, "testclient")
    endpoint_rate_limiter._requests.pop(("testclient", "^/api/auth/login$"), None)

    for _ in range(5):
        response = client.post("/api/auth/login", json={"email": email, "password": "WrongPassword2026!"})
        assert response.status_code == 401
    locked = client.post("/api/auth/login", json={"email": email, "password": "WrongPassword2026!"})

    assert locked.status_code == 429
    assert int(locked.headers["retry-after"]) > 0
    clear_login_failures(email, "testclient")
    endpoint_rate_limiter._requests.pop(("testclient", "^/api/auth/login$"), None)


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


def test_guideline_health_recomputes_distinct_disputed_findings_and_clusters_reasons(api_client):
    client, session_factory, manager = api_client
    with session_factory.begin() as db:
        clause = _add_clause(db, "clause-dfi-live")
        clause.dfi_computed_at = None
        for index in range(2):
            submission_id = f"sub-dfi-{index}"
            version_id = f"ver-dfi-{index}"
            finding_id = f"finding-dfi-{index}"
            db.add(Submission(
                id=submission_id,
                creator_id=manager.id,
                title=f"DFI copy {index}",
            ))
            db.add(SubmissionVersion(
                id=version_id,
                submission_id=submission_id,
                version_no=1,
                text="Campaign wording",
                created_by=manager.id,
            ))
            db.add(Finding(
                id=finding_id,
                submission_id=submission_id,
                version_id=version_id,
                span_start=0,
                span_end=17,
                category=FindingCategory.tone,
                issue="Clarify the tone.",
                source_type=SourceType.guideline_clause,
                source_id=clause.id,
                severity=FindingSeverity.minor,
                confidence=FindingConfidence.high,
                status=FindingStatus.disputed if index == 0 else FindingStatus.open,
            ))
            if index == 0:
                db.add(Decision(
                    id="decision-dfi-0",
                    finding_id=finding_id,
                    user_id=manager.id,
                    action=DecisionAction.dispute,
                    reason="The tone rule is unclear.",
                ))

    response = client.get("/api/guidelines/health")

    assert response.status_code == 200
    clause_result = next(item for item in response.json() if item["id"] == "clause-dfi-live")
    assert clause_result["dispute_friction_index"] == 50.0
    assert clause_result["dispute_clusters"] == [{
        "count": 1,
        "examples": ["The tone rule is unclear."],
    }]
    with session_factory() as db:
        persisted = db.get(GuidelineClause, "clause-dfi-live")
        assert persisted.dfi_computed_at is not None
        assert not dfi_scores_are_stale(db)


def test_recompute_endpoint_reuses_request_session_and_reports_failure(api_client, monkeypatch):
    client, session_factory, _manager = api_client
    with session_factory.begin() as db:
        _add_clause(db, "clause-recompute")

    response = client.post("/api/guidelines/recompute")
    assert response.status_code == 200
    assert response.json()["updated_clauses"] == 1
    with session_factory() as db:
        assert db.get(GuidelineClause, "clause-recompute").dfi_computed_at is not None

    monkeypatch.setattr(guidelines_api, "run_dfi_worker", lambda _db: None)
    failed = client.post("/api/guidelines/recompute")
    assert failed.status_code == 503


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


def test_image_upload_requires_explicit_memory_budget_opt_in(api_client, monkeypatch):
    client, session_factory, _manager = api_client
    creator = User(
        id="image-upload-creator",
        name="Image Creator",
        email="image-creator@example.test",
        password_hash="unused",
        role=UserRole.creator,
        is_active=True,
    )
    with session_factory.begin() as db:
        db.add(creator)
    monkeypatch.setitem(app.dependency_overrides, get_current_user, lambda: creator)
    monkeypatch.setattr(
        submissions_api,
        "get_settings",
        lambda: SimpleNamespace(IMAGE_REVIEW_ENABLED=False),
    )

    response = client.post(
        "/api/submissions/upload",
        data={"title": "Image campaign"},
        files={"file": ("campaign.png", b"image bytes", "image/png")},
    )

    assert response.status_code == 503
    assert "IMAGE_REVIEW_ENABLED" in response.json()["detail"]


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
                category=FindingCategory.tone if index == 2 else FindingCategory.messaging,
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
    assert messaging["decisions_count"] == 2
    assert messaging["acceptance_rate"] == 0.0
    assert messaging["edit_rate"] == 0.0
    assert messaging["suppression_count"] == 1
    tone = next(item for item in response.json()["categories"] if item["category"] == "tone")
    assert tone["suppression_count"] == 1
    with session_factory() as db:
        patterns = suppressed_span_combinations(db)
    assert ("clause-repeat", "claim text") in patterns
    assert should_suppress_finding(
        {"source_type": SourceType.guideline_clause, "source_id": "clause-repeat"},
        "  CLAIM   TEXT ",
        patterns,
    )


def test_reviewer_dismissal_trains_feedback_and_invalidates_guideline_health(api_client, monkeypatch):
    client, session_factory, _manager = api_client
    reviewer = User(
        id="reviewer-feedback",
        name="Compliance Reviewer",
        email="reviewer-feedback@example.test",
        password_hash="unused",
        role=UserRole.reviewer,
        is_active=True,
    )
    creator = User(
        id="creator-reviewer-feedback",
        name="Content Creator",
        email="creator-reviewer-feedback@example.test",
        password_hash="unused",
        role=UserRole.creator,
        is_active=True,
    )
    submission_id = "reviewer-dismiss-submission"
    version_id = "reviewer-dismiss-version"
    finding_id = "reviewer-dismiss-finding"
    with session_factory.begin() as db:
        clause = _add_clause(db, "reviewer-dismiss-clause")
        db.add_all([reviewer, creator])
        db.add(Submission(
            id=submission_id,
            creator_id=creator.id,
            assigned_to_id=reviewer.id,
            title="Escalated claim",
            status=SubmissionStatus.in_review,
        ))
        db.add(SubmissionVersion(
            id=version_id,
            submission_id=submission_id,
            version_no=1,
            text="This product removes every stain.",
            created_by=creator.id,
        ))
        db.add(Finding(
            id=finding_id,
            submission_id=submission_id,
            version_id=version_id,
            span_start=0,
            span_end=34,
            category=FindingCategory.unsupported_claim,
            issue="The absolute claim needs review.",
            source_type=SourceType.guideline_clause,
            source_id=clause.id,
            severity=FindingSeverity.major,
            confidence=FindingConfidence.high,
            needs_human=True,
            suggested_rewrite="This product helps remove stains.",
            status=FindingStatus.open,
        ))

    # Override the manager fixture's default identity for this reviewer workflow.
    from backend.app.services.auth import get_current_user
    monkeypatch.setitem(app.dependency_overrides, get_current_user, lambda: reviewer)

    response = client.post(
        f"/api/findings/{finding_id}/escalate-review",
        json={"action": "dismiss", "justification": "The cited clause does not prohibit this supported claim."},
    )

    assert response.status_code == 200
    with session_factory() as db:
        decision = db.query(Decision).filter(Decision.finding_id == finding_id).one()
        assert decision.action == DecisionAction.dispute
        assert decision.original_span == "This product removes every stain."
        assert decision.suggested_rewrite == "This product helps remove stains."
        assert decision.reason == "The cited clause does not prohibit this supported claim."
        assert db.get(PreferenceModelState, "workspace-default").sample_count == 1
        assert db.get(GuidelineClause, "reviewer-dismiss-clause").dfi_computed_at is None
