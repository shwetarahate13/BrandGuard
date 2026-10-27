# Judge guide

Run `python scripts/setup_local.py`, then `python scripts/run_local.py`, and open `http://localhost:8000`. Local setup enables demo mode; select one of the four accounts in the login-page panel. No demo password needs to be copied. If the panel is absent, check that `DEMO_MODE=true` is set in `.env` and restart the app.

## Creator

1. Open **New Content Check**. Use a sample from `samples/` or paste your own content, then run the check.
2. Open each cited source beside a finding. Accept a suggestion, edit it, or dispute it with a reason.
3. Save and check the revised version, then **Request review**. The status stepper shows progress through review, sign-off, and approval.
4. After a decision, use **My Work** to reopen the item. Find approval certificates from **Certificates**.

## Manager

1. Open **Command Center** and select a submission. Review its findings and creator's decisions.
2. Assign a reviewer when compliance sign-off is required; set or adjust the due date.
3. Open **Guideline Health**. Inspect clause friction and dispute themes, then use **Recompute now** to refresh the latest values.
4. Approve standard-risk content, or request changes/reject it. High-risk items require reviewer sign-off before manager approval.
5. Use the approval report action to download a CSV or PDF of decisions.

## Reviewer

1. Open **Compliance Desk** and choose an assigned or escalated submission.
2. Compare the claim, cited source, and retrieved evidence. Confirm or dismiss each escalation with a written justification.
3. Complete the compliance checklist and add evidence notes, then sign off. A manager makes the final approval decision.
4. Use reviewer metrics to inspect turnaround and decision outcomes.

## Admin

1. Open **Admin** to manage users and approved sources. The Admin role cannot approve submissions.
2. On the Admin dashboard, inspect feedback statistics and reset the preference model if needed.
3. Open **Audit Log** or **Integrity Check** to inspect event history and verify audit chains.
4. Use **System Status** to check database, source-index, and LLM status; the navigation badge reports retrieval-engine warm-up and selection.

## Three improvements

- **Guideline-Gap Insights (A):** clause health and dispute friction are on the manager/admin **Guideline Health** page.
- **Image Review and Format-Aware PDF Inspection (B):** upload an image or PDF from New Content Check, then open its findings to see OCR boxes or page highlights.
- **Reinforcement Feedback Loop (C):** accept, edit, or dispute findings as Creator; then inspect feedback statistics as Creator, Manager, or Admin.

The demo records are fictional. See [FEATURES.md](FEATURES.md) for capabilities and [LIMITATIONS.md](LIMITATIONS.md) for review boundaries.
