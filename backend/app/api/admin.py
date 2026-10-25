"""Admin API routes for managing approved sources (guidelines, facts, terms, assets)."""
import re
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.models.models import (
    User, UserRole, GuidelineDoc, GuidelineClause, ApprovedFact, Term, Asset, AssetKind
)
from backend.app.schemas.schemas import (
    GuidelineDocCreate, GuidelineDocResponse,
    ApprovedFactCreate, ApprovedFactResponse, TermCreate, TermResponse, AssetCreate, AssetResponse
)
from backend.app.services.auth import get_current_user, require_role
from backend.app.utils.audit import log_action
from backend.app.utils.text_extract import extract_text, read_upload_contents
from backend.app.pipeline.retriever import index_all_sources

router = APIRouter(prefix="/admin", tags=["admin"])


def _split_text_into_clauses(text: str) -> List[dict]:
    """Auto-split guideline text into clauses based on headers, numbered sections, or paragraphs."""
    clauses = []
    lines = text.strip().split("\n")
    
    current_title = "General Guideline"
    current_code = None
    current_lines = []
    
    for line in lines:
        stripped = line.strip()
        if not stripped:
            if current_lines:
                current_lines.append("")
            continue

        # Check for markdown header: # or ## or ###
        header_match = re.match(r'^(#{1,4})\s+(.+)$', stripped)
        # Check for numbered clause: e.g. "1.1 Tone and Voice" or "Clause 3: ..."
        numbered_match = re.match(r'^(?:Clause\s+)?(\d+(?:\.\d+)*)[:.]?\s+(.+)$', stripped, re.IGNORECASE)

        if header_match or numbered_match:
            # Flush previous clause if has content
            body = "\n".join(current_lines).strip()
            if body:
                clauses.append({
                    "code": current_code,
                    "title": current_title,
                    "text": body,
                })
                current_lines = []

            if header_match:
                current_title = header_match.group(2).strip()
                current_code = None
            else:
                current_code = numbered_match.group(1).strip()
                current_title = numbered_match.group(2).strip()
        else:
            current_lines.append(stripped)

    # Flush last clause
    body = "\n".join(current_lines).strip()
    if body:
        clauses.append({
            "code": current_code,
            "title": current_title,
            "text": body,
        })

    # If no structured sections detected, split by double newlines or chunks
    if not clauses and text.strip():
        paragraphs = [p.strip() for p in re.split(r'\n{2,}', text) if p.strip()]
        for idx, p in enumerate(paragraphs, 1):
            clauses.append({
                "code": f"G-{idx}",
                "title": f"Clause {idx}",
                "text": p,
            })

    return clauses


# ── Guidelines ──

@router.get("/guidelines", response_model=List[GuidelineDocResponse])
def list_guidelines(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return db.query(GuidelineDoc).all()


@router.post("/guidelines", response_model=GuidelineDocResponse)
def create_guideline_doc(
    payload: GuidelineDocCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.admin, UserRole.manager)),
):
    doc = GuidelineDoc(title=payload.title, description=payload.description)
    db.add(doc)
    db.flush()

    if payload.text:
        clauses_data = _split_text_into_clauses(payload.text)
        for idx, c in enumerate(clauses_data):
            clause = GuidelineClause(
                doc_id=doc.id,
                code=c.get("code"),
                title=c.get("title"),
                text=c.get("text", ""),
                order_index=idx,
            )
            db.add(clause)

    log_action(db, current_user.id, "create_guideline_doc", "guideline_doc", doc.id)
    db.commit()
    db.refresh(doc)
    # Reindex Chroma in background or immediately
    index_all_sources(db)
    return doc


@router.post("/guidelines/import", response_model=GuidelineDocResponse)
async def import_guideline_file(
    file: UploadFile = File(...),
    title: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.admin, UserRole.manager)),
):
    contents = await read_upload_contents(file)
    filename = file.filename or "upload.txt"
    try:
        extracted = extract_text(contents, filename)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    doc_title = title or filename.rsplit(".", 1)[0].replace("-", " ").replace("_", " ").title()
    doc = GuidelineDoc(title=doc_title, description=description or f"Imported from {filename}")
    db.add(doc)
    db.flush()

    clauses_data = _split_text_into_clauses(extracted)
    for idx, c in enumerate(clauses_data):
        clause = GuidelineClause(
            doc_id=doc.id,
            code=c.get("code"),
            title=c.get("title"),
            text=c.get("text", ""),
            order_index=idx,
        )
        db.add(clause)

    log_action(db, current_user.id, "import_guideline_doc", "guideline_doc", doc.id, {"filename": filename})
    db.commit()
    db.refresh(doc)
    index_all_sources(db)
    return doc


