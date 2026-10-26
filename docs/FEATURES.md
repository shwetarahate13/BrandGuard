# Implemented Features

This inventory reflects behavior present in the current application. It does not describe planned work.

## Content review

- Create a text submission or upload supported TXT, DOCX, PDF, PNG, JPEG, or SVG content within the 5 MB upload limit.
- Check content against approved guideline clauses, facts, and terminology. Findings include their cited source and quote, status/severity, and a suggested rewrite when one is available.
- Accept, edit, or dispute a finding. Accepting or editing a fix creates a new revision; revisions must be checked before a creator can request review.
- Inspect PDF page highlights and OCR-linked image findings when image review is enabled.
- Managers can request changes or reject a submission. Creators can revise, recheck, and resubmit. A manager can approve standard-risk copy; high-risk approval requires an assigned reviewer. No user can approve their own submission, and admins cannot approve submissions.

## Role-specific workspaces

- **Creator:** My Work dashboard, own submissions, title/intent search, saved search/status views scoped to the account in this browser, review findings, revision workflow, feedback metrics, and persistent notifications for workflow decisions.
- **Manager:** Team Command Center, organization trends and feedback statistics, status/search filters and saved views scoped to the account in this browser, submission age against the four-hour SLA target, reviewer assignment with a default 24-hour due date, manager-editable deadlines and overdue state, standard-risk approval, changes requested/rejected, and guideline health.
- **Reviewer:** Compliance Desk, assigned submissions and escalated findings, assignment deadlines and overdue state, source lookup, compliance notes, and high-risk sign-off for assigned submissions.
- **Admin:** User and role management, account activation and password reset, approved-source management, runtime settings, system status, audit log and CSV export, feedback statistics/reset, and organization insights.

Managers and admins can export the full workflow approval/changes/rejection history as CSV or PDF. Both formats include decision, submission, creator, reviewer, timestamp, status, deadline, and review note; optional ISO date filters are available on the authenticated API.

Signed-in users can change their own password after verifying the current password. Shared seed demo-account passwords stay fixed while demo mode is enabled so the published one-click credentials keep working.

Dark mode can be toggled from the navigation bar and its preference is saved in the current browser.

The notification bell is available to signed-in roles. Reviewer assignment events go to the assigned reviewer; approval, changes-requested, and rejection decisions go to the creator. Notifications have read/unread state and open the related submission.

## Guideline health (Improvement A)

- A nightly UTC job and manager/admin **Recompute now** action calculate dispute friction by clause and show risk bands, repeated dispute themes, and clause wording.
- Managers and admins can review and edit approved clauses. A proposed rewrite appears only when the Anthropic provider and API key are configured; applying a clause edit refreshes the source index.

## Image and PDF inspection (Improvement B)

- PDF extraction stores page/line coordinates and highlights located findings in the review screen.
- With `IMAGE_REVIEW_ENABLED=true`, PNG, JPEG, and sanitized SVG uploads receive OCR text/word locations, approved-palette checks, readable approved-logo matching, configured clear-space checks, and text contrast checks.
- Tesseract is the configured default OCR backend. RapidOCR/ONNX is an optional backend. The Render Docker configuration selects Tesseract.

## Reviewer feedback loop (Improvement C)

- Accept, edit, and dispute decisions train an online logistic-regression preference model persisted in the database. Compliance reviewer dismissals add negative feedback.
- Rewrite candidates can be ranked by predicted acceptance. Feedback statistics show acceptance rate, edit rate, and suppression counts by category.
- A clause and normalized text span is suppressed after disputes on three distinct findings. This count spans categories in the single-workspace database.

## Security and operations

- bcrypt password hashing, 12-character minimum password policy, expiring JWT authentication, login lockout and endpoint rate limits, role and row-level access checks, and explicit CORS origin allowlisting.
- Upload MIME/type validation and size limits, request IDs, structured HTTP request logs, security headers, and friendly unexpected-error responses with a reference ID.
- Alembic-managed schema changes; SQLite local default and PostgreSQL required in production; liveness routes at `/healthz`, `/api/health`, and `/api/healthz`.
- `DEMO_MODE=false` by default. Demo records and login credentials are enabled only by setting `DEMO_MODE=true` on an empty database.

## Current product boundaries

- The Creator dashboard's activity summary remains derived from decisions and comments. Persistent in-app notifications cover reviewer assignments and workflow decisions, but not finding-level decisions, comments, or email delivery.
- Saved views store the current search and status filter in browser local storage, isolated by user and role; they do not sync across browsers or devices.
- Admins can reset another user's password. First-login onboarding tips are not implemented.
- See [LIMITATIONS.md](LIMITATIONS.md) for image-processing, data-scope, rate-limit, and hosting constraints.
