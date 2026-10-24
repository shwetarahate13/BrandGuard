# BrandGuard Technology & Architecture Specification

## 1. Core Tech Stack

| Layer | Technology | Version | Justification & Role |
| :--- | :--- | :--- | :--- |
| **Backend Framework** | **FastAPI** | 0.110+ | High-throughput asynchronous REST API with automatic OpenAPI documentation and native Pydantic v2 validation. |
| **Database** | **PostgreSQL** (Neon in prod, SQLite in test) | 16 / SQLAlchemy 2.x | ACID-compliant relational source of truth with Alembic migrations and connection-retry resilience for idle cold-start wakeups. |
| **Vector Store** | **ChromaDB** | 0.4+ | Embedded local vector database persistent in `/tmp/chroma`; automatically populated and refreshed from Postgres on startup. |
| **Embeddings** | **TF-IDF Hashing Vectorizer** | Scikit-learn 1.4+ | 256-dimensional L2-normalized stateless embeddings. Uses zero GPU/Torch dependencies, consuming < 5 MB RAM. |
| **Frontend** | **React + Vite + TypeScript** | React 18, Vite 5 | Fast Single-Page Application (SPA) with typed schemas, Tailwind CSS, and Lucide icons. Compiled to static assets served by FastAPI. |
| **Diff Engine** | **jsdiff / diff** | 5.2+ | Word-level diff computation showing inline removals (strikethrough) and additions. |
| **Document Parsers** | **pdfplumber**, **python-docx** | 0.11+, 1.2+ | Safe text extraction from uploaded PDF and DOCX files without external OCR binaries. |
| **LLM Interface** | **Provider-Agnostic Client** | Anthropic SDK + Mock | Unified client switching between deterministic offline mock mode (rules + TF-IDF) and live Claude API. |

---

## 2. Review Pipeline Data Flow

```
Raw Content Submission (Text / DOCX / PDF) + Stated Intent
                          │
                          ▼
            [1. Text Normalization & Segmentation]
            - NFKC unicode normalization
            - Sentence & claim span regex segmentation
                          │
                          ▼
            [2. Deterministic Rules Engine (No LLM)]
            - Avoided terminology matching
            - Banned promotional absolutes ("guaranteed", "100% safe", "cures")
            - Expired fact detection via date comparison
            - Accessibility heuristics (vague links, missing alt, all-caps)
                          │
                          ▼
            [3. ChromaDB Context Retrieval]
            - Top-k (k=3-5) approved sources retrieved per span
            - Excerpts only: whole document libraries never leaked
                          │
                          ▼
            [4. LLM Check / Deterministic Mock Reasoning]
            - Input: Span text + Stated Intent + Retrieved sources ONLY
            - Delimited untrusted user content
            - Strict JSON response schema
                          │
                          ▼
            [5. Citation Validator (Non-Negotiable)]
            - Checks source_id exists in Postgres
            - Checks source_id was in retrieved set
            - Verifies source_quote is an exact substring of the source
            - Drops ungrounded candidate findings
                          │
                          ▼
            [6. Confidence Routing & Reviewer Escalation]
            - High: Direct rule violation or high similarity
            - Medium: Moderate source similarity
            - Low / Ambiguous: Flagged needs_human=True -> routed to Reviewer
                          │
                          ▼
            [7. Intent-Preserving Rewrite Verification]
            - Extracts root semantic anchors from original span and creator intent
            - Rejects divergent suggestions that destroy creator's intent
                          │
                          ▼
            [8. Persistence & Revision Association]
            - Findings linked to submission_version_id in Postgres
```

---

## 3. Key Design Decisions & Technical Trade-Offs

### 1. TF-IDF Hashing Embeddings vs. PyTorch Sentence Transformers
- **Constraint**: Render's free tier provides 512 MB RAM and 0.1 CPU cores. Installing PyTorch and downloading `all-MiniLM-L6-v2` consumes ~450 MB RAM, risking instant OOM (Out Of Memory) container termination.
- **Solution**: We implemented `LightweightEmbeddingFunction` using Scikit-Learn's `HashingVectorizer(n_features=256, norm='l2')`. It is stateless, requires no pre-computed dictionary files, operates in microseconds, and runs in < 5 MB RAM.
- **Total Application Resident Memory**: Measured at **200.7 MB**, leaving > 300 MB headroom under the 512 MB ceiling.

### 2. Single-Service Multi-Stage Docker Architecture
- **Constraint**: Managing two separate free hosting services (frontend on Vercel/Netlify, backend on Render) causes CORS friction, dual cold-start wakeups, and latency spikes.
- **Solution**: A multi-stage `Dockerfile` where Node builds the React SPA into static bundles, and Python slim serves both the REST `/api/*` endpoints and the SPA fallback (`/*` -> `index.html`) on a single port `$PORT`.

### 3. Neon Cold-Start Connection Resilience
- **Constraint**: Serverless PostgreSQL compute on Neon suspends after 5 minutes of inactivity. When a request arrives, the initial TCP handshake may time out.
- **Solution**: `backend/app/database.py` wraps the engine initialization in an exponential backoff loop (attempts 1 to 3, waiting 1s, 2s, 4s) with `pool_pre_ping=True` and `pool_recycle=300`.

### 4. Non-Negotiable Citation Validator
- **Problem**: Large Language Models hallucinate plausible-sounding brand rules or invent guideline clauses that do not exist.
- **Implementation**: In `backend/app/pipeline/citation_validator.py`, every candidate finding must satisfy three criteria:
  1. `source_id` exists in the Postgres database.
  2. `source_id` was in the top-k retrieved set for that check.
  3. `source_quote` exists as an exact or high-threshold normalized substring inside the source's verified text.
- If any check fails, the finding is silently dropped, preserving the core principle: **Grounded or silent**.

### 5. Intent-Preserving Rewrites (Improvement 1)
- **Problem**: Automated AI suggestions often change the creator's voice or eliminate the promotional goal.
- **Implementation**: The creator states the intent up front (e.g., *"Highlight our local organic grain sourcing"*). The engine compares the suggested rewrite against the original span and intent using semantic root extraction (`get_roots`). If the rewrite shares no conceptual anchors with the original text or intent, the suggestion is dropped and the finding is displayed without an auto-rewrite, prompting human decision.
