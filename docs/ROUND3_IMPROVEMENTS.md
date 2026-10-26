# Round 3 Improvements

## A. Guideline-gap insights

BrandGuard records dispute feedback against the cited guideline clause and computes a dispute-friction index from distinct disputed findings divided by distinct findings. A nightly UTC job refreshes the values; managers and admins can also use **Recompute now**. The health screen sorts clauses by risk and shows friction percentage, dispute clusters, and the current clause text.

For clauses above the high-friction threshold, an Anthropic-backed deployment can request a proposed clarity rewrite. The proposal is a draft: a manager or admin must review and apply it. Applying an edit updates the approved clause and refreshes the retrieval index. Mock/offline mode does not generate a proposal.

Verification lives in `tests/integration/test_round3_endpoints.py`: health ordering/values, recompute, stale-score invalidation, and clause-edit behavior are covered. The browser sweep also ran the manager's recompute action successfully.

## B. Image review and spatial PDF inspection

PDF text extraction keeps page and line coordinates with findings. The review screen renders the uploaded PDF and overlays highlights for findings with coordinates. The real PDF fixture produced eight located findings in the Phase 6 browser/API check.

When `IMAGE_REVIEW_ENABLED=true`, PNG, JPEG, and sanitized SVG files are rasterized for OCR and visual checks. OCR text and word boxes connect findings to regions in the review screen. Visual checks compare detected colors with approved asset metadata, match readable approved logo files, evaluate explicit clear-space rules, and compute contrast for detected text when the corresponding guideline exists. SVG scripts, active elements, and external references are rejected. The image size ceiling is 12 megapixels.

Tesseract is the default OCR backend and the Render Docker configuration selects it. RapidOCR/ONNX remains configurable for larger instances. Image review is disabled by default in application settings; Render's demo configuration explicitly enables it. A real image/PDF fixture run with Tesseract measured about 299 MB combined app and OCR-child peak RSS. A separate RapidOCR/OpenCV measurement reached about 611 MB on the development Mac, so it is not selected for the Render free deployment.

Verification is in `tests/unit/test_content_handlers.py` and `tests/integration/test_round3_endpoints.py`; the full workflow suite passed after a fresh SQLite migration. The manual browser pass confirmed OCR-linked image findings and PDF page highlights.

## C. Reinforcement feedback loop

Accepted and edited rewrites, creator disputes, and compliance dismissals update a persisted online logistic-regression model. Its features include sentence length, readability, and formality changes. The confidence pipeline uses its estimated acceptance probability to rank rewrite candidates. The feedback endpoint and dashboard report acceptance rate, edit rate, and suppression totals by category; the admin screen can reset the learned model.

Repeated disputes are grouped by guideline clause and normalized text span. After three distinct findings match a pair, later matching findings are suppressed across categories. This is workspace-wide because the current database has no team or tenant boundary.

Verification is in `tests/integration/test_round3_endpoints.py` and the preference-model unit tests. Coverage includes training labels and persistence, candidate ranking, reviewer-dismissal feedback, category statistics, cross-category suppression, and invalidation of guideline-health values after new feedback.
