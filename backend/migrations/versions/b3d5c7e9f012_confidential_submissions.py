"""Mark submissions that must not be sent to external language models."""
from alembic import op
import sqlalchemy as sa

revision = "b3d5c7e9f012"
down_revision = ("2c7a91d4b5e6", "e8c3a1f6d2b0")
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "submissions",
        sa.Column("confidential", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade():
    op.drop_column("submissions", "confidential")
