"""Track when guideline dispute friction scores were recomputed.

Revision ID: f70ad1c2e9a4
Revises: e5f2a1b9c8d3
Create Date: 2026-10-26
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f70ad1c2e9a4"
down_revision: Union[str, None] = "e5f2a1b9c8d3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "guideline_clauses",
        sa.Column("dfi_computed_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("guideline_clauses", "dfi_computed_at")
