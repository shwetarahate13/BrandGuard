"""Add per-submission audit chains and approval certificates.

Revision ID: 7e4c9a2d1f6b
Revises: d0e1f2a3b4c5
Create Date: 2026-10-27
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "7e4c9a2d1f6b"
down_revision: Union[str, None] = "d0e1f2a3b4c5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


WORKSPACE_SCOPE = "__workspace__"


def _timestamp(value, fallback: datetime) -> str:
    if value is None:
        value = fallback
    if isinstance(value, str):
        value = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _detail(value):
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            # Preserve a legacy scalar string exactly as the runtime verifier
            # will read it instead of silently normalizing it to an object.
            return value
    return value or {}


def _entry_hash(entry_id, submission_id, actor, action, detail, timestamp, prev_hash) -> str:
    canonical = json.dumps(
        {
            "id": entry_id,
            "submission_id": submission_id,
            "actor": actor,
            "action": action,
            "detail": detail,
            "timestamp": timestamp,
            "prev_hash": prev_hash,
        },
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _create_immutability_triggers(dialect: str) -> None:
    if dialect == "sqlite":
        op.execute("""
            CREATE TRIGGER audit_log_reject_update
            BEFORE UPDATE ON audit_log
            BEGIN
                SELECT RAISE(ABORT, 'audit_log is append-only');
            END
        """)
        op.execute("""
            CREATE TRIGGER audit_log_reject_delete
            BEFORE DELETE ON audit_log
            BEGIN
                SELECT RAISE(ABORT, 'audit_log is append-only');
            END
        """)
    elif dialect == "postgresql":
        op.execute("""
            CREATE FUNCTION brandguard_reject_audit_log_mutation()
            RETURNS trigger AS $$
            BEGIN
                RAISE EXCEPTION 'audit_log is append-only';
            END;
            $$ LANGUAGE plpgsql
        """)
        op.execute("""
            CREATE TRIGGER audit_log_reject_mutation
            BEFORE UPDATE OR DELETE ON audit_log
            FOR EACH ROW EXECUTE FUNCTION brandguard_reject_audit_log_mutation()
        """)


def _drop_immutability_triggers(dialect: str) -> None:
    if dialect == "sqlite":
        op.execute("DROP TRIGGER IF EXISTS audit_log_reject_update")
        op.execute("DROP TRIGGER IF EXISTS audit_log_reject_delete")
    elif dialect == "postgresql":
        op.execute("DROP TRIGGER IF EXISTS audit_log_reject_mutation ON audit_log")
        op.execute("DROP FUNCTION IF EXISTS brandguard_reject_audit_log_mutation()")


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name
    migration_time = datetime.now(timezone.utc)

    op.add_column("audit_log", sa.Column("submission_id", sa.String(), nullable=True))
    op.add_column("audit_log", sa.Column("sequence_no", sa.Integer(), nullable=True))
    op.add_column("audit_log", sa.Column("prev_hash", sa.String(length=64), nullable=True))
    op.add_column("audit_log", sa.Column("entry_hash", sa.String(length=64), nullable=True))
    op.add_column("audit_log", sa.Column("chained_at", sa.DateTime(timezone=True), nullable=True))

    op.create_table(
        "audit_chain_heads",
        sa.Column("scope_id", sa.String(length=100), primary_key=True),
        sa.Column("head_hash", sa.String(length=64), nullable=False),
        sa.Column("sequence_no", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    findings = {
        row.id: row.submission_id
        for row in bind.execute(sa.text("SELECT id, submission_id FROM findings")).all()
    }
    versions = {
        row.id: row.submission_id
        for row in bind.execute(sa.text("SELECT id, submission_id FROM submission_versions")).all()
    }
    rows = bind.execute(sa.text(
        "SELECT id, user_id, action, entity, entity_id, meta, created_at FROM audit_log"
    )).mappings().all()

    grouped = {}
    for row in rows:
        detail = _detail(row["meta"])
        submission_id = detail.get("submission_id") if isinstance(detail, dict) else None
        if row["entity"] == "submission":
            submission_id = row["entity_id"]
        elif row["entity"] == "finding":
            submission_id = findings.get(row["entity_id"], submission_id)
        elif row["entity"] == "submission_version":
            submission_id = versions.get(row["entity_id"], submission_id)
        scope_id = submission_id or WORKSPACE_SCOPE
        timestamp = _timestamp(row["created_at"], migration_time)
        grouped.setdefault(scope_id, []).append((row, submission_id, detail, timestamp))

    for scope_id, events in grouped.items():
        previous_hash = None
        sequence_no = 0
        for row, submission_id, detail, timestamp in sorted(events, key=lambda item: (item[3], item[0]["id"])):
            sequence_no += 1
            digest = _entry_hash(
                row["id"], submission_id, row["user_id"], row["action"], detail, timestamp, previous_hash
            )
            bind.execute(
                sa.text("""
                    UPDATE audit_log
                    SET submission_id=:submission_id, sequence_no=:sequence_no, prev_hash=:prev_hash,
                        entry_hash=:entry_hash, chained_at=:chained_at
                    WHERE id=:id
                """),
                {
                    "submission_id": submission_id,
                    "sequence_no": sequence_no,
                    "prev_hash": previous_hash,
                    "entry_hash": digest,
                    "chained_at": migration_time,
                    "id": row["id"],
                },
            )
            previous_hash = digest
        bind.execute(
            sa.text("""
                INSERT INTO audit_chain_heads (scope_id, head_hash, sequence_no, updated_at)
                VALUES (:scope_id, :head_hash, :sequence_no, :updated_at)
            """),
            {"scope_id": scope_id, "head_hash": previous_hash, "sequence_no": sequence_no, "updated_at": migration_time},
        )

    # Rows with no prior audit events still receive an empty workspace head on
    # first append; existing rows are now explicitly marked chained.
    with op.batch_alter_table("audit_log") as batch:
        batch.alter_column("sequence_no", existing_type=sa.Integer(), nullable=False)
        batch.alter_column("entry_hash", existing_type=sa.String(length=64), nullable=False)
        batch.alter_column("chained_at", existing_type=sa.DateTime(timezone=True), nullable=False)
    op.create_index("ix_audit_submission_sequence", "audit_log", ["submission_id", "sequence_no"])

    op.add_column("approvals", sa.Column("content_hash", sa.String(length=64), nullable=True))
    approval_rows = bind.execute(sa.text(
        "SELECT id, decision, version_id FROM approvals"
    )).mappings().all()
    for approval in approval_rows:
        if approval["decision"] != "approved":
            continue
        version = bind.execute(
            sa.text("SELECT text, source_file, source_mime_type FROM submission_versions WHERE id=:id"),
            {"id": approval["version_id"]},
        ).mappings().first() if approval["version_id"] else None
        if version and version["source_file"] is not None and (
            version["source_mime_type"] == "application/pdf"
            or (version["source_mime_type"] or "").startswith("image/")
        ):
            content = bytes(version["source_file"])
        else:
            content = (version["text"] if version and version["text"] is not None else "").encode("utf-8")
        bind.execute(
            sa.text("UPDATE approvals SET content_hash=:content_hash WHERE id=:id"),
            {"content_hash": hashlib.sha256(content).hexdigest(), "id": approval["id"]},
        )

    op.create_table(
        "approval_certificates",
        sa.Column("certificate_id", sa.String(length=48), primary_key=True),
        sa.Column("approval_id", sa.String(), sa.ForeignKey("approvals.id"), nullable=False, unique=True),
        sa.Column("submission_id", sa.String(), sa.ForeignKey("submissions.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("version_id", sa.String(), sa.ForeignKey("submission_versions.id"), nullable=False),
        sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("audit_head_hash", sa.String(length=64), nullable=False),
        sa.Column("ai_engine", sa.String(length=200), nullable=False),
        sa.Column("ai_mode", sa.String(length=80), nullable=False),
        sa.Column("verification_url", sa.String(length=1000), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_by_id", sa.String(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revocation_reason", sa.Text(), nullable=True),
        sa.Column("revocation_audit_head_hash", sa.String(length=64), nullable=True),
    )
    op.create_index("ix_certificates_submission_created", "approval_certificates", ["submission_id", "created_at"])
    op.create_index("ix_certificates_status", "approval_certificates", ["status"])
    _create_immutability_triggers(dialect)


def downgrade() -> None:
    dialect = op.get_bind().dialect.name
    _drop_immutability_triggers(dialect)
    op.drop_index("ix_certificates_status", table_name="approval_certificates")
    op.drop_index("ix_certificates_submission_created", table_name="approval_certificates")
    op.drop_table("approval_certificates")
    op.drop_column("approvals", "content_hash")
    op.drop_index("ix_audit_submission_sequence", table_name="audit_log")
    op.drop_table("audit_chain_heads")
    with op.batch_alter_table("audit_log") as batch:
        batch.drop_column("chained_at")
        batch.drop_column("entry_hash")
        batch.drop_column("prev_hash")
        batch.drop_column("sequence_no")
        batch.drop_column("submission_id")
