"""Integration test covering full workflow and role-based guards:
Login -> Submit -> Check -> Decide (diff/accept) -> Request Review -> RBAC checks -> Approve -> History -> Insights.
"""
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.database import get_session_factory
from backend.app.seed import run_seed

client = TestClient(app)


def test_full_governance_workflow_and_rbac():
    # 0. Seed database
    db = get_session_factory()()
    run_seed(db)
    db.close()

    # 1. Login with demo accounts
    res_creator = client.post("/api/auth/login", json={"email": "creator@nexora.dev", "password": "Creator123!"})
    assert res_creator.status_code == 200, res_creator.text
    tok_creator = res_creator.json()["access_token"]
    h_creator = {"Authorization": f"Bearer {tok_creator}"}

    res_manager = client.post("/api/auth/login", json={"email": "manager@nexora.dev", "password": "Manager123!"})
    assert res_manager.status_code == 200
    tok_manager = res_manager.json()["access_token"]
    h_manager = {"Authorization": f"Bearer {tok_manager}"}

    # 2. Creator creates submission
    submit_payload = {
        "title": "E2E Campaign Draft",
        "intent": "Introduce our fairly priced artisan sourdough bread to regional community",
        "content_type": "text",
        "text": "Our cheap sourdough loaves are guaranteed to please everyone. Visit our website [click here] for more."
    }
    res_sub = client.post("/api/submissions", json=submit_payload, headers=h_creator)
    assert res_sub.status_code == 200
    sub_data = res_sub.json()
    sub_id = sub_data["id"]
    assert sub_data["status"] == "draft"

    # 3. Creator runs review check
    res_check = client.post(f"/api/submissions/{sub_id}/check", headers=h_creator)
    assert res_check.status_code == 200
    check_data = res_check.json()
    assert check_data["findings_count"] >= 2
    assert check_data["submission_status"] == "checked"

    # 4. View findings
    res_findings = client.get(f"/api/submissions/{sub_id}/findings", headers=h_creator)
    assert res_findings.status_code == 200
    findings = res_findings.json()
    assert len(findings) >= 2

    # Find the terminology finding for 'cheap'
    term_finding = next((f for f in findings if "cheap" in f["issue"].lower()), None)
    assert term_finding is not None
    assert term_finding["suggested_rewrite"] is not None

    # 5. Creator accepts the rewrite (diff applied, new version created)
    res_decide = client.post(
        f"/api/findings/{term_finding['id']}/decision",
        json={"action": "accept"},
        headers=h_creator,
    )
    assert res_decide.status_code == 200

    # Verify new version created with accepted rewrite
    res_sub_updated = client.get(f"/api/submissions/{sub_id}", headers=h_creator)
    assert res_sub_updated.status_code == 200
    versions = res_sub_updated.json()["versions"]
    assert len(versions) >= 2
    assert term_finding["suggested_rewrite"] in versions[-1]["text"]

    # 6. Creator requests review
    res_req = client.post(f"/api/submissions/{sub_id}/request-review", headers=h_creator)
    assert res_req.status_code == 200
    assert res_req.json()["submission_status"] == "in_review"

    # 7. RBAC Guard: Creator CANNOT approve their own submission
    res_creator_approve = client.post(
        f"/api/submissions/{sub_id}/approve",
        json={"decision": "approved", "note": "Trying to self-approve"},
        headers=h_creator,
    )
    assert res_creator_approve.status_code == 403

    # 8. Manager adds comment
    res_comm = client.post(
        f"/api/submissions/{sub_id}/comments",
        json={"body": "Content verified against term registry. Looking good for final approval."},
        headers=h_manager,
    )
    assert res_comm.status_code == 200

    # 9. Manager approves submission
    res_mgr_approve = client.post(
        f"/api/submissions/{sub_id}/approve",
        json={"decision": "approved", "note": "Approved by Brand Manager"},
        headers=h_manager,
    )
    assert res_mgr_approve.status_code == 200
    assert res_mgr_approve.json()["decision"] == "approved"

    # Verify submission status is now approved
    res_final = client.get(f"/api/submissions/{sub_id}", headers=h_manager)
    assert res_final.json()["status"] == "approved"

    # 10. Check audit history
    res_hist = client.get(f"/api/submissions/{sub_id}/history", headers=h_manager)
    assert res_hist.status_code == 200
    hist_data = res_hist.json()
    assert len(hist_data["versions"]) >= 2
    assert len(hist_data["approvals"]) >= 1
    assert len(hist_data["comments"]) >= 1
    assert len(hist_data["audit_logs"]) >= 1

    # 11. Check insights
    res_insights = client.get("/api/insights/summary", headers=h_manager)
    assert res_insights.status_code == 200
    insights = res_insights.json()
    assert insights["total_submissions"] >= 1
    assert insights["accepted_count"] >= 1
    assert "terminology" in insights["findings_by_category"]
