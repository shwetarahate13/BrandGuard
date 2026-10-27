"""Integration coverage for the new guideline, media, and feedback APIs."""
import uuid
import io
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
import pdfplumber
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
    Notification,
    Approval,
    ApprovalDecision,
    PreferenceModelState,
    SourceType,
    Submission,
    SubmissionStatus,
    SubmissionVersion,
    User,
    UserRole,
)
from backend.app.services.auth import get_current_user, hash_password
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


def test_image_upload_requires_image_review_to_be_enabled(api_client, monkeypatch):
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
    assert "IMAGE_REVIEW_ENABLED=true" in response.json()["detail"]


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


def test_assignment_and_workflow_decisions_create_private_notifications(api_client, monkeypatch):
    client, session_factory, manager = api_client
    creator = User(
        id="notify-creator", name="Notify Creator", email="notify-creator@example.test",
        password_hash="x", role=UserRole.creator, is_active=True,
    )
    reviewer = User(
        id="notify-reviewer", name="Notify Reviewer", email="notify-reviewer@example.test",
        password_hash="x", role=UserRole.reviewer, is_active=True,
    )
    approved = Submission(
        id="notify-approved", creator_id=creator.id, title="Approved copy",
        status=SubmissionStatus.in_review,
    )
    changes = Submission(
        id="notify-changes", creator_id=creator.id, title="Copy with requested changes",
        status=SubmissionStatus.in_review,
    )
    rejected = Submission(
        id="notify-rejected", creator_id=creator.id, title="Rejected copy",
        status=SubmissionStatus.in_review,
    )
    with session_factory.begin() as db:
        db.add_all([
            creator,
            reviewer,
            approved,
            changes,
            rejected,
            SubmissionVersion(
                id="notify-approved-v1",
                submission_id=approved.id,
                version_no=1,
                text="Approved copy text for notification coverage.",
                created_by=creator.id,
            ),
        ])

    assigned = client.post(
        f"/api/submissions/{approved.id}/assign",
        json={"reviewer_id": reviewer.id},
    )
    assert assigned.status_code == 200, assigned.text

    monkeypatch.setitem(app.dependency_overrides, get_current_user, lambda: reviewer)
    reviewer_inbox = client.get("/api/notifications?unread_only=true")
    assert reviewer_inbox.status_code == 200
    assert len(reviewer_inbox.json()) == 1
    assignment_notice = reviewer_inbox.json()[0]
    assert assignment_notice["kind"] == "review_assignment"
    assert assignment_notice["submission_id"] == approved.id
    assert "Approved copy" in assignment_notice["message"]
    assert assignment_notice["is_read"] is False

    # A different authenticated user cannot read or change the reviewer's notification.
    monkeypatch.setitem(app.dependency_overrides, get_current_user, lambda: creator)
    assert client.patch(f"/api/notifications/{assignment_notice['id']}/read").status_code == 404

    monkeypatch.setitem(app.dependency_overrides, get_current_user, lambda: manager)
    approval = client.post(
        f"/api/submissions/{approved.id}/approve",
        json={"decision": "approved", "note": "Approved for launch."},
    )
    assert approval.status_code == 200, approval.text
    change_response = client.post(
        f"/api/submissions/{changes.id}/reject",
        json={"decision": "changes_requested", "note": "Update the supporting claim."},
    )
    assert change_response.status_code == 200, change_response.text
    rejection = client.post(
        f"/api/submissions/{rejected.id}/reject",
        json={"decision": "rejected", "note": "This copy is outside the brief."},
    )
    assert rejection.status_code == 200, rejection.text

    monkeypatch.setitem(app.dependency_overrides, get_current_user, lambda: creator)
    inbox = client.get("/api/notifications")
    assert inbox.status_code == 200
    notices = inbox.json()
    assert len(notices) == 3
    assert {item["title"] for item in notices} == {
        "Submission approved", "Changes requested", "Submission rejected",
    }
    approval_notice = next(item for item in notices if item["submission_id"] == approved.id)
    assert "Approved for launch." in approval_notice["message"]
    marked = client.patch("/api/notifications/read-all")
    assert marked.json()["updated_count"] == 3
    assert client.get("/api/notifications?unread_only=true").json() == []

    with session_factory() as db:
        assert db.query(Notification).count() == 4


