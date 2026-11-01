"""Append-only machine evidence and stable processing-job identity."""

from alembic import op

revision = "0005_evidence_guards"
down_revision = "0004_document_processing"
branch_labels = depends_on = None


def upgrade():
    pg = op.get_bind().dialect.name == "postgresql"
    for table in ["evidence_nodes", "evidence_edges", "findings"]:
        if pg:
            op.execute(
                f"CREATE TRIGGER immutable_machine_evidence BEFORE UPDATE OR DELETE ON {table} FOR EACH ROW EXECUTE FUNCTION deny_immutable()"
            )
        else:
            for action in ["UPDATE", "DELETE"]:
                op.execute(
                    f"CREATE TRIGGER {table}_machine_{action.lower()} BEFORE {action} ON {table} BEGIN SELECT RAISE(ABORT,'Immutable machine evidence'); END"
                )
    if pg:
        op.execute("""CREATE FUNCTION processing_identity_guard() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          IF NEW.version_id <> OLD.version_id OR NEW.attempt <> OLD.attempt OR NEW.processor_version <> OLD.processor_version
          THEN RAISE EXCEPTION 'Immutable job identity'; END IF;
          RETURN NEW;
        END; $$""")
        op.execute(
            "CREATE TRIGGER immutable_job_identity BEFORE UPDATE ON processing_jobs FOR EACH ROW EXECUTE FUNCTION processing_identity_guard()"
        )
    else:
        op.execute(
            "CREATE TRIGGER immutable_job_identity BEFORE UPDATE ON processing_jobs WHEN NEW.version_id<>OLD.version_id OR NEW.attempt<>OLD.attempt OR NEW.processor_version<>OLD.processor_version BEGIN SELECT RAISE(ABORT,'Immutable job identity'); END"
        )


def downgrade():
    pg = op.get_bind().dialect.name == "postgresql"
    for table in ["evidence_nodes", "evidence_edges", "findings"]:
        if pg:
            op.execute(f"DROP TRIGGER immutable_machine_evidence ON {table}")
        else:
            for action in ["update", "delete"]:
                op.execute(f"DROP TRIGGER {table}_machine_{action}")
    if pg:
        op.execute("DROP TRIGGER immutable_job_identity ON processing_jobs")
        op.execute("DROP FUNCTION processing_identity_guard()")
    else:
        op.execute("DROP TRIGGER immutable_job_identity")
