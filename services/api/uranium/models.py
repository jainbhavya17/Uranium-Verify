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


class PortalContent(Base):
    __tablename__ = "portal_content"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    payload: Mapped[dict] = mapped_column(JSON)


class PortalCaseRecord(Base):
    __tablename__ = "portal_case_records"
    id: Mapped[str] = mapped_column(ForeignKey("applications.id"), primary_key=True)
    reference: Mapped[str] = mapped_column(String(100), unique=True)
    payload: Mapped[dict] = mapped_column(JSON)


class PortalInstitutionProfile(Base):
    __tablename__ = "portal_institution_profiles"
    id: Mapped[str] = mapped_column(ForeignKey("institutions.id"), primary_key=True)
    payload: Mapped[dict] = mapped_column(JSON)


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
    __table_args__ = (UniqueConstraint("request_id"),)


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


class ReportPublication(Entity, Base):
    __tablename__ = "report_publications"
    snapshot_id: Mapped[str] = mapped_column(ForeignKey("report_snapshots.id"), unique=True)
    actor_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    storage_key: Mapped[str] = mapped_column(String(128), unique=True)
    manifest: Mapped[dict] = mapped_column(JSON)


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


class ApplicationCatalogue(Entity, Base):
    __tablename__ = "application_catalogue"
    code: Mapped[str] = mapped_column(String(64))
    academic_year: Mapped[str] = mapped_column(String(16))
    display_name: Mapped[str] = mapped_column(String(160))
    availability: Mapped[str] = mapped_column(String(16))
    ruleset_id: Mapped[str] = mapped_column(ForeignKey("rule_sets.id"))
    definition: Mapped[dict] = mapped_column(JSON)
    __table_args__ = (
        UniqueConstraint("code", "academic_year"),
        CheckConstraint("availability IN ('enabled','preview','external')"),
    )


class ApplicationDraft(Base):
    __tablename__ = "application_drafts"
    id: Mapped[str] = mapped_column(ForeignKey("applications.id"), primary_key=True)
    revision_id: Mapped[str] = mapped_column(String(64))
    catalogue_id: Mapped[str] = mapped_column(ForeignKey("application_catalogue.id"))
    baseline_snapshot_id: Mapped[str] = mapped_column(ForeignKey("historical_approval_snapshots.id"))
    draft_key: Mapped[str | None] = mapped_column(String(200), unique=True)
    lock_version: Mapped[int] = mapped_column(Integer, default=1)
    updated_at: Mapped[int] = mapped_column(Integer, default=lambda: int(time.time()))
    details: Mapped[dict] = mapped_column(JSON)
    __table_args__ = (
        ForeignKeyConstraint(
            ["revision_id", "id"], ["application_revisions.id", "application_revisions.application_id"]
        ),
        CheckConstraint("lock_version > 0"),
    )


