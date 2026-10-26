"""Add indexes for dashboard, assignment, feedback, and audit queries.

Revision ID: 1a7c3e9f6b20
Revises: f70ad1c2e9a4
Create Date: 2026-10-26
"""
from typing import Sequence, Union

from alembic import op


revision: str = "1a7c3e9f6b20"
down_revision: Union[str, None] = "f70ad1c2e9a4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index("ix_submissions_status_created", "submissions", ["status", "created_at"])
    op.create_index("ix_submissions_assigned_to", "submissions", ["assigned_to_id"])
    op.create_index("ix_findings_source", "findings", ["source_type", "source_id"])
    op.create_index("ix_findings_submission", "findings", ["submission_id"])
    op.create_index("ix_decisions_action_finding", "decisions", ["action", "finding_id"])
    op.create_index("ix_audit_created_at", "audit_log", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_audit_created_at", table_name="audit_log")
    op.drop_index("ix_decisions_action_finding", table_name="decisions")
    op.drop_index("ix_findings_submission", table_name="findings")
    op.drop_index("ix_findings_source", table_name="findings")
    op.drop_index("ix_submissions_assigned_to", table_name="submissions")
    op.drop_index("ix_submissions_status_created", table_name="submissions")
