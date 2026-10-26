# BrandGuard - Progress & Phase Checklist

## Status Summary
- **Current Step**: Approval-report CSV/PDF export is complete; remaining Step 5 features continue in listed order
- **Phase Checklist**:
  - [x] **Phase 1: Fix Existing Bugs First**
    - [x] Run backend tests (identified missing Alembic migrations on existing SQLite DB; applied to head; 22/22 tests passing)
    - [x] Test frontend build (`npm run build` succeeds)
    - [x] Audit all API endpoints, routes, status codes, and error handlers
    - [x] Fix offline Flesch readability calculation in `preference_model.py` (avoid NLTK cmudict download failures)
    - [x] Smoke test & E2E verification of all current flows (`smoke_test.py` passes 100%)
  - [x] **Phase 2: Roles That Are Really Different & An Exciting UI**
    - [x] Create permission matrix in `backend/app/services/permissions.py`
    - [x] Enforce permissions and row-level access on submission, workflow, finding, insights, source, guideline, feedback, system and admin APIs; disallow self-approval
    - [x] Add independent unit assertions for every permission matrix cell and approval/visibility rules
    - [x] Role-specific frontend navigation, landing pages, and views:
      - Creator: "My Work", own submissions only, fix findings, personal stats & notifications
      - Manager: Team command center, approval queue with SLA/age, reviewer assignment, sign-off, org insights, guideline health
      - Reviewer: Compliance desk, assigned items & escalated findings, side-by-side claim checking, justification, compliance notes
      - Admin: User management, approved-sources registry, system settings, full audit log with filters and CSV export, feedback model stats/reset
    - [x] Add role-specific KPIs; manager 7-day trend, category/severity charts, status pipeline and recent activity; skeletons, empty states, toasts and responsive mobile navigation
  - [x] **Phase 3: Improvement A, Guideline-Gap Insights**
    - [x] Nightly UTC APScheduler job groups disputed findings by cited guideline clause
    - [x] TF-IDF cosine similarity dispute clustering
    - [x] DFI uses distinct disputed findings / distinct findings (%); recomputes reset zero-finding clauses to 0%
    - [x] `GET /api/guidelines/health` is available to managers and admins and sorts high DFI first
    - [x] `/dashboard/guideline-health` sortable risk bands and current/proposed wording diff
    - [x] Proposed clearer wording only when a live LLM provider is configured
    - [x] `PATCH /api/guidelines/clauses/{clause_id}` applies edits and refreshes the source index
    - [x] "Recompute now" action, DB-stored compute time, 24-hour stale check, and invalidation on new reviews/disputes/revisions
  - [x] **Phase 4: Improvement B, Image Review and Spatial PDF Inspection**
    - [x] Selectable Tesseract (configured default) or RapidOCR/ONNX OCR with word-level boxes; `opencv-python-headless` remains lazy-loaded
    - [x] Dominant color extraction against approved asset RGB metadata, ±15 per channel
    - [x] OpenCV template matching for readable approved logo files
    - [x] Measurable clear-space checks only when a logo file and explicit minimum both exist
    - [x] WCAG AA contrast calculation for OCR-detected text regions with an approved accessibility clause
    - [x] Canvas overlays and linked finding selection in the image/PDF review screen
    - [x] PDF inspection with `pdfminer.six` page coordinates and finding `location` boxes
    - [x] Semi-transparent PDF page highlights
    - [x] Lazy-loaded OCR/CV and explicit `IMAGE_REVIEW_ENABLED` memory gate; image review is disabled by default, and the Render demo enables Tesseract explicitly
  - [x] **Phase 5: Improvement C, Reinforcement Feedback Loop**
    - [x] Snapshot original span, proposed rewrite, human edit on decisions; compliance dismissals also create dispute decisions
    - [x] Online SGD logistic regression features: sentence length, Flesch readability, and formality deltas
    - [x] Persist model state in a database blob
    - [x] Train accepts (+), edits (chosen +, suggested -), and disputes (-)
    - [x] Rank rewrite candidates by predicted acceptance probability in the confidence pipeline
    - [x] Suppress repeated disputed patterns after 3 distinct findings for the same clause and normalized span
    - [x] `GET /api/feedback/stats` reports acceptance rate, edit rate, and suppression counts by category
    - [x] Creator/admin feedback views retained; manager command center now displays the category stats bar; admin model reset remains available
    - [x] Targeted Phase 5 verification: 14 tests passed; frontend production build, Python compile, and `git diff --check` passed
  - [x] **Phase 6: Real-World Readiness and Deployment**
    - [x] Local non-Docker setup (uvicorn :8000, Vite :5173 with `/api` proxy, SQLite default, first-admin bootstrap)
    - [x] Render free deployment stays on the existing Docker runtime because the image workflow needs Tesseract; Docker builds frontend, installs backend, runs Alembic, and serves the SPA on `$PORT`. `build.sh` supports a local/native build when system packages are installed.
    - [x] Production configuration requires a strong JWT secret and PostgreSQL; bcrypt/password policy, login rate limiting and lockout, JWT expiry, exact CORS allowlist, security headers, 5 MB upload validation/type sniffing, pagination, request IDs, structured logs, `/healthz`, and friendly global error responses are implemented.
    - [x] `DEMO_MODE` defaults false and gates demo seeding, role switching, demo login, and the four-role login credentials panel.
  - [x] **Phase 7: Tests and Docs**
    - [x] Permission matrix tests cover every role/action cell and row-level/self-approval policy
    - [x] Improvement tests cover guideline health/recompute (A), OCR/PDF/media checks (B), and model training/suppression (C)
    - [x] Update `docs/FEATURES.md`, `docs/ROUND3_IMPROVEMENTS.md`, `docs/LIMITATIONS.md`, and `README.md`
  - [x] **Step 5 feature: In-app notifications for assignments and workflow decisions**
    - [x] Persist user-scoped notifications with read/unread state and submission links
    - [x] Notify assigned reviewers and creators on approval, changes requested, and rejection
    - [x] Add authenticated inbox endpoints, UI bell, unread count, mark-read actions, and end-to-end coverage
  - [ ] **Remaining Step 5 features (resume when quota allows)**
    - [x] Assignment due dates and SLA/overdue indicators
    - [x] Saved views (basic creator/manager search and filters already exist)
    - [x] Approval-report CSV/PDF export (audit-log CSV already exists)
    - [ ] Self-service password change (admin-triggered password reset already exists)
    - [ ] Dark mode
    - [ ] First-login onboarding tips

