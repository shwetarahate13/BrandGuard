# Known Limitations and Disclosures

This page describes the current implementation in the repository. Hosting providers and their service plans can add their own operational behavior and controls.

## Review scope

- BrandGuard does not publish content to a CMS, social network, or advertising platform. A human must complete any publishing step outside the app.
- TXT, DOCX, and PDF uploads are extracted for text review. PDF findings include page coordinates for visual highlights; complex columns, rotated text, or decorative layouts can make a highlight approximate. DOCX is checked as extracted text rather than rendered page layout.
- PNG, JPEG, and sanitized SVG files can be checked for OCR text, approved palette metadata, logo matches, measurable clear space, and detected-text contrast. SVG external references and active content are rejected. Image review is disabled by default and requires `IMAGE_REVIEW_ENABLED=true`.
- The OCR backend is configurable. Tesseract is the configured default and is used by the Render Docker deployment; RapidOCR/ONNX is optional. A real Tesseract image-review run measured about 240 MB for the app process plus 59 MB for its OCR child process (about 299 MB combined). A separate RapidOCR/OpenCV run reached about 611 MB on the development Mac. These are sample measurements, not deployment guarantees; use Tesseract for the Render free configuration.
- OCR can miss or misread stylized text. Palette checks need color values in approved asset metadata. Logo matching needs a readable approved logo file. Clear-space checks need an explicit measurable minimum. Contrast checks cover detected word regions. EXIF/IPTC metadata is not read.
- PDF and image uploads are capped at 5 MB. Raster image dimensions are capped at 12 megapixels. Text review is capped at 5,000 words per check.
- The data model has no separate organization or team boundary. Submission access is scoped by role and creator/reviewer assignment, but guideline feedback statistics and repeated-dispute suppression apply across the single workspace. A repeated clause/span is suppressed after three distinct findings.
- The Creator dashboard's activity summary is derived from recent decisions and review comments. The persistent in-app inbox covers reviewer assignment and workflow approval/changes/rejection events; it does not notify on finding-level accept/edit/dispute decisions, comments, or email.
- New reviewer assignments in review receive a 24-hour default deadline. Managers can change or clear it; managers and assigned reviewers see whether it is overdue. Deadlines are stored in UTC and displayed in each browser's local time.
- Managers and admins can export approval decisions as CSV/PDF with optional API date filters. These reports cover decisions recorded in the current workspace database; they are not cross-workspace or externally archived reports.
- Proposed guideline wording is created only when the Anthropic provider is configured with an API key. In mock/offline mode, the app computes friction metrics but does not draft wording. When Anthropic is enabled for content review, each text segment, the creator's declared intent, and retrieved source excerpts are sent to the provider; guideline rewrite requests send the current clause and dispute examples. Review the provider's current terms and data controls before using it with sensitive content.
- Rate limits and login lockouts are stored in process memory. Multiple workers or replicas do not share their counters.
- There is no real-time collaborative editing. Users create distinct revisions, review word-level diffs, and exchange structured comments.

## Deployment and data

- Dark mode is a browser-local preference and does not sync across browsers or devices.
- Role onboarding tips appear on first sign-in in each browser; reopening Tips is always available in the signed-in navigation. Dismissal is stored per account and role in browser storage.

- SQLite is the local default. Production configuration requires PostgreSQL. Apply schema changes with `alembic upgrade head`.
- Render remains on the repository's Docker runtime because image review needs the Tesseract system package. `render.yaml` enables image review for the demo service and selects Tesseract. The repository's `build.sh` can build the frontend, install backend requirements, and apply migrations in a native environment that has Node.js 18+; it does not change the configured Render runtime.
- Render's Chroma index is stored under `/tmp/chroma`, so it is disposable. PostgreSQL stores approved source records; the app rebuilds an empty vector index from those records at startup. Keep backups of PostgreSQL data using the database provider's controls.
- The application exposes liveness routes at `/healthz`, `/api/health`, and `/api/healthz`. A liveness response does not verify the database, LLM provider, or OCR runtime; detailed system status is restricted to admins.

## Security and privacy boundaries

- Passwords are hashed with bcrypt. New passwords must be at least 12 characters and no more than 72 UTF-8 bytes. JWTs use HS256 and default to an eight-hour lifetime; production requires a configured secret of at least 32 bytes.
- Users can change their own password after verifying their current password. Seeded shared demo accounts keep their throwaway passwords while `DEMO_MODE=true` so the published demo credentials remain valid.
- Login lockout and endpoint rate limiting are process-local, as described above. The application does not provide a shared distributed rate-limit store.
- CORS uses an explicit origin allowlist. Local Vite development proxies API requests and does not need a CORS entry.
- If an external LLM provider is enabled, it processes the review or rewrite inputs described above. Mock/offline mode makes no external LLM request.
- This repository configures application security headers. HTTPS termination, database encryption at rest, backups, and retention depend on the selected hosting and database providers and their settings; the application does not independently verify those controls.
- Demo credentials are created only when `DEMO_MODE=true` and the database is empty. Keep demo mode off for private workspaces and never use the throwaway demo passwords for real accounts.
