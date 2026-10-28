#!/usr/bin/env python3
"""BrandGuard Production Smoke Test Script.

Usage:
    python scripts/smoke_test.py [BASE_URL]

Tests:
1. Health check (/healthz and /api/health)
2. Public runtime mode and admin-only system status
3. SPA frontend root serving (/)
4. Authentication for all 4 demo accounts (Creator, Manager, Reviewer, Admin)
5. Full governance pipeline:
   - Submit text with stated intent
   - Run governance check
   - Verify citations & quotes
   - Accept intent-preserving diff rewrite (v1 -> v2)
   - Creator requests review
   - RBAC check (Creator blocked from approving)
   - Manager assigns escalated work; reviewer records a justified sign-off
   - Verify history & insights metrics
"""
import os
import sys
import time
from pathlib import Path
import httpx

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

DEFAULT_BASE_URL = "http://localhost:8000"


def run_background_check(client, submission_id: str, headers: dict[str, str]) -> dict:
    response = client.post(f"/api/submissions/{submission_id}/check?background=true", headers=headers)
    assert response.status_code == 202, f"Background check was not accepted: {response.text}"
    job = response.json()
    deadline = time.monotonic() + 310
    while time.monotonic() < deadline:
        state_response = client.get(f"/api/jobs/{job['id']}", headers=headers)
        assert state_response.status_code == 200, f"Background job status failed: {state_response.text}"
        state = state_response.json()
        if state["status"] == "completed":
            return state["result"]
        if state["status"] == "failed":
            raise AssertionError(f"Background review failed: {state['error']}")
        time.sleep(0.25)
    raise AssertionError("Background review exceeded the smoke-test timeout")


def run_background_upload(client, filename: str, mime_type: str, headers: dict[str, str]) -> tuple[dict, dict]:
    sample = Path(__file__).resolve().parents[1] / "samples" / filename
    with sample.open("rb") as handle:
        response = client.post(
            "/api/submissions/upload?background=true",
            headers=headers,
            data={"title": f"Smoke {filename}", "intent": "Verify format-aware extraction"},
            files={"file": (filename, handle, mime_type)},
        )
    assert response.status_code == 202, f"Background upload was not accepted: {response.text}"
    job = response.json()
    deadline = time.monotonic() + 185
    while time.monotonic() < deadline:
        state_response = client.get(f"/api/jobs/{job['id']}", headers=headers)
        assert state_response.status_code == 200, f"Upload job status failed: {state_response.text}"
        state = state_response.json()
        if state["status"] == "completed":
            submission_response = client.get(f"/api/submissions/{job['submission_id']}", headers=headers)
            assert submission_response.status_code == 200, submission_response.text
            return submission_response.json(), state
        if state["status"] == "failed":
            raise AssertionError(f"Background extraction failed: {state['error']}")
        time.sleep(0.25)
    raise AssertionError("Background extraction exceeded the smoke-test timeout")


