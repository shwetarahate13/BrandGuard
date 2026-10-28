# Round 3 progress

## Current state

- Phase 0: complete and pushed in commit `2705e51` (`fix: verify role workspaces and theme contrast`).
- Phase 1: implementation complete; fresh README setup proof remains blocked by the local disk limit, so Phase 1 verification is not closed.
- Phase 2: resilience changes and tests complete; committed frontend bundle is current.
- Next exact step: Phase 3, verify Improvements A, B, and C end to end, add any missing seeded history, and fix the UI/API gaps found.

## Phase 0 — health check and bugs

- Backend suite passed: 189 tests. Frontend suite passed: 7 tests. Frontend production build and `scripts/smoke_test.py inprocess` passed.
- Smoke covered demo login for all four roles, main workflow, permissions, certificates, and audit integrity. Browser pass checked 32 role/navigation/theme combinations with no console errors or server failures.
- Semantic light/dark tokens were added and the contrast script passed all configured token pairs. Canvas finding overlays respond when the theme changes.
- Backend tests now use an isolated Alembic-migrated temporary database.

## Phase 1 — local runtime

- Removed the container and hosted-service configuration and the obsolete startup banner.
- Set local defaults to SQLite, pip-only RapidOCR, 25 MB uploads, 20,000-word checks, 30-megapixel raster images, and retrieval top-k 12.
- Neural all-MiniLM-L6-v2 retrieval warms in the background; the HashingVectorizer fallback remains available and the navigation reports engine status.
- Added bounded process-isolated upload and content-review jobs with progress polling and process termination at the job timeout. PDF/DOCX/image extraction and the review/LLM pipeline can run through these jobs.
- Reworked setup and doctor scripts for the complete Python runtime and committed frontend bundle. README now gives local clone/run/test commands.
- Removed old hosted deployment and reduced-runtime claims from active feature, limitation, improvement, judge, and sample documentation. Added `docs/PLAN_CHANGES.md`.
- Verification: full backend suite passed (194 tests), frontend suite passed (7 tests), and production frontend build passed. The in-process smoke test covered all four demo roles, workflow permissions, certificates, PDF extraction/review locations, and image OCR. A separate local API run verified process-backed text, PDF, and image jobs.
- The clean setup was attempted twice. The original single pip transaction and the disk-conscious two-batch retry both failed with `ENOSPC` on this host's roughly 2 GiB of free disk; no setup `.venv` was left behind. The setup script now installs large OCR/neural dependencies separately and uses longer pip/model-download timeouts.

## Phase 2 — resilience

- Reject blank titles and empty/whitespace-only content before creating or checking a submission. Keep the 20,000-word limit and accept Unicode and emoji text.
- Upload checks reject empty and corrupt PDF, DOCX, and image inputs, mismatched file signatures, and files over the configured cap with client errors instead of server failures.
- Added persisted `Idempotency-Key` records for text and file creation, including background uploads and comments. The UI reuses a key when retrying the same form data; the server returns the original resource for a retry and rejects reuse with different content. API callers can use the same header.
- Decision, review-request, approval, and rejection transitions now claim the previous state atomically. Duplicate decisions return 409; concurrent manager approvals produce one approval and one 409. Duplicate version text returns the saved version.
- Review actions, comments, and review requests show disabled/loading states and inline retryable errors. The existing expired-session path still clears the token and returns to login.
- Background timeouts are covered for both document extraction (PDF/DOCX/image work) and content review (retrieval/LLM work); timed-out workers are terminated. The job status remains in-process and is lost on app restart.
- Verification: full backend suite passed (202 tests); frontend tests passed (7); frontend TypeScript check and production build passed. Targeted tests cover invalid text/files, create and upload retries, repeated accept/dispute/approve/request-review, concurrent approvals, and session expiry.
- No Phase 2 feature was removed. A clean local install remains unverified for the Phase 1 disk-space reason recorded above.

### Current cuts and limits

- Hosted deployment files were removed for the local-only Round 3 decision.
- There is no source-code feature cut in Phase 1 so far. The neural model's fresh installation and full local startup still need verification on a machine with adequate free disk.
- Background-job status is in-process; restarting the app loses progress records. The worker itself is terminated at its configured timeout.

## Remaining phases

- Phase 3: Improvements A, B, and C are implemented and verified. Guideline Health includes DFI recompute-on-read, clustered dispute reasons, recompute, LLM proposals or a clearly labelled offline template, and a guarded revision flow. Image review defaults on; default settings produce a boxed image finding, and missing RapidOCR gives a setup instruction. Feedback learning and suppression stats appear on dashboards; demo seed history shows a >30% DFI and one suppressed pattern. The manager UI showed the seeded clause, recomputed it, and applied edited wording; the dashboard showed the suppressed count. The sample image upload returned the actionable OCR dependency error in this environment.
  - Verification: backend suite 203 passed, 1 skipped; targeted Phase 3 tests 36 passed, 1 skipped; frontend TypeScript and production build passed; committed static bundle rebuilt.
  - Phase 3 limits: offline wording is an editing template and cannot be applied until its prompts are replaced. This environment does not have RapidOCR installed, so the real OCR engine could not be exercised here; the default-enabled image finding/box path is covered with the handler test, and the upload error path was exercised with the sample image.
  - Next exact step: Phase 4, implement the reviewer workbench and verify the full role permission matrix.
- Phase 4: reviewer workbench and full role matrix.
- Phase 5: fictional demo content, typo checks, and first-run experience.
- Phase 6: role journeys, complete docs, and fresh-clone verification.
- Phase 7: optional extras only after Phases 0–6 pass.
- Phase 8: full final verification, secret scan, commit, and push.
