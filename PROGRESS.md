# Round 3 progress

## Frontend redesign (2026-10-28)

- Scope: frontend-only UI redesign requested after Round 3. Backend application code, migrations, scripts, tests outside `frontend/`, API shapes, roles, and workflow rules remain untouched. The committed `backend/app/static/` distribution is rebuilt when the production bundle changes so local installs display the same UI as frontend development.
- Instructions/design read: `AGENTS.md`, `DESIGN.md`, and this progress file. The source palette is mapped into BrandGuard-specific tokens; the BrandGuard UI must not reuse Starbucks marks or retail copy.
- Skills consulted: project `design-taste-frontend` and `web-design-guidelines`; global `frontend-app-builder`, `frontend-testing-debugging`, `react-best-practices`, and `shadcn-best-practices`. shadcn-specific component generation is not used because this project has no `components.json` or shadcn dependency. The existing React/Vite/Tailwind stack and Lucide icon set are retained.
- Baseline: after `npm ci`, frontend tests passed (7) and `npm run build` passed. `npm run` shows no lint or Playwright script/config in this checkout. Computer-use browser inventory reports browser use disabled in Work settings; temporary Playwright+Chrome is used outside the repository as the visual QA fallback.

### Step 1 — design tokens and shared primitives

- Added semantic BrandGuard tokens for warm light surfaces and green-neutral dark surfaces, status pairs, controls, focus, highlights, typography, spacing, radii, shadows, and motion. Mapped Tailwind to the tokens and added a compatibility bridge for existing screens.
- Added shared `Button`, `Card`, `Badge`, `Input`, `Select`, `Tabs`, `Table`, `Modal`/`Drawer`, `EmptyState`, `Stat`, `Stepper`, `Tooltip`, and `Toast` primitives. Existing `Skeleton` and toast provider now use the shared theme, reduced motion, and larger dismiss targets.
- Added the BrandGuard application mapping, token table, component rules, and accessibility contract to `DESIGN.md`.
- Verification: semantic contrast script passed all checked token pairs in light/dark; frontend tests 7 passed; TypeScript + Vite build passed. No lint script or Playwright tests exist in the repository.
- Step 2 — app shell and dark mode: replaced the horizontal header with a role-aware sidebar and sticky top bar, semantic breadcrumbs, engine badges, account popover, mobile navigation sheet, skip link, and themed footer. Preserved existing role link sets, notification actions, password change, demo-role switch, transparency modal, and theme storage. Removed a duplicated user name in the old header.
- Verification: frontend tests 7 passed; TypeScript/Vite build passed; contrast script passed. Temporary Playwright+Chrome smoke (API mode mocked because no backend environment is configured) captured desktop light/dark and mobile dark login views, verified theme persistence across reload, no horizontal overflow, visible mobile brand, and zero console/page errors. Screenshots are under `/private/tmp/brandguard-qa/` and are not committed. Browser plugin remains unavailable and this repo has no Playwright suite or lint script.
- Step 3 — role dashboards: redesigned the Creator, Manager, Reviewer, and Admin workspaces with distinct role-focused heroes, consistent KPI cards, meaningful data views, responsive status boards, semantic chart colors, and accessible admin tabs. Creator charts use personal submissions and recurring findings; Reviewer status counts use assigned work; Admin role mix and audit feed use the data already returned by its API. Added useful empty states and explicit labels to dashboard filters and admin controls. No API shape, permission, or workflow rule changed.
- Verification: frontend tests 7 passed; TypeScript + Vite production build passed; the semantic token contrast script passed. Temporary Playwright rendered all four dashboards in light/dark at desktop (1440px) and mobile (390px), with mocked API responses: 16 screenshots saved under `/private/tmp/brandguard-qa/`, zero page/console errors, zero horizontal overflow, and zero computed text contrast failures below AA. Interactions verified: Creator new-submission route, Manager queue empty state/filter reset and guideline-health route, Reviewer justified finding action, and Admin tab activation plus Home/End keyboard navigation. Screenshots were visually reviewed in a contact sheet. No lint or repository Playwright suite is configured.
- Visibility fix: dashboard code had been pushed, but judges running the committed FastAPI bundle still received the older `backend/app/static/` build. Rebuilt and replaced the committed static distribution so local setup shows the redesigned dashboards without Node. No backend Python/API code changed.
- README: added step-by-step clone/setup/run instructions for macOS, Linux, and Windows, with a reuse/update section so people clone once and pull updates into the same folder.
- Verification: frontend tests 7 passed; TypeScript + Vite build passed; bundled HTML asset references resolve; dashboard bundle contains the redesigned role headings; semantic contrast script passes. Temporary Playwright served the committed static bundle (not Vite dev) and rendered all four role dashboards in both themes at 1440px and 390px with mocked API data: no browser errors, no horizontal overflow, and no computed AA text contrast failures. Lint and Playwright scripts are not configured in the repository.
- Next exact step: redesign the review and approval screens, then repeat frontend tests/build, contrast checks, static-bundle smoke and role/theme visual QA.

