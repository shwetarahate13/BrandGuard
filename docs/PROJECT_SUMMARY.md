# BrandGuard: Pre-Publication Brand Governance Platform
**Hackathon Round 2 Build Summary • Team Nexora**
*Engineered by Shweta Rahate & Janvi Thakre*

---

## 1. Problem Statement
Growing organizations publish content across distributed teams, external marketing agencies, and automated AI writing tools. This velocity creates severe governance risks:
- **Unsupported Promotional Claims**: Absolutes ("guaranteed", "clinically proven", "100% safe") that trigger regulatory fines or consumer mistrust.
- **Outdated Facts**: Superseded pricing, legacy statistics, and expired certifications published in new materials.
- **Voice & Tone Erosion**: Off-brand slang, aggressive hype, ALL-CAPS text, and accessibility oversights (vague links, missing alt text).
- **The Blind Rejection Flaw**: Existing tools simply reject or alter content without citing approved sources, alienating creators and hallucinating ungrounded rules.

---

## 2. Solution: BrandGuard
BrandGuard is an intelligent pre-publication brand governance platform that reviews content against **approved brand sources only**, explains every issue with exact source citations, suggests intent-preserving fixes as word-level diffs, and enforces human-controlled approval workflows.

### Core Principles
1. **Grounded or Silent**: Every finding cites an approved guideline clause, verified fact, or registered term with an exact quote. No valid citation means no flag.
2. **Intent-Preserving Diff Fixes**: Creators state their intent up front; suggested fixes preserve their voice and display as inline word diffs. Nothing changes without an explicit accept.
3. **AI Suggests, People Decide**: The engine never edits or auto-publishes. Authorised reviewers have full audit trails and sign-off authority.

---

## 3. High-Level Architecture

```
[Creators & Agencies] ─── Submissions (Text/DOCX/PDF) ───┐
                                                         ▼
[Render Web Service: 512 MB RAM] ─── [FastAPI + React SPA (Single URL)]
       │
       ├─ [Text Segmenter] ────── Regex span & sentence boundary parsing
       ├─ [Rules Engine] ──────── Deterministic term, claim, and a11y checks
       ├─ [ChromaDB Vector] ───── Top-k retrieval using TF-IDF Hashing (200MB RAM)
       ├─ [LLM / Mock Engine] ─── Provider-agnostic reasoning (Claude / Offline Mock)
       ├─ [Citation Validator] ── Strict database quote verification (non-negotiable)
       ├─ [Confidence Routing] ── High/Med/Low; Ambiguous cases -> Human Reviewer
       └─ [Diff Engine] ───────── Word-level insertion/deletion generation
                                                         │
                                                         ▼
[PostgreSQL (Neon)] ──────────── Users, Guidelines, 26 Facts, Revisions, Audit Logs
```

---

## 4. Key Results & Verification Metrics

- **Pipeline Accuracy**: Evaluated across 7 structured test fixtures containing planted claims, expired facts, terminology violations, accessibility issues, and clean controls:
  - **Precision**: **93.3%**
  - **Recall**: **87.5%**
  - **F1 Score**: **90.3%**
  - **Clean Control Over-flagging**: **0.0 per sample** (Zero false alarms on clean copy).
- **Automated Smoke Test**: 100% pass across all endpoints, 4 demo roles, and full submit-check-accept-approve workflow (`scripts/smoke_test.py`).
- **Memory Footprint**: Peak resident memory **200.7 MB**, operating smoothly within Render's 512 MB ceiling.

---

## 5. UI Screenshots Overview

1. **Sign-In & Demo Quick-Fill**: One-click login for Creator, Manager, Reviewer, and Admin.
2. **Governance Dashboard**: Filterable submission pipeline tracking status from Draft to Approved.
3. **Hero Review Screen**: Content with highlighted clickable spans on the left; findings panel on the right with cited source quotes, confidence chips, and word-level diff fixes.
4. **Sign-Off Dossier View**: Version history (v1 vs v2 comparison), unresolved finding alerts, and Approve / Request Changes / Reject controls.
5. **Approved Sources Registry**: Central brand kit managing guidelines (with auto-split parser), 26 facts (active vs expired), terms, and Chroma vector re-indexing.
6. **Governance Insights**: Real-time charts on issues by category, severity distribution, 88% fix acceptance rate, and top repeated brand mistakes.
