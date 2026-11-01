"""Persistent public notices, separate from confidential case evidence."""

from alembic import op
import sqlalchemy as sa

revision = "0011_portal_content"
down_revision = "0010_report_publication"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "portal_content",
        sa.Column("id", sa.String(40), primary_key=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
    )


def downgrade():
    op.drop_table("portal_content")
