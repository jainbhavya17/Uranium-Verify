"""Canonical entities. JSON stores bounded domain payloads; ownership/version links remain relational."""

import time
import uuid

from sqlalchemy import JSON, Boolean, CheckConstraint, Float, ForeignKey, ForeignKeyConstraint
from sqlalchemy import Integer, String, UniqueConstraint, event
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def new_id():
    return str(uuid.uuid4())


class Base(DeclarativeBase):
    pass


class Entity:
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=new_id)
    created_at: Mapped[int] = mapped_column(Integer, default=lambda: int(time.time()))


class User(Entity, Base):
    __tablename__ = "users"
    email: Mapped[str] = mapped_column(String(254), unique=True)
    name: Mapped[str] = mapped_column(String(160))
    password_hash: Mapped[str] = mapped_column(String(256))
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class Role(Base):
    __tablename__ = "roles"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    label: Mapped[str] = mapped_column(String(100))


class Institution(Entity, Base):
    __tablename__ = "institutions"
    permanent_id: Mapped[str] = mapped_column(String(64), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    is_mock: Mapped[bool] = mapped_column(Boolean, default=True)


class Membership(Entity, Base):
    __tablename__ = "memberships"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    role_id: Mapped[str] = mapped_column(ForeignKey("roles.id"))
    institution_id: Mapped[str | None] = mapped_column(ForeignKey("institutions.id"))
    valid_until: Mapped[int | None] = mapped_column(Integer)
    __table_args__ = (UniqueConstraint("user_id", "role_id", "institution_id"),)


class AuthSession(Entity, Base):
    __tablename__ = "auth_sessions"
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    csrf_hash: Mapped[str] = mapped_column(String(64))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    expires_at: Mapped[int] = mapped_column(Integer)
    revoked_at: Mapped[int | None] = mapped_column(Integer)


class ApprovalSnapshot(Entity, Base):
    __tablename__ = "historical_approval_snapshots"
    institution_id: Mapped[str] = mapped_column(ForeignKey("institutions.id"))
    academic_year: Mapped[str] = mapped_column(String(16))
    version: Mapped[int] = mapped_column(Integer, default=1)
    payload: Mapped[dict] = mapped_column(JSON)
    source_ref: Mapped[str] = mapped_column(String(200))
    published: Mapped[bool] = mapped_column(Boolean, default=False)
    is_mock: Mapped[bool] = mapped_column(Boolean, default=True)
    __table_args__ = (UniqueConstraint("institution_id", "academic_year", "version"),)


class Application(Entity, Base):
    __tablename__ = "applications"
    institution_id: Mapped[str] = mapped_column(ForeignKey("institutions.id"))
    category: Mapped[str] = mapped_column(String(64))
    academic_year: Mapped[str] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(String(40), default="DRAFT")
    is_mock: Mapped[bool] = mapped_column(Boolean, default=True)
    __table_args__ = (
        CheckConstraint(
            "status IN ('DRAFT','SUBMITTED','UNDER_REVIEW',"
            "'CLARIFICATION_REQUESTED','PENDING_VERIFICATION',"
            "'INSPECTION_RECOMMENDED','REVIEW_COMPLETED')"
        ),
    )


class RuleSet(Entity, Base):
    __tablename__ = "rule_sets"
    version: Mapped[str] = mapped_column(String(64), unique=True)
    status: Mapped[str] = mapped_column(String(32), default="DRAFT")
    source_ref: Mapped[str] = mapped_column(String(300))
    authored_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    approved_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    effective_from: Mapped[str | None] = mapped_column(String(16))


class Revision(Entity, Base):
    __tablename__ = "application_revisions"
    application_id: Mapped[str] = mapped_column(ForeignKey("applications.id"))
    number: Mapped[int] = mapped_column(Integer)
    actor_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    ruleset_id: Mapped[str | None] = mapped_column(ForeignKey("rule_sets.id"))
    frozen: Mapped[bool] = mapped_column(Boolean, default=False)
    submitted_at: Mapped[int | None] = mapped_column(Integer)
    manifest: Mapped[dict] = mapped_column(JSON, default=dict)
    __table_args__ = (UniqueConstraint("application_id", "number"), UniqueConstraint("id", "application_id"))


class Claim(Entity, Base):
    __tablename__ = "application_claims"
    revision_id: Mapped[str] = mapped_column(ForeignKey("application_revisions.id"))
    field_key: Mapped[str] = mapped_column(String(100))
    value: Mapped[dict] = mapped_column(JSON)
    __table_args__ = (UniqueConstraint("revision_id", "field_key"),)


class CourseIntake(Entity, Base):
    __tablename__ = "course_intake_records"
    revision_id: Mapped[str] = mapped_column(ForeignKey("application_revisions.id"))
    programme: Mapped[str] = mapped_column(String(100))
    course: Mapped[str] = mapped_column(String(100))
    approved_intake: Mapped[int] = mapped_column(Integer)
    requested_intake: Mapped[int] = mapped_column(Integer)
    __table_args__ = (CheckConstraint("approved_intake >= 0 AND requested_intake >= 0"),)


class RoomRecord(Entity, Base):
    __tablename__ = "infrastructure_room_records"
    revision_id: Mapped[str] = mapped_column(ForeignKey("application_revisions.id"))
    room_code: Mapped[str] = mapped_column(String(64))
    room_type: Mapped[str] = mapped_column(String(64))
    declared_area: Mapped[float] = mapped_column(Float)
    __table_args__ = (UniqueConstraint("revision_id", "room_code"), CheckConstraint("declared_area >= 0"))


class RequirementTemplate(Entity, Base):
    __tablename__ = "requirement_templates"
    ruleset_id: Mapped[str] = mapped_column(ForeignKey("rule_sets.id"))
    code: Mapped[str] = mapped_column(String(64))
    category: Mapped[str] = mapped_column(String(64))
    stage_due: Mapped[str] = mapped_column(String(64))
    predicate: Mapped[dict] = mapped_column(JSON)
    field_schema: Mapped[dict] = mapped_column(JSON, default=dict)
    __table_args__ = (UniqueConstraint("ruleset_id", "code"),)


class ApplicationRequirement(Entity, Base):
    __tablename__ = "application_requirements"
    revision_id: Mapped[str] = mapped_column(ForeignKey("application_revisions.id"))
    template_id: Mapped[str] = mapped_column(ForeignKey("requirement_templates.id"))
    applicability: Mapped[str] = mapped_column(String(32))
    __table_args__ = (UniqueConstraint("revision_id", "template_id"),)


class Document(Entity, Base):
    __tablename__ = "documents"
    application_id: Mapped[str] = mapped_column(ForeignKey("applications.id"))
    document_type: Mapped[str] = mapped_column(String(64))
    requirement_id: Mapped[str | None] = mapped_column(ForeignKey("application_requirements.id"))
    __table_args__ = (UniqueConstraint("id", "application_id"),)


class DocumentVersion(Entity, Base):
    __tablename__ = "document_versions"
    document_id: Mapped[str] = mapped_column(String(64))
    application_id: Mapped[str] = mapped_column(String(64))
    revision_id: Mapped[str] = mapped_column(String(64))
    number: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64))
    storage_key: Mapped[str] = mapped_column(String(128), unique=True)
    original_name: Mapped[str] = mapped_column(String(200))
    media_type: Mapped[str] = mapped_column(String(100))
    uploader_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    status: Mapped[str] = mapped_column(String(40), default="UPLOADED")
    is_mock: Mapped[bool] = mapped_column(Boolean, default=True)
    __table_args__ = (
        ForeignKeyConstraint(["document_id", "application_id"], ["documents.id", "documents.application_id"]),
        ForeignKeyConstraint(
            ["revision_id", "application_id"],
            ["application_revisions.id", "application_revisions.application_id"],
        ),
        UniqueConstraint("document_id", "number"),
        CheckConstraint("number > 0"),
    )


