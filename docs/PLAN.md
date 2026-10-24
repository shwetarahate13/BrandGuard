# BrandGuard Build Plan – Round 2

## Milestones

### M1: Repo + DB + Auth/Roles
- [x] Initialize repo structure: `backend/`, `frontend/`, `docs/`, `scripts/`, `tests/`
- [x] SQLAlchemy models for all entities
- [x] Alembic migrations
- [x] JWT auth with bcrypt password hashing
- [x] Role-based permission guards
- [x] Auth endpoints: login, me

### M2: Sources Import + Retrieval
- [x] Admin CRUD for guidelines, facts, terms, assets
- [x] Bulk import (paste/upload text, PDF, DOCX)
- [x] Auto-split guidelines into clauses
- [x] ChromaDB integration with TF-IDF embeddings
- [x] Re-index from Postgres on startup if collection empty

### M3: Pipeline + Validator + Mock Mode
- [x] Content normalization and segmentation
- [x] Deterministic rules engine
- [x] ChromaDB retrieval per span
- [x] LLM check with strict JSON output (Anthropic provider)
- [x] Mock/offline mode (rules + keyword/TF-IDF)
- [x] Citation validator (drop unfounded findings)
- [x] Confidence routing
- [x] Intent-preserving rewrite verification

### M4: Review UI + Diff + Decisions
- [x] Review screen with highlighted spans
- [x] Findings panel with cited sources
- [x] Word-level diff for suggestions
- [x] Accept / Edit / Dispute buttons
- [x] Live preview of resulting text

### M5: Workflow + Comments + Approvals + History
- [x] Submission lifecycle (draft→checked→in_review→approved/rejected/changes_requested)
- [x] Comments per submission and per finding
- [x] Approval / rejection with notes
- [x] Revision history
- [x] Audit log

### M6: Insights Dashboard
- [x] Issues by category and severity
- [x] Top repeated issues
- [x] Accepted vs disputed ratio
- [x] Review turnaround time

### M7: Seed Data + Evaluation
- [x] Fictional brand "Aurelia Foods"
- [x] 25+ approved facts, guidelines, terms
- [x] 3+ demo users
- [x] 8-10 sample submissions with planted errors
- [x] Sample PDF and DOCX
- [x] Evaluation script with precision/recall

### M8: Docker + Render + Smoke Test
- [x] Multi-stage Dockerfile
- [x] render.yaml blueprint
- [x] smoke_test.py
- [x] Production image verification
- [x] Memory measurement

### M9: Documentation + Hardening
- [x] All required docs
- [x] Final testing and polish
- [x] Lint pass
