"""Canonical hashing and verification for the append-only audit log."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Iterable

from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.app.models.models import AuditChainHead, AuditLog, utcnow


WORKSPACE_SCOPE = "__workspace__"


def canonical_timestamp(value: datetime | str | None) -> str:
    if value is None:
        raise ValueError("Audit timestamps cannot be empty")
    if isinstance(value, str):
        value = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def canonical_audit_json(
    *,
    entry_id: str,
    submission_id: str | None,
    actor: str | None,
    action: str,
    detail: dict[str, Any] | None,
    timestamp: datetime | str,
    prev_hash: str | None,
) -> bytes:
    payload = {
        "id": entry_id,
        "submission_id": submission_id,
        "actor": actor,
        "action": action,
        "detail": detail or {},
        "timestamp": canonical_timestamp(timestamp),
        "prev_hash": prev_hash,
    }
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def hash_audit_entry(
    *,
    entry_id: str,
    submission_id: str | None,
    actor: str | None,
    action: str,
    detail: dict[str, Any] | None,
    timestamp: datetime | str,
    prev_hash: str | None,
) -> str:
    canonical = canonical_audit_json(
        entry_id=entry_id,
        submission_id=submission_id,
        actor=actor,
        action=action,
        detail=detail,
        timestamp=timestamp,
        prev_hash=prev_hash,
    )
    return hashlib.sha256(canonical).hexdigest()


def _ensure_locked_head(db: Session, scope_id: str, now: datetime) -> tuple[str | None, int]:
    dialect = db.get_bind().dialect.name
    params = {"scope_id": scope_id, "updated_at": now}
    if dialect == "sqlite":
        db.execute(text("""
            INSERT OR IGNORE INTO audit_chain_heads (scope_id, head_hash, sequence_no, updated_at)
            VALUES (:scope_id, '', 0, :updated_at)
        """), params)
    elif dialect == "postgresql":
        db.execute(text("""
            INSERT INTO audit_chain_heads (scope_id, head_hash, sequence_no, updated_at)
            VALUES (:scope_id, '', 0, :updated_at)
            ON CONFLICT (scope_id) DO NOTHING
        """), params)
    else:
        head = db.get(AuditChainHead, scope_id)
        if head is None:
            head = AuditChainHead(scope_id=scope_id, head_hash="", sequence_no=0, updated_at=now)
            db.add(head)
            db.flush()

    # This write acquires the row lock on Postgres and the write lock on
    # SQLite before the head is read, preventing concurrent chain forks.
    db.execute(
        text("UPDATE audit_chain_heads SET updated_at=:updated_at WHERE scope_id=:scope_id"),
        params,
    )
    row = db.execute(
        text("SELECT head_hash, sequence_no FROM audit_chain_heads WHERE scope_id=:scope_id"),
        {"scope_id": scope_id},
    ).first()
    if row is None:
        raise RuntimeError("Could not lock the audit chain head")
    return (row[0] if row[1] else None, int(row[1]))


def append_audit_entry(
    db: Session,
    *,
    entry_id: str,
    submission_id: str | None,
    actor: str | None,
    action: str,
    entity: str | None,
    entity_id: str | None,
    detail: dict[str, Any] | None,
) -> AuditLog:
    now = utcnow()
    scope_id = submission_id or WORKSPACE_SCOPE
    previous_hash, previous_sequence = _ensure_locked_head(db, scope_id, now)
    sequence_no = previous_sequence + 1
    detail = detail or {}
    entry_hash = hash_audit_entry(
        entry_id=entry_id,
        submission_id=submission_id,
        actor=actor,
        action=action,
        detail=detail,
        timestamp=now,
        prev_hash=previous_hash,
    )
    entry = AuditLog(
        id=entry_id,
        submission_id=submission_id,
        sequence_no=sequence_no,
        user_id=actor,
        action=action,
        entity=entity,
        entity_id=entity_id,
        meta=detail,
        created_at=now,
        prev_hash=previous_hash,
        entry_hash=entry_hash,
        chained_at=now,
    )
    db.add(entry)
    db.flush()
    db.execute(
        text("""
            UPDATE audit_chain_heads
            SET head_hash=:head_hash, sequence_no=:sequence_no, updated_at=:updated_at
            WHERE scope_id=:scope_id
        """),
        {
            "scope_id": scope_id,
            "head_hash": entry_hash,
            "sequence_no": sequence_no,
            "updated_at": now,
        },
    )
    return entry


def verify_rows(
    rows: Iterable[AuditLog],
    expected_head: AuditChainHead | None = None,
    *,
    require_head: bool = False,
) -> dict[str, Any]:
    ordered = sorted(rows, key=lambda row: (row.sequence_no or 0, row.id))
    previous_hash = None
    hashes: list[str] = []
    errors: list[str] = []
    expected_sequence = 1
    for row in ordered:
        if row.sequence_no != expected_sequence:
            errors.append(f"sequence gap at entry {row.id}")
        if row.prev_hash != previous_hash:
            errors.append(f"previous hash mismatch at entry {row.id}")
        if row.chained_at is None:
            errors.append(f"entry {row.id} is not marked as chained")
        try:
            recomputed = hash_audit_entry(
                entry_id=row.id,
                submission_id=row.submission_id,
                actor=row.user_id,
                action=row.action,
                detail=row.meta or {},
                timestamp=row.created_at,
                prev_hash=row.prev_hash,
            )
        except (TypeError, ValueError, OverflowError):
            recomputed = ""
            errors.append(f"entry {row.id} contains invalid canonical data")
        if recomputed != row.entry_hash:
            errors.append(f"entry hash mismatch at entry {row.id}")
        previous_hash = row.entry_hash
        hashes.append(row.entry_hash)
        expected_sequence += 1

    if require_head and expected_head is None:
        errors.append("stored chain head is missing")
    if expected_head:
        if expected_head.head_hash != (previous_hash or ""):
            errors.append("stored chain head does not match the final audit entry")
        if expected_head.sequence_no != len(ordered):
            errors.append("stored chain head sequence does not match the audit entries")
    return {
        "valid": not errors,
        "entry_count": len(ordered),
        "head_hash": previous_hash,
        "entry_hashes": hashes,
        "errors": errors,
    }


def verify_submission_chain(db: Session, submission_id: str) -> dict[str, Any]:
    rows = (
        db.query(AuditLog)
        .filter(AuditLog.submission_id == submission_id)
        .order_by(AuditLog.sequence_no.asc())
        .all()
    )
    head = db.get(AuditChainHead, submission_id)
    result = verify_rows(rows, head, require_head=True)
    result["submission_id"] = submission_id
    return result


def verify_all_chains(db: Session) -> list[dict[str, Any]]:
    rows = db.query(AuditLog).order_by(AuditLog.sequence_no.asc(), AuditLog.id.asc()).all()
    grouped: dict[str, list[AuditLog]] = {}
    for row in rows:
        scope_id = row.submission_id or WORKSPACE_SCOPE
        grouped.setdefault(scope_id, []).append(row)
    heads = {head.scope_id: head for head in db.query(AuditChainHead).all()}
    results = []
    for scope_id in sorted(grouped.keys() | heads.keys()):
        chain_rows = grouped.get(scope_id, [])
        checked = verify_rows(chain_rows, heads.get(scope_id), require_head=True)
        results.append({
            "scope_id": scope_id,
            "submission_id": None if scope_id == WORKSPACE_SCOPE else scope_id,
            "entry_count": checked["entry_count"],
            "valid": checked["valid"],
            "head_hash": checked["head_hash"],
            "errors": checked["errors"],
        })
    results.sort(key=lambda result: (not result["valid"], result["scope_id"]))
    return results