class ExtractedField(Entity, Base):
    __tablename__ = "extracted_fields"
    version_id: Mapped[str] = mapped_column(ForeignKey("document_versions.id"))
    page: Mapped[int] = mapped_column(Integer)
    field_key: Mapped[str] = mapped_column(String(100))
    value: Mapped[dict] = mapped_column(JSON)
    bounding_box: Mapped[list] = mapped_column(JSON)
    confidence: Mapped[float | None] = mapped_column(Float)
    processor_version: Mapped[str] = mapped_column(String(100))
    __table_args__ = (
        CheckConstraint("page > 0"),
        CheckConstraint("confidence IS NULL OR (confidence >= 0 AND confidence <= 1)"),
    )


class ComplianceRule(Entity, Base):
    __tablename__ = "compliance_rules"
    ruleset_id: Mapped[str] = mapped_column(ForeignKey("rule_sets.id"))
    code: Mapped[str] = mapped_column(String(64))
    clause: Mapped[str] = mapped_column(String(100))
    definition: Mapped[dict] = mapped_column(JSON)
    __table_args__ = (UniqueConstraint("ruleset_id", "code"),)


class Evaluation(Entity, Base):
    __tablename__ = "evaluations"
    revision_id: Mapped[str] = mapped_column(ForeignKey("application_revisions.id"))
    ruleset_id: Mapped[str] = mapped_column(ForeignKey("rule_sets.id"))
    state: Mapped[str] = mapped_column(String(32), default="QUEUED")


