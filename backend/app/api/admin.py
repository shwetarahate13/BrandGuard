"""Admin API routes for managing approved sources (guidelines, facts, terms, assets), users, settings, and audit logs."""
import csv
import io
import re
from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query, Response
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.models.models import (
    User, UserRole, GuidelineDoc, GuidelineClause, ApprovedFact, Term, Asset, AssetKind,
    AuditLog, SystemSetting, WritingRuleDispute
)
from backend.app.schemas.schemas import (
    GuidelineDocCreate, GuidelineDocResponse,
    ApprovedFactCreate, ApprovedFactResponse, TermCreate, TermResponse, AssetCreate, AssetResponse,
    UserCreateAdmin, UserUpdateAdmin, UserResetPasswordAdmin, UserResponse,
    SystemSettingsResponse, SystemSettingsUpdate, AuditLogResponse
)
from backend.app.services.auth import get_current_user, hash_password
from backend.app.services.permissions import Action, check_permission
from backend.app.utils.audit import log_action
from backend.app.utils.text_extract import extract_text, read_upload_contents, sanitize_upload_filename, sniff_upload_mime_type
from backend.app.pipeline.retriever import index_all_sources
from backend.app.pipeline.writing_rule_feedback import writing_rule_dispute_counts

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
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    check_permission(current_user, Action.SOURCES_READ)
    return db.query(GuidelineDoc).order_by(GuidelineDoc.created_at.desc()).offset(offset).limit(limit).all()


@router.post("/guidelines", response_model=GuidelineDocResponse)
def create_guideline_doc(
    payload: GuidelineDocCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    check_permission(current_user, Action.SOURCES_MANAGE)
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
    current_user: User = Depends(get_current_user),
):
    check_permission(current_user, Action.SOURCES_MANAGE)
    contents = await read_upload_contents(file)
    filename = sanitize_upload_filename(file.filename)
    try:
        sniff_upload_mime_type(contents, filename)
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
    current_user: User = Depends(get_current_user),
):
    check_permission(current_user, Action.SOURCES_MANAGE)
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
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    check_permission(current_user, Action.SOURCES_READ)
    return db.query(ApprovedFact).order_by(ApprovedFact.created_at.desc()).offset(offset).limit(limit).all()


@router.post("/facts", response_model=ApprovedFactResponse)
def create_fact(
    payload: ApprovedFactCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    check_permission(current_user, Action.SOURCES_MANAGE)
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
    current_user: User = Depends(get_current_user),
):
    check_permission(current_user, Action.SOURCES_MANAGE)
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
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    check_permission(current_user, Action.SOURCES_READ)
    return db.query(Term).order_by(Term.created_at.desc()).offset(offset).limit(limit).all()


@router.post("/terms", response_model=TermResponse)
def create_term(
    payload: TermCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    check_permission(current_user, Action.SOURCES_MANAGE)
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
    current_user: User = Depends(get_current_user),
):
    check_permission(current_user, Action.SOURCES_MANAGE)
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
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    check_permission(current_user, Action.SOURCES_READ)
    return db.query(Asset).order_by(Asset.created_at.desc()).offset(offset).limit(limit).all()


@router.post("/assets", response_model=AssetResponse)
def create_asset(
    payload: AssetCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    check_permission(current_user, Action.SOURCES_MANAGE)
    try:
        kind_enum = AssetKind(payload.kind)
    except ValueError:
        kind_enum = AssetKind.other

    asset = Asset(
        name=payload.name,
        kind=kind_enum,
        file_path=payload.file_path,
        metadata_=payload.metadata,
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
    current_user: User = Depends(get_current_user),
):
    check_permission(current_user, Action.SOURCES_MANAGE)
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
    current_user: User = Depends(get_current_user),
):
    """Re-index all approved guidelines, facts, terms, and assets into ChromaDB."""
    check_permission(current_user, Action.SOURCES_MANAGE)
    count = index_all_sources(db)
    log_action(db, current_user.id, "reindex_sources", meta={"indexed_count": count})
    db.commit()
    return {"status": "ok", "indexed_count": count}


# ── User Management (Admin only) ──

