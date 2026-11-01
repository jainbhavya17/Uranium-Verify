"""Canonical foundation and database-enforced immutable evidence/audit boundaries.

The accompanying schema_v1 snapshot keeps this migration independent of future model edits.
"""

from alembic import op
from sqlalchemy import MetaData

from uranium.schema_v1 import Base

revision = "0001_foundation"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    Base.metadata.create_all(bind)
    always = ["audit_events", "document_versions", "report_snapshots", "officer_actions"]
    conditional = [("historical_approval_snapshots", "published"), ("application_revisions", "frozen")]
    children = ["application_claims", "course_intake_records", "infrastructure_room_records"]
    if bind.dialect.name == "postgresql":
        op.execute("""CREATE FUNCTION deny_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN RAISE EXCEPTION 'Immutable record'; END; $$""")
        for table in always:
            op.execute(
                f"CREATE TRIGGER immutable BEFORE UPDATE OR DELETE ON {table} "
                "FOR EACH ROW EXECUTE FUNCTION deny_immutable()"
            )
        for table, flag in conditional:
            op.execute(
                f"CREATE TRIGGER immutable BEFORE UPDATE OR DELETE ON {table} "
                f"FOR EACH ROW WHEN (OLD.{flag}) EXECUTE FUNCTION deny_immutable()"
            )
        op.execute("""CREATE FUNCTION deny_frozen_child() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          IF TG_OP <> 'INSERT' THEN
            IF EXISTS (SELECT 1 FROM application_revisions WHERE id=OLD.revision_id AND frozen)
            THEN RAISE EXCEPTION 'Frozen revision child'; END IF;
          END IF;
          IF TG_OP <> 'DELETE' THEN
            IF EXISTS (SELECT 1 FROM application_revisions WHERE id=NEW.revision_id AND frozen)
            THEN RAISE EXCEPTION 'Frozen revision child'; END IF;
            RETURN NEW;
          END IF;
          RETURN OLD;
        END; $$""")
        for table in children:
            op.execute(
                f"CREATE TRIGGER immutable BEFORE INSERT OR UPDATE OR DELETE ON {table} "
                "FOR EACH ROW EXECUTE FUNCTION deny_frozen_child()"
            )
    elif bind.dialect.name == "sqlite":
        for table in always:
            for action in ["UPDATE", "DELETE"]:
                op.execute(
                    f"CREATE TRIGGER {table}_{action.lower()} BEFORE {action} ON {table} "
                    "BEGIN SELECT RAISE(ABORT, 'Immutable record'); END"
                )
        for table, flag in conditional:
            for action in ["UPDATE", "DELETE"]:
                op.execute(
                    f"CREATE TRIGGER {table}_{action.lower()} BEFORE {action} ON {table} "
                    f"WHEN OLD.{flag}=1 BEGIN SELECT RAISE(ABORT, 'Immutable record'); END"
                )
        for table in children:
            for action in ["INSERT", "UPDATE", "DELETE"]:
                references = (
                    ["NEW"] if action == "INSERT" else ["OLD"] if action == "DELETE" else ["OLD", "NEW"]
                )
                predicate = " OR ".join(
                    f"EXISTS (SELECT 1 FROM application_revisions WHERE id={r}.revision_id AND frozen=1)"
                    for r in references
                )
                op.execute(
                    f"CREATE TRIGGER {table}_{action.lower()} BEFORE {action} ON {table} "
                    f"WHEN {predicate} BEGIN SELECT RAISE(ABORT, 'Frozen revision child'); END"
                )


def downgrade():
    bind = op.get_bind()
    metadata = MetaData()
    metadata.reflect(bind, only=list(Base.metadata.tables))
    metadata.drop_all(bind)
    if bind.dialect.name == "postgresql":
        op.execute("DROP FUNCTION IF EXISTS deny_frozen_child()")
        op.execute("DROP FUNCTION IF EXISTS deny_immutable()")
