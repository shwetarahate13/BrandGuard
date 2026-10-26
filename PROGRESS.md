# BrandGuard - Progress & Phase Checklist

## Status Summary
- **Current Phase**: Phase 2 (Roles That Are Really Different & An Exciting UI)
- **Phase Checklist**:
  - [x] **Phase 1: Fix Existing Bugs First**
    - [x] Run backend tests (identified missing Alembic migrations on existing SQLite DB; applied to head; 22/22 tests passing)
    - [x] Test frontend build (`npm run build` succeeds)
    - [x] Audit all API endpoints, routes, status codes, and error handlers
    - [x] Fix offline Flesch readability calculation in `preference_model.py` (avoid NLTK cmudict download failures)
    - [x] Smoke test & E2E verification of all current flows (`smoke_test.py` passes 100%)
  - [ ] **Phase 2: Roles That Are Really Different & An Exciting UI**
    - [ ] Create permission matrix in `backend/app/services/permissions.py`
    - [ ] Enforce 403 on every endpoint and disallow self-approval
    - [ ] Add unit test for every permission matrix cell
    - [ ] Role-specific frontend navigation, landing pages, and views:
      - Creator: "My Work", own submissions only, fix findings, personal stats & notifications
      - Manager: Team command center, approval queue with SLA/age, reviewer assignment, sign-off, org insights, guideline health
      - Reviewer: Compliance desk, assigned items & escalated findings, side-by-side claim checking, justification, compliance notes
      - Admin: User management, approved-sources registry, system settings, full audit log with filters and CSV export, feedback model stats/reset
    - [ ] Redesign dashboards: KPI cards, trend charts, category/severity breakdowns, status pipeline board, activity feed, skeleton loaders, empty states, toasts, WCAG AA contrast
  - [ ] **Phase 3: Improvement A, Guideline-Gap Insights**
    - [ ] Nightly APScheduler job grouping disputed findings by cited guideline clause
    - [ ] TF-IDF cosine similarity dispute clustering
    - [ ] Dispute Friction Index (DFI) calculation: distinct disputed findings / distinct findings (%)
    - [ ] `GET /api/guidelines/health` (managers and admins)
    - [ ] `/dashboard/guideline-health` page with sortable risk bands
    - [ ] Proposed clearer wording for DFI > 30% (live LLM only)
    - [ ] `PATCH /api/guidelines/clauses/{clause_id}` to apply revision and re-index vector store
    - [ ] "Recompute now" button and stale-check auto-recompute on read
  - [ ] **Phase 4: Improvement B, Image Review and Spatial PDF Inspection**
    - [ ] Pip-only OCR (`rapidocr-onnxruntime`, no system Tesseract) and `opencv-python-headless`
    - [ ] Dominant color extraction vs approved asset RGB
    - [ ] OpenCV template matching for approved logos
    - [ ] Measurable clear-space checking from guideline text (only when logo file + explicit minimum exist)
    - [ ] WCAG AA contrast calculation for OCR-detected text regions
    - [ ] Canvas-drawn visual bounding boxes linked to findings in review UI
    - [ ] PDF inspection with `pdfminer.six` page coordinates and bounding boxes in `location`
    - [ ] Semi-transparent visual highlight on PDF pages in review UI
    - [ ] Lazy loading & RSS memory budget (< 450 MB) / environment flag
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
2. **Pip-only OCR**: Render free has no apt package manager and 512MB RAM cap. We will replace `pytesseract` with `rapidocr-onnxruntime` and `opencv-python-headless` with lazy loading to ensure memory consumption stays under 450 MB.
3. **Offline Flesch Calculation**: Avoid reliance on external NLTK network downloads for cmudict by implementing a deterministic syllable-counter fallback for Flesch reading ease in `preference_model.py`.

## Exact Next Step
Execute Phase 2: Create `backend/app/services/permissions.py`, enforce the permission matrix across all endpoints with 403 Forbidden checks, disallow self-approval, add comprehensive cell tests in `tests/unit/test_permissions.py`, and implement distinct role-based UI flows (Creator "My Work", Manager Command Center, Reviewer Compliance Desk, Admin Management) with modernized accessible UI.