class EvidenceNode(Entity, Base):
    __tablename__ = "evidence_nodes"
    revision_id: Mapped[str] = mapped_column(ForeignKey("application_revisions.id"))
    kind: Mapped[str] = mapped_column(String(64))
    reference: Mapped[dict] = mapped_column(JSON)
    __table_args__ = (UniqueConstraint("id", "revision_id"),)


class EvidenceEdge(Entity, Base):
    __tablename__ = "evidence_edges"
    revision_id: Mapped[str] = mapped_column(ForeignKey("application_revisions.id"))
    from_node: Mapped[str] = mapped_column(String(64))
    to_node: Mapped[str] = mapped_column(String(64))
    relationship: Mapped[str] = mapped_column(String(32))
    __table_args__ = (
        ForeignKeyConstraint(
            ["from_node", "revision_id"], ["evidence_nodes.id", "evidence_nodes.revision_id"]
        ),
        ForeignKeyConstraint(["to_node", "revision_id"], ["evidence_nodes.id", "evidence_nodes.revision_id"]),
        UniqueConstraint("from_node", "to_node", "relationship"),
        CheckConstraint("relationship IN ('SUPPORTS','CONTRADICTS','SUPERSEDES','DECLARES','VERIFIED_BY')"),
    )


class Finding(Entity, Base):
    __tablename__ = "findings"
    evaluation_id: Mapped[str] = mapped_column(ForeignKey("evaluations.id"))
    evidence_node_id: Mapped[str | None] = mapped_column(ForeignKey("evidence_nodes.id"))
    evidence_gap: Mapped[str | None] = mapped_column(String(500))
    rule_id: Mapped[str | None] = mapped_column(ForeignKey("compliance_rules.id"))
    method: Mapped[str] = mapped_column(String(100))
    visibility: Mapped[str] = mapped_column(String(32))
    severity: Mapped[str] = mapped_column(String(32))
    human_review_required: Mapped[bool] = mapped_column(Boolean, default=True)
    payload: Mapped[dict] = mapped_column(JSON)
    __table_args__ = (CheckConstraint("evidence_node_id IS NOT NULL OR evidence_gap IS NOT NULL"),)


class Connector(Entity, Base):
    __tablename__ = "issuer_connectors"
    name: Mapped[str] = mapped_column(String(100), unique=True)
    mode: Mapped[str] = mapped_column(String(16), default="MOCK")
    status: Mapped[str] = mapped_column(String(32), default="NOT_CONFIGURED")
    secret_reference: Mapped[str | None] = mapped_column(String(200))
    __table_args__ = (CheckConstraint("mode IN ('MOCK','LIVE')"),)


class VerificationAttempt(Entity, Base):
    __tablename__ = "verification_attempts"
    application_id: Mapped[str] = mapped_column(ForeignKey("applications.id"))
    version_id: Mapped[str] = mapped_column(ForeignKey("document_versions.id"))
    connector_id: Mapped[str] = mapped_column(ForeignKey("issuer_connectors.id"))
    status: Mapped[str] = mapped_column(String(32))
    mode: Mapped[str] = mapped_column(String(16))
    source_response: Mapped[dict] = mapped_column(JSON)


class Assignment(Entity, Base):
    __tablename__ = "review_assignments"
    application_id: Mapped[str] = mapped_column(ForeignKey("applications.id"))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    scope: Mapped[str] = mapped_column(String(32))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    __table_args__ = (
        UniqueConstraint("application_id", "user_id", "scope"),
        CheckConstraint("scope IN ('REVIEW','VERIFY','SUPERVISE')"),
    )


class ContentGrant(Entity, Base):
    __tablename__ = "content_grants"
    application_id: Mapped[str] = mapped_column(ForeignKey("applications.id"))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    granted_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    expires_at: Mapped[int] = mapped_column(Integer)
    __table_args__ = (UniqueConstraint("application_id", "user_id"),)


class OfficerAction(Entity, Base):
    __tablename__ = "officer_actions"
    revision_id: Mapped[str] = mapped_column(ForeignKey("application_revisions.id"))
    actor_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(String(64))
    rationale: Mapped[str] = mapped_column(String(2000))
    publishable: Mapped[bool] = mapped_column(Boolean, default=False)


