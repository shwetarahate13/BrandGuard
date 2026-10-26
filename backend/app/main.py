"""BrandGuard main FastAPI application."""
import os
import logging
import json
import time
import uuid
from contextlib import asynccontextmanager
from datetime import timezone
from pathlib import Path

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse

from backend.app.config import get_settings
from backend.app.database import get_engine, get_session_factory
from backend.app.api.auth import router as auth_router
from backend.app.api.admin import router as admin_router
from backend.app.api.submissions import router as submissions_router
from backend.app.api.findings import router as findings_router
from backend.app.api.workflow import router as workflow_router
from backend.app.api.insights import router as insights_router
from backend.app.api.system import router as system_router
from backend.app.api.guidelines import router as guidelines_router
from backend.app.api.feedback import router as feedback_router
from backend.app.services.rate_limit import endpoint_rate_limiter
from backend.app.pipeline.retriever import reindex_if_empty
from backend.app.workers.dfi_worker import run_dfi_worker

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("brandguard")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: connect services, optionally seed demo data, and run DFI refreshes."""
    settings = get_settings()
    logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION} (LLM mode: {settings.LLM_PROVIDER})")

    # Production and local schema changes are applied only through Alembic.
    get_engine()

    # Demo records are created only on an empty DB with explicit opt-in.
    session_factory = get_session_factory()
    with session_factory() as db:
        from backend.app.models.models import User
        user_count = db.query(User).count()
        if user_count == 0 and settings.DEMO_MODE:
            logger.info("Demo mode enabled on an empty database; seeding judge accounts and sample content")
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
app.middleware("http")(endpoint_rate_limiter)


def security_headers(request_id: str) -> dict[str, str]:
    headers = {
        "X-Request-ID": request_id,
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "Referrer-Policy": "strict-origin-when-cross-origin",
        "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
        "Content-Security-Policy": (
            "default-src 'self'; object-src 'none'; frame-ancestors 'none'; base-uri 'self'; "
            "img-src 'self' data: blob:; style-src 'self' 'unsafe-inline'; "
            "script-src 'self'; connect-src 'self'; worker-src 'self' blob:"
        ),
    }
    if settings.ENVIRONMENT.casefold() == "production" or os.getenv("RENDER", "").casefold() == "true":
        headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return headers


@app.middleware("http")
async def request_context_and_security_headers(request: Request, call_next):
    supplied_id = request.headers.get("X-Request-ID", "")
    valid_id = supplied_id[:64] if supplied_id and all(ch.isalnum() or ch in "-_." for ch in supplied_id) else ""
    request_id = valid_id or str(uuid.uuid4())
    request.state.request_id = request_id
    started = time.perf_counter()
    response = await call_next(request)
    for name, value in security_headers(request_id).items():
        response.headers[name] = value
    logger.info(json.dumps({
        "event": "http_request",
        "request_id": request_id,
        "method": request.method,
        "path": request.url.path,
        "status_code": response.status_code,
        "duration_ms": round((time.perf_counter() - started) * 1000, 2),
    }))
    return response


@app.exception_handler(Exception)
async def unexpected_error_handler(request: Request, exc: Exception):
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    logger.exception(json.dumps({
        "event": "unhandled_exception",
        "request_id": request_id,
        "path": request.url.path,
        "exception_type": type(exc).__name__,
    }))
    return JSONResponse(
        status_code=500,
        content={
            "detail": f"An unexpected error occurred. Please try again or contact your administrator. Reference ID: {request_id}",
            "request_id": request_id,
        },
        headers=security_headers(request_id),
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


@app.get("/healthz")
def root_healthz():
    """Native host liveness probe at the platform-standard path."""
    return {"status": "ok", "version": settings.APP_VERSION}

# Static Files & SPA Fallback
frontend_dist = Path(__file__).resolve().parents[2] / "frontend" / "dist"
committed_static = Path(__file__).parent / "static"
static_dir = frontend_dist if (frontend_dist / "index.html").is_file() else committed_static

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
