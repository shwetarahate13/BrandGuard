"""Guideline health analytics and clause revision routes."""
import logging

from fastapi import APIRouter, Depends, HTTPException, Path as APIPath
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.models.models import GuidelineClause, GuidelineDoc, User, UserRole
from backend.app.pipeline.retriever import index_all_sources
from backend.app.schemas.schemas import (
    GuidelineClauseRevision,
    GuidelineClauseResponse,
    GuidelineHealthClause,
)
from backend.app.services.auth import require_role
from backend.app.utils.audit import log_action
from backend.app.workers.dfi_worker import collect_clause_dispute_metrics
from backend.app.llm.client import draft_guideline_revision

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/guidelines", tags=["guidelines"])


@router.get("/health", response_model=list[GuidelineHealthClause])
def get_guideline_health(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.manager, UserRole.admin)),
):
    """Return persisted clause risk scores and AI revisions for high-friction clauses."""
    metrics = collect_clause_dispute_metrics(db)
    clauses = (
        db.query(GuidelineClause)
        .join(GuidelineDoc, GuidelineDoc.id == GuidelineClause.doc_id)
        .order_by(
            GuidelineClause.dispute_friction_index.desc(),
            GuidelineClause.title.asc().nullslast(),
            GuidelineClause.id.asc(),
        )
        .all()
    )

    results = []
    for clause in clauses:
        clause_metrics = metrics.get(clause.id, {})
        clusters = clause_metrics.get("dispute_clusters", [])
        proposed_revision = None
        if (clause.dispute_friction_index or 0.0) > 30:
            proposed_revision = draft_guideline_revision(clause.text, clusters)
        results.append(GuidelineHealthClause(
            id=clause.id,
            doc_id=clause.doc_id,
            doc_title=clause.doc.title,
            code=clause.code,
            title=clause.title,
            text=clause.text,
            dispute_friction_index=clause.dispute_friction_index or 0.0,
            dispute_clusters=clusters,
            proposed_revision=proposed_revision,
        ))
    return results


@router.patch("/clauses/{clause_id}", response_model=GuidelineClauseResponse)
def apply_clause_revision(
    payload: GuidelineClauseRevision,
    clause_id: str = APIPath(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9-]+$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.manager, UserRole.admin)),
):
    """Apply revised wording to a guideline clause and refresh its vector index."""
    clause = db.query(GuidelineClause).filter(GuidelineClause.id == clause_id).first()
    if not clause:
        raise HTTPException(status_code=404, detail="Guideline clause not found")

    revision_text = payload.text.strip()
    if not revision_text:
        raise HTTPException(status_code=422, detail="Revision text cannot be blank")

    previous_text = clause.text
    clause.text = revision_text
    log_action(
        db,
        current_user.id,
        "revise_guideline_clause",
        "guideline_clause",
        clause.id,
        {"previous_text": previous_text, "revision_text": revision_text},
    )
    db.commit()
    db.refresh(clause)

    try:
        index_all_sources(db)
    except Exception as exc:
        logger.exception("Guideline clause changed, but source reindex failed")
        raise HTTPException(
            status_code=503,
            detail="Revision was saved, but approved sources could not be reindexed. Retry the source reindex.",
        ) from exc
    return clause
