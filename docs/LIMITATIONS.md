# Limitations

BrandGuard is a local judging and review application, not a multi-user hosted service. Run one application process for one local workspace. In-process rate limits, scheduled recomputation, and background-job status are not shared across processes; restarting the application stops queued work and loses its transient progress records.

## Review limits

- Human reviewers remain responsible for legal, accessibility, and brand decisions. BrandGuard does not publish to external channels.
- The writing assistant checks English only. It uses a heuristic to skip text that is mostly non-Latin or contains multiple common Spanish, French, German, or Portuguese markers. This is not a language detector; mixed-language text can be misclassified, and the checker does not support non-English grammar or spelling.
- Spelling coverage is a small bundled list of reviewed common mistakes, not a general dictionary. Unknown words are ignored to avoid flagging product names and brand terms; manage additional protected words in the Admin Brand words setting. The grammar checks are deterministic and conservative, covering a limited set of simple patterns. They are weaker than a full grammar checker and may miss errors or flag an unusual but intentional construction.
- A configured LLM can add sourced findings in the broader compliance review, but it does not supply extra grammar or spelling suggestions. The offline writing rules run with or without an LLM key. Unsupported claims without an approved supporting fact stay with the reviewer instead of receiving an invented replacement.
- The under-two-second performance target applies to the offline writing checker on a 1,000-word sample, not to the complete review pipeline. Retrieval, document extraction, and any configured provider can make a complete review take longer; review jobs are bounded by the local worker timeout.
- PDF review uses extracted text and page coordinates. Complex columns, rotation, and decorative layouts can make highlights approximate. DOCX is checked as extracted text, not as rendered pages.
- OCR can miss stylized, low-contrast, or rotated text. Palette checks require RGB values in approved asset metadata. Logo matching needs a readable approved logo file. Clear-space checks need a measurable guideline; contrast checks cover detected text regions.
- SVG active content and external references are rejected. Raster image dimensions are limited to 30 megapixels. Uploads are limited to 25 MB and each text check to 20,000 words.
- The local neural retrieval model is loaded in the background. If it is missing or cannot load, BrandGuard uses the labelled hashing-vectorizer fallback until restarted after the issue is corrected.
- The pip-only RapidOCR runtime may be slower on machines without hardware acceleration. OCR, PDF extraction, and content reviews use bounded background worker processes and report a timeout; terminating a timed-out worker can discard its transient progress record.
- Clause rewrite proposals and optional content checks use an external language model only when configured. In mock/offline mode no provider request is made, and guideline rewrite proposals are not generated. The writing assistant's deterministic grammar and spelling rules are offline-only.
- Expired facts are labelled in the source registry and checked during new content reviews. BrandGuard does not yet track every already-approved document affected by a fact that expires, changes, or is removed, and it does not create a one-click recheck draft for those documents.
- External agency review links are not included. Reviewers must use a BrandGuard account; public certificate verification exposes certificate validity only and does not provide access to submission content or comments.
- The database has no tenant boundary. Guideline feedback and repeat-dispute suppression are workspace-wide. Files and indexes are stored locally and are not backed up by the application.

## Requirements and security boundaries

- Python 3.11 or newer is required. First setup installs the pinned OCR, PDF, OpenCV, database, and neural retrieval dependencies and downloads the all-MiniLM-L6-v2 model (about 100 MB). Allow several gigabytes of free disk space for the environment, model, and local data.
- SQLite is the default local database; PostgreSQL is supported through `DATABASE_URL`. Apply schema changes only with Alembic. Backups and encryption at rest are the operator's responsibility.
- Login lockout and request rate limits are process-local. There is no real-time collaborative editing.
- The audit hash chain detects changes relative to its stored chain head but is not an independent timestamp. An operator with full database control can rebuild the chain; publishing the chain head to an independently controlled system is needed to detect that case.
- If a live language model is enabled, review text, stated intent, and retrieved source excerpts may be sent to that provider. Check its data terms before using sensitive material.