def run_smoke_test(base_url: str):
    print("=" * 65)
    print(f"BrandGuard Local Smoke Test -> {base_url}")
    print("=" * 65)

    if base_url in ("inprocess", "--inprocess", "local", "testclient"):
        from fastapi.testclient import TestClient
        from backend.app.main import app
        client = TestClient(app)
        client.__enter__()
        healthy = True
        r_healthz = client.get("/healthz")
        assert r_healthz.status_code == 200 and r_healthz.json().get("status") == "ok", f"/healthz returned {r_healthz.status_code}: {r_healthz.text}"
        print(f"  ✓ /healthz returned 200 OK: {r_healthz.json()} (in-process)")
        r = client.get("/api/health")
        assert r.status_code == 200, f"/api/health returned {r.status_code}: {r.text}"
        print(f"  ✓ /api/health returned 200 OK: {r.json()} (in-process)")
    else:
        client = httpx.Client(base_url=base_url, timeout=30.0)

        # 1. Health check
        print("\n[Step 1] Checking /api/health...")
        max_wait = 60
        start_time = time.time()
        healthy = False

        while time.time() - start_time < max_wait:
            try:
                r = client.get("/healthz")
                if r.status_code == 200:
                    assert r.json().get("status") == "ok", f"/healthz returned unexpected body: {r.text}"
                    print(f"  ✓ /healthz returned 200 OK: {r.json()}")
                    r = client.get("/api/health")
                if r.status_code == 200:
                    print(f"  ✓ /api/health returned 200 OK: {r.json()} (waited {time.time()-start_time:.1f}s)")
                    healthy = True
                    break
            except Exception:
                time.sleep(2)

        if not healthy:
            print("  ✗ Health check failed after 60s timeout.")
            sys.exit(1)

    # 2. Public runtime mode (detailed system status requires Admin)
    print("\n[Step 2] Checking public runtime mode...")
    r = client.get("/api/system/mode")
    assert r.status_code == 200 and "llm_mode" in r.json(), f"System mode failed: {r.text}"
    print(f"  ✓ Active review mode: {r.json()['llm_mode']}")

    # 3. Static SPA Serving
    print("\n[Step 3] Verifying Single-Service Frontend Serving (GET /)...")
    r = client.get("/")
    assert r.status_code == 200, f"Frontend root failed: {r.status_code}"
    assert "BrandGuard" in r.text or "<div id=\"root\">" in r.text
    print("  ✓ Root / successfully returned compiled React SPA index.html")

    # 4. Authentication with all 4 demo accounts
    print("\n[Step 4] Authenticating demo user accounts...")
    demo_creds = [
        ("Creator", "creator@nexora.dev", "CreatorDemo2026!"),
        ("Manager", "manager@nexora.dev", "ManagerDemo2026!"),
        ("Reviewer", "reviewer@nexora.dev", "ReviewerDemo2026!"),
        ("Admin", "admin@nexora.dev", "AdminDemo2026!"),
    ]
    tokens = {}
    user_ids = {}

    for role_name, email, pwd in demo_creds:
        r = client.post("/api/auth/login", json={"email": email, "password": pwd})
        assert r.status_code == 200, f"Login failed for {role_name}: {r.text}"
        tok = r.json()["access_token"]
        tokens[role_name] = tok

        # Verify /auth/me
        r_me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {tok}"})
        assert r_me.status_code == 200
        me = r_me.json()
        user_ids[role_name] = me["id"]
        print(f"  ✓ {role_name} Authenticated: {me['name']} ({me['email']}) -> role={me['role']}")

    print("\n[Step 4b] Verifying Admin-only system status...")
    admin_auth = {"Authorization": f"Bearer {tokens['Admin']}"}
    r = client.get("/api/system/status", headers=admin_auth)
    assert r.status_code == 200, f"Admin system status failed: {r.text}"
    status_data = r.json()
    assert status_data["database_connected"]
    assert client.get("/api/system/status", headers={"Authorization": f"Bearer {tokens['Creator']}"}).status_code == 403
    print(f"  ✓ Admin-only health status verified: DB={status_data['database_connected']}, index={status_data['chroma_indexed']}")

    creator_auth = {"Authorization": f"Bearer {tokens['Creator']}"}
    manager_auth = {"Authorization": f"Bearer {tokens['Manager']}"}

    # 5. Full Governance Flow
    print("\n[Step 5] Running Full Governance Workflow...")

    # A. Submit content
    submission_payload = {
        "title": "Smoke Test Campaign Announcement",
        "intent": "Announce seasonal artisan sourdough and highlight fairly priced pantry boxes",
        "content_type": "text",
        "text": "Teh bakery accomodate our patrons."
    }
    r = client.post("/api/submissions", json=submission_payload, headers=creator_auth)
    assert r.status_code == 200, f"Submission creation failed: {r.text}"
    sub = r.json()
    sub_id = sub["id"]
    print(f"  ✓ Created Submission #{sub_id} (Status: {sub['status']})")

    # B. Trigger check
    check_res = run_background_check(client, sub_id, creator_auth)
    print(f"  ✓ Review Pipeline Completed: {check_res['findings_count']} findings generated (Status: {check_res['submission_status']})")

    print("\n[Step 5b] Verifying background PDF and image extraction...")
    pdf_submission, _pdf_job = run_background_upload(client, "campaign-copy.pdf", "application/pdf", creator_auth)
    pdf_version = pdf_submission["versions"][-1]
    assert pdf_version["text"].strip() and pdf_version["source_layout"]["pages"], "PDF extraction must save text and page layout"
    pdf_review = run_background_check(client, pdf_submission["id"], creator_auth)
    pdf_findings_response = client.get(f"/api/submissions/{pdf_submission['id']}/findings", headers=creator_auth)
    assert pdf_findings_response.status_code == 200, pdf_findings_response.text
    pdf_findings = pdf_findings_response.json()
    assert any(finding.get("location", {}).get("page") for finding in pdf_findings), "PDF findings should have page locations"
    print(f"  ✓ PDF worker extracted {len(pdf_version['text'])} characters and saved {pdf_review['findings_count']} located findings")

    image_submission, _image_job = run_background_upload(client, "campaign-image.png", "image/png", creator_auth)
    image_version = image_submission["versions"][-1]
    assert image_version["text"].strip() and image_version["source_layout"]["regions"], "Image OCR must save text and word boxes"
    print(f"  ✓ Image OCR extracted {len(image_version['text'])} characters and {len(image_version['source_layout']['regions'])} boxes")

    # C. Verify findings & citations
    r = client.get(f"/api/submissions/{sub_id}/findings", headers=creator_auth)
    assert r.status_code == 200
    findings = r.json()
    assert len(findings) >= 2, f"Expected at least 2 findings, got {len(findings)}"

    fix_finding = next((f for f in findings if f.get("suggested_rewrite") and not f.get("needs_human")), None)

    assert fix_finding is not None, "Expected a safe, suggested writing fix for the creator journey"
    assert fix_finding["source_quote"], "Missing verified source quote on the cited writing guideline"
    print(f"  ✓ Verified Finding Grounding: Cited source quote: '{fix_finding['source_quote'][:45]}...'")

    # D. Accept Terminology Rewrite
    r = client.post(
        f"/api/findings/{fix_finding['id']}/decision",
        json={"action": "accept"},
        headers=creator_auth,
    )
    assert r.status_code == 200
    print(f"  ✓ Accepted Fix for Finding #{fix_finding['id']}: '{fix_finding['suggested_rewrite']}' applied")

    # Verify version 2 created
    r = client.get(f"/api/submissions/{sub_id}", headers=creator_auth)
    versions = r.json()["versions"]
    assert len(versions) == 2, f"Expected 2 versions after accept, got {len(versions)}"
    assert fix_finding["suggested_rewrite"] in versions[1]["text"]
    print(f"  ✓ Verified Version 2 generated with diff fix applied to content text")

    # Re-run review on the changed content; review status is version-scoped.
    run_background_check(client, sub_id, creator_auth)
    r = client.get(f"/api/submissions/{sub_id}/findings", headers=creator_auth)
    findings = r.json()
    assert findings, "Expected the writing assistant to re-evaluate the revised version"

    # E. Request Review
    r = client.post(f"/api/submissions/{sub_id}/request-review", headers=creator_auth)
    assert r.status_code == 200
    assert r.json()["submission_status"] == "in_review"
    print("  ✓ Creator successfully requested review -> status: in_review")

    # F. Verify RBAC Guard
    r = client.post(
        f"/api/submissions/{sub_id}/approve",
        json={"decision": "approved", "note": "Illegal self-approval"},
        headers=creator_auth,
    )
    assert r.status_code == 403, "Creator must NOT be allowed to approve"
    print("  ✓ Verified Server-Side RBAC Guard: Creator blocked with 403 Forbidden on approval endpoint")

    # G. Manager can approve this standard-risk writing submission.
    r = client.post(
        f"/api/submissions/{sub_id}/comments",
        json={"body": "The writing fix was rechecked and the revised copy is ready."},
        headers=manager_auth,
    )
    assert r.status_code == 200

    reviewer_auth = {"Authorization": f"Bearer {tokens['Reviewer']}"}
    # High-risk work goes through reviewer sign-off, then a different manager.
    high_risk = client.post("/api/submissions", json={
        "title": "Smoke Test Compliance Escalation",
        "intent": "Describe a fictional botanical food product without making medical claims.",
        "content_type": "text",
        "text": "Our botanical blend cures digestive illness.",
    }, headers=creator_auth)
    assert high_risk.status_code == 200, high_risk.text
    high_risk_id = high_risk.json()["id"]
    assert client.post(f"/api/submissions/{high_risk_id}/check", headers=creator_auth).status_code == 200
    escalations = client.get(f"/api/submissions/{high_risk_id}/findings", headers=creator_auth).json()
    claim_finding = next((f for f in escalations if f["needs_human"] or f["severity"] in ("critical", "major")), None)
    assert claim_finding is not None, "The unsupported health claim should be escalated"
    assert claim_finding["source_quote"], "The escalation must cite its approved guideline source"
    assert client.post(f"/api/submissions/{high_risk_id}/request-review", headers=creator_auth).status_code == 200
    assigned = client.post(f"/api/submissions/{high_risk_id}/assign", json={"reviewer_id": user_ids["Reviewer"]}, headers=manager_auth)
    assert assigned.status_code == 200, assigned.text
    assert client.post(f"/api/submissions/{high_risk_id}/approve", json={"decision": "approved", "note": "Gate check"}, headers=manager_auth).status_code == 403
    r = client.post(f"/api/findings/{claim_finding['id']}/escalate-review", json={
        "action": "confirm",
        "justification": "The cited approved guidance prohibits unsupported medical claims.",
    }, headers=reviewer_auth)
    assert r.status_code == 200, f"Reviewer escalation decision failed: {r.text}"
    r = client.post(f"/api/submissions/{high_risk_id}/reviewer-signoff", json={
        "checklist": {"claims_verified": True, "facts_current": True, "accessibility_reviewed": True, "legal_wording_reviewed": True},
        "evidence_notes": "Checked the claim against the cited approved health-claims clause.",
        "justification": "Compliance review is complete and the unsupported claim was confirmed.",
    }, headers=reviewer_auth)
    assert r.status_code == 200, f"Reviewer sign-off failed: {r.text}"
    assert client.post(f"/api/submissions/{high_risk_id}/approve", json={"decision": "approved", "note": "Reviewer cannot finally approve."}, headers=reviewer_auth).status_code == 403
    r = client.post(f"/api/submissions/{high_risk_id}/approve", json={"decision": "approved", "note": "Compliance sign-off recorded; manager final decision."}, headers=manager_auth)
    assert r.status_code == 200, f"Manager final approval failed after reviewer sign-off: {r.text}"

    r = client.post(f"/api/submissions/{sub_id}/approve", json={"decision": "approved", "note": "Rechecked writing fix approved."}, headers=manager_auth)
    assert r.status_code == 200, r.text
    assert client.get(f"/api/submissions/{sub_id}", headers=manager_auth).json()["status"] == "approved"
    assert client.get(f"/api/submissions/{high_risk_id}", headers=manager_auth).json()["status"] == "approved"
    print("  ✓ Assigned reviewer signed off escalated content; manager made the final approval")

    # 6. Audit History & Insights
    print("\n[Step 6] Verifying Audit History & Insights...")
    r = client.get(f"/api/submissions/{sub_id}/history", headers=manager_auth)
    assert r.status_code == 200
    hist = r.json()
    assert len(hist["versions"]) == 2
    assert len(hist["approvals"]) >= 1
    print(f"  ✓ Audit History verified: {len(hist['versions'])} versions, {len(hist['approvals'])} approvals, {len(hist['audit_logs'])} events")

    r = client.get("/api/insights/summary", headers=manager_auth)
    assert r.status_code == 200
    insights = r.json()
    print(f"  ✓ Insights Summary: {insights['total_submissions']} submissions, {insights['accepted_count']} accepted fixes, {insights['dropped_findings_count']} dropped citations")

    print("\n[Step 7] Verifying Approval Certificate & Audit Integrity...")
    r = client.get("/api/certificates", headers=creator_auth)
    assert r.status_code == 200, r.text
    certificates = [item for item in r.json() if item["title"] == submission_payload["title"]]
    assert certificates, "Creator should be able to list their approved certificate"
    certificate = certificates[0]
    certificate_id = certificate["certificate_id"]
    r = client.get(f"/api/certificates/{certificate_id}/download", headers=creator_auth)
    assert r.status_code == 200 and r.content.startswith(b"%PDF"), "Certificate PDF download failed"
    r = client.get(f"/api/certificates/verify/{certificate_id}")
    assert r.status_code == 200 and r.json()["status"] == "valid", f"Public verification failed: {r.text}"
    assert submission_payload["text"] not in r.text, "Public verification must not return approved content"
    r = client.post(f"/api/certificates/verify/{certificate_id}/copy", json={"text": versions[1]["text"]})
    assert r.status_code == 200 and r.json()["copy_result"] == "Match", f"Approved-copy match failed: {r.text}"
    r = client.get("/api/admin/integrity-check", headers=admin_auth)
    assert r.status_code == 200 and r.json()["invalid_chains"] == 0, f"Audit integrity check failed: {r.text}"
    print(f"  ✓ Certificate {certificate_id} downloaded; public verification and pasted-copy match passed")
    print(f"  ✓ Admin integrity check verified {r.json()['total_chains']} chain(s)")

    print("\n" + "=" * 65)
    print("ALL SMOKE TESTS PASSED CLEANLY (100% SUCCESS)!")
    print("BrandGuard role and workflow smoke checks passed.")
    print("=" * 65)
    if base_url in ("inprocess", "--inprocess", "local", "testclient"):
        client.__exit__(None, None, None)


if __name__ == "__main__":
    url = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_BASE_URL
    run_smoke_test(url)
