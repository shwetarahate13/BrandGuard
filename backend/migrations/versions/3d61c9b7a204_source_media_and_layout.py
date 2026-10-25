"""Persist uploaded source media and extracted layout coordinates.

Revision ID: 3d61c9b7a204
Revises: 8f1a2c6e4b90
Create Date: 2026-10-26
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "3d61c9b7a204"
down_revision: Union[str, None] = "8f1a2c6e4b90"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("ALTER TYPE contenttype ADD VALUE IF NOT EXISTS 'image'")
    op.add_column("submission_versions", sa.Column("source_file", sa.LargeBinary(), nullable=True))
    op.add_column("submission_versions", sa.Column("source_mime_type", sa.String(length=100), nullable=True))
    op.add_column("submission_versions", sa.Column("source_filename", sa.String(length=500), nullable=True))
    op.add_column("submission_versions", sa.Column("source_layout", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("submission_versions", "source_layout")
    op.drop_column("submission_versions", "source_filename")
    op.drop_column("submission_versions", "source_mime_type")
    op.drop_column("submission_versions", "source_file")
