"""Persistent idempotency records for retryable write requests."""
import hashlib
import json
import re
from typing import Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from backend.app.models.models import IdempotencyRecord


_IDEMPOTENCY_KEY = re.compile(r"^[A-Za-z0-9._:-]{8,128}$")


def request_fingerprint(value) -> str:
    canonical = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def find_idempotency_record(
    db: Session,
    user_id: str,
    scope: str,
    key: Optional[str],
    fingerprint: str,
) -> Optional[IdempotencyRecord]:
    if key is None:
        return None
    if not _IDEMPOTENCY_KEY.fullmatch(key):
        raise HTTPException(
            status_code=400,
            detail="Idempotency-Key must be 8–128 letters, numbers, dots, underscores, colons, or hyphens",
        )
    record = (
        db.query(IdempotencyRecord)
        .filter(
            IdempotencyRecord.user_id == user_id,
            IdempotencyRecord.scope == scope,
            IdempotencyRecord.key == key,
        )
        .first()
    )
    if record and record.request_hash != fingerprint:
        raise HTTPException(status_code=409, detail="This Idempotency-Key was already used with different request data")
    return record


def remember_request(
    db: Session,
    user_id: str,
    scope: str,
    key: Optional[str],
    fingerprint: str,
    resource_id: str,
) -> None:
    if key:
        db.add(IdempotencyRecord(
            user_id=user_id,
            scope=scope,
            key=key,
            request_hash=fingerprint,
            resource_id=resource_id,
        ))