def test_assignment_due_dates_are_manager_only_and_expose_overdue_state(api_client, monkeypatch):
    client, session_factory, manager = api_client
    creator = User(
        id="due-creator", name="Due Creator", email="due-creator@example.test",
        password_hash="unused", role=UserRole.creator, is_active=True,
    )
    reviewer = User(
        id="due-reviewer", name="Due Reviewer", email="due-reviewer@example.test",
        password_hash="unused", role=UserRole.reviewer, is_active=True,
    )
    active = Submission(
        id="due-active", creator_id=creator.id, title="Due date review",
        status=SubmissionStatus.in_review,
    )
    unassigned = Submission(
        id="due-unassigned", creator_id=creator.id, title="Unassigned review",
        status=SubmissionStatus.in_review,
    )
    with session_factory.begin() as db:
        db.add_all([creator, reviewer, active, unassigned])

    assigned = client.post(f"/api/submissions/{active.id}/assign", json={"reviewer_id": reviewer.id})
    assert assigned.status_code == 200, assigned.text
    assert assigned.json()["assignment_due_at"] is not None
    assert assigned.json()["assignment_due_at"].endswith(("Z", "+00:00"))

    overdue = client.patch(
        f"/api/submissions/{active.id}/due-date",
        json={"assignment_due_at": "2020-01-01T00:00:00Z"},
    )
    assert overdue.status_code == 200, overdue.text
    assert overdue.json()["assignment_due_at"].startswith("2020-01-01T00:00:00")
    rows = client.get("/api/submissions").json()
    assert next(row for row in rows if row["id"] == active.id)["is_overdue"] is True

    monkeypatch.setitem(app.dependency_overrides, get_current_user, lambda: reviewer)
    reviewer_rows = client.get("/api/submissions").json()
    reviewer_item = next(row for row in reviewer_rows if row["id"] == active.id)
    assert reviewer_item["assignment_due_at"].startswith("2020-01-01T00:00:00")
    assert reviewer_item["is_overdue"] is True
    assert client.patch(
        f"/api/submissions/{active.id}/due-date",
        json={"assignment_due_at": None},
    ).status_code == 403

    monkeypatch.setitem(app.dependency_overrides, get_current_user, lambda: creator)
    assert client.patch(
        f"/api/submissions/{active.id}/due-date",
        json={"assignment_due_at": None},
    ).status_code == 403

    monkeypatch.setitem(app.dependency_overrides, get_current_user, lambda: manager)
    cleared = client.patch(
        f"/api/submissions/{active.id}/due-date",
        json={"assignment_due_at": None},
    )
    assert cleared.status_code == 200, cleared.text
    assert cleared.json()["assignment_due_at"] is None
    rows = client.get("/api/submissions").json()
    assert next(row for row in rows if row["id"] == active.id)["is_overdue"] is False
    assert client.patch(
        f"/api/submissions/{unassigned.id}/due-date",
        json={"assignment_due_at": "2030-01-01T00:00:00Z"},
    ).status_code == 409


