# Round 3 Major Improvements Specification (Planned)

> [!NOTE]
> The features outlined below are **planned for Round 3 and are NOT coded in the Round 2 build**.
> In accordance with hackathon instructions, the Round 2 codebase contains the foundational architectural hooks (content-type registry, source-type enums, location JSON schemas) but zero stub screens or half-built endpoints.
>
> *(Note: **Improvement 1: Intent-Preserving Fixes with Word-Level Diff** was completed in Round 2 and is documented in [`docs/FEATURES.md`](FEATURES.md).)*

---

## Improvement A: Guideline-Gap Insights & Guideline Health Analytics

### 1. What It Is
An executive brand health analytics suite that analyzes dispute patterns and recurring creator objections at the individual clause level. Rather than only flagging content errors, it diagnoses **friction in the brand guidelines themselves** and generates AI-assisted clarification proposals for brand directors.

### 2. Why It Matters
In growing enterprises, high finding dispute rates (e.g., creators constantly disputing a tone rule) often signal that the brand guideline is ambiguous, outdated, or unrealistic. Current tools treat guidelines as static; Guideline-Gap Insights turns the governance engine into a two-way feedback loop where guidelines evolve alongside organizational needs.

### 3. How We Will Build It on Current Architecture
- **Data Foundation**: Leverages the existing `decisions` table (`action='dispute'`, `reason`, `finding_id`) and relational links to `guideline_clauses`.
- **Aggregation Worker**: A scheduled background job will cluster dispute justifications using TF-IDF / vector similarity, calculating a **Dispute Friction Index (DFI)** per clause.
- **Guideline Revision Proposals**: Clauses with a DFI > 30% will trigger automated clarification drafts submitted to the Brand Manager for review and one-click guideline updating.

---

## Improvement B: Image Review & Format-Aware Document Inspection

### 1. What It Is
1. **Visual Asset Review**: Inspecting image files and document graphics for approved logo clear-space, brand color palette compliance (Netarts Bay gold, forest charcoal), contrast ratios, and embedded EXIF/IPTC metadata.
2. **Format-Aware Review**: Upgrading PDF and Word review from plain text extraction to coordinate-aware spatial review, linking findings to specific page numbers, columns, and visual bounding boxes.

### 2. Why It Matters
Marketing materials rely heavily on imagery and structured layout. A marketing brochure might have compliant copy but violate logo placement or use low-contrast text on background graphics that violates WCAG AA standards.

### 3. How We Will Build It on Current Architecture
- **Location JSON Schema**: The `findings` table already includes a nullable `location` JSON column (`page`, `bbox`, `xpath`), ready for spatial annotations.
- **Content-Type Handler Registry**: We will register visual handlers for `image/png`, `image/jpeg`, and `image/svg` using lightweight OpenCV / Pillow routines to inspect dominant RGB/HEX palettes and logo clear-space against `assets` records.
- **PDF Annotation Engine**: Integrating `pdfminer.six` layout coordinates to render interactive visual highlight overlays directly atop PDF page canvases in the React review screen.

---

## Improvement C: Reinforcement Feedback Loop (Adaptive Confidence & Ranking)

### 1. What It Is
A calibrated machine learning feedback loop that continuously learns from human decisions (accepted fixes, edited rewrites, and disputed findings). As team members interact with suggestions over time, the system:
1. Re-calibrates confidence scoring thresholds.
2. Dynamically re-ranks suggested rewrites to prioritize patterns preferred by brand managers.
3. Suppresses low-value repetitive false positives that managers consistently dismiss.

### 2. Why It Matters
Static governance engines suffer from fatigue: if an AI model repeatedly suggests a stiff phrasing that authors always edit, user trust degrades. By learning from actual human editorial choices, BrandGuard becomes tailored to the specific stylistic nuances of the organization.

### 3. How We Will Build It on Current Architecture
- **Training Dataset**: Derived directly from the `decisions` table, pairing original span text, suggested rewrite, human edited text, and accept/reject outcomes.
- **Preference Modeling**: Compute feature vectors over accepted vs. edited rewrites (sentence length, readability delta, formality score) to calibrate the confidence scoring module in `backend/app/pipeline/confidence.py`.
- **Ranking Weights**: Update candidate suggestion weights via online logistic regression or bandit scoring before presenting diffs to creators.
