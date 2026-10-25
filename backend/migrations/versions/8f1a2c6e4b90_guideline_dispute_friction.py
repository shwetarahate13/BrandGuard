"""Add dispute friction index to guideline clauses.

Revision ID: 8f1a2c6e4b90
Revises: 5afdccd05dc9
Create Date: 2026-10-26
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "8f1a2c6e4b90"
down_revision: Union[str, None] = "5afdccd05dc9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "guideline_clauses",
        sa.Column("dispute_friction_index", sa.Float(), server_default="0", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("guideline_clauses", "dispute_friction_index")
