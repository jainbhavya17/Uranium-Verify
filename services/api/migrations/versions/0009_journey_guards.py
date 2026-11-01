"""Response ownership, immutable communications and captured report inputs."""

from alembic import op
import sqlalchemy as sa

revision = "0009_journey_guards"
down_revision = "0008_complete_journey"
branch_labels = depends_on = None
TABLES = [
    "clarification_scopes",
    "clarification_response_lineage",
    "clarification_responses",
    "clarification_resolutions",
    "clarification_requests",
]


def upgrade():
    with op.batch_alter_table("clarification_resolutions") as batch:
        batch.alter_column("response_id", existing_type=sa.String(64), nullable=True)
    with op.batch_alter_table("clarification_responses") as batch:
        batch.create_unique_constraint("uq_clarification_single_response", ["request_id"])
    pg = op.get_bind().dialect.name == "postgresql"
    for table in TABLES:
        if pg:
            op.execute(
                f"CREATE TRIGGER journey_immutable BEFORE UPDATE OR DELETE ON {table} FOR EACH ROW EXECUTE FUNCTION deny_immutable()"
            )
        else:
            for event in ["UPDATE", "DELETE"]:
                op.execute(
                    f"CREATE TRIGGER {table}_journey_{event.lower()} BEFORE {event} ON {table} BEGIN SELECT RAISE(ABORT,'Immutable clarification evidence'); END"
                )
    if pg:
        op.execute("""CREATE FUNCTION report_input_guard() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
            IF TG_OP='DELETE' THEN RAISE EXCEPTION 'Immutable captured report'; END IF;
            IF NEW.manifest::jsonb IS DISTINCT FROM OLD.manifest::jsonb OR NEW.input_version<>OLD.input_version OR NEW.id<>OLD.id THEN RAISE EXCEPTION 'Immutable report inputs'; END IF; RETURN NEW; END; $$""")
        op.execute(
            "CREATE TRIGGER report_job_input_guard BEFORE UPDATE OR DELETE ON report_jobs FOR EACH ROW EXECUTE FUNCTION report_input_guard()"
        )
    else:
        op.execute(
            "CREATE TRIGGER report_job_input_update BEFORE UPDATE ON report_jobs WHEN NEW.manifest<>OLD.manifest OR NEW.input_version<>OLD.input_version OR NEW.id<>OLD.id BEGIN SELECT RAISE(ABORT,'Immutable report inputs'); END"
        )
        op.execute(
            "CREATE TRIGGER report_job_input_delete BEFORE DELETE ON report_jobs BEGIN SELECT RAISE(ABORT,'Immutable report inputs'); END"
        )


def downgrade():
    pg = op.get_bind().dialect.name == "postgresql"
    if pg:
        op.execute("DROP TRIGGER report_job_input_guard ON report_jobs")
        op.execute("DROP FUNCTION report_input_guard()")
    else:
        op.execute("DROP TRIGGER report_job_input_update")
        op.execute("DROP TRIGGER report_job_input_delete")
    for table in TABLES:
        if pg:
            op.execute(f"DROP TRIGGER journey_immutable ON {table}")
        else:
            for event in ["update", "delete"]:
                op.execute(f"DROP TRIGGER {table}_journey_{event}")
    with op.batch_alter_table("clarification_responses") as batch:
        batch.drop_constraint("uq_clarification_single_response", type_="unique")
    with op.batch_alter_table("clarification_resolutions") as batch:
        batch.alter_column("response_id", existing_type=sa.String(64), nullable=False)
