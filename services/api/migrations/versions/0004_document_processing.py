"""Observable jobs, immutable extraction and saved prechecks."""

from alembic import op
import sqlalchemy as sa

revision = "0004_document_processing"
down_revision = "0003_institution_journey"
branch_labels = depends_on = None


def entity():
    return [
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("created_at", sa.Integer(), nullable=False),
    ]


def upgrade():
    op.create_table(
        "upload_attempts",
        *entity(),
        sa.Column("application_id", sa.String(64), sa.ForeignKey("applications.id"), nullable=False),
        sa.Column("actor_id", sa.String(64), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("state", sa.String(32), nullable=False),
        sa.Column("bytes_received", sa.Integer(), nullable=False),
        sa.Column("version_id", sa.String(64), sa.ForeignKey("document_versions.id")),
    )
    op.create_table(
        "processing_jobs",
        *entity(),
        sa.Column("version_id", sa.String(64), sa.ForeignKey("document_versions.id"), nullable=False),
        sa.Column("attempt", sa.Integer(), nullable=False),
        sa.Column("state", sa.String(40), nullable=False),
        sa.Column("code", sa.String(64), nullable=False),
        sa.Column("lease_until", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.Integer(), nullable=False),
        sa.Column("scanner_mode", sa.String(32), nullable=False),
        sa.Column("scan_status", sa.String(32), nullable=False),
        sa.Column("processor_version", sa.String(100), nullable=False),
        sa.UniqueConstraint("version_id", "attempt"),
        sa.CheckConstraint("attempt BETWEEN 1 AND 3"),
    )
    op.create_table(
        "processing_events",
        *entity(),
        sa.Column("job_id", sa.String(64), sa.ForeignKey("processing_jobs.id"), nullable=False),
        sa.Column("state", sa.String(40), nullable=False),
        sa.Column("code", sa.String(64), nullable=False),
    )
    op.create_table(
        "processing_results",
        *entity(),
        sa.Column("job_id", sa.String(64), sa.ForeignKey("processing_jobs.id"), nullable=False, unique=True),
        sa.Column("payload", sa.JSON(), nullable=False),
    )
    op.create_table(
        "processing_result_fields",
        sa.Column("result_id", sa.String(64), sa.ForeignKey("processing_results.id"), primary_key=True),
        sa.Column("field_id", sa.String(64), sa.ForeignKey("extracted_fields.id"), primary_key=True),
    )
    op.create_table(
        "precheck_snapshots",
        *entity(),
        sa.Column("revision_id", sa.String(64), sa.ForeignKey("application_revisions.id"), nullable=False),
        sa.Column("evaluation_id", sa.String(64), sa.ForeignKey("evaluations.id"), nullable=False),
        sa.Column("application_version", sa.Integer(), nullable=False),
        sa.Column("input_hash", sa.String(64), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
    )
    for table in [
        "processing_events",
        "processing_results",
        "processing_result_fields",
        "extracted_fields",
        "precheck_snapshots",
    ]:
        if op.get_bind().dialect.name == "postgresql":
            op.execute(
                f"CREATE TRIGGER immutable_processing BEFORE UPDATE OR DELETE ON {table} FOR EACH ROW EXECUTE FUNCTION deny_immutable()"
            )
        else:
            for action in ["UPDATE", "DELETE"]:
                op.execute(
                    f"CREATE TRIGGER {table}_immutable_{action.lower()} BEFORE {action} ON {table} BEGIN SELECT RAISE(ABORT, 'Immutable processing evidence'); END"
                )


def downgrade():
    op.drop_table("upload_attempts")
    if op.get_bind().dialect.name == "postgresql":
        op.execute("DROP TRIGGER immutable_processing ON extracted_fields")
    else:
        for action in ["update", "delete"]:
            op.execute(f"DROP TRIGGER extracted_fields_immutable_{action}")
    for table in [
        "precheck_snapshots",
        "processing_result_fields",
        "processing_results",
        "processing_events",
        "processing_jobs",
    ]:
        op.drop_table(table)
