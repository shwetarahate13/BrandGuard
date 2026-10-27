"""Append-only audit logging helper."""
from sqlalchemy.orm import Session
from backend.app.models.models import Finding, SubmissionVersion, gen_id
from backend.app.utils.audit_chain import append_audit_entry


def log_action(
    db: Session,
    user_id: str | None,
    action: str,
    entity: str | None = None,
    entity_id: str | None = None,
    meta: dict | None = None,
    submission_id: str | None = None,
):
    """Append a canonically hashed audit row to its submission chain."""
    detail = meta or {}
    if submission_id is None:
        if entity == "submission":
            submission_id = entity_id
        elif entity == "finding" and entity_id:
            finding = db.query(Finding.submission_id).filter(Finding.id == entity_id).first()
            submission_id = finding[0] if finding else detail.get("submission_id")
        elif entity == "submission_version" and entity_id:
            version = db.query(SubmissionVersion.submission_id).filter(SubmissionVersion.id == entity_id).first()
            submission_id = version[0] if version else detail.get("submission_id")
        else:
            submission_id = detail.get("submission_id")
    return append_audit_entry(
        db,
        entry_id=gen_id(),
        submission_id=submission_id,
        actor=user_id,
        action=action,
        entity=entity,
        entity_id=entity_id,
        detail=detail,
    )
