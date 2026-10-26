# BrandGuard - Progress & Phase Checklist

## Status Summary
- **Current Phase**: Phase 4 complete; Phase 5 (Improvement C, Reinforcement Feedback Loop) is next
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
    - [x] Pip-only RapidOCR/ONNX runtime (no Tesseract) with word-level OCR boxes; `opencv-python-headless` remains lazy-loaded
    - [x] Dominant color extraction against approved asset RGB metadata, ±15 per channel
    - [x] OpenCV template matching for readable approved logo files
    - [x] Measurable clear-space checks only when a logo file and explicit minimum both exist
    - [x] WCAG AA contrast calculation for OCR-detected text regions with an approved accessibility clause
    - [x] Canvas overlays and linked finding selection in the image/PDF review screen
    - [x] PDF inspection with `pdfminer.six` page coordinates and finding `location` boxes
    - [x] Semi-transparent PDF page highlights
    - [x] Lazy-loaded OCR/CV and explicit `IMAGE_REVIEW_ENABLED` memory gate; measured image review exceeds the 450 MB target and is disabled by default
  - [ ] **Phase 5: Improvement C, Reinforcement Feedback Loop**
    - [ ] Snapshot original span, proposed rewrite, human edit on decisions
    - [ ] Online SGD logistic regression (sentence length change, Flesch delta, formality delta)
    - [ ] Persist model state in DB blob
    - [ ] Train on accepts (+), edits (chosen +, rejected -), disputes (-)
    - [ ] Rank rewrite candidates by predicted acceptance probability in confidence pipeline
    - [ ] Suppress repeated disputed patterns (same clause + normalized span >= 3 distinct disputes, workspace-scoped)
    - [ ] `GET /api/feedback/stats` (acceptance rate, edit rate, suppression counts)
    - [ ] Dashboard integration and admin model reset
  - [ ] **Phase 6: Real-World Readiness and Deployment (No Docker)**
    - [ ] Local non-Docker setup (uvicorn :8000, vite :5173 with proxy, SQLite/Postgres compatibility)
    - [ ] Render free native runtime (`render.yaml`, `build.sh`, SPA serving on `$PORT`)
    - [ ] Production hardening (secrets validation, bcrypt policy, login rate limiting & lockout, JWT expiry, CORS allowlist, security headers, upload validation 5MB type sniffing, pagination, request IDs, structured logs, `/healthz`, global error handlers)
    - [ ] `DEMO_MODE=true` gate for demo seeds and quick-switch role switcher
  - [ ] **Phase 7: Tests and Docs**
    - [ ] Permission matrix tests
    - [ ] Improvement tests (A, B, C)
    - [ ] Update `FEATURES.md`, `ROUND3_IMPROVEMENTS.md`, `LIMITATIONS.md`, `README.md`

## Decisions Made
1. **Migrations & Database**: SQLite default locally, PostgreSQL (Neon) in production. Database migrations must always be executed via `alembic upgrade head`. Added dispute friction, media layout, and preference state migrations.
2. **Pip-only OCR**: Image OCR uses RapidOCR and ONNX Runtime without system Tesseract. OpenCV and OCR modules are lazy-loaded. Because measured peak memory exceeded Render free's 512 MB cap, image review is opt-in through `IMAGE_REVIEW_ENABLED` and remains off on the free tier.
3. **Offline Flesch Calculation**: Avoid reliance on external NLTK network downloads for cmudict by implementing a deterministic syllable-counter fallback for Flesch reading ease in `preference_model.py`.
4. **Role policy**: Only creators create submissions and decide findings; managers handle standard-risk workflow and assign active reviewers; reviewers resolve escalations and sign off high-risk assigned items; admins manage the system but cannot approve. High-risk submissions are not manager-approved.
5. **Manager observability**: Trends and activity come from persisted submissions, findings, and audit records. Creator notifications are derived from actual approvals and review comments; empty accounts show an empty state instead of demo copy.
6. **Public system metadata**: `/system/mode` exposes only the active LLM mode for the navigation badge; detailed `/system/status` requires the Admin permission.
7. **Phase 2 verification**: 111 targeted permission/API tests passed, Vite production build passed, full SQLite migration chain applied with the reviewer FK verified, and the isolated end-to-end workflow smoke passed. Browser checks confirmed Creator, Manager, Reviewer, and Admin dashboards/nav; browser console had no errors or warnings. A local Vite proxy target was supplied through `BRANDGUARD_API_PROXY_TARGET` during UI verification; native local defaults are scheduled for Phase 6.
8. **Phase 3 verification**: DFI session ownership now supports both request Sessions and APScheduler session factories. Newly computed timestamps and source-data invalidation prevent stale scores; a read recomputes stale data. SQLite Alembic upgrade to head and `npm run build` passed; the targeted permission/API suite passed 113 tests. One existing Chroma embedding-function deprecation warning remains.
9. **Phase 4 verification**: RapidOCR 3.10.0 (packaged ONNX models) processed the real 1020×1320 sample image into 455 characters and 77 word boxes; `pdfminer.six` extracted page/line boxes from the real PDF fixture. Palette, logo clear-space, OCR geometry, PDF location, and image-memory-gate tests passed (17 targeted tests). Full-app OCR plus OpenCV peak RSS measured 611 MB on the development Mac, so image uploads/reviews require explicit `IMAGE_REVIEW_ENABLED=true`; `docs/LIMITATIONS.md` records the Render-free-tier restriction. `pip check`, Python compile, and diff checks passed.

## Exact Next Step
Commit the completed Phase 4 image/PDF inspection changes, then start Phase 5 by tracing decision snapshot persistence, the existing SGD model blob, confidence ranking, and workspace-scoped dispute suppression before extending them.