class RequirementSnapshot(Base):
    __tablename__ = "requirement_snapshots"
    id: Mapped[str] = mapped_column(ForeignKey("application_requirements.id"), primary_key=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    computed_version: Mapped[int] = mapped_column(Integer)
    payload: Mapped[dict] = mapped_column(JSON)
    selected_version_id: Mapped[str | None] = mapped_column(ForeignKey("document_versions.id"))


class ReviewedException(Entity, Base):
    __tablename__ = "reviewed_exceptions"
    institution_id: Mapped[str] = mapped_column(ForeignKey("institutions.id"))
    academic_year: Mapped[str] = mapped_column(String(16))
    code: Mapped[str] = mapped_column(String(64))
    approved_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    source_ref: Mapped[str] = mapped_column(String(300))
    is_mock: Mapped[bool] = mapped_column(Boolean, default=True)
    __table_args__ = (UniqueConstraint("institution_id", "academic_year", "code"),)


class InstitutionRouting(Base):
    __tablename__ = "institution_routing"
    id: Mapped[str] = mapped_column(ForeignKey("institutions.id"), primary_key=True)
    officer_id: Mapped[str] = mapped_column(ForeignKey("users.id"))


class MutationReceipt(Entity, Base):
    __tablename__ = "mutation_receipts"
    actor_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    operation: Mapped[str] = mapped_column(String(100))
    request_key: Mapped[str] = mapped_column(String(100))
    request_hash: Mapped[str] = mapped_column(String(64))
    complete: Mapped[bool] = mapped_column(Boolean, default=False)
    result: Mapped[dict] = mapped_column(JSON, default=dict)
    __table_args__ = (UniqueConstraint("actor_id", "operation", "request_key"),)


class SubmissionReceipt(Entity, Base):
    __tablename__ = "submission_receipts"
    application_id: Mapped[str] = mapped_column(ForeignKey("applications.id"), unique=True)
    revision_id: Mapped[str] = mapped_column(String(64))
    actor_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    request_hash: Mapped[str] = mapped_column(String(64))
    payload: Mapped[dict] = mapped_column(JSON)
    __table_args__ = (
        ForeignKeyConstraint(
            ["revision_id", "application_id"],
            ["application_revisions.id", "application_revisions.application_id"],
        ),
    )


class ApplicationTimeline(Entity, Base):
    __tablename__ = "application_timeline"
    application_id: Mapped[str] = mapped_column(ForeignKey("applications.id"))
    actor_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    event_key: Mapped[str] = mapped_column(String(200), unique=True)
    event_type: Mapped[str] = mapped_column(String(64))
    summary: Mapped[str] = mapped_column(String(300))
    payload: Mapped[dict] = mapped_column(JSON, default=dict)


class ProcessingJob(Entity, Base):
    __tablename__ = "processing_jobs"
    version_id: Mapped[str] = mapped_column(ForeignKey("document_versions.id"))
    attempt: Mapped[int] = mapped_column(Integer)
    state: Mapped[str] = mapped_column(String(40))
    code: Mapped[str] = mapped_column(String(64), default="")
    lease_until: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[int] = mapped_column(Integer, default=lambda: int(time.time()))
    scanner_mode: Mapped[str] = mapped_column(String(32), default="UNAVAILABLE")
    scan_status: Mapped[str] = mapped_column(String(32), default="PENDING")
    processor_version: Mapped[str] = mapped_column(String(100))
    __table_args__ = (UniqueConstraint("version_id", "attempt"), CheckConstraint("attempt BETWEEN 1 AND 3"))


class UploadAttempt(Entity, Base):
    __tablename__ = "upload_attempts"
    application_id: Mapped[str] = mapped_column(ForeignKey("applications.id"))
    actor_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    state: Mapped[str] = mapped_column(String(32))
    bytes_received: Mapped[int] = mapped_column(Integer, default=0)
    version_id: Mapped[str | None] = mapped_column(ForeignKey("document_versions.id"))


class ProcessingEvent(Entity, Base):
    __tablename__ = "processing_events"
    # Preserve sub-second event order without changing the public seconds timestamp.
    id: Mapped[str] = mapped_column(
        String(64), primary_key=True, default=lambda: f"{time.time_ns():020d}-{uuid.uuid4()}"
    )
    job_id: Mapped[str] = mapped_column(ForeignKey("processing_jobs.id"))
    state: Mapped[str] = mapped_column(String(40))
    code: Mapped[str] = mapped_column(String(64))


class ProcessingResult(Entity, Base):
    __tablename__ = "processing_results"
    job_id: Mapped[str] = mapped_column(ForeignKey("processing_jobs.id"), unique=True)
    payload: Mapped[dict] = mapped_column(JSON)


class ResultField(Base):
    __tablename__ = "processing_result_fields"
    result_id: Mapped[str] = mapped_column(ForeignKey("processing_results.id"), primary_key=True)
    field_id: Mapped[str] = mapped_column(ForeignKey("extracted_fields.id"), primary_key=True)


class PrecheckSnapshot(Entity, Base):
    __tablename__ = "precheck_snapshots"
    revision_id: Mapped[str] = mapped_column(ForeignKey("application_revisions.id"))
    evaluation_id: Mapped[str] = mapped_column(ForeignKey("evaluations.id"))
    application_version: Mapped[int] = mapped_column(Integer)
    input_hash: Mapped[str] = mapped_column(String(64))
    payload: Mapped[dict] = mapped_column(JSON)


class ReviewState(Base):
    __tablename__ = "case_review_state"
    id: Mapped[str] = mapped_column(ForeignKey("applications.id"), primary_key=True)
    revision_id: Mapped[str] = mapped_column(ForeignKey("application_revisions.id"))
    version: Mapped[int] = mapped_column(Integer, default=1)
    priority_override: Mapped[int | None] = mapped_column(Integer)
    priority_reason: Mapped[str | None] = mapped_column(String(2000))
    due_at: Mapped[int] = mapped_column(Integer)
    latest_evaluation_id: Mapped[str | None] = mapped_column(ForeignKey("evaluations.id"))
    context: Mapped[dict] = mapped_column(JSON, default=dict)
    __table_args__ = (
        CheckConstraint("version > 0"),
        CheckConstraint("priority_override IS NULL OR priority_override BETWEEN 0 AND 100"),
    )


class ExtractionCorrection(Entity, Base):
    __tablename__ = "extraction_corrections"
    id: Mapped[str] = mapped_column(
        String(64), primary_key=True, default=lambda: f"{time.time_ns():020d}-{uuid.uuid4()}"
    )
    field_id: Mapped[str] = mapped_column(ForeignKey("extracted_fields.id"))
    actor_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    supersedes_id: Mapped[str | None] = mapped_column(ForeignKey("extraction_corrections.id"))
    corrected_value: Mapped[dict] = mapped_column(JSON)
    rationale: Mapped[str] = mapped_column(String(2000))


class ReviewActionContext(Base):
    __tablename__ = "review_action_context"
    id: Mapped[str] = mapped_column(ForeignKey("officer_actions.id"), primary_key=True)
    payload: Mapped[dict] = mapped_column(JSON)


class SpecialistTask(Entity, Base):
    __tablename__ = "specialist_tasks"
    application_id: Mapped[str] = mapped_column(ForeignKey("applications.id"))
    revision_id: Mapped[str] = mapped_column(ForeignKey("application_revisions.id"))
    assignee_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    creator_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    kind: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(32), default="PENDING")
    due_at: Mapped[int] = mapped_column(Integer)
    version: Mapped[int] = mapped_column(Integer, default=1)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    evidence: Mapped[dict] = mapped_column(JSON)
    __table_args__ = (CheckConstraint("attempts BETWEEN 0 AND 3"), CheckConstraint("version > 0"))


