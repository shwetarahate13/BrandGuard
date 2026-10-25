"""Persist rewrite feedback features and online preference model state.

Revision ID: b4c1d9a8e2f7
Revises: 3d61c9b7a204
Create Date: 2026-10-26
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b4c1d9a8e2f7"
down_revision: Union[str, None] = "3d61c9b7a204"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("decisions", sa.Column("original_span", sa.Text(), nullable=True))
    op.add_column("decisions", sa.Column("suggested_rewrite", sa.Text(), nullable=True))
    op.add_column("decisions", sa.Column("human_edited_text", sa.Text(), nullable=True))
    op.add_column("findings", sa.Column("acceptance_probability", sa.Float(), nullable=True))
    op.create_table(
        "preference_model_states",
        sa.Column("id", sa.String(length=50), nullable=False),
        sa.Column("model_blob", sa.LargeBinary(), nullable=False),
        sa.Column("sample_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("preference_model_states")
    op.drop_column("findings", "acceptance_probability")
    op.drop_column("decisions", "human_edited_text")
    op.drop_column("decisions", "suggested_rewrite")
    op.drop_column("decisions", "original_span")
