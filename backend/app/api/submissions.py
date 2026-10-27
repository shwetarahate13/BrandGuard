"""Submissions API routes: create, upload, view, check, and add versions."""
from datetime import datetime, timedelta, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Path as APIPath, Query, status
from fastapi.responses import Response, JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import or_, select

from backend.app.config import get_settings
from backend.app.database import get_db, get_session_factory
from backend.app.models.models import (
    User, UserRole, Submission, SubmissionVersion, SubmissionStatus,
    ContentType, Finding, GuidelineClause
)
from backend.app.schemas.schemas import (
    SubmissionCreate, SubmissionResponse, SubmissionListResponse,
    SubmissionAssignRequest, SubmissionDueDateUpdate, VersionCreate, VersionResponse
)
from backend.app.services.auth import get_current_user
from backend.app.services.permissions import (
    Action, check_permission, check_can_view_submission
)
from backend.app.services.notifications import add_notification
from backend.app.utils.audit import log_action
from backend.app.utils.text_extract import (
    extract_text,
    extract_pdf_text_with_layout,
    get_upload_mime_type,
    read_upload_contents,
    sanitize_upload_filename,
    sniff_upload_mime_type,
)
from backend.app.pipeline.content_handlers import get_content_handler
from urllib.parse import quote
from backend.app.pipeline.runner import run_pipeline
from backend.app.workers.background_jobs import BackgroundQueueFull, background_jobs

router = APIRouter(prefix="/submissions", tags=["submissions"])


def _extract_uploaded_version(version_id: str, owner_id: str, progress):
    """Extract a slow PDF/image/DOCX upload in a bounded worker."""
    from backend.app.models.models import User

    factory = get_session_factory()
    db = factory()
    try:
        version = db.query(SubmissionVersion).filter(SubmissionVersion.id == version_id).first()
        submission = db.query(Submission).filter(Submission.id == version.submission_id).first() if version else None
        if not version or not submission or submission.creator_id != owner_id:
            raise ValueError("Uploaded submission is no longer available")
        if not db.query(User.id).filter(User.id == owner_id, User.is_active.is_(True)).first():
            raise ValueError("Your account is no longer active")

        progress(10, "Validating uploaded document.")
        contents = version.source_file or b""
        mime_type = version.source_mime_type or ""
        progress(30, "Extracting text and page or image coordinates.")
        if mime_type == "application/pdf":
            extracted, source_layout = extract_pdf_text_with_layout(contents)
        elif mime_type.startswith("image/"):
            handler = get_content_handler(mime_type)
            if handler is None:
                raise ValueError(f"No content handler registered for {mime_type}")
            extracted, source_layout = handler.extract_content(contents)
        else:
            extracted = extract_text(contents, version.source_filename or "uploaded.docx")
            source_layout = None
        validate_submission_text(extracted)
        progress(90, "Saving extracted content.")
        version.text = extracted
        version.source_layout = source_layout
        db.commit()
        return {"submission_id": submission.id}
    except Exception:
        db.rollback()
        if version_id:
            failed = db.query(SubmissionVersion).filter(SubmissionVersion.id == version_id).first()
            if failed:
                parent_id = failed.submission_id
                db.delete(failed)
                parent = db.query(Submission).filter(Submission.id == parent_id).first()
                if parent and parent.status == SubmissionStatus.draft:
                    db.delete(parent)
                db.commit()
        raise
    finally:
        db.close()


