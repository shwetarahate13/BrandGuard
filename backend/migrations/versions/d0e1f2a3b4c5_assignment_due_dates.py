"""Add reviewer assignment due dates.

Revision ID: d0e1f2a3b4c5
Revises: c91b4e7a2d60
Create Date: 2026-10-26
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d0e1f2a3b4c5"
down_revision: Union[str, None] = "c91b4e7a2d60"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("submissions", sa.Column("assignment_due_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index(
        "ix_submissions_assigned_due",
        "submissions",
        ["assigned_to_id", "assignment_due_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_submissions_assigned_due", table_name="submissions")
    op.drop_column("submissions", "assignment_due_at")
