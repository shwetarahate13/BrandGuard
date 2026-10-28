# Round 3 improvements

These are the three committed Round 2 improvements, with their current local implementation.

## A. Guideline-Gap Insights

BrandGuard groups disputed findings by cited guideline clause, clusters similar dispute reasons with TF-IDF cosine similarity, and calculates the Dispute Friction Index from distinct disputed findings divided by distinct findings. Managers and admins can view sortable risk bands and use **Recompute now**; stale health data is refreshed on read. Clauses above 30% receive a live LLM suggestion when configured, or a clearly labelled offline clarification template with prompts that must be replaced before applying. A manager or admin reviews and applies a revision, which refreshes retrieval data.

## B. Image Review and Format-Aware PDF Inspection

PDF extraction stores page and line coordinates; the review screen displays page highlights for located findings. PNG, JPEG, and sanitized SVG uploads use pip-installed RapidOCR by default and retain OCR text boxes. Image checks compare dominant colors against approved palette metadata, match readable approved logo files, enforce measurable clear-space rules when supplied, and evaluate detected text contrast when an accessibility clause exists. Finding selection links to the corresponding canvas box. If RapidOCR is missing, the upload error tells the user to rerun `scripts/setup_local.py`. Raster images are limited to 30 megapixels.

The embedding and OCR models load on demand. The navigation badge shows model warm-up and the active retrieval engine. If the neural model cannot load, a labelled HashingVectorizer fallback keeps retrieval available.

The local demo seed includes three fictional disputes on one guideline clause. Opening Guideline Health after the seed runs shows a clause above 30% DFI and a repeated span that the feedback loop suppresses.

## C. Reinforcement Feedback Loop

Accepted rewrites, human edits, creator disputes, and reviewer dismissals train a persisted online logistic-regression model. The model uses sentence-length, readability, and formality changes to rank suggested rewrites. Dashboards show acceptance/edit statistics. The same normalized span and clause is suppressed after disputes on three distinct findings. Statistics and suppression are workspace-wide because the current database has no tenant boundary.

## Verification

Tests are maintained in `tests/unit/` and `tests/integration/`. The main workflow and role-specific browser path are documented in [JUDGE_GUIDE.md](JUDGE_GUIDE.md). The local setup and current limits are described in the [README](../README.md) and [LIMITATIONS.md](LIMITATIONS.md).

## Phase 4 — reviewer workbench and approval controls

High-risk submissions, including findings that cite expired or outdated approved facts, need assigned reviewer sign-off for the latest content version before a manager can issue final approval. Reviewer sign-off is stored as its own record with evidence notes, justification, and four required checklist items. It does not transition the submission to approved or create an approval certificate. The final manager must be a different user from the reviewer.

The reviewer queue presents the claim excerpt and cited evidence side by side. Confirming or dismissing a finding requires a written justification. The reviewer dashboard reports turnaround time, confirmed and dismissed counts, and the rate of findings later changed by another user. The role permission tests check every action for each of the four roles, including the reviewer's lack of final-approval permission.

Phase 4 verification: targeted workflow and permission tests passed (122); full backend suite passed (203, 1 skipped); frontend TypeScript and production build passed. `backend/app/static` was rebuilt from the frontend output.
