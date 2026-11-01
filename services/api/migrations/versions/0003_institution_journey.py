"""Persistent catalogue, draft concurrency, checklist snapshots and submission receipts."""

from alembic import op
import sqlalchemy as sa

revision = "0003_institution_journey"
down_revision = "0002_frozen_evidence"
branch_labels = None
depends_on = None


def entity():
    return [
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("created_at", sa.Integer(), nullable=False),
    ]


def upgrade():
    op.create_table(
        "application_catalogue",
        *entity(),
        sa.Column("code", sa.String(64), nullable=False),
        sa.Column("academic_year", sa.String(16), nullable=False),
        sa.Column("display_name", sa.String(160), nullable=False),
        sa.Column("availability", sa.String(16), nullable=False),
        sa.Column("ruleset_id", sa.String(64), sa.ForeignKey("rule_sets.id"), nullable=False),
        sa.Column("definition", sa.JSON(), nullable=False),
        sa.UniqueConstraint("code", "academic_year"),
        sa.CheckConstraint("availability IN ('enabled','preview','external')"),
    )
    op.create_table(
        "application_drafts",
        sa.Column("id", sa.String(64), sa.ForeignKey("applications.id"), primary_key=True),
        sa.Column("revision_id", sa.String(64), nullable=False),
        sa.Column("catalogue_id", sa.String(64), sa.ForeignKey("application_catalogue.id"), nullable=False),
        sa.Column(
            "baseline_snapshot_id",
            sa.String(64),
            sa.ForeignKey("historical_approval_snapshots.id"),
            nullable=False,
        ),
        sa.Column("draft_key", sa.String(200), unique=True),
        sa.Column("lock_version", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.Integer(), nullable=False),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(
            ["revision_id", "id"], ["application_revisions.id", "application_revisions.application_id"]
        ),
        sa.CheckConstraint("lock_version > 0"),
    )
    op.create_table(
        "requirement_snapshots",
        sa.Column("id", sa.String(64), sa.ForeignKey("application_requirements.id"), primary_key=True),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("computed_version", sa.Integer(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("selected_version_id", sa.String(64), sa.ForeignKey("document_versions.id")),
    )
    op.create_table(
        "reviewed_exceptions",
        *entity(),
        sa.Column("institution_id", sa.String(64), sa.ForeignKey("institutions.id"), nullable=False),
        sa.Column("academic_year", sa.String(16), nullable=False),
        sa.Column("code", sa.String(64), nullable=False),
        sa.Column("approved_by", sa.String(64), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("source_ref", sa.String(300), nullable=False),
        sa.Column("is_mock", sa.Boolean(), nullable=False),
        sa.UniqueConstraint("institution_id", "academic_year", "code"),
    )
    op.create_table(
        "institution_routing",
        sa.Column("id", sa.String(64), sa.ForeignKey("institutions.id"), primary_key=True),
        sa.Column("officer_id", sa.String(64), sa.ForeignKey("users.id"), nullable=False),
    )
    op.create_table(
        "mutation_receipts",
        *entity(),
        sa.Column("actor_id", sa.String(64), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("operation", sa.String(100), nullable=False),
        sa.Column("request_key", sa.String(100), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("complete", sa.Boolean(), nullable=False),
        sa.Column("result", sa.JSON(), nullable=False),
        sa.UniqueConstraint("actor_id", "operation", "request_key"),
    )
    op.create_table(
        "submission_receipts",
        *entity(),
        sa.Column(
            "application_id", sa.String(64), sa.ForeignKey("applications.id"), nullable=False, unique=True
        ),
        sa.Column("revision_id", sa.String(64), nullable=False),
        sa.Column("actor_id", sa.String(64), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(
            ["revision_id", "application_id"],
            ["application_revisions.id", "application_revisions.application_id"],
        ),
    )
    op.create_table(
        "application_timeline",
        *entity(),
        sa.Column("application_id", sa.String(64), sa.ForeignKey("applications.id"), nullable=False),
        sa.Column("actor_id", sa.String(64), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("event_key", sa.String(200), nullable=False, unique=True),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("summary", sa.String(300), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
    )
    pg = op.get_bind().dialect.name == "postgresql"
    for table in [
        "submission_receipts",
        "application_timeline",
        "reviewed_exceptions",
        "application_catalogue",
    ]:
        if pg:
            op.execute(
                f"CREATE TRIGGER immutable BEFORE UPDATE OR DELETE ON {table} "
                "FOR EACH ROW EXECUTE FUNCTION deny_immutable()"
            )
        else:
            for action in ["UPDATE", "DELETE"]:
                op.execute(
                    f"CREATE TRIGGER {table}_{action.lower()} BEFORE {action} ON {table} "
                    "BEGIN SELECT RAISE(ABORT, 'Immutable record'); END"
                )
    if pg:
        op.execute(
            "CREATE TRIGGER frozen_requirements BEFORE INSERT OR UPDATE OR DELETE ON application_requirements "
            "FOR EACH ROW EXECUTE FUNCTION deny_frozen_child()"
        )
        op.execute("""CREATE FUNCTION phase2_draft_guard() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          IF TG_OP <> 'INSERT' AND EXISTS (SELECT 1 FROM application_revisions WHERE id=OLD.revision_id AND frozen)
          THEN RAISE EXCEPTION 'Frozen draft metadata'; END IF;
          IF TG_OP <> 'DELETE' THEN
            IF EXISTS (SELECT 1 FROM application_revisions WHERE id=NEW.revision_id AND frozen)
            THEN RAISE EXCEPTION 'Frozen draft metadata'; END IF;
            RETURN NEW;
          END IF;
          RETURN OLD;
        END; $$""")
        op.execute(
            "CREATE TRIGGER immutable BEFORE INSERT OR UPDATE OR DELETE ON application_drafts "
            "FOR EACH ROW EXECUTE FUNCTION phase2_draft_guard()"
        )
        op.execute("""CREATE FUNCTION phase2_snapshot_guard() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          IF TG_OP <> 'INSERT' AND EXISTS (SELECT 1 FROM application_requirements q JOIN application_revisions r
            ON q.revision_id=r.id WHERE q.id=OLD.id AND r.frozen) THEN RAISE EXCEPTION 'Frozen checklist'; END IF;
          IF TG_OP <> 'DELETE' THEN
            IF EXISTS (SELECT 1 FROM application_requirements q JOIN application_revisions r
              ON q.revision_id=r.id WHERE q.id=NEW.id AND r.frozen) THEN RAISE EXCEPTION 'Frozen checklist'; END IF;
            RETURN NEW;
          END IF;
          RETURN OLD;
        END; $$""")
        op.execute(
            "CREATE TRIGGER immutable BEFORE INSERT OR UPDATE OR DELETE ON requirement_snapshots "
            "FOR EACH ROW EXECUTE FUNCTION phase2_snapshot_guard()"
        )
        op.execute(
            "CREATE TRIGGER completed_receipt BEFORE UPDATE OR DELETE ON mutation_receipts "
            "FOR EACH ROW WHEN (OLD.complete) EXECUTE FUNCTION deny_immutable()"
        )
        op.execute(
            "CREATE TRIGGER locked_ruleset BEFORE UPDATE OR DELETE ON rule_sets FOR EACH ROW "
            "WHEN (OLD.status IN ('DEMO_REVIEWED','PUBLISHED')) EXECUTE FUNCTION deny_immutable()"
        )
        op.execute("""CREATE FUNCTION phase2_template_guard() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          IF TG_OP <> 'INSERT' AND EXISTS (SELECT 1 FROM rule_sets WHERE id=OLD.ruleset_id
            AND status IN ('DEMO_REVIEWED','PUBLISHED')) THEN RAISE EXCEPTION 'Locked requirement template'; END IF;
          IF TG_OP <> 'DELETE' THEN
            IF EXISTS (SELECT 1 FROM rule_sets WHERE id=NEW.ruleset_id AND status IN ('DEMO_REVIEWED','PUBLISHED'))
            THEN RAISE EXCEPTION 'Locked requirement template'; END IF;
            RETURN NEW;
          END IF;
          RETURN OLD;
        END; $$""")
        op.execute(
            "CREATE TRIGGER immutable BEFORE INSERT OR UPDATE OR DELETE ON requirement_templates "
            "FOR EACH ROW EXECUTE FUNCTION phase2_template_guard()"
        )
        op.execute("""CREATE FUNCTION phase2_document_guard() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          IF EXISTS (SELECT 1 FROM document_versions WHERE document_id=OLD.id)
          THEN RAISE EXCEPTION 'Versioned document identity is immutable'; END IF;
          IF TG_OP='DELETE' THEN RETURN OLD; END IF;
          RETURN NEW;
        END; $$""")
        op.execute(
            "CREATE TRIGGER immutable_identity BEFORE UPDATE OR DELETE ON documents "
            "FOR EACH ROW EXECUTE FUNCTION phase2_document_guard()"
        )
    else:
        for table, expression in [
            (
                "application_drafts",
                "EXISTS (SELECT 1 FROM application_revisions WHERE id={row}.revision_id AND frozen=1)",
            ),
            (
                "application_requirements",
                "EXISTS (SELECT 1 FROM application_revisions WHERE id={row}.revision_id AND frozen=1)",
            ),
            (
                "requirement_snapshots",
                "EXISTS (SELECT 1 FROM application_requirements q JOIN application_revisions r ON q.revision_id=r.id WHERE q.id={row}.id AND r.frozen=1)",
            ),
            (
                "requirement_templates",
                "EXISTS (SELECT 1 FROM rule_sets WHERE id={row}.ruleset_id AND status IN ('DEMO_REVIEWED','PUBLISHED'))",
            ),
        ]:
            for action in ["INSERT", "UPDATE", "DELETE"]:
                rows = ["NEW"] if action == "INSERT" else ["OLD"] if action == "DELETE" else ["OLD", "NEW"]
                predicate = " OR ".join(expression.format(row=row) for row in rows)
                op.execute(
                    f"CREATE TRIGGER {table}_guard_{action.lower()} BEFORE {action} ON {table} "
                    f"WHEN {predicate} BEGIN SELECT RAISE(ABORT, 'Frozen or locked record'); END"
                )
        for table, predicate in [
            ("mutation_receipts", "OLD.complete=1"),
            ("rule_sets", "OLD.status IN ('DEMO_REVIEWED','PUBLISHED')"),
        ]:
            for action in ["UPDATE", "DELETE"]:
                op.execute(
                    f"CREATE TRIGGER {table}_locked_{action.lower()} BEFORE {action} ON {table} "
                    f"WHEN {predicate} BEGIN SELECT RAISE(ABORT, 'Immutable record'); END"
                )
        for action in ["UPDATE", "DELETE"]:
            op.execute(
                f"CREATE TRIGGER document_identity_{action.lower()} BEFORE {action} ON documents "
                "WHEN EXISTS (SELECT 1 FROM document_versions WHERE document_id=OLD.id) "
                "BEGIN SELECT RAISE(ABORT, 'Versioned document identity is immutable'); END"
            )


def downgrade():
    pg = op.get_bind().dialect.name == "postgresql"
    if pg:
        op.execute("DROP TRIGGER frozen_requirements ON application_requirements")
        op.execute("DROP TRIGGER locked_ruleset ON rule_sets")
        op.execute("DROP TRIGGER immutable ON requirement_templates")
        op.execute("DROP TRIGGER immutable_identity ON documents")
    else:
        for table in ["application_requirements", "requirement_templates"]:
            for action in ["insert", "update", "delete"]:
                op.execute(f"DROP TRIGGER {table}_guard_{action}")
        for action in ["update", "delete"]:
            op.execute(f"DROP TRIGGER rule_sets_locked_{action}")
            op.execute(f"DROP TRIGGER document_identity_{action}")
    for table in [
        "application_timeline",
        "submission_receipts",
        "mutation_receipts",
        "institution_routing",
        "reviewed_exceptions",
        "requirement_snapshots",
        "application_drafts",
        "application_catalogue",
    ]:
        op.drop_table(table)
    if pg:
        for name in [
            "phase2_draft_guard",
            "phase2_snapshot_guard",
            "phase2_template_guard",
            "phase2_document_guard",
        ]:
            op.execute(f"DROP FUNCTION {name}()")
