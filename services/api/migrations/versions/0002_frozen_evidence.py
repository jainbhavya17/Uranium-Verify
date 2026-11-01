"""Prevent original evidence from being appended to an already frozen revision."""

from alembic import op

revision = "0002_frozen_evidence"
down_revision = "0001_foundation"
branch_labels = None
depends_on = None


def upgrade():
    if op.get_bind().dialect.name == "postgresql":
        op.execute("""CREATE FUNCTION deny_frozen_evidence() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          IF EXISTS (SELECT 1 FROM application_revisions WHERE id=NEW.revision_id AND frozen)
          THEN RAISE EXCEPTION 'Frozen revision evidence'; END IF;
          RETURN NEW;
        END; $$""")
        op.execute(
            "CREATE TRIGGER frozen_evidence BEFORE INSERT ON document_versions "
            "FOR EACH ROW EXECUTE FUNCTION deny_frozen_evidence()"
        )
    else:
        op.execute(
            "CREATE TRIGGER frozen_evidence BEFORE INSERT ON document_versions "
            "WHEN EXISTS (SELECT 1 FROM application_revisions WHERE id=NEW.revision_id AND frozen=1) "
            "BEGIN SELECT RAISE(ABORT, 'Frozen revision evidence'); END"
        )


def downgrade():
    if op.get_bind().dialect.name == "postgresql":
        op.execute("DROP TRIGGER frozen_evidence ON document_versions")
        op.execute("DROP FUNCTION deny_frozen_evidence()")
    else:
        op.execute("DROP TRIGGER frozen_evidence")
