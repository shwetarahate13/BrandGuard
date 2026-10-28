"""Track disputes for writing-rule suppression.

Revision ID: d3e7a91b5c20
Revises: c4a2b79d31ef
Create Date: 2026-10-28
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "d3e7a91b5c20"
down_revision: Union[str, None] = "c4a2b79d31ef"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "writing_rule_disputes",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("rule_id", sa.String(length=32), nullable=False),
        sa.Column("finding_id", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["finding_id"], ["findings.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("finding_id", name="uq_writing_rule_dispute_finding"),
    )
    op.create_index("ix_writing_rule_disputes_rule_id", "writing_rule_disputes", ["rule_id"])


def downgrade() -> None:
    op.drop_index("ix_writing_rule_disputes_rule_id", table_name="writing_rule_disputes")
    op.drop_table("writing_rule_disputes")