def _run_check_job(submission_id: str, version_id: str, owner_id: str, progress):
    """Run the governance pipeline with an independent, worker-owned session."""
    factory = get_session_factory()
    with factory() as db:
        user = db.query(User).filter(User.id == owner_id, User.is_active.is_(True)).first()
        submission = db.query(Submission).filter(Submission.id == submission_id).first()
        version = db.query(SubmissionVersion).filter(
            SubmissionVersion.id == version_id,
            SubmissionVersion.submission_id == submission_id,
        ).first()
        if not user or not submission or not version:
            raise ValueError("Submission or active user is no longer available")
        check_permission(user, Action.SUBMISSION_CREATE)
        check_can_view_submission(user, submission)
        progress(10, "Preparing approved sources and review rules.")
        db.query(Finding).filter(Finding.version_id == version.id).delete()
        db.query(GuidelineClause).update({GuidelineClause.dfi_computed_at: None})
        db.commit()
        findings = run_pipeline(submission, version, db, progress=progress)
        if submission.status == SubmissionStatus.draft:
            submission.status = SubmissionStatus.checked
        log_action(db, user.id, "check_submission", "submission", submission.id, {
            "version_no": version.version_no,
            "findings_count": len(findings),
        })
        db.commit()
        return {
            "submission_id": submission.id,
            "findings_count": len(findings),
            "submission_status": submission.status.value,
        }


def _submit_background_job(**kwargs):
    try:
        return background_jobs.submit(**kwargs)
    except BackgroundQueueFull as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc


def validate_submission_text(text: str) -> None:
    max_words = get_settings().MAX_TEXT_WORDS
    if len(text.split()) > max_words:
        raise HTTPException(
            status_code=413,
            detail=f"Submission exceeds the {max_words}-word limit",
        )


def check_submission_access(submission: Submission, user: User):
    """Compatibility wrapper for the centralized row-level permission check."""
    check_can_view_submission(user, submission)