## Decisions Made
1. **Migrations & Database**: SQLite default locally, PostgreSQL (Neon) in production. Database migrations must always be executed via `alembic upgrade head`. Added dispute friction, media layout, and preference state migrations.
2. **OCR runtime**: Tesseract is the configured default lower-memory backend; RapidOCR/ONNX remains optional for larger machines. Render free uses the working Docker runtime to install Tesseract and enables image review. OpenCV and OCR modules are loaded only as needed.
3. **Offline Flesch Calculation**: Avoid reliance on external NLTK network downloads for cmudict by implementing a deterministic syllable-counter fallback for Flesch reading ease in `preference_model.py`.
4. **Role policy**: Only creators create submissions and decide findings; managers handle standard-risk workflow and assign active reviewers; reviewers resolve escalations and sign off high-risk assigned items; admins manage the system but cannot approve. High-risk submissions are not manager-approved.
5. **Manager observability**: Trends and activity come from persisted submissions, findings, and audit records. Creator notifications are derived from actual approvals and review comments; empty accounts show an empty state instead of demo copy.
6. **Public system metadata**: `/system/mode` exposes only the active LLM mode for the navigation badge; detailed `/system/status` requires the Admin permission.
7. **Phase 2 verification**: 111 targeted permission/API tests passed, Vite production build passed, full SQLite migration chain applied with the reviewer FK verified, and the isolated end-to-end workflow smoke passed. Browser checks confirmed Creator, Manager, Reviewer, and Admin dashboards/nav; browser console had no errors or warnings. A local Vite proxy target was supplied through `BRANDGUARD_API_PROXY_TARGET` during UI verification; native local defaults are scheduled for Phase 6.
8. **Phase 3 verification**: DFI session ownership now supports both request Sessions and APScheduler session factories. Newly computed timestamps and source-data invalidation prevent stale scores; a read recomputes stale data. SQLite Alembic upgrade to head and `npm run build` passed; the targeted permission/API suite passed 113 tests. One existing Chroma embedding-function deprecation warning remains.
9. **Phase 4 verification**: RapidOCR 3.10.0 (packaged ONNX models) processed the real 1020×1320 sample image into 455 characters and 77 word boxes; `pdfminer.six` extracted page/line boxes from the real PDF fixture. Palette, logo clear-space, OCR geometry, PDF location, and image-memory-gate tests passed (17 targeted tests). A RapidOCR/OpenCV run measured 611 MB peak RSS on the development Mac; a later Tesseract run measured 240.4 MB for the app plus a 58.6 MB OCR child (299.0 MB conservative combined). Image review remains opt-in by default; Render explicitly enables the lower-memory Tesseract backend. `pip check`, Python compile, and diff checks passed.
10. **Feedback training and suppression**: A dispute invalidates clause-health freshness and trains a negative rewrite example; compliance reviewer dismissals now follow the same path. Suppression groups distinct findings across categories for each clause and normalized span. This deployment has one workspace database, so suppression is workspace-wide; it is not yet tenant-isolated.
11. **Phase 5 verification**: `.venv/bin/pytest -q tests/unit/test_preference_model.py tests/integration/test_round3_endpoints.py` passed 14 tests. Tests cover offline feature extraction, online model persistence/labels, candidate ranking, endpoint snapshots, reviewer dismissal training, cross-category suppression, and DFI invalidation. `npm run build`, targeted `compileall`, and `git diff --check` passed. One existing Chroma embedding-function deprecation warning remains.

