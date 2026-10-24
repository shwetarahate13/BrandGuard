"""Audit logging helper."""
from sqlalchemy.orm import Session
from backend.app.models.models import AuditLog


def log_action(
    db: Session,
    user_id: str | None,
    action: str,
    entity: str | None = None,
    entity_id: str | None = None,
    meta: dict | None = None,
):
    """Create an audit log entry."""
    entry = AuditLog(
        user_id=user_id,
        action=action,
        entity=entity,
        entity_id=entity_id,
        meta=meta or {},
    )
    db.add(entry)
    db.flush()
    return entry
