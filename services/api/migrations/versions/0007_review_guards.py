"""Canonical rule links and append-only scrutiny evidence."""

from alembic import op
import sqlalchemy as sa

revision = "0007_review_guards"
down_revision = "0006_officer_scrutiny"
branch_labels = depends_on = None
IMMUTABLE = [
    "extraction_corrections",
    "review_action_context",
    "specialist_responses",
    "knowledge_passages",
    "certified_room_evidence",
    "rule_runs",
    "provenance_results",
    "verification_attempts",
    "governed_rule_links",
]


def upgrade():
    op.create_table(
        "governed_rule_links",
        sa.Column("id", sa.String(64), sa.ForeignKey("governed_versions.id"), primary_key=True),
        sa.Column(
            "rule_id", sa.String(64), sa.ForeignKey("compliance_rules.id"), nullable=False, unique=True
        ),
    )
    pg = op.get_bind().dialect.name == "postgresql"
    for table in IMMUTABLE:
        if pg:
            op.execute(
                f"CREATE TRIGGER scrutiny_immutable BEFORE UPDATE OR DELETE ON {table} FOR EACH ROW EXECUTE FUNCTION deny_immutable()"
            )
        else:
            for event in ["UPDATE", "DELETE"]:
                op.execute(
                    f"CREATE TRIGGER {table}_scrutiny_{event.lower()} BEFORE {event} ON {table} BEGIN SELECT RAISE(ABORT,'Immutable scrutiny evidence'); END"
                )
    if pg:
        op.execute("""CREATE FUNCTION governed_version_guard() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
        IF TG_OP='DELETE' THEN RAISE EXCEPTION 'Governed versions cannot be deleted'; END IF;
        IF NEW.payload::jsonb IS DISTINCT FROM OLD.payload::jsonb OR NEW.author_id<>OLD.author_id OR NEW.kind<>OLD.kind OR NEW.code<>OLD.code OR NEW.number<>OLD.number OR NEW.source_id IS DISTINCT FROM OLD.source_id
        THEN RAISE EXCEPTION 'Create a new governed version'; END IF;
        IF OLD.approver_id IS NOT NULL AND NEW.approver_id IS DISTINCT FROM OLD.approver_id THEN RAISE EXCEPTION 'Immutable approval attribution'; END IF;
        IF NOT ((OLD.status='DRAFT' AND NEW.status='APPROVED' AND NEW.approver_id IS NOT NULL) OR (OLD.status='APPROVED' AND NEW.status IN ('PUBLISHED','SUPERSEDED')) OR (OLD.status='PUBLISHED' AND NEW.status='SUPERSEDED'))
        THEN RAISE EXCEPTION 'Invalid governed transition'; END IF; RETURN NEW; END; $$""")
        op.execute(
            "CREATE TRIGGER governed_guard BEFORE UPDATE OR DELETE ON governed_versions FOR EACH ROW EXECUTE FUNCTION governed_version_guard()"
        )
    else:
        op.execute(
            "CREATE TRIGGER governed_delete BEFORE DELETE ON governed_versions BEGIN SELECT RAISE(ABORT,'Governed versions cannot be deleted'); END"
        )
        op.execute("""CREATE TRIGGER governed_update BEFORE UPDATE ON governed_versions WHEN
            NEW.payload<>OLD.payload OR NEW.author_id<>OLD.author_id OR NEW.kind<>OLD.kind OR NEW.code<>OLD.code OR NEW.number<>OLD.number OR NEW.source_id IS NOT OLD.source_id
            OR (OLD.approver_id IS NOT NULL AND NEW.approver_id IS NOT OLD.approver_id)
            OR NOT ((OLD.status='DRAFT' AND NEW.status='APPROVED' AND NEW.approver_id IS NOT NULL) OR (OLD.status='APPROVED' AND NEW.status IN ('PUBLISHED','SUPERSEDED')) OR (OLD.status='PUBLISHED' AND NEW.status='SUPERSEDED'))
            BEGIN SELECT RAISE(ABORT,'Immutable version or invalid governed transition'); END""")


def downgrade():
    pg = op.get_bind().dialect.name == "postgresql"
    if pg:
        op.execute("DROP TRIGGER governed_guard ON governed_versions")
        op.execute("DROP FUNCTION governed_version_guard()")
    else:
        op.execute("DROP TRIGGER governed_delete")
        op.execute("DROP TRIGGER governed_update")
    for table in IMMUTABLE:
        if pg:
            op.execute(f"DROP TRIGGER scrutiny_immutable ON {table}")
        else:
            for event in ["update", "delete"]:
                op.execute(f"DROP TRIGGER {table}_scrutiny_{event}")
    op.drop_table("governed_rule_links")
