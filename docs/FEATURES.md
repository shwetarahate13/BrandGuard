# BrandGuard Completed Features Matrix (Round 3 Build)

This document tracks all completed features for the Round 2 build of **BrandGuard** by Team **Nexora** (Shweta Rahate, Janvi Thakre).

| # | Feature Area | Status | Location in Code / UI | Verification Method |
| :--- | :--- | :--- | :--- | :--- |
| **1** | **Review Engine: Text Governance** | `Working` | `backend/app/pipeline/runner.py`, `backend/app/pipeline/rules_engine.py` | Unit tests in `test_rules_engine.py`; verified across 7 fixtures in `scripts/eval.py`. |
| **2** | **Grounding & Citation Validator** | `Working` | `backend/app/pipeline/citation_validator.py` | Tested in `test_citation_validator.py`. Enforces exact quote verification against database sources. |
| **3** | **Confidence Routing & Reviewer Escalation** | `Working` | `backend/app/pipeline/confidence.py` | Tested in `test_confidence_and_rewrites.py`. High/Med/Low labels; ambiguous claims flag `needs_human=True`. |
| **4** | **Improvement 1: Intent-Preserving Fixes with Diff** | `Working` | `frontend/src/components/DiffViewer.tsx`, `backend/app/pipeline/confidence.py` | UI Hero Review screen (`/review/:id`). Word-level deletion/addition rendering; verified in `test_full_workflow.py`. |
| **5** | **Zero-Disruption Explicit Accept** | `Working` | `backend/app/api/findings.py` | Accepting a fix creates a new revision `v+1` without mutating prior version history. |
| **6** | **Text Extraction from PDF and DOCX** | `Working` | `backend/app/utils/text_extract.py`, `frontend/src/pages/NewSubmission.tsx` | Tested with `sample_with_errors.docx` and `sample_with_errors.pdf` in `test_text_extract.py`. |
| **7** | **Role-Based Access Control (RBAC)** | `Working` | `backend/app/services/auth.py`, `backend/app/api/submissions.py` | Server-side enforcement verified: Creators cannot approve submissions (returns 403 Forbidden). |
| **8** | **Approval & Changes Requested Workflow** | `Working` | `backend/app/api/workflow.py`, `frontend/src/pages/ApprovalView.tsx` | Approval dossier view (`/approval/:id`) with approve, request changes, and reject modals. |
| **9** | **Audit Trail & Revision History** | `Working` | `backend/app/models/models.py`, `backend/app/api/workflow.py` | History endpoint `/api/submissions/:id/history` tracks all version diffs, approvals, and user comments. |
| **10** | **Insights Governance Dashboard** | `Working` | `backend/app/api/insights.py`, `frontend/src/pages/Insights.tsx` | UI page `/insights` shows findings by category, severity distribution, dispute rate, and top recurring issues. |
| **11** | **Admin: Approved Sources Management** | `Working` | `backend/app/api/admin.py`, `frontend/src/pages/AdminSources.tsx` | UI page `/sources` managing guidelines (auto-split), 26 facts, terms, assets, and vector re-indexing. |
| **12** | **ChromaDB Vector Retrieval & TF-IDF Embeddings** | `Working` | `backend/app/pipeline/retriever.py` | Lightweight TF-IDF hashing embeddings operating in ~200 MB RAM budget; auto-reindexes from Postgres on startup. |
| **13** | **Provider-Agnostic LLM Client & Mock Mode** | `Working` | `backend/app/llm/client.py` | UI displays active engine badge; runs completely offline without API keys; seamless Claude API toggle. |
| **14** | **Cold-Start Resilience UI** | `Working` | `frontend/src/components/ColdStartBanner.tsx` | Graceful notification banner when initial free-tier boot request takes > 2.5s. |
| **15** | **Single Docker Web Service on Render** | `Working` | `Dockerfile`, `render.yaml`, `scripts/smoke_test.py` | Multi-stage Docker build verified locally; passes full automated smoke test. |
| **16** | **Guideline-Gap Insights** | `Working` | `backend/app/workers/dfi_worker.py`, `backend/app/api/guidelines.py` | Nightly dispute-friction index by clause, TF-IDF reason clusters, manager health API, and one-click clause revision. |
| **17** | **Guideline Health Analytics** | `Working` | `frontend/src/pages/GuidelineHealth.tsx` | `/dashboard/guideline-health` sorts clauses by DFI, highlights risk bands, and offers proposed wording when an active LLM is configured. |
| **18** | **Image Review and Brand Checks** | `Working` | `backend/app/pipeline/content_handlers.py`, `frontend/src/components/SourceMediaViewer.tsx` | OCR, dominant palette comparison (±15 RGB/channel), approved logo template matching, measurable clear-space checks, and WCAG AA contrast checks. |
| **19** | **Spatial PDF Inspection** | `Working` | `backend/app/utils/text_extract.py`, `frontend/src/components/SourceMediaViewer.tsx` | pdfminer page layout coordinates are stored on findings and rendered as translucent highlights in the PDF review. |
| **20** | **Reinforcement Feedback Loop** | `Working` | `backend/app/pipeline/preference_model.py`, `backend/app/pipeline/confidence.py`, `/feedback/stats` | Accept/edit/dispute decisions update a persisted SGD logistic model; suggestions are ranked by acceptance probability and repeated disputed clause/span pairs are suppressed after three distinct findings. Suppression is workspace-scoped because the current deployment model has one brand workspace. |
| **21** | **Round 3 API Hardening** | `Working` | `backend/app/services/rate_limit.py`, `tests/integration/test_round3_endpoints.py` | Validated request and path inputs, rate limits on added APIs, and integration coverage for each added endpoint. |

