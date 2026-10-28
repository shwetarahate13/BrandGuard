"""Mark seeded submissions as fictional demo data.

Revision ID: e8c3a1f6d2b0
Revises: d3e7a91b5c20
Create Date: 2026-10-29
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "e8c3a1f6d2b0"
down_revision: Union[str, None] = "d3e7a91b5c20"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "submissions",
        sa.Column("is_demo", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("submissions", "is_demo")
