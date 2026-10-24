# Deploying BrandGuard to Render + Neon (Click-by-Click Guide)

BrandGuard is engineered to run on **Render's free tier** (512 MB RAM, 0.1 CPU) as a **single Docker web service**, connected to **Neon** serverless PostgreSQL.

---

## Architecture at a Glance

```
                         [Render Web Service]
                         Single URL (HTTPS)
                       ┌─────────────────────────┐
                       │  FastAPI (Uvicorn)      │
                       │  Port: $PORT (8000)     │
                       ├────────────┬────────────┤
                       │  /api/*    │  /* (SPA)  │
                       │  Endpoints │ Static UI  │
                       └─────┬──────┴─────┬──────┘
                             │            │
            ┌────────────────┴────┐       │
            ▼                     ▼       ▼
    [Neon PostgreSQL]     [ChromaDB Local] [React UI]
  Users, Guidelines,      TF-IDF vectors   Single-page
  Facts, Submissions,     in /tmp/chroma   application
  Decisions, Audit Logs   (re-indexed)
```

---

## Step 1: Create a Managed PostgreSQL Database on Neon (2 minutes)

1. Navigate to [neon.tech](https://neon.tech) and create a free account or sign in with GitHub.
2. Click **Create Project**.
3. Name your project (e.g. `brandguard-db`) and select region **US East (Ohio)** or closest to your Render region.
4. Once the project is created, copy your **Connection String** from the dashboard.
   - It looks like:
     ```
     postgresql://neondb_owner:npg_AbCdEf12345@ep-cool-forest-12345.us-east-2.aws.neon.tech/neondb?sslmode=require
     ```
   - *Note: BrandGuard automatically handles both `postgres://` and `postgresql://` connection strings and enforces SSL.*

---

## Step 2: Push Repository to GitHub

Ensure your BrandGuard repository is pushed to your GitHub account:

```bash
git remote add origin https://github.com/YOUR_USERNAME/BrandGuard.git
git branch -M main
git push -u origin main
```

---

## Step 3: Deploy Blueprint on Render (3 minutes)

1. Log into your [Render Dashboard](https://dashboard.render.com).
2. Click the **New +** button in the top navigation bar and select **Blueprint**.
3. Connect your GitHub account and select your `BrandGuard` repository.
4. Render will automatically detect the [`render.yaml`](file:///Users/shwetarahate/Downloads/BrandGuard-2/render.yaml) file in the root directory.
5. In the configuration prompt, provide the environment variables:
   - `DATABASE_URL`: Paste the Neon connection string copied in Step 1.
   - `JWT_SECRET`: Render will auto-generate a secure random value.
   - `SECRET_KEY`: Render will auto-generate a secure random value.
   - `LLM_PROVIDER`: Keep as `mock` for deterministic zero-key demo mode, or set to `anthropic` if you have an API key.
   - `LLM_API_KEY`: *(Optional)* Leave blank if using `mock`, or paste your Anthropic API key.
   - `AUTO_SEED`: Keep as `true` (idempotently seeds demo users, 26 facts, brand guidelines, and sample submissions).
6. Click **Apply**.
7. Render will pull the multi-stage [`Dockerfile`](file:///Users/shwetarahate/Downloads/BrandGuard-2/Dockerfile), build the React static bundle, install the lightweight Python dependencies, and start the service.

---

## Step 4: Verify Live Service & Run Smoke Test

Once the build finishes and shows **Live**:

1. Click on your assigned Render URL (e.g., `https://brandguard.onrender.com`).
2. Open the health endpoint in your browser:
   ```
   https://brandguard.onrender.com/api/health
   ```
   Expected response: `{"status":"ok","version":"1.0.0"}`

3. Run the automated smoke test script from your local terminal against your live Render URL:
   ```bash
   python scripts/smoke_test.py https://brandguard.onrender.com
   ```
   The smoke test will:
   - Poll `/api/health` with cold-start wait
   - Verify system status and Chroma vector indexing
   - Log in with all 4 demo accounts (Creator, Manager, Reviewer, Admin)
   - Execute a full end-to-end check -> diff fix accept -> review request -> approval flow
   - Verify audit history and insights summary

---

## Step 5: Demo Accounts for Judges

| Role | Email | Password | Responsibilities |
| :--- | :--- | :--- | :--- |
| **Creator** | `creator@nexora.dev` | `Creator123!` | Submits content, states intent, accepts/edits/disputes diff fixes |
| **Brand Manager** | `manager@nexora.dev` | `Manager123!` | Overview of all submissions, final approval, review trends |
| **Reviewer** | `reviewer@nexora.dev` | `Reviewer123!` | Verifies legal/medical claims and sensitive wording sign-off |
| **Admin** | `admin@nexora.dev` | `Admin123!` | Manages guideline docs, 25+ facts, terms, and triggers Chroma re-index |

*Note: The login page includes one-click quick-fill buttons for all 4 roles.*

---

## Troubleshooting & Common Questions

### 1. Free Tier Cold Starts
- **Symptom**: The first request after 15 minutes of inactivity takes 40-50 seconds.
- **Cause**: Render spins down free containers when idle.
- **Handling**: BrandGuard includes a friendly client-side banner (*"Waking up the server instance on Render free tier..."*) that triggers if any request takes longer than 2.5 seconds, ensuring users never see a white screen or raw error.

### 2. Neon Database Connection Timeout
- **Symptom**: `OperationalError: connection to server at ... failed`.
- **Cause**: An idle Neon database compute endpoint takes 2-3 seconds to wake up from sleep.
- **Handling**: `backend/app/database.py` implements an exponential backoff connection retry loop (attempts 1 to 3) and sets `pool_pre_ping=True`, gracefully absorbing Neon wake-up latency.

### 3. Disposable Disk on Render
- **Symptom**: Server restarts and ChromaDB directory in `/tmp/chroma` is reset.
- **Handling**: Postgres is the sole source of truth. On startup (`lifespan` in `backend/app/main.py`), BrandGuard checks if the Chroma collection is empty and automatically re-indexes all approved guidelines, facts, and terms from PostgreSQL into ChromaDB.

### 4. Memory Budget Exceeded (512 MB Limit)
- **Symptom**: Render logs `Out of memory` (OOM killed).
- **Handling**: BrandGuard uses stateless TF-IDF hashing vectors (`LightweightEmbeddingFunction`) and regex sentence segmenters instead of heavy PyTorch, Transformers, or NLTK models. Measured peak memory is ~200 MB, well under the 512 MB limit.
