# BrandGuard Judge Guide

This five-minute path uses the local lite run and the four visible demo roles. The offline mock engine works without API keys.

## Start

From the repository root:

```bash
python scripts/setup_local.py
python scripts/run_local.py
```

Open `http://127.0.0.1:8000`. Lite mode supports text and PDF review; image review displays a clear disabled message. Use `python scripts/setup_local.py --full` when you want to see OCR and visual image checks.

## Click path

1. **Creator — run a review and fix findings.** Sign in with `creator@nexora.dev` / `CreatorDemo2026!`. Choose **New Content Check** and use the planted copy in `samples/campaign-copy.txt` (or upload `samples/campaign-copy.pdf`). Run the review to see cited findings. Accept the terminology rewrite for “cheap”, edit vague link wording, and save the corrected version. Re-run the review so findings belong to the version you submit. The Creator dashboard’s feedback metrics show the accept/edit signals used by the preference model.
2. **Creator — submit.** On the submission review page, choose **Request review**. The sample retains an unsupported health claim so the submission requires compliance sign-off.
3. **Manager — route and inspect.** Sign in with `manager@nexora.dev` / `ManagerDemo2026!`. In **Command Center**, open the submission and assign the seeded Reviewer. Add a review comment. The manager cannot sign off the high-risk health claim alone. Open **Guideline Health** to see clause dispute friction, trends, and the recompute action (Improvement A).
4. **Reviewer — record compliance approval.** Sign in with `reviewer@nexora.dev` / `ReviewerDemo2026!`. Open the assigned item from **Compliance Desk**, review the cited source, and record a justified confirmed/dismissed escalation decision. Approve the item. For Improvement B, open the PDF sample in the review screen and inspect its page-coordinate highlights; full mode also shows OCR text and image overlays.
5. **Creator — download and verify.** Sign back in as Creator and open **Certificates**. Download the new PDF, then open its **Verify** link. The public page should show **Valid** and the approval metadata, without the approved copy. Paste the approved version text into the copy checker to see **Match**; change a word and check again for **Differs**.
6. **Admin — inspect integrity and feedback.** Sign in with `admin@nexora.dev` / `AdminDemo2026!`. Open **Integrity Check** to recompute every chain and export the safe results CSV. Admin can also inspect feedback statistics and the audit log; Admin cannot approve submissions.

## What to look for

- **Improvement A — guideline-gap insights:** managers/admins see dispute friction by guideline clause and can recompute the metrics.
- **Improvement B — image and spatial review:** PDF findings link to page locations in lite mode. Full mode enables image OCR, palette/logo checks, and visual overlays. Lite mode intentionally explains when image review is not enabled.
- **Improvement C — human feedback loop:** accept/edit/dispute decisions train the persisted preference model. Creator feedback metrics and manager/admin feedback statistics show the recorded outcomes.
- **Four-eyes control:** creators cannot approve their own work, admins cannot approve, and escalated high-risk work needs an assigned Reviewer.
- **Certificate integrity:** database triggers block ordinary audit-row updates/deletes; public verification recomputes hashes and checks the approved content without disclosing it.

See [LIMITATIONS.md](LIMITATIONS.md) for the audit-chain trust boundary and other implementation limits.
