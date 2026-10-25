"""Submissions API routes: create, upload, view, check, and add versions."""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from fastapi.responses import Response
from sqlalchemy.orm import Session
from sqlalchemy import or_

from backend.app.config import get_settings
from backend.app.database import get_db
from backend.app.models.models import (
    User, UserRole, Submission, SubmissionVersion, SubmissionStatus,
    ContentType, Finding
)
from backend.app.schemas.schemas import (
    SubmissionCreate, SubmissionResponse, SubmissionListResponse,
    VersionCreate, VersionResponse
)
from backend.app.services.auth import get_current_user
from backend.app.utils.audit import log_action
from backend.app.utils.text_extract import (
    extract_text,
    extract_pdf_text_with_layout,
    get_upload_mime_type,
    read_upload_contents,
)
from backend.app.pipeline.content_handlers import get_content_handler
from urllib.parse import quote
from backend.app.pipeline.runner import run_pipeline

router = APIRouter(prefix="/submissions", tags=["submissions"])


def validate_submission_text(text: str) -> None:
    max_words = get_settings().MAX_TEXT_WORDS
    if len(text.split()) > max_words:
        raise HTTPException(
            status_code=413,
            detail=f"Submission exceeds the {max_words}-word limit",
        )


def check_submission_access(submission: Submission, user: User):
    """Enforce RBAC for viewing a submission."""
    if user.role in (UserRole.admin, UserRole.manager):
        return
    if user.role == UserRole.creator:
        if submission.creator_id != user.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    elif user.role == UserRole.reviewer:
        # Reviewers see submissions under review, or with human review needed, or non-draft
        if submission.status == SubmissionStatus.draft and submission.creator_id != user.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied to draft")


@router.post("", response_model=SubmissionResponse)
def create_submission(
    payload: SubmissionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new submission with text content."""
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
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a submission from supported text, PDF, DOCX, or image uploads."""
    contents = await read_upload_contents(file)
    filename = file.filename or "uploaded_content.txt"
    try:
        mime_type = get_upload_mime_type(filename)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
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
    submission_id: str,
    version_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Serve the original upload for an authorized review session."""
    submission = db.query(Submission).filter(Submission.id == submission_id).first()
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")
    check_submission_access(submission, current_user)
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
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List submissions based on user role permissions."""
    query = db.query(Submission)

    if current_user.role == UserRole.creator:
        query = query.filter(Submission.creator_id == current_user.id)
    elif current_user.role == UserRole.reviewer:
        # Reviewers see in_review, changes_requested, approved, rejected, or submissions flagged needs_human
        subquery_needs_human = db.query(Finding.submission_id).filter(Finding.needs_human == True).subquery()
        query = query.filter(
            or_(
                Submission.status.in_([
                    SubmissionStatus.in_review,
                    SubmissionStatus.changes_requested,
                    SubmissionStatus.approved,
                    SubmissionStatus.rejected,
                ]),
                Submission.id.in_(subquery_needs_human),
                Submission.creator_id == current_user.id,
            )
        )
    # Manager and Admin see all

    submissions = query.order_by(Submission.created_at.desc()).all()

    # Attach finding counts
    result = []
    for s in submissions:
        count = db.query(Finding).filter(Finding.submission_id == s.id).count()
        item = SubmissionListResponse(
            id=s.id,
            creator_id=s.creator_id,
            title=s.title,
            intent=s.intent,
            status=s.status.value,
            content_type=s.content_type.value,
            created_at=s.created_at,
            updated_at=s.updated_at,
            creator=s.creator,
            finding_count=count,
        )
        result.append(item)

    return result


@router.get("/{submission_id}", response_model=SubmissionResponse)
def get_submission(
    submission_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    submission = db.query(Submission).filter(Submission.id == submission_id).first()
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")

    check_submission_access(submission, current_user)
    return submission


@router.post("/{submission_id}/check")
def check_submission(
    submission_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Run the brand governance review pipeline on the latest version of the submission."""
    submission = db.query(Submission).filter(Submission.id == submission_id).first()
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")

    check_submission_access(submission, current_user)

    # Get latest version
    latest_version = (
        db.query(SubmissionVersion)
        .filter(SubmissionVersion.submission_id == submission_id)
        .order_by(SubmissionVersion.version_no.desc())
        .first()
    )
    if not latest_version:
        raise HTTPException(status_code=400, detail="Submission has no content versions")

    # Clear old findings for this version before re-checking
    db.query(Finding).filter(Finding.version_id == latest_version.id).delete()
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
    submission = db.query(Submission).filter(Submission.id == submission_id).first()
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")

    check_submission_access(submission, current_user)
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
