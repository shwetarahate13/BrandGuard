# Limitations

BrandGuard is a local judging and review application, not a multi-user hosted service. Run one application process for one local workspace. In-process rate limits, scheduled recomputation, and background-job status are not shared across processes; restarting the application stops queued work and loses its transient progress records.

## Review limits

- Human reviewers remain responsible for legal, accessibility, and brand decisions. BrandGuard does not publish to external channels.
- PDF review uses extracted text and page coordinates. Complex columns, rotation, and decorative layouts can make highlights approximate. DOCX is checked as extracted text, not as rendered pages.
- OCR can miss stylized, low-contrast, or rotated text. Palette checks require RGB values in approved asset metadata. Logo matching needs a readable approved logo file. Clear-space checks need a measurable guideline; contrast checks cover detected text regions.
- SVG active content and external references are rejected. Raster image dimensions are limited to 30 megapixels. Uploads are limited to 25 MB and each text check to 20,000 words.
- The local neural retrieval model is loaded in the background. If it is missing or cannot load, BrandGuard uses the labelled hashing-vectorizer fallback until restarted after the issue is corrected.
- The pip-only RapidOCR runtime may be slower on machines without hardware acceleration. OCR, PDF extraction, and content reviews use bounded background workers and report a timeout; a timed-out native library call may continue until that worker returns.
- Clause rewrite proposals and optional content checks use an external language model only when configured. In mock/offline mode no provider request is made, and guideline rewrite proposals are not generated.
- The database has no tenant boundary. Guideline feedback and repeat-dispute suppression are workspace-wide. Files and indexes are stored locally and are not backed up by the application.

## Requirements and security boundaries

- Python 3.11 or newer is required. First setup installs the pinned OCR, PDF, OpenCV, database, and neural retrieval dependencies and downloads the all-MiniLM-L6-v2 model (about 100 MB). Allow several gigabytes of free disk space for the environment, model, and local data.
- SQLite is the default local database; PostgreSQL is supported through `DATABASE_URL`. Apply schema changes only with Alembic. Backups and encryption at rest are the operator's responsibility.
- Login lockout and request rate limits are process-local. There is no real-time collaborative editing.
- The audit hash chain detects changes relative to its stored chain head but is not an independent timestamp. An operator with full database control can rebuild the chain; publishing the chain head to an independently controlled system is needed to detect that case.
- If a live language model is enabled, review text, stated intent, and retrieved source excerpts may be sent to that provider. Check its data terms before using sensitive material.