@router.delete("/guidelines/{doc_id}")
def delete_guideline_doc(
    doc_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.admin)),
):
    doc = db.query(GuidelineDoc).filter(GuidelineDoc.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Guideline document not found")
    db.delete(doc)
    log_action(db, current_user.id, "delete_guideline_doc", "guideline_doc", doc_id)
    db.commit()
    index_all_sources(db)
    return {"message": "Deleted successfully"}


# ── Approved Facts ──

@router.get("/facts", response_model=List[ApprovedFactResponse])
def list_facts(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return db.query(ApprovedFact).order_by(ApprovedFact.created_at.desc()).all()


@router.post("/facts", response_model=ApprovedFactResponse)
def create_fact(
    payload: ApprovedFactCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.admin, UserRole.manager)),
):
    fact = ApprovedFact(
        statement=payload.statement,
        source_note=payload.source_note,
        valid_from=payload.valid_from,
        valid_to=payload.valid_to,
    )
    db.add(fact)
    db.flush()
    log_action(db, current_user.id, "create_fact", "approved_fact", fact.id)
    db.commit()
    db.refresh(fact)
    index_all_sources(db)
    return fact


@router.delete("/facts/{fact_id}")
def delete_fact(
    fact_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.admin)),
):
    fact = db.query(ApprovedFact).filter(ApprovedFact.id == fact_id).first()
    if not fact:
        raise HTTPException(status_code=404, detail="Fact not found")
    db.delete(fact)
    log_action(db, current_user.id, "delete_fact", "approved_fact", fact_id)
    db.commit()
    index_all_sources(db)
    return {"message": "Deleted successfully"}


# ── Terms ──

@router.get("/terms", response_model=List[TermResponse])
def list_terms(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return db.query(Term).all()


@router.post("/terms", response_model=TermResponse)
def create_term(
    payload: TermCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.admin, UserRole.manager)),
):
    term = Term(
        preferred=payload.preferred,
        avoid=payload.avoid,
        note=payload.note,
    )
    db.add(term)
    db.flush()
    log_action(db, current_user.id, "create_term", "term", term.id)
    db.commit()
    db.refresh(term)
    index_all_sources(db)
    return term


@router.delete("/terms/{term_id}")
def delete_term(
    term_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.admin)),
):
    term = db.query(Term).filter(Term.id == term_id).first()
    if not term:
        raise HTTPException(status_code=404, detail="Term not found")
    db.delete(term)
    log_action(db, current_user.id, "delete_term", "term", term_id)
    db.commit()
    index_all_sources(db)
    return {"message": "Deleted successfully"}


# ── Assets ──

@router.get("/assets", response_model=List[AssetResponse])
def list_assets(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return db.query(Asset).all()


@router.post("/assets", response_model=AssetResponse)
def create_asset(
    payload: AssetCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.admin, UserRole.manager)),
):
    try:
        kind_enum = AssetKind(payload.kind)
    except ValueError:
        kind_enum = AssetKind.other

    asset = Asset(
        name=payload.name,
        kind=kind_enum,
        file_path=payload.file_path,
    )
    db.add(asset)
    db.flush()
    log_action(db, current_user.id, "create_asset", "asset", asset.id)
    db.commit()
    db.refresh(asset)
    index_all_sources(db)
    return asset


@router.delete("/assets/{asset_id}")
def delete_asset(
    asset_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.admin)),
):
    asset = db.query(Asset).filter(Asset.id == asset_id).first()
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    db.delete(asset)
    log_action(db, current_user.id, "delete_asset", "asset", asset_id)
    db.commit()
    index_all_sources(db)
    return {"message": "Deleted successfully"}


# ── Reindex ──

@router.post("/reindex")
def trigger_reindex(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.admin, UserRole.manager)),
):
    """Re-index all approved guidelines, facts, terms, and assets into ChromaDB."""
    count = index_all_sources(db)
    log_action(db, current_user.id, "reindex_sources", meta={"indexed_count": count})
    db.commit()
    return {"status": "ok", "indexed_count": count}
