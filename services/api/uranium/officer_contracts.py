"""Bounded human actions; uploaded evidence and suggestions never become executable rules."""

from datetime import date
from typing import Literal
from pydantic import Field, model_validator
from .institution_contracts import StrictModel


class ReviewCommand(StrictModel):
    expected_version: int = Field(ge=1)
    rationale: str = Field(min_length=10, max_length=2000)


class PriorityCommand(ReviewCommand):
    priority: int = Field(ge=0, le=100)


class AssignmentCommand(ReviewCommand):
    assignee_id: str = Field(max_length=64)


class FindingReviewCommand(ReviewCommand):
    disposition: Literal["ACKNOWLEDGED", "DISPUTED", "RESOLVED"]
    evidence_version_id: str | None = Field(default=None, max_length=64)


class CorrectionCommand(ReviewCommand):
    field_id: str = Field(max_length=64)
    normalized: str | None = Field(default=None, max_length=500)


class RoomCommand(ReviewCommand):
    room_id: str = Field(max_length=64)
    version_id: str = Field(max_length=64)
    page: int = Field(ge=1, le=50)
    bbox: list[float] = Field(min_length=4, max_length=4)
    certified_area: float = Field(ge=0, le=100000, allow_inf_nan=False)
    source_ref: str = Field(min_length=5, max_length=500)
    reliable: bool
    division: Literal[30, 60] | None = None


class TaskCommand(ReviewCommand):
    assignee_id: str = Field(max_length=64)
    kind: Literal["ISSUER", "INSPECTION", "SUPERVISION"]
    due_at: int = Field(gt=0)
    version_id: str | None = Field(default=None, max_length=64)


class TaskReply(StrictModel):
    expected_version: int = Field(ge=1)
    outcome: Literal["CONFIRMED", "CONFLICT", "UNRESOLVED", "TIMEOUT", "UNSUPPORTED"]
    source_ref: str = Field(min_length=5, max_length=500)
    observed_at: int = Field(gt=0)
    rationale: str = Field(min_length=10, max_length=2000)


class ReviewActionCommand(ReviewCommand):
    action: Literal["OBSERVATION", "RECOMMENDATION", "CLARIFICATION", "COMPLETE", "REOPEN"]
    publishable: bool = False
    due_at: int | None = Field(default=None, gt=0)
    allowed_fields: list[Literal["proposed_name", "proposed_address", "affiliation", "signatory"]] = Field(
        default_factory=list, max_length=4
    )
    document_types: list[str] = Field(default_factory=lambda: ["FIRE_SAFETY"], max_length=10)
    required_documents: list[str] = Field(default_factory=list, max_length=10)


class IssuerCommand(ReviewCommand):
    version_id: str = Field(max_length=64)
    provider_id: str = Field(max_length=64)
    fixture: Literal["match", "conflict", "timeout", "unsupported"] = "match"
    certificate_id: str = Field(min_length=1, max_length=100)


class ScopeSpec(StrictModel):
    years: list[str] = Field(min_length=1, max_length=10)
    categories: list[str] = Field(min_length=1, max_length=20)
    programmes: list[str] = Field(min_length=1, max_length=10)
    stages: list[Literal["SUBMISSION", "SCRUTINY", "EVC"]] = Field(min_length=1, max_length=3)
    effective_from: date
    effective_until: date
    roles: list[Literal["officer", "specialist", "supervisor", "admin"]] = Field(min_length=1, max_length=4)

    @model_validator(mode="after")
    def dates(self):
        if self.effective_until < self.effective_from:
            raise ValueError("Effective interval is inverted")
        return self


class SourceSpec(StrictModel):
    scope: ScopeSpec
    title: str = Field(min_length=5, max_length=200)
    source_url: str = Field(pattern=r"^https://", max_length=500)
    publication_date: date
    clause: str = Field(min_length=1, max_length=100)
    printed_page: int = Field(gt=0, le=10000)
    pdf_page: int = Field(gt=0, le=10000)
    text: str = Field(min_length=20, max_length=10000)
    interpretation: Literal["SRS_DEMO_TRANSCRIPTION", "DOMAIN_REVIEWED"]


class RuleSpec(StrictModel):
    scope: ScopeSpec
    metric: Literal["CLASSROOM_AREA_MINIMUM"]
    minimum: float = Field(gt=0, le=1000, allow_inf_nan=False)
    division: Literal[30, 60]
    room_type: Literal["CLASSROOM"] = "CLASSROOM"
    exception_codes: list[str] = Field(default_factory=list, max_length=20)


class GovernanceDraft(StrictModel):
    kind: Literal["RULE", "SOURCE"]
    code: str = Field(pattern=r"^[A-Z0-9_-]{3,100}$")
    source_id: str | None = Field(default=None, max_length=64)
    payload: dict
    rationale: str = Field(min_length=10, max_length=2000)

    @model_validator(mode="after")
    def payload_schema(self):
        self.payload = (
            (RuleSpec if self.kind == "RULE" else SourceSpec)
            .model_validate(self.payload)
            .model_dump(mode="json")
        )
        if self.kind == "RULE" and not self.source_id:
            raise ValueError("A rule requires an approved source version")
        return self


class GovernanceReason(StrictModel):
    rationale: str = Field(min_length=10, max_length=2000)


class GovernanceAction(GovernanceReason):
    action: Literal["APPROVE", "PUBLISH", "SUPERSEDE"]


class RetrievalQuery(StrictModel):
    query: str = Field(min_length=3, max_length=500)
    academic_year: str = Field(max_length=16)
    category: str = Field(max_length=64)
    programme: str = Field(max_length=100)
    stage: Literal["SUBMISSION", "SCRUTINY", "EVC"] = "SCRUTINY"
    reference_date: date


class UserAccessCommand(StrictModel):
    action: Literal["ACTIVATE", "DEACTIVATE", "REVOKE_SESSIONS", "GRANT_ROLE", "REVOKE_ROLE", "GRANT_CONTENT"]
    rationale: str = Field(min_length=10, max_length=2000)
    role: (
        Literal[
            "institution_admin",
            "institution_submitter",
            "officer",
            "specialist",
            "supervisor",
            "admin",
            "auditor",
        ]
        | None
    ) = None
    institution_id: str | None = Field(default=None, max_length=64)
    application_id: str | None = Field(default=None, max_length=64)


class ConnectorCommand(StrictModel):
    mode: Literal["MOCK", "LIVE"]
    status: Literal["AVAILABLE", "UNAVAILABLE", "MAINTENANCE"]
    secret_reference: str | None = Field(default=None, pattern=r"^secret://[A-Za-z0-9/_-]{1,150}$")
    rationale: str = Field(min_length=10, max_length=2000)
