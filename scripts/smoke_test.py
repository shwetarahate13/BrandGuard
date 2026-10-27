#!/usr/bin/env python3
"""BrandGuard Production Smoke Test Script.

Usage:
    python scripts/smoke_test.py [BASE_URL]

Tests:
1. Health check & cold-start readiness (/healthz and /api/health)
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
import httpx

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

DEFAULT_BASE_URL = "http://127.0.0.1:8000"


def run_smoke_test(base_url: str):
    print("=" * 65)
    print(f"BrandGuard Production Smoke Test -> {base_url}")
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

        # 1. Health check & Cold Start Readiness
        print("\n[Step 1] Checking /api/health with cold-start wait...")
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
        "text": "Our cheap sourdough loaves are guaranteed to boost health. Visit [click here] for more."
    }
    r = client.post("/api/submissions", json=submission_payload, headers=creator_auth)
    assert r.status_code == 200, f"Submission creation failed: {r.text}"
    sub = r.json()
    sub_id = sub["id"]
    print(f"  ✓ Created Submission #{sub_id} (Status: {sub['status']})")

    # B. Trigger check
    r = client.post(f"/api/submissions/{sub_id}/check", headers=creator_auth)
    assert r.status_code == 200, f"Check failed: {r.text}"
    check_res = r.json()
    print(f"  ✓ Review Pipeline Completed: {check_res['findings_count']} findings generated (Status: {check_res['submission_status']})")

    # C. Verify findings & citations
    r = client.get(f"/api/submissions/{sub_id}/findings", headers=creator_auth)
    assert r.status_code == 200
    findings = r.json()
    assert len(findings) >= 2, f"Expected at least 2 findings, got {len(findings)}"

    term_finding = next((f for f in findings if "cheap" in f["issue"].lower()), None)
    claim_finding = next((f for f in findings if "guaranteed" in f["issue"].lower()), None)

    assert term_finding is not None, "Missing terminology finding"
    assert claim_finding is not None, "Missing promotional claim finding"
    assert claim_finding["source_quote"], "Missing verified source quote on claim finding"
    print(f"  ✓ Verified Finding Grounding: Cited source quote: '{claim_finding['source_quote'][:45]}...'")

    # D. Accept Terminology Rewrite
    r = client.post(
        f"/api/findings/{term_finding['id']}/decision",
        json={"action": "accept"},
        headers=creator_auth,
    )
    assert r.status_code == 200
    print(f"  ✓ Accepted Fix for Finding #{term_finding['id']}: '{term_finding['suggested_rewrite']}' applied")

    # Verify version 2 created
    r = client.get(f"/api/submissions/{sub_id}", headers=creator_auth)
    versions = r.json()["versions"]
    assert len(versions) == 2, f"Expected 2 versions after accept, got {len(versions)}"
    assert term_finding["suggested_rewrite"] in versions[1]["text"]
    print(f"  ✓ Verified Version 2 generated with diff fix applied to content text")

    # Re-run review on the changed content; review status is version-scoped.
    r = client.post(f"/api/submissions/{sub_id}/check", headers=creator_auth)
    assert r.status_code == 200, f"Recheck after rewrite failed: {r.text}"
    r = client.get(f"/api/submissions/{sub_id}/findings", headers=creator_auth)
    findings = r.json()
    claim_finding = next((f for f in findings if "guaranteed" in f["issue"].lower()), None)
    assert claim_finding is not None, "Expected the current version to retain the unsupported claim finding"
    assert claim_finding["needs_human"] or claim_finding["severity"] in ("critical", "major") or claim_finding["category"] == "unsupported_claim"

    # E. Request Review
    r = client.post(f"/api/submissions/{sub_id}/request-review", headers=creator_auth)
    assert r.status_code == 200
    assert r.json()["submission_status"] == "in_review"
    print("  ✓ Creator successfully requested review -> status: in_review")

    # Manager assigns escalated content to the reviewer.
    r = client.post(
        f"/api/submissions/{sub_id}/assign",
        json={"reviewer_id": user_ids["Reviewer"]},
        headers=manager_auth,
    )
    assert r.status_code == 200, f"Reviewer assignment failed: {r.text}"

    # F. Verify RBAC Guard
    r = client.post(
        f"/api/submissions/{sub_id}/approve",
        json={"decision": "approved", "note": "Illegal self-approval"},
        headers=creator_auth,
    )
    assert r.status_code == 403, "Creator must NOT be allowed to approve"
    print("  ✓ Verified Server-Side RBAC Guard: Creator blocked with 403 Forbidden on approval endpoint")

    # G. Manager adds a note; a manager cannot approve high-risk copy.
    r = client.post(
        f"/api/submissions/{sub_id}/comments",
        json={"body": "Verified wording against approved terms. Approved for launch."},
        headers=manager_auth,
    )
    assert r.status_code == 200

    r = client.post(
        f"/api/submissions/{sub_id}/approve",
        json={"decision": "approved", "note": "Certified by Brand Manager"},
        headers=manager_auth,
    )
    assert r.status_code == 403, "Managers must not approve high-risk content"

    reviewer_auth = {"Authorization": f"Bearer {tokens['Reviewer']}"}
    r = client.post(
        f"/api/findings/{claim_finding['id']}/escalate-review",
        json={"action": "confirm", "justification": "The cited approved source does not substantiate this health claim."},
        headers=reviewer_auth,
    )
    assert r.status_code == 200, f"Reviewer escalation decision failed: {r.text}"
    r = client.post(
        f"/api/submissions/{sub_id}/approve",
        json={"decision": "approved", "note": "Compliance sign-off recorded"},
        headers=reviewer_auth,
    )
    assert r.status_code == 200, f"Reviewer high-risk sign-off failed: {r.text}"
    assert r.json()["decision"] == "approved"

    # Verify final approved status
    r = client.get(f"/api/submissions/{sub_id}", headers=manager_auth)
    assert r.json()["status"] == "approved"
    print("  ✓ Assigned reviewer signed off high-risk submission -> status: approved")

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
