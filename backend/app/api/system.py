"""System API routes: health check and system status."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text

from backend.app.config import get_settings
from backend.app.database import get_db
from backend.app.schemas.schemas import HealthResponse, SystemStatus
from backend.app.llm.client import get_llm_mode
from backend.app.pipeline.retriever import get_collection
from backend.app.models.models import GuidelineClause, ApprovedFact, Term, Asset
from backend.app.models.models import User
from backend.app.services.auth import get_current_user
from backend.app.services.permissions import Action, check_permission

router = APIRouter(tags=["system"])


@router.get("/system/mode")
def system_mode():
    """Expose only the non-sensitive active generation mode used by the UI."""
    return {"llm_mode": get_llm_mode()}


@router.get("/health", response_model=HealthResponse)
def health_check():
    """Liveness probe for Render and load balancers."""
    settings = get_settings()
    return HealthResponse(status="ok", version=settings.APP_VERSION)


@router.get("/system/status", response_model=SystemStatus)
def system_status(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """System information including active LLM mode and source index counts."""
    check_permission(current_user, Action.SYSTEM_STATUS_VIEW)
    settings = get_settings()

    # Check database
    db_ok = False
    try:
        db.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False

    # Check chroma
    chroma_ok = False
    try:
        col = get_collection()
        chroma_ok = col.count() > 0
    except Exception:
        chroma_ok = False

    # Source counts
    counts = {
        "guideline_clauses": db.query(GuidelineClause).count() if db_ok else 0,
        "approved_facts": db.query(ApprovedFact).count() if db_ok else 0,
        "terms": db.query(Term).count() if db_ok else 0,
        "assets": db.query(Asset).count() if db_ok else 0,
    }

    return SystemStatus(
        app_name=settings.APP_NAME,
        version=settings.APP_VERSION,
        llm_mode=get_llm_mode(),
        llm_available=settings.llm_available,
        database_connected=db_ok,
        chroma_indexed=chroma_ok,
        source_counts=counts,
    )
