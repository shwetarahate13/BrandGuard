# Engineering Assumptions & Design Decisions

This document records sensible assumptions made during the autonomous build of **BrandGuard Round 2** by Team **Nexora**.

---

## 1. Brand Kit & Sample Data Persona
- **Assumption**: We created **Aurelia Foods** (a fictional Pacific Northwest artisan organic pantry and beverage brand) as the reference enterprise brand.
- **Rationale**: An artisan food and wellness brand provides clear, realistic tests across all required governance categories:
  - Regulatory claims (FDA health disclaimers, adaptogen claims)
  - Superlatives ("world's best", "guaranteed", "clinically proven")
  - Certified facts vs. outdated statistics (renewable energy percentages, historical subscription box pricing)
  - Accessibility (alt text in markdown recipes, descriptive links, readability).

## 2. Embeddings Strategy on 512 MB RAM Budget
- **Assumption**: Retrieval uses Scikit-Learn's `HashingVectorizer(n_features=256, norm='l2')` for production.
- **Rationale**: PyTorch and sentence-transformers consume > 400 MB of resident memory upon initialization. Using TF-IDF hashing embeddings reduces memory to < 5 MB and total container footprint to ~200 MB, guaranteeing zero Out-Of-Memory crashes on Render's free tier.

## 3. Substring Citation Matching Tolerance
- **Assumption**: When validating `source_quote` against the source text, we perform exact substring matching, followed by normalized word matching (stripping punctuation and whitespace), with a 75% sliding window fuzzy fallback.
- **Rationale**: LLMs occasionally trim leading/trailing punctuation or articles when quoting. Strict string equality would cause false drops of valid citations, while a 75% window preserves semantic fidelity without allowing ungrounded hallucinations.

## 4. Automatic Clause Splitting on Document Import
- **Assumption**: When an admin imports a guideline document (via pasted text, PDF, or DOCX), BrandGuard automatically parses sections into distinct `GuidelineClause` entities by detecting Markdown headers (`#`, `##`), numbered clauses (`1.1`, `Clause 2:`), or double paragraph breaks.
- **Rationale**: Enables bulk import of real-world brand books into granular, citable units without forcing administrators to manually copy-paste every paragraph.

## 5. Intent-Preserving Rewrite Anchor Extraction
- **Assumption**: Verification of intent preservation evaluates word roots (minimum length 4 characters) shared between the suggested fix and the original span or creator's stated intent.
- **Rationale**: Creators frequently state intents like *"Highlight fairly priced sourdough"* while the avoided term is *"cheap"*. Root extraction (`pric` in `priced` and `pricing`) validates that the approved replacement (*"accessible pricing"*) preserves the creator's purpose.

## 6. Cold-Start Handling
- **Assumption**: Render free tier containers sleep after 15 minutes of inactivity and take ~45 seconds to wake up.
- **Rationale**: Rather than letting the frontend show network failure or a generic error, we implemented a 2.5s timer that automatically surfaces a reassuring banner: *"Waking up the server instance on Render free tier..."*.
