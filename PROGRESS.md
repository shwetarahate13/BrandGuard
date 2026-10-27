# Round 3 progress

## Current state

- Phase 0: complete and pushed in commit `2705e51` (`fix: verify role workspaces and theme contrast`).
- Phase 1: implementation in progress in the current checkout; this checkpoint does not close the phase.
- Next exact step: run `python scripts/setup_local.py`, `python scripts/run_local.py`, and a browser check from a clean clone on Python 3.11+ with at least 5 GiB free. The committed static bundle matches the successful frontend build; this host cannot complete the clean install because it has Python 3.9 system-wide and about 2 GiB free.

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
- The current machine has about 2 GiB free disk and its system Python is 3.9, below the project requirement. A clean install/model download could not be run here; it needs Python 3.11+ and at least 5 GiB free.

### Current cuts and limits

- Hosted deployment files were removed for the local-only Round 3 decision.
- There is no source-code feature cut in Phase 1 so far. The neural model's fresh installation and full local startup still need verification on a machine with adequate free disk.
- Background-job status is in-process; restarting the app loses progress records. The worker itself is terminated at its configured timeout.

## Remaining phases

- Phase 2: resilience for invalid input, repeat actions, concurrent users, expired sessions, and failure states.
- Phase 3: end-to-end verification and tests for improvements A, B, and C, including seeded visible history.
- Phase 4: reviewer workbench and full role matrix.
- Phase 5: fictional demo content, typo checks, and first-run experience.
- Phase 6: role journeys, complete docs, and fresh-clone verification.
- Phase 7: optional extras only after Phases 0–6 pass.
- Phase 8: full final verification, secret scan, commit, and push.
