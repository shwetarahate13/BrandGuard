"""Integration test covering full workflow and role-based guards:
Login -> Submit -> Check -> Decide (diff/accept) -> Request Review -> RBAC checks -> Approve -> History -> Insights.
"""
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.database import get_session_factory
from backend.app.seed import run_seed
from backend.app.models.models import Approval, Decision

client = TestClient(app)


def test_full_governance_workflow_and_rbac():
    # 0. Seed database
    db = get_session_factory()()
    run_seed(db)
    db.close()

    # 1. Login with demo accounts
    res_creator = client.post("/api/auth/login", json={"email": "creator@nexora.dev", "password": "CreatorDemo2026!"})
    assert res_creator.status_code == 200, res_creator.text
    tok_creator = res_creator.json()["access_token"]
    h_creator = {"Authorization": f"Bearer {tok_creator}"}

    res_manager = client.post("/api/auth/login", json={"email": "manager@nexora.dev", "password": "ManagerDemo2026!"})
    assert res_manager.status_code == 200
    tok_manager = res_manager.json()["access_token"]
    h_manager = {"Authorization": f"Bearer {tok_manager}"}

    # 2. Creator creates submission
    submit_payload = {
        "title": "E2E Campaign Draft",
        "intent": "Introduce our fairly priced artisan sourdough bread to regional community",
        "content_type": "text",
        "text": "Teh bakery accomodate our patrons. Our cheap sourdough loaves bring warmth to your table. Visit our website [click here] for more."
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
    fix_finding = next((f for f in findings if f.get("suggested_rewrite") and not f.get("needs_human")), None)
    assert fix_finding is not None

    # 5. Creator accepts the rewrite (diff applied, new version created)
    res_decide = client.post(
        f"/api/findings/{fix_finding['id']}/decision",
        json={"action": "accept"},
        headers=h_creator,
    )
    assert res_decide.status_code == 200
    duplicate_accept = client.post(
        f"/api/findings/{fix_finding['id']}/decision",
        json={"action": "accept"},
        headers=h_creator,
    )
    assert duplicate_accept.status_code == 409

    # Verify new version created with accepted rewrite
    res_sub_updated = client.get(f"/api/submissions/{sub_id}", headers=h_creator)
    assert res_sub_updated.status_code == 200
    versions = res_sub_updated.json()["versions"]
    assert len(versions) >= 2
    assert fix_finding["suggested_rewrite"] in versions[-1]["text"]

    # A rewrite creates a new draft version; it must be checked before resubmission.
    res_req_early = client.post(f"/api/submissions/{sub_id}/request-review", headers=h_creator)
    assert res_req_early.status_code == 400
    res_recheck = client.post(f"/api/submissions/{sub_id}/check", headers=h_creator)
    assert res_recheck.status_code == 200
    assert res_recheck.json()["submission_status"] == "checked"

    # 6. Creator requests review
    res_req = client.post(f"/api/submissions/{sub_id}/request-review", headers=h_creator)
    assert res_req.status_code == 200
    assert res_req.json()["submission_status"] == "in_review"
    assert client.post(f"/api/submissions/{sub_id}/request-review", headers=h_creator).status_code == 409

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
    repeated_approval = client.post(
        f"/api/submissions/{sub_id}/approve",
        json={"decision": "approved", "note": "Duplicate click"},
        headers=h_manager,
    )
    assert repeated_approval.status_code == 409
    with get_session_factory()() as db:
        assert db.query(Approval).filter(Approval.submission_id == sub_id).count() == 1

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


def test_edit_dispute_changes_rejection_resubmission_and_review_assignment():
    db = get_session_factory()()
    run_seed(db)
    db.close()

    def login(email, password):
        response = client.post("/api/auth/login", json={"email": email, "password": password})
        assert response.status_code == 200, response.text
        return {"Authorization": f"Bearer {response.json()['access_token']}"}

    creator = login("creator@nexora.dev", "CreatorDemo2026!")
    manager = login("manager@nexora.dev", "ManagerDemo2026!")
    reviewer = login("reviewer@nexora.dev", "ReviewerDemo2026!")

    # Edit and dispute findings, get changes requested, then resubmit a new revision.
    created = client.post("/api/submissions", headers=creator, json={
        "title": "Revision lifecycle coverage",
        "intent": "Describe our sourdough clearly to the community.",
        "content_type": "text",
        "text": "Our cheap sourdough is baked with care. Visit [click here] for details.",
    })
    assert created.status_code == 200, created.text
    submission_id = created.json()["id"]
    assert client.post(f"/api/submissions/{submission_id}/check", headers=creator).status_code == 200
    findings = client.get(f"/api/submissions/{submission_id}/findings", headers=creator).json()
    term_finding = next(item for item in findings if "cheap" in item["issue"].lower())
    edited = client.post("/api/decisions", headers=creator, json={
        "finding_id": term_finding["id"],
        "action": "edit",
        "edited_text": "fairly priced",
    })
    assert edited.status_code == 200, edited.text
    assert edited.json()["action"] == "edit"
    version = client.get(f"/api/submissions/{submission_id}", headers=creator).json()["versions"][-1]
    assert "fairly priced" in version["text"]
    assert client.post(f"/api/submissions/{submission_id}/check", headers=creator).status_code == 200

    latest_findings = client.get(f"/api/submissions/{submission_id}/findings", headers=creator).json()
    link_finding = next(item for item in latest_findings if "link" in item["issue"].lower())
    disputed = client.post("/api/decisions", headers=creator, json={
        "finding_id": link_finding["id"],
        "action": "dispute",
        "reason": "The link label is descriptive in the live campaign context.",
    })
    assert disputed.status_code == 200, disputed.text
    assert disputed.json()["action"] == "dispute"
    repeated_dispute = client.post("/api/decisions", headers=creator, json={
        "finding_id": link_finding["id"],
        "action": "dispute",
        "reason": "Repeated submit should not create a second decision.",
    })
    assert repeated_dispute.status_code == 409
    with get_session_factory()() as db:
        assert db.query(Decision).filter(Decision.finding_id == link_finding["id"]).count() == 1
    assert client.post(f"/api/submissions/{submission_id}/request-review", headers=creator).status_code == 200

    changes = client.post(f"/api/submissions/{submission_id}/reject", headers=manager, json={
        "decision": "changes_requested",
        "note": "Please update the final copy before approval.",
    })
    assert changes.status_code == 200, changes.text
    assert changes.json()["decision"] == "changes_requested"
    submitted_version = client.post(f"/api/submissions/{submission_id}/versions", headers=creator, json={
        "text": "Aurelia Artisan Pantry sourdough is baked with care. Read our sourdough details page.",
    })
    assert submitted_version.status_code == 200, submitted_version.text
    assert client.post(f"/api/submissions/{submission_id}/check", headers=creator).status_code == 200
    assert client.post(f"/api/submissions/{submission_id}/request-review", headers=creator).status_code == 200

    rejection = client.post(f"/api/submissions/{submission_id}/reject", headers=manager, json={
        "decision": "rejected",
        "note": "The revised draft does not match the approved campaign brief.",
    })
    assert rejection.status_code == 200, rejection.text
    assert rejection.json()["decision"] == "rejected"
    final_version = client.post(f"/api/submissions/{submission_id}/versions", headers=creator, json={
        "text": "Our sourdough is made for sharing at the table.",
    })
    assert final_version.status_code == 200, final_version.text
    assert client.post(f"/api/submissions/{submission_id}/check", headers=creator).status_code == 200
    assert client.post(f"/api/submissions/{submission_id}/request-review", headers=creator).status_code == 200
    approved = client.post(f"/api/submissions/{submission_id}/approve", headers=manager, json={
        "decision": "approved",
        "note": "Updated submission approved.",
    })
    assert approved.status_code == 200, approved.text
    assert client.get(f"/api/submissions/{submission_id}", headers=manager).json()["status"] == "approved"

    # A high-risk item must be assigned and signed off by the compliance reviewer.
    high_risk = client.post("/api/submissions", headers=creator, json={
        "title": "Compliance escalation coverage",
        "intent": "Describe the botanical blend.",
        "content_type": "text",
        "text": "Our botanical blend cures digestive illness.",
    })
    assert high_risk.status_code == 200, high_risk.text
    high_risk_id = high_risk.json()["id"]
    assert client.post(f"/api/submissions/{high_risk_id}/check", headers=creator).status_code == 200
    assert client.post(f"/api/submissions/{high_risk_id}/request-review", headers=creator).status_code == 200
    reviewer_id = next(
        item["id"] for item in client.get("/api/submissions/reviewers", headers=manager).json()
        if item["email"] == "reviewer@nexora.dev"
    )
    assigned = client.post(f"/api/submissions/{high_risk_id}/assign", headers=manager, json={"reviewer_id": reviewer_id})
    assert assigned.status_code == 200, assigned.text
    assert assigned.json()["assigned_to_id"] == reviewer_id
    assert client.get(f"/api/submissions/{high_risk_id}", headers=reviewer).status_code == 200
    creator_self_approval = client.post(f"/api/submissions/{high_risk_id}/approve", headers=creator, json={
        "decision": "approved",
        "note": "Self approval must fail.",
    })
    assert creator_self_approval.status_code == 403
    manager_approval = client.post(f"/api/submissions/{high_risk_id}/approve", headers=manager, json={
        "decision": "approved",
        "note": "High-risk approval must come from the reviewer.",
    })
    assert manager_approval.status_code == 403
    high_risk_findings = client.get(f"/api/submissions/{high_risk_id}/findings", headers=reviewer).json()
    for finding in high_risk_findings:
        if finding["needs_human"] or finding["severity"] in ("critical", "major") or finding["category"] == "unsupported_claim":
            reviewed = client.post(f"/api/findings/{finding['id']}/escalate-review", headers=reviewer, json={
                "action": "confirm", "justification": "Claim reviewed against cited evidence and confirmed."
            })
            assert reviewed.status_code == 200, reviewed.text
    signoff = client.post(f"/api/submissions/{high_risk_id}/reviewer-signoff", headers=reviewer, json={
        "checklist": {"claims_verified": True, "facts_current": True, "accessibility_reviewed": True, "legal_wording_reviewed": True},
        "evidence_notes": "Reviewed the approved fact and source excerpt for this claim.",
        "justification": "Compliance review is complete; all findings are resolved."
    })
    assert signoff.status_code == 200, signoff.text
    reviewer_approval = client.post(f"/api/submissions/{high_risk_id}/approve", headers=reviewer, json={
        "decision": "approved",
        "note": "Reviewer cannot give final approval.",
    })
    assert reviewer_approval.status_code == 403
    manager_approval = client.post(f"/api/submissions/{high_risk_id}/approve", headers=manager, json={
        "decision": "approved", "note": "Reviewer sign-off checked; final manager approval."
    })
    assert manager_approval.status_code == 200, manager_approval.text