class TaskResponse(Entity, Base):
    __tablename__ = "specialist_responses"
    task_id: Mapped[str] = mapped_column(ForeignKey("specialist_tasks.id"))
    actor_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    payload: Mapped[dict] = mapped_column(JSON)


class GovernedVersion(Entity, Base):
    __tablename__ = "governed_versions"
    kind: Mapped[str] = mapped_column(String(16))
    code: Mapped[str] = mapped_column(String(100))
    number: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default="DRAFT")
    author_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    approver_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    source_id: Mapped[str | None] = mapped_column(ForeignKey("governed_versions.id"))
    payload: Mapped[dict] = mapped_column(JSON)
    __table_args__ = (
        UniqueConstraint("kind", "code", "number"),
        CheckConstraint("kind IN ('RULE','SOURCE')"),
        CheckConstraint("status IN ('DRAFT','APPROVED','PUBLISHED','SUPERSEDED')"),
        CheckConstraint("approver_id IS NULL OR approver_id <> author_id"),
    )


class KnowledgePassage(Entity, Base):
    __tablename__ = "knowledge_passages"
    source_id: Mapped[str] = mapped_column(ForeignKey("governed_versions.id"))
    checksum: Mapped[str] = mapped_column(String(64))
    clause: Mapped[str] = mapped_column(String(100))
    printed_page: Mapped[int] = mapped_column(Integer)
    pdf_page: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(String(10000))
    embedding: Mapped[list | None] = mapped_column(JSON)
    embedding_model: Mapped[str | None] = mapped_column(String(200))


class RoomEvidence(Entity, Base):
    __tablename__ = "certified_room_evidence"
    id: Mapped[str] = mapped_column(
        String(64), primary_key=True, default=lambda: f"{time.time_ns():020d}-{uuid.uuid4()}"
    )
    room_id: Mapped[str] = mapped_column(ForeignKey("infrastructure_room_records.id"))
    version_id: Mapped[str] = mapped_column(ForeignKey("document_versions.id"))
    page: Mapped[int] = mapped_column(Integer)
    bbox: Mapped[list] = mapped_column(JSON)
    certified_area: Mapped[float] = mapped_column(Float)
    actor_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    source_ref: Mapped[str] = mapped_column(String(500))
    reliable: Mapped[bool] = mapped_column(Boolean, default=False)
    __table_args__ = (CheckConstraint("page > 0"), CheckConstraint("certified_area >= 0"))


class RuleRun(Entity, Base):
    __tablename__ = "rule_runs"
    evaluation_id: Mapped[str] = mapped_column(ForeignKey("evaluations.id"))
    rule_id: Mapped[str] = mapped_column(ForeignKey("governed_versions.id"))
    payload: Mapped[dict] = mapped_column(JSON)


class GovernedRuleLink(Base):
    __tablename__ = "governed_rule_links"
    id: Mapped[str] = mapped_column(ForeignKey("governed_versions.id"), primary_key=True)
    rule_id: Mapped[str] = mapped_column(ForeignKey("compliance_rules.id"), unique=True)


class ProvenanceResult(Entity, Base):
    __tablename__ = "provenance_results"
    version_id: Mapped[str] = mapped_column(ForeignKey("document_versions.id"))
    actor_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    method: Mapped[str] = mapped_column(String(100))
    outcome: Mapped[str] = mapped_column(String(40))
    payload: Mapped[dict] = mapped_column(JSON)


