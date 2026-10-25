"""BrandGuard main FastAPI application."""
import os
import logging
from contextlib import asynccontextmanager
from datetime import timezone
from pathlib import Path

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse

from backend.app.config import get_settings
from backend.app.database import get_engine, Base, get_session_factory
from backend.app.api.auth import router as auth_router
from backend.app.api.admin import router as admin_router
from backend.app.api.submissions import router as submissions_router
from backend.app.api.findings import router as findings_router
from backend.app.api.workflow import router as workflow_router
from backend.app.api.insights import router as insights_router
from backend.app.api.system import router as system_router
from backend.app.api.guidelines import router as guidelines_router
from backend.app.api.feedback import router as feedback_router
from backend.app.pipeline.retriever import reindex_if_empty
from backend.app.workers.dfi_worker import run_dfi_worker

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("brandguard")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: initialize tables, seed demo data if needed, re-index Chroma."""
    settings = get_settings()
    logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION} (LLM mode: {settings.LLM_PROVIDER})")

    # 1. Initialize DB tables
    engine = get_engine()
    Base.metadata.create_all(bind=engine)
    logger.info("Database schema initialized")

    # 2. Seed data if empty or AUTO_SEED=True
    session_factory = get_session_factory()
    with session_factory() as db:
        from backend.app.models.models import User
        user_count = db.query(User).count()
        if user_count == 0 or settings.AUTO_SEED:
            logger.info("Database has no users or AUTO_SEED=true. Running seed...")
            from backend.app.seed import run_seed
            run_seed(db)

        # 3. Chroma index check
        try:
            reindex_if_empty(db)
        except Exception as e:
            logger.warning(f"Chroma reindex on boot encountered: {e}")

    scheduler = BackgroundScheduler(timezone=timezone.utc)
    scheduler.add_job(
        run_dfi_worker,
        CronTrigger(hour=2, minute=0, timezone=timezone.utc),
        id="nightly-guideline-dfi",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    scheduler.start()
    try:
        yield
    finally:
        scheduler.shutdown(wait=False)
        logger.info("Shutting down BrandGuard")


settings = get_settings()
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

# CORS (enabled for local Vite dev server)
origins = [orig.strip() for orig in settings.CORS_ORIGINS.split(",") if orig.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API Routers under /api
api_prefix = "/api"
app.include_router(auth_router, prefix=api_prefix)
app.include_router(admin_router, prefix=api_prefix)
app.include_router(submissions_router, prefix=api_prefix)
app.include_router(findings_router, prefix=api_prefix)
app.include_router(workflow_router, prefix=api_prefix)
app.include_router(insights_router, prefix=api_prefix)
app.include_router(system_router, prefix=api_prefix)
app.include_router(guidelines_router, prefix=api_prefix)
app.include_router(feedback_router, prefix=api_prefix)

# Static Files & SPA Fallback
static_dir = Path(__file__).parent / "static"
os.makedirs(static_dir, exist_ok=True)

# Mount /assets if built React assets folder exists
assets_dir = static_dir / "assets"
if assets_dir.exists():
    app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")


@app.get("/{full_path:path}")
def serve_spa(full_path: str):
    """Serve built React single-page app or fall back to index.html for client routing."""
    # Don't intercept API routes
    if full_path.startswith("api/"):
        return JSONResponse(status_code=404, content={"detail": "API endpoint not found"})

    target_file = (static_dir / full_path).resolve()
    if full_path and target_file.is_relative_to(static_dir.resolve()) and target_file.is_file():
        return FileResponse(str(target_file))

    index_file = static_dir / "index.html"
    if index_file.exists():
        return FileResponse(str(index_file))

    # Fallback if frontend is not yet built
    return JSONResponse(
        content={
            "app": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "status": "online",
            "message": "Frontend static build not detected. Access API docs at /api/docs",
            "api_health": "/api/health",
        }
    )
