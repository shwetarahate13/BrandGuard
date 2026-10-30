"""Role-facing API journeys complement the permission-matrix unit tests."""
from fastapi.testclient import TestClient

from backend.app.database import get_session_factory
from backend.app.main import app
from backend.app.models.models import SubmissionStatus
from backend.app.seed import run_seed

client = TestClient(app)


def _demo_auth(role: str) -> dict[str, str]:
    response = client.post("/api/auth/demo-login", json={"role": role})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_admin_main_journey_covers_sources_feedback_audit_and_approval_boundary(monkeypatch):
    monkeypatch.setattr("backend.app.api.admin.index_all_sources", lambda _db: None)
    with get_session_factory()() as db:
        run_seed(db)

    admin = _demo_auth("admin")
    assert client.get("/api/admin/users", headers=admin).status_code == 200
    assert client.get("/api/admin/facts", headers=admin).status_code == 200
    structured_fact = client.post(
        "/api/admin/facts",
        json={
            "statement": "Bright Desk plan costs $39 per month.",
            "subject": "Bright Desk plan",
            "value": "$39",
            "unit": "per month",
            "source_note": "Approved pricing sheet",
        },
        headers=admin,
    )
    assert structured_fact.status_code == 200, structured_fact.text
    assert structured_fact.json()["value"] == "$39"
    assert client.get("/api/admin/guidelines", headers=admin).status_code == 200
    assert client.get("/api/guidelines/health", headers=admin).status_code == 200
    assert client.get("/api/feedback/stats", headers=admin).status_code == 200
    assert client.get("/api/admin/audit-logs", headers=admin).status_code == 200
    assert client.get("/api/system/status", headers=admin).json()["database_connected"] is True

    submissions = client.get("/api/submissions", headers=admin).json()
    gated = next(item for item in submissions if item["status"] == SubmissionStatus.in_review.value)
    approval = client.post(
        f"/api/submissions/{gated['id']}/approve",
        json={"decision": "approved", "note": "Admin must not approve."},
        headers=admin,
    )
    assert approval.status_code == 403

    reviewer = _demo_auth("reviewer")
    metrics = client.get("/api/submissions/reviewer-metrics", headers=reviewer)
    assert metrics.status_code == 200, metrics.text
    assert {"confirmed", "dismissed", "overturned_rate"} <= metrics.json().keys()