## Exact Next Step
Assignment due dates, manager-only updates, and manager/reviewer overdue indicators are implemented, tested, and committed in `9015376`. Saved views are implemented for Creator and Manager with browser persistence isolated by account and role. Approval-report CSV/PDF export is now implemented and verified. Next in order: self-service password change, dark mode, and first-login onboarding tips. Admin password reset, basic search/filter controls, and audit CSV export already exist.

## Phase 6 Resume Check (2026-10-26)
- Ran the requested baseline checks before implementation changes: `npm run build` passed. The first backend run had 4 failures because the existing local SQLite database was behind Alembic head; after `alembic upgrade head`, the full suite reported 147 passed and 1 failed.
- The remaining failure is `test_full_governance_workflow_and_rbac`: accepting a rewrite creates a new draft revision, but the test requests review without checking that revision again. Confirm the intended UI flow and repair the integration coverage/workflow before declaring the full sweep green.
- Local settings use SQLite and `DEMO_MODE=false`. In a separate migrated SQLite instance with `DEMO_MODE=true`, signed in as Creator and Manager, then switched to Reviewer and Admin. Each showed its role-specific dashboard and navigation; the mobile demo-role switcher worked. Vite on `:5173` reached the backend on `:8000` through its `/api` proxy.
- The login page still lacks the requested demo-credentials panel; add it in the next implementation step. Keep the role switcher hidden when demo mode is off.
- Phase 6 changes were already present but uncommitted when this resume began; audit and complete those changes before committing them with the finished phase.
- Local setup and deployment hardening are now complete. `build.sh` passed end to end with the repository virtualenv, frontend production build, and Alembic migration. A local Docker image build passed; a temporary container applied migrations, served the SPA, returned 200 from `/healthz` and `/api/health`, and completed demo admin login. The temporary container was isolated from the repository database.
- Image review with Tesseract processed a real 1020×1320 campaign image and the PDF fixture, producing 437 OCR characters/73 boxes and 8 PDF highlights. Peak app RSS was 240.4 MB and the Tesseract child peak was 58.6 MB (299.0 MB conservative combined), below the ~450 MB target. RapidOCR measured above the target, so it is not used by the free Render configuration.
- `DEMO_MODE=false` is the local/default configuration; demo users are created only for an empty database when demo mode is enabled. `.gitignore` now covers `.env`, SQLite databases, Chroma directories, uploads, and the frontend build output; `.env.example` remains trackable.
- Final backend suite for Step 1: 151 passed, 1 failed. The remaining existing workflow test still requests review immediately after accepting a revision; the new revision is a draft and needs a fresh check. This is intentionally carried to Step 3, where the full workflow sweep will fix its test and verify the UI behavior. Chroma emits five existing embedding-function deprecation warnings.

