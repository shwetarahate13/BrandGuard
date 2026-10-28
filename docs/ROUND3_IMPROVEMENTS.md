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
