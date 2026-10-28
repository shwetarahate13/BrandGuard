"""Persist version-specific compliance reviewer sign-offs."""
from alembic import op
import sqlalchemy as sa

revision = "2c7a91d4b5e6"
down_revision = ("f70ad1c2e9a4", "a81f4c2d9e10")
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "reviewer_signoffs",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("submission_id", sa.String(), nullable=False),
        sa.Column("version_id", sa.String(), nullable=False),
        sa.Column("reviewer_id", sa.String(), nullable=False),
        sa.Column("checklist", sa.JSON(), nullable=False),
        sa.Column("evidence_notes", sa.Text(), nullable=False),
        sa.Column("justification", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["submission_id"], ["submissions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["version_id"], ["submission_versions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["reviewer_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("submission_id", "version_id", name="uq_reviewer_signoff_version"),
    )


def downgrade():
    op.drop_table("reviewer_signoffs")