class Clarification(Entity, Base):
    __tablename__ = "clarification_requests"
    application_id: Mapped[str] = mapped_column(ForeignKey("applications.id"))
    actor_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    message: Mapped[str] = mapped_column(String(2000))
    published: Mapped[bool] = mapped_column(Boolean, default=False)
    allowed_until: Mapped[int] = mapped_column(Integer)


class ClarificationResponse(Entity, Base):
    __tablename__ = "clarification_responses"
    request_id: Mapped[str] = mapped_column(ForeignKey("clarification_requests.id"))
    revision_id: Mapped[str] = mapped_column(ForeignKey("application_revisions.id"))
    actor_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    explanation: Mapped[str] = mapped_column(String(2000))


class Notification(Entity, Base):
    __tablename__ = "notifications"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    deduplication_key: Mapped[str] = mapped_column(String(100), unique=True)
    summary: Mapped[str] = mapped_column(String(300))
    target: Mapped[dict] = mapped_column(JSON)
    read_at: Mapped[int | None] = mapped_column(Integer)


class OutboxEvent(Entity, Base):
    __tablename__ = "outbox_events"
    deduplication_key: Mapped[str] = mapped_column(String(100), unique=True)
    event_type: Mapped[str] = mapped_column(String(100))
    payload: Mapped[dict] = mapped_column(JSON)
    delivered_at: Mapped[int | None] = mapped_column(Integer)


class AuditEvent(Entity, Base):
    __tablename__ = "audit_events"
    actor_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    operation: Mapped[str] = mapped_column(String(100))
    target_id: Mapped[str] = mapped_column(String(100))
    request_id: Mapped[str] = mapped_column(String(64))
    metadata_digest: Mapped[str] = mapped_column(String(64))


class RagSource(Entity, Base):
    __tablename__ = "rag_sources"
    source_url: Mapped[str] = mapped_column(String(500))
    checksum: Mapped[str] = mapped_column(String(64))
    academic_year: Mapped[str] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(String(32), default="DRAFT")
    approved_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    effective_from: Mapped[str | None] = mapped_column(String(16))
    effective_until: Mapped[str | None] = mapped_column(String(16))


class RagChunk(Entity, Base):
    __tablename__ = "rag_chunks"
    source_id: Mapped[str] = mapped_column(ForeignKey("rag_sources.id"))
    clause: Mapped[str] = mapped_column(String(100))
    page: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(String(10000))
    embedding_reference: Mapped[str | None] = mapped_column(String(100))


class InspectionTask(Entity, Base):
    __tablename__ = "inspection_tasks"
    application_id: Mapped[str] = mapped_column(ForeignKey("applications.id"))
    finding_id: Mapped[str | None] = mapped_column(ForeignKey("findings.id"))
    assignee_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    status: Mapped[str] = mapped_column(String(32))
    evidence: Mapped[dict] = mapped_column(JSON)


class ReportSnapshot(Entity, Base):
    __tablename__ = "report_snapshots"
    revision_id: Mapped[str] = mapped_column(ForeignKey("application_revisions.id"))
    reviewer_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    version: Mapped[int] = mapped_column(Integer)
    storage_key: Mapped[str] = mapped_column(String(128), unique=True)
    manifest: Mapped[dict] = mapped_column(JSON)
    __table_args__ = (UniqueConstraint("revision_id", "version"),)


class PreviewTicket(Entity, Base):
    __tablename__ = "preview_tickets"
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("auth_sessions.id"))
    version_id: Mapped[str] = mapped_column(ForeignKey("document_versions.id"))
    expires_at: Mapped[int] = mapped_column(Integer)


class LoginThrottle(Base):
    __tablename__ = "login_throttles"
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    attempts: Mapped[int] = mapped_column(Integer)
    reset_at: Mapped[int] = mapped_column(Integer)


@event.listens_for(Base, "before_update", propagate=True)
@event.listens_for(Base, "before_delete", propagate=True)
def prevent_immutable_change(mapper, connection, target):
    if isinstance(target, (AuditEvent, DocumentVersion, ReportSnapshot, OfficerAction)):
        raise ValueError("Immutable record; create a new version/event")
    if isinstance(target, ApprovalSnapshot):
        from sqlalchemy import inspect

        history = inspect(target).attrs.published.history
        if target.published or True in history.deleted:
            raise ValueError("Published approval snapshots are immutable")
    if isinstance(target, Revision):
        from sqlalchemy import inspect

        history = inspect(target).attrs.frozen.history
        if True in history.deleted or (target.frozen and not history.has_changes()):
            raise ValueError("Frozen submission is immutable")
