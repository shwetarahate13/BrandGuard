"""Persist request keys for submission create and upload retries.

Revision ID: a81f4c2d9e10
Revises: 7e4c9a2d1f6b
Create Date: 2026-10-28
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a81f4c2d9e10"
down_revision: Union[str, None] = "7e4c9a2d1f6b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "idempotency_records",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("scope", sa.String(length=80), nullable=False),
        sa.Column("key", sa.String(length=128), nullable=False),
        sa.Column("request_hash", sa.String(length=64), nullable=False),
        sa.Column("resource_id", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "scope", "key", name="uq_idempotency_user_scope_key"),
    )
    op.create_index("ix_idempotency_resource", "idempotency_records", ["resource_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_idempotency_resource", table_name="idempotency_records")
    op.drop_table("idempotency_records")