## Step 2: Demo Credentials on the Login Page (2026-10-26)
- Added a responsive “Demo accounts” panel gated by `/api/system/mode`'s `demo_mode` value. It lists Admin, Manager, Reviewer, and Creator usernames/passwords and provides a **Fill / Sign in** button for each; each button fills the login fields and authenticates through the regular password-login endpoint.
- In the browser with `DEMO_MODE=true`, verified the four cards and successfully signed in through each button. The resulting pages showed the matching Admin Console, Manager Command Center, Reviewer Compliance Desk, and Creator My Work dashboard.
- Restarted with `DEMO_MODE=false` and a newly migrated empty SQLite database. The login panel was absent, the database contained zero users, and `/api/auth/demo-login` returned 404.
- `npm run build --prefix frontend` passed. No real user password is shown or logged; the displayed values are throwaway credentials from the demo seed.

## Step 3: Full Bug Sweep (2026-10-26)
- Fixed the confirmed terminology rewrite regression: approved deterministic term replacements such as `cheap` → `accessible pricing` are no longer dropped by the generic intent-overlap heuristic. Added a focused unit regression test.
- Fixed the workflow that left a submission in draft after accepting a rewrite: the integration test now asserts that a new version must be checked before review can be requested. Added a creator revision form for `changes_requested` and `rejected` submissions; saving creates a version, reruns the check, and enables resubmission. Added assignment fields to submission responses so the manager/reviewer queue can render its allocation state.
- Updated the Chroma embedding function to its current typed config interface, eliminating the existing embedding deprecation warnings.
- Expanded workflow integration coverage for create, check, accept, edit, dispute, submit, assign, changes requested, reject, resubmit, and approve. It verifies that creators cannot approve their own submission, managers cannot approve a high-risk submission, and an assigned reviewer can. Also verifies assignment is returned in the submission response.
- Browser sweep with the four demo roles confirmed distinct Creator My Work, Manager Team Command Center, Reviewer Compliance Desk, and Admin Console dashboards/nav. Checked manager search/filter queue and reviewer assignment, reviewer high-risk sign-off, Admin user/settings/audit/feedback/source screens, Org Insights, Approved Sources, Limitations, and Guideline Health. `Recompute now` returned “Guideline friction recomputed.” Browser console reported no errors or warnings.
- End-to-end review checks included an image OCR submission (26 findings), PDF inspection with 8 page-highlighted findings, and reviewer approval recorded in the audit trail. Manager feedback stats displayed persisted decision outcomes; the targeted feedback tests cover suppression after three disputes. The completed PDF sample remained in the isolated local demo database.
- Verification on a fresh isolated SQLite database: full backend suite **154 passed**; `npm run build --prefix frontend` passed; `git diff --check` passed. Earlier Phase 6 memory measurement for a real image plus PDF was 299 MB conservative combined peak RSS, below the ~450 MB target.

## Step 4: Tests and Documentation (2026-10-26)
- Verified the independent permission matrix covers every role/action cell, creator/reviewer row visibility, manager/reviewer approval boundaries, admin denial, and self-approval prevention.
- Verified the Improvement A/B/C endpoint and unit tests cover DFI calculation/recompute/invalidation, OCR/PDF geometry and image gates, preference-model persistence/training/ranking, and suppression after three distinct disputed findings.
- Created `docs/FEATURES.md` and `docs/ROUND3_IMPROVEMENTS.md` because README linked those files but they were missing. Rewrote `docs/LIMITATIONS.md` to match the current configuration and measured OCR backends; removed unsupported TLS/at-rest and obsolete OCR claims.
- Updated README with exact local setup/run/test commands, production environment requirements, Render's retained Docker runtime rationale, and truthful role responsibilities. Removed the unsupported `EMBEDDING_BACKEND` setting from `.env.example`.
- Updated the in-app Limitations screen so its security, LLM, image, and workspace disclosures match the current code. The Markdown links resolve, `npm run build --prefix frontend` passed, `git diff --check` passed, and the Step 3 full suite remained **154 passed** on its fresh isolated database.

