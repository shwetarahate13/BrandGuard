"""Helpers for persisting user-scoped workflow notifications."""
from sqlalchemy.orm import Session

from backend.app.models.models import Notification


def add_notification(
    db: Session,
    *,
    user_id: str,
    submission_id: str,
    kind: str,
    title: str,
    message: str,
) -> Notification:
    notification = Notification(
        user_id=user_id,
        submission_id=submission_id,
        kind=kind,
        title=title,
        message=message,
    )
    db.add(notification)
    return notification