---

## Where to See Each Feature in the App

### 1. Hero Review Screen (`/review/:id`)
- **Interactive content highlighting**: Click any flagged span on the left to highlight the matching finding on the right.
- **Cited source quote badge**: Click "Cited Source" on any finding to view the exact excerpt from the approved brand kit.
- **Word-Level Diff Fix (Improvement 1)**: View proposed replacements rendered as strikethrough red deletions and green additions.
- **Decision buttons**: Click **Accept Fix** to generate a new version `v2`, or click **Edit** or **Dispute**.
- **Audit comments**: Add a reviewer comment at the bottom of the review page.
- **Image review**: PNG, JPEG, and SVG previews show canvas-drawn finding boxes linked to the findings list.
- **PDF review**: Extracted page coordinates are highlighted over rendered PDF pages.

### 2. Approval Dossier (`/approval/:id`)
- Accessible by Managers, Reviewers, and Admins.
- Side-by-side comparison of Original Draft (v1) vs Current Revision (v2).
- Shows unresolved findings count and warning alert if ungrounded claims remain.
- One-click **Approve**, **Request Changes**, or **Reject** with compliance notes.

### 3. Approved Sources Registry (`/sources`)
- **Guidelines**: View full brand guidelines auto-split into clauses (`VOICE-1`, `CLAIM-1`, `TERM-1`, `A11Y-1`, `LEGAL-1`).
- **Approved Facts**: 26 certified facts, including expired facts marked with red expiration badges.
- **Terminology Registry**: Preferred vs avoided terms.
- **Re-index Chroma Vector Store**: One-click re-indexing with instant count confirmation.

### 4. Governance Insights (`/insights`)
- KPI summary: Total findings, Fix acceptance rate, Review turnaround time, and Citation validator drops.
- Breakdown of issues by category: `tone`, `terminology`, `messaging`, `factual_accuracy`, `unsupported_claim`, `accessibility`.
- Severity distribution: `critical`, `major`, `minor`, `info`.
- Top recurring violations table.
- The main dashboard also shows acceptance rate, edit rate, and suppressed patterns by category.

### 5. Guideline Health (`/dashboard/guideline-health`)
- Clauses are sorted by dispute-friction index, with green, amber, and red risk bands.
- Clauses above 30% can show an LLM-drafted revision when a live provider is configured.
- Managers can accept, edit, or dismiss the proposed revision.