def test_approval_report_exports_are_role_protected_and_filterable(api_client, monkeypatch):
    client, session_factory, manager = api_client
    creator = User(
        id="report-creator", name="Report Creator", email="report-creator@example.test",
        password_hash="unused", role=UserRole.creator, is_active=True,
    )
    admin = User(
        id="report-admin", name="Report Admin", email="report-admin@example.test",
        password_hash="unused", role=UserRole.admin, is_active=True,
    )
    approved = Submission(
        id="report-approved", creator_id=creator.id, title="=1+1 injected title",
        status=SubmissionStatus.approved,
    )
    rejected = Submission(
        id="report-rejected", creator_id=creator.id, title="Rejected campaign",
        status=SubmissionStatus.rejected,
    )
    with session_factory.begin() as db:
        db.add_all([creator, admin, approved, rejected])
        db.flush()
        db.add_all([
            Approval(
                id="report-approval-one", submission_id=approved.id, user_id=manager.id,
                decision=ApprovalDecision.approved, note="Approved for release",
                created_at=datetime(2026, 10, 1),
            ),
            Approval(
                id="report-approval-two", submission_id=rejected.id, user_id=manager.id,
                decision=ApprovalDecision.rejected, note="Missing evidence",
                created_at=datetime(2026, 10, 10),
            ),
        ])

    csv_response = client.get("/api/reports/approvals.csv")
    assert csv_response.status_code == 200
    assert "text/csv" in csv_response.headers["content-type"]
    assert 'attachment; filename="brandguard_approval_report.csv"' == csv_response.headers["content-disposition"]
    assert "'=1+1 injected title" in csv_response.text
    assert "Approved for release" in csv_response.text
    filtered = client.get("/api/reports/approvals.csv?start_date=2026-10-05T00:00:00Z")
    assert filtered.status_code == 200
    assert "Rejected campaign" in filtered.text
    assert "=1+1 injected title" not in filtered.text
    assert client.get(
        "/api/reports/approvals.csv?start_date=2026-10-20T00:00:00Z&end_date=2026-10-01T00:00:00Z"
    ).status_code == 422

    pdf_response = client.get("/api/reports/approvals.pdf")
    assert pdf_response.status_code == 200
    assert pdf_response.headers["content-type"] == "application/pdf"
    assert pdf_response.content.startswith(b"%PDF-1.4")
    assert b"Approved for release" in pdf_response.content
    assert b"Rejected campaign" in pdf_response.content
    with pdfplumber.open(io.BytesIO(pdf_response.content)) as document:
        extracted_pdf_text = "\n".join(page.extract_text() or "" for page in document.pages)
    assert "BrandGuard Approval Report" in extracted_pdf_text
    assert "Approved for release" in extracted_pdf_text

    monkeypatch.setitem(app.dependency_overrides, get_current_user, lambda: creator)
    assert client.get("/api/reports/approvals.csv").status_code == 403
    assert client.get("/api/reports/approvals.pdf").status_code == 403
    reviewer = User(
        id="report-reviewer", name="Report Reviewer", email="report-reviewer@example.test",
        password_hash="unused", role=UserRole.reviewer, is_active=True,
    )
    monkeypatch.setitem(app.dependency_overrides, get_current_user, lambda: reviewer)
    assert client.get("/api/reports/approvals.csv").status_code == 403
    assert client.get("/api/reports/approvals.pdf").status_code == 403
    monkeypatch.setitem(app.dependency_overrides, get_current_user, lambda: admin)
    assert client.get("/api/reports/approvals.csv").status_code == 200
    assert client.get("/api/reports/approvals.pdf").status_code == 200


def test_self_service_password_change_verifies_current_password_and_preserves_demo_credentials(api_client, monkeypatch):
    client, session_factory, _manager = api_client
    current_password = "OldAccountPass2026!"
    new_password = "NewAccountPass2026!"
    user = User(
        id="password-change-user", name="Password Change User", email="password-change@example.test",
        password_hash=hash_password(current_password), role=UserRole.creator, is_active=True,
    )
    demo_user = User(
        id="password-change-demo", name="Demo Creator", email="creator@nexora.dev",
        password_hash=hash_password(current_password), role=UserRole.creator, is_active=True,
    )
    with session_factory.begin() as db:
        db.add_all([user, demo_user])
    monkeypatch.setattr(auth_api, "get_settings", lambda: SimpleNamespace(DEMO_MODE=False))
    monkeypatch.setitem(app.dependency_overrides, get_current_user, lambda: user)

    assert client.post("/api/auth/change-password", json={
        "current_password": "WrongCurrentPass2026!", "new_password": new_password,
    }).status_code == 400
    assert client.post("/api/auth/change-password", json={
        "current_password": current_password, "new_password": current_password,
    }).status_code == 400
    assert client.post("/api/auth/change-password", json={
        "current_password": current_password, "new_password": "Badpass123!",
    }).status_code == 422
    assert client.post("/api/auth/change-password", json={
        "current_password": current_password, "new_password": "😀" * 25,
    }).status_code == 422

    changed = client.post("/api/auth/change-password", json={
        "current_password": current_password, "new_password": new_password,
    })
    assert changed.status_code == 200, changed.text
    assert client.post("/api/auth/login", json={
        "email": user.email, "password": current_password,
    }).status_code == 401
    assert client.post("/api/auth/login", json={
        "email": user.email, "password": new_password,
    }).status_code == 200

    monkeypatch.setattr(auth_api, "get_settings", lambda: SimpleNamespace(DEMO_MODE=True))
    monkeypatch.setitem(app.dependency_overrides, get_current_user, lambda: demo_user)
    assert client.post("/api/auth/change-password", json={
        "current_password": current_password, "new_password": new_password,
    }).status_code == 403


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