@router.post("", response_model=SubmissionResponse)
def create_submission(
    payload: SubmissionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new submission with text content."""
    check_permission(current_user, Action.SUBMISSION_CREATE)
    try:
        ctype = ContentType(payload.content_type)
    except ValueError:
        ctype = ContentType.text

    submission = Submission(
        creator_id=current_user.id,
        title=payload.title.strip(),
        intent=payload.intent.strip() if payload.intent else None,
        status=SubmissionStatus.draft,
        content_type=ctype,
    )
    db.add(submission)
    db.flush()

    # Create Version 1
    text_content = payload.text or ""
    validate_submission_text(text_content)
    v1 = SubmissionVersion(
        submission_id=submission.id,
        version_no=1,
        text=text_content,
        created_by=current_user.id,
    )
    db.add(v1)
    db.flush()

    log_action(db, current_user.id, "create_submission", "submission", submission.id)
    db.commit()
    db.refresh(submission)
    return submission


@router.post("/upload", response_model=SubmissionResponse)
async def upload_submission(
    file: UploadFile = File(...),
    title: str = Form(...),
    intent: Optional[str] = Form(None),
    content_type: Optional[str] = Form("text"),
    background: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a submission from supported text, PDF, DOCX, or image uploads."""
    check_permission(current_user, Action.SUBMISSION_CREATE)
    contents = await read_upload_contents(file)
    filename = sanitize_upload_filename(file.filename)
    try:
        declared_mime_type = get_upload_mime_type(filename)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    settings = get_settings()
    if declared_mime_type.startswith("image/") and not settings.IMAGE_REVIEW_ENABLED:
        raise HTTPException(
            status_code=503,
            detail="Image review is disabled in this configuration; set IMAGE_REVIEW_ENABLED=true to enable it.",
        )
    try:
        mime_type = sniff_upload_mime_type(contents, filename)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if background and mime_type in {
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "image/png",
        "image/jpeg",
        "image/svg+xml",
    }:
        if mime_type == "application/pdf":
            ctype = ContentType.pdf
        elif mime_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
            ctype = ContentType.docx
        else:
            ctype = ContentType.image
        submission = Submission(
            creator_id=current_user.id,
            title=title.strip() or filename,
            intent=intent.strip() if intent else None,
            status=SubmissionStatus.draft,
            content_type=ctype,
        )
        db.add(submission)
        db.flush()
        version = SubmissionVersion(
            submission_id=submission.id,
            version_no=1,
            text="",
            created_by=current_user.id,
            source_file=contents,
            source_mime_type=mime_type,
            source_filename=filename,
        )
        db.add(version)
        db.flush()
        version_id = version.id
        log_action(db, current_user.id, "upload_submission", "submission", submission.id, {"filename": filename})
        db.commit()
        db.refresh(submission)
        job = _submit_background_job(
            owner_id=current_user.id,
            kind="document-extraction",
            payload={"version_id": version_id, "owner_id": current_user.id},
            timeout_seconds=180,
            dedupe_key=f"extract:{version.id}",
        )
        return JSONResponse(status_code=202, content={**job, "submission_id": submission.id})
    source_layout = None
    try:
        if mime_type == "application/pdf":
            extracted, source_layout = extract_pdf_text_with_layout(contents)
        elif mime_type.startswith("image/"):
            handler = get_content_handler(mime_type)
            if handler is None:
                raise ValueError(f"No content handler registered for {mime_type}")
            extracted, source_layout = handler.extract_content(contents)
        else:
            extracted = extract_text(contents, filename)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    validate_submission_text(extracted)

    if mime_type == "application/pdf":
        ctype = ContentType.pdf
    elif mime_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
        ctype = ContentType.docx
    elif mime_type.startswith("image/"):
        ctype = ContentType.image
    elif mime_type == "text/markdown":
        ctype = ContentType.markdown
    elif mime_type == "text/html":
        ctype = ContentType.html
    else:
        ctype = ContentType.text

    submission = Submission(
        creator_id=current_user.id,
        title=title.strip() or filename,
        intent=intent.strip() if intent else None,
        status=SubmissionStatus.draft,
        content_type=ctype,
    )
    db.add(submission)
    db.flush()

    v1 = SubmissionVersion(
        submission_id=submission.id,
        version_no=1,
        text=extracted,
        created_by=current_user.id,
        source_file=contents,
        source_mime_type=mime_type,
        source_filename=filename,
        source_layout=source_layout,
    )
    db.add(v1)
    db.flush()

    log_action(db, current_user.id, "upload_submission", "submission", submission.id, {"filename": filename})
    db.commit()
    db.refresh(submission)
    return submission


@router.get("/{submission_id}/versions/{version_id}/source")
def get_submission_source(
    submission_id: str = APIPath(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9-]+$"),
    version_id: str = APIPath(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9-]+$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Serve the original upload for an authorized review session."""
    submission = db.query(Submission).filter(Submission.id == submission_id).first()
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")
    check_can_view_submission(current_user, submission)
    version = (
        db.query(SubmissionVersion)
        .filter(
            SubmissionVersion.id == version_id,
            SubmissionVersion.submission_id == submission_id,
        )
        .first()
    )
    if not version or not version.source_file or not version.source_mime_type:
        raise HTTPException(status_code=404, detail="Original source file not found")

    filename = quote(version.source_filename or "source", safe="")
    return Response(
        content=version.source_file,
        media_type=version.source_mime_type,
        headers={
            "Content-Disposition": f"inline; filename*=UTF-8''{filename}",
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "private, no-store",
            "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; img-src data:",
        },
    )


@router.get("", response_model=List[SubmissionListResponse])
def list_submissions(
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List submissions based on user role permissions."""
    list_action = {
        UserRole.creator: Action.SUBMISSION_VIEW_OWN,
        UserRole.manager: Action.SUBMISSION_VIEW_ALL,
        UserRole.reviewer: Action.SUBMISSION_VIEW_ASSIGNED,
        UserRole.admin: Action.SUBMISSION_VIEW_ALL,
    }[current_user.role]
    check_permission(current_user, list_action)
    query = db.query(Submission)

    if current_user.role == UserRole.creator:
        query = query.filter(Submission.creator_id == current_user.id)
    elif current_user.role == UserRole.reviewer:
        # Reviewers see only assigned work or submissions with compliance escalation.
        subquery_escalated = select(Finding.submission_id).where(
            or_(
                Finding.needs_human.is_(True),
                Finding.severity.in_(["critical", "major"]),
                Finding.category == "unsupported_claim",
            )
        ).distinct()
        query = query.filter(
            or_(
                Submission.assigned_to_id == current_user.id,
                Submission.id.in_(subquery_escalated),
            )
        )
    # Manager and Admin see all

    submissions = query.order_by(Submission.created_at.desc()).offset(offset).limit(limit).all()

    # Attach finding counts, needs_human counts, and age in hours
    result = []
    now = datetime.now(timezone.utc)
    for s in submissions:
        count = db.query(Finding).filter(Finding.submission_id == s.id).count()
        needs_human_cnt = db.query(Finding).filter(Finding.submission_id == s.id, Finding.needs_human == True).count()
        created_dt = s.created_at.replace(tzinfo=timezone.utc) if s.created_at.tzinfo is None else s.created_at
        age_hours = round(max(0.0, (now - created_dt).total_seconds() / 3600.0), 1)

        item = SubmissionListResponse(
            id=s.id,
            creator_id=s.creator_id,
            assigned_to_id=s.assigned_to_id,
            assignment_due_at=s.assignment_due_at,
            assigned_to=s.assigned_to,
            title=s.title,
            intent=s.intent,
            status=s.status.value,
            content_type=s.content_type.value,
            created_at=s.created_at,
            updated_at=s.updated_at,
            creator=s.creator,
            finding_count=count,
            needs_human_count=needs_human_cnt,
            age_hours=age_hours,
            is_overdue=(
                s.status == SubmissionStatus.in_review
                and s.assigned_to_id is not None
                and s.assignment_due_at is not None
                and (s.assignment_due_at.replace(tzinfo=timezone.utc) if s.assignment_due_at.tzinfo is None else s.assignment_due_at) < now
            ),
        )
        result.append(item)

    return result


@router.get("/reviewers")
def list_reviewers(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return the active reviewers available for manager assignment."""
    check_permission(current_user, Action.SUBMISSION_ASSIGN)
    reviewers = (
        db.query(User)
        .filter(User.role == UserRole.reviewer, User.is_active.is_(True))
        .order_by(User.name.asc())
        .all()
    )
    return [{"id": item.id, "name": item.name, "email": item.email, "role": item.role.value,
             "is_active": item.is_active} for item in reviewers]


@router.get("/{submission_id}", response_model=SubmissionResponse)
def get_submission(
    submission_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    submission = db.query(Submission).filter(Submission.id == submission_id).first()
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")

    check_can_view_submission(current_user, submission)
    return submission


@router.post("/{submission_id}/assign", response_model=SubmissionResponse)
def assign_submission(
    submission_id: str,
    payload: SubmissionAssignRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Manager assigns submission to a reviewer (Compliance desk)."""
    check_permission(current_user, Action.SUBMISSION_ASSIGN)
    submission = db.query(Submission).filter(Submission.id == submission_id).first()
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")

    reviewer = db.query(User).filter(
        User.id == payload.reviewer_id,
        User.role == UserRole.reviewer,
        User.is_active.is_(True),
    ).first()
    if not reviewer:
        raise HTTPException(status_code=400, detail="Assigned user must be an active reviewer")

    previous_reviewer_id = submission.assigned_to_id
    submission.assigned_to_id = reviewer.id
    if submission.status == SubmissionStatus.in_review and submission.assignment_due_at is None:
        submission.assignment_due_at = datetime.now(timezone.utc) + timedelta(hours=24)
    if previous_reviewer_id != reviewer.id:
        add_notification(
            db,
            user_id=reviewer.id,
            submission_id=submission.id,
            kind="review_assignment",
            title="New review assignment",
            message=f"{current_user.name} assigned you to review ‘{submission.title}’.",
        )
    log_action(db, current_user.id, "assign_reviewer", "submission", submission.id, {
        "reviewer_id": reviewer.id,
        "reviewer_name": reviewer.name,
        "assignment_due_at": submission.assignment_due_at.isoformat() if submission.assignment_due_at else None,
    })
    db.commit()
    db.refresh(submission)
    return submission


@router.patch("/{submission_id}/due-date", response_model=SubmissionResponse)
def update_assignment_due_date(
    submission_id: str,
    payload: SubmissionDueDateUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Set or clear the due date for an active reviewer assignment."""
    check_permission(current_user, Action.SUBMISSION_ASSIGN)
    submission = db.query(Submission).filter(Submission.id == submission_id).first()
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")
    if submission.assigned_to_id is None or submission.status != SubmissionStatus.in_review:
        raise HTTPException(status_code=409, detail="A due date requires an assigned submission in review")

    due_at = payload.assignment_due_at
    if due_at is not None and due_at.tzinfo is None:
        due_at = due_at.replace(tzinfo=timezone.utc)
    submission.assignment_due_at = due_at
    log_action(db, current_user.id, "update_assignment_due_date", "submission", submission.id, {
        "assignment_due_at": due_at.isoformat() if due_at else None,
    })
    db.commit()
    db.refresh(submission)
    return submission


@router.post("/{submission_id}/check")
def check_submission(
    submission_id: str,
    background: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Run the brand governance review pipeline on the latest version of the submission."""
    check_permission(current_user, Action.SUBMISSION_CREATE)
    submission = db.query(Submission).filter(Submission.id == submission_id).first()
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")

    check_can_view_submission(current_user, submission)

    # Get latest version
    latest_version = (
        db.query(SubmissionVersion)
        .filter(SubmissionVersion.submission_id == submission_id)
        .order_by(SubmissionVersion.version_no.desc())
        .first()
    )
    if not latest_version:
        raise HTTPException(status_code=400, detail="Submission has no content versions")
    if (
        latest_version.source_mime_type
        and latest_version.source_mime_type.startswith("image/")
        and not get_settings().IMAGE_REVIEW_ENABLED
    ):
        raise HTTPException(status_code=503, detail="Image review is disabled on this instance")

    if background:
        job = _submit_background_job(
            owner_id=current_user.id,
            kind="content-review",
            payload={
                "submission_id": submission.id,
                "version_id": latest_version.id,
                "owner_id": current_user.id,
            },
            timeout_seconds=300,
            dedupe_key=f"check:{submission.id}:{latest_version.id}",
        )
        return JSONResponse(status_code=202, content=job)

    # Clear old findings for this version before re-checking
    db.query(Finding).filter(Finding.version_id == latest_version.id).delete()
    # Rechecking may change the clause finding denominator. Recompute on the
    # next guideline-health read instead of returning stale risk scores.
    db.query(GuidelineClause).update({GuidelineClause.dfi_computed_at: None})
    db.commit()

    # Run review pipeline
    findings = run_pipeline(submission, latest_version, db)

    # Update status to checked if still draft
    if submission.status == SubmissionStatus.draft:
        submission.status = SubmissionStatus.checked
        db.commit()

    log_action(db, current_user.id, "check_submission", "submission", submission.id, {
        "version_no": latest_version.version_no,
        "findings_count": len(findings),
    })
    db.commit()

    return {
        "status": "ok",
        "findings_count": len(findings),
        "submission_status": submission.status.value,
    }


@router.post("/{submission_id}/versions", response_model=VersionResponse)
def add_version(
    submission_id: str,
    payload: VersionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Manually add an updated content version."""
    check_permission(current_user, Action.SUBMISSION_CREATE)
    submission = db.query(Submission).filter(Submission.id == submission_id).first()
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")

    if submission.creator_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the submission creator can add updated content versions")

    validate_submission_text(payload.text)

    # Get current max version
    max_ver = (
        db.query(SubmissionVersion.version_no)
        .filter(SubmissionVersion.submission_id == submission_id)
        .order_by(SubmissionVersion.version_no.desc())
        .first()
    )
    next_ver = (max_ver[0] + 1) if max_ver else 1

    new_version = SubmissionVersion(
        submission_id=submission.id,
        version_no=next_ver,
        text=payload.text,
        created_by=current_user.id,
    )
    db.add(new_version)
    submission.status = SubmissionStatus.draft  # New version returns to draft until checked
    log_action(db, current_user.id, "add_version", "submission_version", new_version.id, {"version_no": next_ver})
    db.commit()
    db.refresh(new_version)
    return new_version