@router.get("/users", response_model=List[UserResponse])
def list_users(
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    check_permission(current_user, Action.USERS_MANAGE)
    return db.query(User).order_by(User.name.asc()).offset(offset).limit(limit).all()


@router.post("/users", response_model=UserResponse)
def create_user(
    payload: UserCreateAdmin,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    check_permission(current_user, Action.USERS_MANAGE)
    existing = db.query(User).filter(User.email == payload.email.lower().strip()).first()
    if existing:
        raise HTTPException(status_code=400, detail="User with this email already exists")

    try:
        role_enum = UserRole(payload.role.lower().strip())
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid role '{payload.role}'")

    new_user = User(
        name=payload.name.strip(),
        email=payload.email.lower().strip(),
        password_hash=hash_password(payload.password),
        role=role_enum,
        is_active=True,
    )
    db.add(new_user)
    db.flush()
    log_action(db, current_user.id, "create_user", "user", new_user.id, {"role": role_enum.value})
    db.commit()
    db.refresh(new_user)
    return new_user


@router.patch("/users/{user_id}", response_model=UserResponse)
def update_user(
    user_id: str,
    payload: UserUpdateAdmin,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    check_permission(current_user, Action.USERS_MANAGE)
    target_user = db.query(User).filter(User.id == user_id).first()
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")

    if payload.name is not None:
        target_user.name = payload.name.strip()
    if payload.role is not None:
        try:
            target_user.role = UserRole(payload.role.lower().strip())
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid role '{payload.role}'")
    if payload.is_active is not None:
        target_user.is_active = payload.is_active

    log_action(db, current_user.id, "update_user", "user", target_user.id, {
        "role": target_user.role.value,
        "is_active": target_user.is_active,
    })
    db.commit()
    db.refresh(target_user)
    return target_user


@router.post("/users/{user_id}/reset-password")
def reset_user_password(
    user_id: str,
    payload: UserResetPasswordAdmin,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    check_permission(current_user, Action.USERS_MANAGE)
    target_user = db.query(User).filter(User.id == user_id).first()
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")

    target_user.password_hash = hash_password(payload.password)
    log_action(db, current_user.id, "reset_password", "user", target_user.id)
    db.commit()
    return {"status": "ok", "message": "Password reset successfully"}


# ── System Settings (Admin only) ──

@router.get("/writing-assistant/rule-disputes")
def get_writing_rule_disputes(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    check_permission(current_user, Action.SETTINGS_MANAGE)
    counts = writing_rule_dispute_counts(db)
    return {"threshold": 3, "rules": counts, "suppressed": sorted(rule for rule, count in counts.items() if count >= 3)}


@router.post("/writing-assistant/reset-rule-disputes")
def reset_writing_rule_disputes(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    check_permission(current_user, Action.SETTINGS_MANAGE)
    deleted = db.query(WritingRuleDispute).delete(synchronize_session=False)
    log_action(db, current_user.id, "reset_writing_rule_disputes", "writing_rule_dispute", meta={"deleted_count": deleted})
    db.commit()
    return {"deleted_count": deleted, "suppressed": []}

@router.get("/settings", response_model=SystemSettingsResponse)
def get_system_settings(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    check_permission(current_user, Action.SETTINGS_MANAGE)
    setting = db.query(SystemSetting).filter(SystemSetting.id == "default").first()
    if not setting:
        setting = SystemSetting(id="default", llm_enabled=True, min_confidence="medium", similarity_threshold=0.75, brand_words=[])
        db.add(setting)
        db.commit()
        db.refresh(setting)
    return setting


@router.patch("/settings", response_model=SystemSettingsResponse)
def update_system_settings(
    payload: SystemSettingsUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    check_permission(current_user, Action.SETTINGS_MANAGE)
    setting = db.query(SystemSetting).filter(SystemSetting.id == "default").first()
    if not setting:
        setting = SystemSetting(id="default")
        db.add(setting)

    if payload.llm_enabled is not None:
        setting.llm_enabled = payload.llm_enabled
    if payload.min_confidence is not None:
        setting.min_confidence = payload.min_confidence
    if payload.similarity_threshold is not None:
        setting.similarity_threshold = payload.similarity_threshold
    if payload.brand_words is not None:
        setting.brand_words = list(dict.fromkeys(word.strip() for word in payload.brand_words if word.strip()))

    log_action(db, current_user.id, "update_settings", "system_settings", "default", {
        "llm_enabled": setting.llm_enabled,
        "min_confidence": setting.min_confidence,
        "similarity_threshold": setting.similarity_threshold,
        "brand_words_count": len(setting.brand_words or []),
    })
    db.commit()
    db.refresh(setting)
    return setting


# ── Audit Logs (Admin only) ──

@router.get("/audit-logs", response_model=List[AuditLogResponse])
def get_audit_logs(
    action: Optional[str] = Query(None),
    entity: Optional[str] = Query(None),
    user_id: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    check_permission(current_user, Action.AUDIT_LOG_VIEW)
    query = db.query(AuditLog)
    if action:
        query = query.filter(AuditLog.action == action)
    if entity:
        query = query.filter(AuditLog.entity == entity)
    if user_id:
        query = query.filter(AuditLog.user_id == user_id)
    return query.order_by(AuditLog.created_at.desc()).offset(offset).limit(limit).all()


@router.get("/audit-logs/export")
def export_audit_logs_csv(
    action: Optional[str] = Query(None),
    entity: Optional[str] = Query(None),
    user_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    check_permission(current_user, Action.AUDIT_LOG_EXPORT)
    query = db.query(AuditLog)
    if action:
        query = query.filter(AuditLog.action == action)
    if entity:
        query = query.filter(AuditLog.entity == entity)
    if user_id:
        query = query.filter(AuditLog.user_id == user_id)
    logs = query.order_by(AuditLog.created_at.desc()).limit(1000).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID", "Timestamp", "User ID", "User Name", "Action", "Entity", "Entity ID", "Metadata"])
    for entry in logs:
        user_name = entry.user.name if entry.user else "System"
        writer.writerow([
            entry.id,
            entry.created_at.isoformat() if entry.created_at else "",
            entry.user_id or "",
            user_name,
            entry.action,
            entry.entity or "",
            entry.entity_id or "",
            str(entry.meta or ""),
        ])

    csv_data = output.getvalue()
    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="brandguard_audit_log.csv"'},
    )
