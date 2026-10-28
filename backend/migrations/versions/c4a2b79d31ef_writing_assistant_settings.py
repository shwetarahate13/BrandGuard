"""Add spelling and grammar categories and admin-managed brand words.

Revision ID: c4a2b79d31ef
Revises: 2c7a91d4b5e6
Create Date: 2026-10-28
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "c4a2b79d31ef"
down_revision: Union[str, None] = "2c7a91d4b5e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("system_settings", sa.Column("brand_words", sa.JSON(), nullable=False, server_default="[]"))


def downgrade() -> None:
    op.drop_column("system_settings", "brand_words")