class ClarificationScope(Base):
    __tablename__ = "clarification_scopes"
    id: Mapped[str] = mapped_column(ForeignKey("clarification_requests.id"), primary_key=True)
    original_revision_id: Mapped[str] = mapped_column(ForeignKey("application_revisions.id"))
    allowed_fields: Mapped[list] = mapped_column(JSON)
    document_types: Mapped[list] = mapped_column(JSON)
    required_documents: Mapped[list] = mapped_column(JSON)


class ResponseDraft(Base):
    __tablename__ = "clarification_drafts"
    id: Mapped[str] = mapped_column(ForeignKey("clarification_requests.id"), primary_key=True)
    revision_id: Mapped[str] = mapped_column(ForeignKey("application_revisions.id"), unique=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    explanation: Mapped[str] = mapped_column(String(2000), default="")
    changes: Mapped[dict] = mapped_column(JSON, default=dict)
    selected: Mapped[dict] = mapped_column(JSON, default=dict)


class ResponseLineage(Base):
    __tablename__ = "clarification_response_lineage"
    id: Mapped[str] = mapped_column(ForeignKey("clarification_responses.id"), primary_key=True)
    original_revision_id: Mapped[str] = mapped_column(ForeignKey("application_revisions.id"))
    receipt: Mapped[dict] = mapped_column(JSON)


class ClarificationResolution(Entity, Base):
    __tablename__ = "clarification_resolutions"
    request_id: Mapped[str] = mapped_column(ForeignKey("clarification_requests.id"), unique=True)
    response_id: Mapped[str | None] = mapped_column(ForeignKey("clarification_responses.id"), unique=True)
    actor_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    rationale: Mapped[str] = mapped_column(String(2000))


class AccountPreference(Base):
    __tablename__ = "account_preferences"
    id: Mapped[str] = mapped_column(ForeignKey("users.id"), primary_key=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    in_app: Mapped[bool] = mapped_column(Boolean, default=True)
    reduced_motion: Mapped[bool] = mapped_column(Boolean, default=False)
    high_contrast: Mapped[bool] = mapped_column(Boolean, default=False)


class RecoveryToken(Entity, Base):
    __tablename__ = "recovery_tokens"
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    expires_at: Mapped[int] = mapped_column(Integer)
    used_at: Mapped[int | None] = mapped_column(Integer)


class ReportJob(Base):
    __tablename__ = "report_jobs"
    id: Mapped[str] = mapped_column(ForeignKey("report_requests.id"), primary_key=True)
    attempt: Mapped[int] = mapped_column(Integer, default=0)
    lease_until: Mapped[int] = mapped_column(Integer, default=0)
    snapshot_id: Mapped[str | None] = mapped_column(ForeignKey("report_snapshots.id"))
    code: Mapped[str] = mapped_column(String(40), default="")
    input_version: Mapped[int] = mapped_column(Integer)
    manifest: Mapped[dict] = mapped_column(JSON)


class ReportRequest(Entity, Base):
    __tablename__ = "report_requests"
    revision_id: Mapped[str] = mapped_column(ForeignKey("application_revisions.id"))
    actor_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    state: Mapped[str] = mapped_column(String(32), default="PENDING_GENERATION")
    payload: Mapped[dict] = mapped_column(JSON)


@event.listens_for(Base, "before_update", propagate=True)
@event.listens_for(Base, "before_delete", propagate=True)
def prevent_immutable_change(mapper, connection, target):
    if isinstance(target, ReportJob):
        from sqlalchemy import inspect

        if any(
            inspect(target).attrs[key].history.has_changes() for key in ["id", "input_version", "manifest"]
        ):
            raise ValueError("Captured report inputs are immutable")
    if isinstance(
        target,
        (
            AuditEvent,
            DocumentVersion,
            ReportSnapshot,
            ReportPublication,
            OfficerAction,
            ProcessingEvent,
            ProcessingResult,
            ResultField,
            ExtractedField,
            PrecheckSnapshot,
            EvidenceNode,
            EvidenceEdge,
            Finding,
            ClarificationScope,
            Clarification,
            ResponseLineage,
            ClarificationResponse,
            ClarificationResolution,
            GovernedRuleLink,
            ExtractionCorrection,
            ReviewActionContext,
            TaskResponse,
            KnowledgePassage,
            RoomEvidence,
            RuleRun,
            ProvenanceResult,
            VerificationAttempt,
        ),
    ):
        raise ValueError("Immutable record; create a new version/event")
    if isinstance(target, ApprovalSnapshot):
        from sqlalchemy import inspect

        history = inspect(target).attrs.published.history
        if True in history.deleted or (target.published and not history.has_changes()):
            raise ValueError("Published approval snapshots are immutable")
    if isinstance(target, Revision):
        from sqlalchemy import inspect

        history = inspect(target).attrs.frozen.history
        if True in history.deleted or (target.frozen and not history.has_changes()):
            raise ValueError("Frozen submission is immutable")
