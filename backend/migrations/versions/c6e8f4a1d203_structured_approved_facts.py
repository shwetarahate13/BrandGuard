"""Add structured values to approved facts."""
from alembic import op
import sqlalchemy as sa

revision = "c6e8f4a1d203"
down_revision = "b3d5c7e9f012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("approved_facts", sa.Column("subject", sa.String(length=300), nullable=True))
    op.add_column("approved_facts", sa.Column("value", sa.String(length=300), nullable=True))
    op.add_column("approved_facts", sa.Column("unit", sa.String(length=100), nullable=True))


def downgrade() -> None:
    op.drop_column("approved_facts", "unit")
    op.drop_column("approved_facts", "value")
    op.drop_column("approved_facts", "subject")
