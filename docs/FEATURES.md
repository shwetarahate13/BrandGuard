# Features

This inventory describes behavior in the current local application.

## Content review

- Create text submissions or upload TXT, Markdown, HTML, DOCX, PDF, PNG, JPEG, or sanitized SVG files. Uploads support up to 25 MB; text checks support up to 20,000 words.
- Review copy against approved guideline clauses, facts, terminology, accessibility rules, and optional configured language-model checks. Findings link to their cited source and quote.
- Accept, edit, or dispute findings; creators can revise, recheck, and resubmit. Managers can request changes, reject, or approve standard-risk work. High-risk work needs reviewer sign-off before manager approval. Self-approval is blocked.
- PDF findings include extracted page coordinates and visible highlights. Images use OCR-linked text boxes and visual checks against configured approved assets and guidelines.
- Slow document extraction and review run as bounded local background jobs with progress and a time limit. A retrieval-engine badge shows model warm-up or the active neural/hash engine.

## Round 3 improvements

- **A — Guideline-Gap Insights:** dispute-friction index by cited clause, similar-reason clusters, risk bands, recompute action, and clause revision.
- **B — Image Review and Format-Aware PDF Inspection:** pip-only OCR, image palette/logo/clear-space/contrast checks, PDF page and line coordinates, and linked review overlays.
- **C — Reinforcement Feedback Loop:** persisted online preference model trained from reviewer decisions, acceptance statistics, and suppression after three distinct disputes for the same normalized clause/span.

See [ROUND3_IMPROVEMENTS.md](ROUND3_IMPROVEMENTS.md) for implementation detail and [LIMITATIONS.md](LIMITATIONS.md) for boundaries.

## Additional capabilities

### Writing assistant

- The offline writing checker reports common misspellings from a small, reviewed correction list and 11 conservative grammar rules. Each result uses the seeded `STYLE-1` guideline, keeps the exact text span for review, and has a stable rule ID. Admins can maintain the brand-word allowlist; code, markup, URLs, email addresses, mentions, and hashtags are protected from those checks.
- Review findings are grouped by writing and compliance category and show the cited reason with a before/after diff when a replacement is available. Creators can accept, edit, or dispute individual suggestions, preview the combined draft, apply eligible high-confidence grammar/spelling or other safe fixes, edit the draft directly, recheck it, and use version history to undo a revision.
- Unsupported claims are not rewritten from guesswork. A replacement that cannot be grounded in an approved fact remains with the reviewer. Claims and facts are excluded from the safe batch actions.
- The New Submission sample picker includes grammar/spelling-heavy copy and a separate guideline/regulatory example alongside the existing demo samples.

The deterministic writing checker works offline. The optional configured model is used by the broader sourced compliance review; it does not extend the writing checker's spelling dictionary or grammar rules. See [LIMITATIONS.md](LIMITATIONS.md) for language and coverage boundaries.

## Role workspaces

- **Creator:** own submissions, checks, finding decisions, revision and resubmission, activity and feedback statistics, notifications, and onboarding tips.
- **Manager:** team queue, assignment and due dates, approval decisions, organization metrics, guideline health, and approval-report export.
- **Reviewer:** assigned compliance work, escalated findings, evidence notes, required sign-off checklist, and reviewer metrics.
- **Admin:** account and approved-source management, runtime status, audit and integrity tools, feedback reset, and organization insights.

Other implemented capabilities include saved browser-local views, CSV/PDF approval reports, password change/reset, dark mode, first-run role tips, tamper-evident audit records, approval certificates, and public certificate verification.

## Demo workspace

With `DEMO_MODE=true`, the local setup creates four throwaway role accounts and at least 15 fictional, explicitly flagged submissions across draft, checked, in-review, changes-requested, approved, and rejected states. The seed includes planted claim, pricing, expired-fact, typo, tone, accessibility, PDF, and image examples. Re-running the seed adds missing examples without duplicating or resetting submissions. The login page exposes one-click demo sign-in only while demo mode is enabled. The New Submission picker has six core review examples plus two writing-assistant examples.

## Local operations

- SQLite is the local default; PostgreSQL is supported through `DATABASE_URL`. Schema changes use Alembic.
- `python scripts/setup_local.py` installs pinned Python dependencies, downloads the neural retrieval model, creates `.env`, migrates the database, and seeds demo data when enabled. `python scripts/run_local.py` serves the prebuilt app on one port; Node.js is not needed at runtime.
- `python scripts/doctor.py` checks Python, dependencies, storage, database access, model files, and the committed frontend bundle.
