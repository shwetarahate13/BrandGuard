# Round 3 Improvements: As Built

This document records the delivered behavior for the three Round 3 improvements. The completed feature matrix is in [`FEATURES.md`](FEATURES.md).

## Improvement A: Guideline-Gap Insights

The nightly APScheduler job groups disputed findings by cited guideline clause, clusters available dispute reasons with TF-IDF cosine similarity, and stores each clause's DFI as a percentage of distinct disputed findings over distinct findings.

Managers and admins can read `/api/guidelines/health` and use `/dashboard/guideline-health` to sort and review risk bands. Clauses above 30% receive proposed wording only when a live LLM provider is configured. `PATCH /api/guidelines/clauses/{clause_id}` applies a revision and refreshes the approved-source index.

## Improvement B: Image Review and Spatial PDF Inspection

### Image uploads

PNG, JPEG, and SVG uploads are retained with extracted OCR text and word boxes. Visual checks compare dominant colors with RGB colors recorded in approved asset metadata, search for accessible approved logo files with OpenCV template matching, check measurable clear-space rules in guideline text, and calculate WCAG AA contrast for OCR-detected text regions. The review UI shows original images with canvas-drawn boxes linked to findings.

Clear-space findings require both a readable approved logo file and an explicit measurable minimum in a guideline. Palette findings require color metadata on approved assets. The checks do not interpret EXIF/IPTC fields.

### PDF uploads

pdfminer.six extracts page text and line boxes. Each finding stores a page number and bounding box; the review UI renders semi-transparent highlights on the matching PDF page. DOCX review remains text-based.

## Improvement C: Reinforcement Feedback Loop

Decision records snapshot the original span, proposed rewrite, and human edit. The online SGD logistic-regression classifier uses sentence-length change, Flesch readability change, and formality change, then persists its state as a database blob. Accept decisions train positive examples; edits train the rejected suggestion and reviewer-selected wording; disputes train a negative suggestion example.

The confidence pipeline scores and ranks candidate findings by predicted rewrite acceptance probability. Findings that cite the same clause and normalized original span are suppressed after three distinct disputed findings. The current application stores one brand workspace per database, so suppression is workspace-scoped rather than partitioned by a separate team identifier.

`GET /api/feedback/stats` returns acceptance rate, edit rate, and suppressed-pattern counts by finding category. The main dashboard displays these values.