## Writing Assistant progress (additional capability)

- Phase 1: deterministic offline spelling and conservative grammar findings are integrated with the existing cited-finding pipeline. Findings use the seeded `STYLE-1` clause, retain exact source-text offsets, and include stable rule IDs and confidence. Admins can manage an allowlist of brand words. The bundled spelling correction list is deliberately conservative; unknown words are not flagged.
- Verification: focused backend tests passed (4); frontend production build passed and the committed static bundle was rebuilt. Alembic now includes the admin brand-word setting. Secret/artifact scan found no tracked environment files, databases, Chroma folders, uploads, or key files.
- Phase 2: suggestions now quote the relevant coded guideline in their reason, preserve intent, and route unsupported claims to a reviewer unless the exact proposed wording is present in the cited approved fact. Overlapping edits are prioritized by claims/facts, terminology, tone, accessibility, then grammar/spelling. Suggested drafts are rechecked through the full pipeline; if that check adds a high-severity finding, the suggestions are withheld.
- Verification: writing-assistant tests passed (7); demo seed tests passed (2). The full-workflow integration test did not finish within about 100 seconds and was stopped; it needs a separate performance investigation before full-suite verification.
- Phase 3: the review UI groups findings, shows before/after diffs and cited reasons, offers individual decisions plus safe batch actions, and previews a highlighted full draft. Creators can edit, debounced re-check, manually re-check, and undo through version history. Batch safe fixes make one next version and record each acceptance in the existing feedback loop. Grammar-rule disputes are counted separately and suppress a rule at three; admins can inspect and reset these counters.
- Verification: focused backend tests passed (9); frontend TypeScript check and production build passed; committed static bundle rebuilt. Batch version creation/replay and three-dispute suppression/admin reset are covered. The full-workflow integration test did not finish within about 100 seconds and was stopped, as recorded under Phase 2.
- Current writing-assistant phase: Phase 4, robustness fixtures, evaluation, and journey coverage.

## Current state

- Phase 0: complete and pushed in commit `2705e51` (`fix: verify role workspaces and theme contrast`).
- Phase 1: implementation complete; fresh README setup proof remains blocked by the local disk limit, so Phase 1 verification is not closed.
- Phase 2: resilience changes and tests complete; committed frontend bundle is current.
- Phases 0–3 are complete and pushed. Current active phase: Phase 4 reviewer workbench and role matrix.

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
- Phase 4: Reviewer findings now require the assigned reviewer to confirm or dismiss each escalated item with justification. The queue shows the claim excerpt beside its cited source. Reviewers record source evidence notes and complete the claims, current facts, accessibility, and legal wording checklist for the current version. Their sign-off is persisted separately and never approves the submission; a different manager must make final approval. Expired/outdated approved-fact findings also require reviewer sign-off. Reviewer metrics report average turnaround, confirmed and dismissed findings, and later overturn rate. Admin, manager, reviewer, and creator action permissions are covered across every action cell; reviewers no longer have final-approval permission.
  - Verification: targeted workflow and permission tests 122 passed; full backend suite 203 passed, 1 skipped; frontend TypeScript and production build passed; rebuilt committed static bundle.
  - Next exact step: Phase 5, fictional demo content, typo checks, and first-run experience.
- Phase 5: fictional demo content, typo checks, and first-run experience.
- Phase 6: role journeys, complete docs, and fresh-clone verification.
- Phase 7: optional extras only after Phases 0–6 pass.
- Phase 8: full final verification, secret scan, commit, and push.