## Step 5: Persistent In-App Notifications (2026-10-26)
- Added an Alembic migration and indexed notification table with per-user read state, authenticated list/read/read-all endpoints, and strict user ownership checks.
- Reviewer assignment creates an inbox item for the assigned reviewer. Approval, changes-requested, and rejection decisions create inbox items for the creator, including the review note. The navbar bell shows an unread count, polls for updates, supports mark-read/mark-all-read, and opens the related submission.
- Integration coverage verifies all three workflow decision types, reviewer assignment delivery, inbox isolation between roles, read state, and bulk mark-read behavior.
- Browser end-to-end check created and checked a standard-risk submission as Creator, requested review, assigned a Reviewer as Manager, confirmed the Reviewer received and opened the assignment notification, approved as Manager, and confirmed the Creator received the approval note and opened the submission. No browser errors/warnings.
- Verification: fresh SQLite migration to head passed; full backend suite **155 passed**; `npm run build --prefix frontend` passed; `git diff --check` passed. Updated README, feature inventory, and limitations to describe the inbox and its event scope.
- Quota check: **79% used, 21% remaining**. Stop optional feature work at this committed state.

## GitHub Sync (2026-10-26)
- Reconciled the in-progress `origin/main` merge while preserving the Phase 6 deployment example and limitations documentation; retained the remote PostgreSQL driver dependency update and clarified the JWT environment-variable description.
- Committed the remaining eligible workspace files in merge commit `23b4bf1` and pushed `main` to `origin`. `.env`, databases, Chroma data, and uploads remain excluded by `.gitignore` and were not committed.

## Assignment Due Dates (2026-10-26)
- Added an Alembic migration for indexed UTC assignment deadlines. Assigning an in-review submission sets a default deadline 24 hours ahead; managers can update or clear a deadline through a manager-only API.
- Manager queues show editable deadlines and overdue state; assigned reviewers see their deadline and overdue state in the Compliance Desk. Closed or unassigned submissions are not marked overdue.
- Added integration coverage for default deadline creation, manager-only updates, role denials, clearing, overdue calculation, and unassigned submissions. A fresh SQLite migration to head passed; the full backend suite passed (**156 tests**); and the frontend production build passed.
- Verification: **156 backend tests passed**, fresh SQLite migration to head passed, frontend production build passed, and `git diff --check` passed. Committed as `9015376`.
- Usage check: **87% used (13% remaining)**. Stop optional feature work at this clean, verified step. Next in order: implement saved views for the existing creator/manager search and filter controls, with persistence, role isolation, and tests; then approval-report CSV/PDF export, self-service password change, dark mode, and first-login onboarding tips.

## Login Credential Error Fix (2026-10-26)
- Public `/auth/login` and `/auth/demo-login` requests no longer send a previously stored bearer token, and their credential 401 responses are shown as authentication errors instead of “Session expired.” Protected API 401 responses still clear the token and redirect to login.
- Added frontend regression tests for both response paths. `npm test --prefix frontend` passed (2 tests), `npm run build --prefix frontend` passed, and `git diff --check` passed.

## Saved Views (2026-10-27)
- Added save, apply, overwrite-by-name, and delete controls to Creator My Work and the Manager Approval Queue. Each view stores its search text and status filter in browser local storage, scoped by user ID and role; views do not sync across browsers or devices.
- Added regression tests for persistence, per-user/per-role isolation, overwrite, deletion, and blank-name validation. `npm test --prefix frontend` passed (**4 tests** total), `npm run build --prefix frontend` passed, and `git diff --check` passed.
- Quota check: **94% used (6% remaining)**. Stop optional feature work at this clean checkpoint. Next in order: approval-report CSV/PDF export; then self-service password change, dark mode, and first-login onboarding tips.

## Approval Report Export (2026-10-27)
- Added Manager/Admin-only CSV and PDF exports for approval, changes-requested, and rejection decisions, with optional start/end filters and spreadsheet formula protection in CSV output. Reports include content, creator, assigned reviewer, decision maker, UTC timestamps, current status, due date, and review note.
- Wired authenticated export actions into Manager and Admin screens. Replaced the Admin audit CSV link with an authenticated download so it sends the required bearer token.
- Added integration coverage for role permissions, date filtering and invalid ranges, CSV content/disposition/formula protection, and PDF generation/content extraction. The full backend suite passed (**161 tests**); frontend tests passed (**4 tests**); frontend production build and `git diff --check` passed.
