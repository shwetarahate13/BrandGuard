"""Add assigned_to_id to submissions and create system_settings table.

Revision ID: e5f2a1b9c8d3
Revises: b4c1d9a8e2f7
Create Date: 2026-10-26
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "e5f2a1b9c8d3"
down_revision: Union[str, None] = "b4c1d9a8e2f7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("submissions") as batch_op:
        batch_op.add_column(sa.Column("assigned_to_id", sa.String(), nullable=True))
        batch_op.create_foreign_key(
            "fk_submissions_assigned_to_id_users",
            "users",
            ["assigned_to_id"],
            ["id"],
            ondelete="SET NULL",
        )
    op.create_table(
        "system_settings",
        sa.Column("id", sa.String(length=50), nullable=False),
        sa.Column("llm_enabled", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("min_confidence", sa.String(length=20), nullable=False, server_default="medium"),
        sa.Column("similarity_threshold", sa.Float(), nullable=False, server_default="0.75"),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("system_settings")
    with op.batch_alter_table("submissions") as batch_op:
        batch_op.drop_constraint("fk_submissions_assigned_to_id_users", type_="foreignkey")
        batch_op.drop_column("assigned_to_id")
