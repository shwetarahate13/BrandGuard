# Evolution & Plan Changes (Round 1 Plan to Round 2 Build)

Team **Nexora** (Shweta Rahate, Janvi Thakre) maintained strict adherence to the product vision established in Round 1, while making pragmatic engineering adaptations during the Round 2 build to ensure stability, performance, and memory compliance on Render's 512 MB free tier.

---

## Summary of Architectural Changes

| Area | Round 1 Plan | Round 2 Implementation | Engineering Rationale |
| :--- | :--- | :--- | :--- |
| **Database Architecture** | Local SQLite file database | **PostgreSQL** via Neon in production; SQLAlchemy 2.x + Alembic | Required for multi-user transactional consistency, role-based security, and disposable container disk compatibility on Render. |
| **Frontend Framework** | Vanilla HTML + JavaScript in `static/index.html` | **React + Vite + TypeScript + Tailwind CSS** | Provides rich component state for the hero review screen, clickable span highlights, and word-level diff views. |
| **Embedding Engine** | `sentence-transformers` (`all-MiniLM-L6-v2`) | **TF-IDF Hashing Vectorizer** (Scikit-Learn) | PyTorch and neural embeddings consumed ~450 MB RAM, risking OOM kills on Render's 512 MB tier. TF-IDF uses < 5 MB RAM, achieving 200 MB peak resident memory. |
| **Citation Verification** | Prompt-level instructions to the LLM | **Deterministic Citation Validator** (`citation_validator.py`) | Non-negotiable code enforcement: drops candidate findings that lack verified database sources or exact substring quotes. |
| **Intent Capture & Rewrite Verification** | Simple rule replacement string | **Creator Stated Intent + Semantic Root Anchoring** | Captured via a dedicated UI field. The engine verifies suggested rewrites preserve the creator's stated purpose before displaying diffs. |
| **Deployment Topology** | Separate static site + backend service | **Single Multi-Stage Docker Web Service** | Bundles compiled React assets into FastAPI on `$PORT`. Eliminates CORS issues, simplifies DNS, and ensures one cold-start cycle. |

---

## Detailed Rationale for Key Decisions

### 1. Replacing Neural Transformers with Stateless TF-IDF Hashing
- **Observation during local testing**: Loading `torch` and importing `sentence_transformers` raised startup time by 8.4 seconds and pushed process baseline RAM from 85 MB to 410 MB. On Render's 512 MB free tier with 0.1 CPU cores, this left virtually no buffer for Chroma queries or PDF text extraction.
- **Adjustment**: We created `LightweightEmbeddingFunction` in `backend/app/pipeline/retriever.py` utilizing `HashingVectorizer(n_features=256, norm='l2')`. It delivers immediate cosine similarity search across brand guidelines without model weights or GPU requirements, dropping peak memory to **200.7 MB**.

### 2. Moving from In-Memory Dicts to Declarative PostgreSQL Relational Model
- In Round 1, findings and decisions were tied to loosely structured document records.
- In Round 2, we implemented 10 relational tables (`users`, `guideline_docs`, `guideline_clauses`, `approved_facts`, `terms`, `assets`, `submissions`, `submission_versions`, `findings`, `decisions`, `comments`, `approvals`, `audit_log`).
- This allows full historical traceability: when a creator accepts a diff fix, a new `submission_version` (v2) is generated, linking all findings directly to the content version they evaluated.

### 3. Strict Word-Level Diff Visualization
- In Round 1, suggestions were displayed as replacement text blocks.
- In Round 2, we integrated `diff.diffWordsWithSpace` via a dedicated `<DiffViewer />` component that visually highlights exact deletions (strikethrough red) and additions (green highlight), providing total transparency before any fix is accepted.
