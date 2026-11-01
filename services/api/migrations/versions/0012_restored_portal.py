"""Preserve the earlier portal's reference numbers and institution context."""

from alembic import op
import sqlalchemy as sa

revision = "0012_restored_portal"
down_revision = "0011_portal_content"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "portal_case_records",
        sa.Column("id", sa.String(64), sa.ForeignKey("applications.id"), primary_key=True),
        sa.Column("reference", sa.String(100), nullable=False, unique=True),
        sa.Column("payload", sa.JSON(), nullable=False),
    )
    op.create_table(
        "portal_institution_profiles",
        sa.Column("id", sa.String(64), sa.ForeignKey("institutions.id"), primary_key=True),
        sa.Column("payload", sa.JSON(), nullable=False),
    )


def downgrade():
    op.drop_table("portal_case_records")
    op.drop_table("portal_institution_profiles")
