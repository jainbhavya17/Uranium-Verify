from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class CourseInput(StrictModel):
    course: str = Field(min_length=1, max_length=100)
    level: Literal["UG", "PG", "FELLOW"] = "UG"
    requested_intake: int = Field(ge=0, le=5000)


class RoomInput(StrictModel):
    room_id: str = Field(min_length=1, max_length=64)
    room_type: Literal["CLASSROOM", "LABORATORY", "OTHER"] = "CLASSROOM"
    declared_area: float = Field(ge=0, le=100000, allow_inf_nan=False)


class DraftDetails(StrictModel):
    proposed_name: str = Field(default="", max_length=200)
    proposed_address: str = Field(default="", max_length=500)
    affiliation: str = Field(default="", max_length=200)
    signatory: str = Field(default="", max_length=160)
    programme: Literal["Engineering & Technology", "Management"] = "Engineering & Technology"
    courses: list[CourseInput] = Field(default_factory=list, max_length=30)
    rooms: list[RoomInput] = Field(default_factory=list, max_length=100)
    completion_date: date | None = None
    payment_applicable: bool = False
    originals_unavailable: bool = False
    land_tenure: Literal["OWNED", "LEASED"] = "OWNED"
    land_area_acres: float | None = Field(default=None, ge=0, le=100000, allow_inf_nan=False)
    built_up_area_m2: float | None = Field(default=None, ge=0, le=10000000, allow_inf_nan=False)
    faculty_count: int | None = Field(default=None, ge=0, le=100000)

    @model_validator(mode="after")
    def distinct_rows(self):
        for items, key in [(self.courses, "course"), (self.rooms, "room_id")]:
            values = [getattr(x, key).casefold() for x in items]
            if len(values) != len(set(values)):
                raise ValueError(f"Duplicate {key} rows are not allowed")
        return self


class CreateDraft(StrictModel):
    institution_id: str = Field(min_length=1, max_length=64)
    catalogue_id: str = Field(min_length=1, max_length=64)


class SaveDraft(StrictModel):
    expected_version: int = Field(ge=1)
    details: DraftDetails
    catalogue_id: str | None = Field(default=None, max_length=64)


class FixtureAttachment(StrictModel):
    expected_version: int = Field(ge=1)
    requirement_id: str = Field(min_length=1, max_length=64)
    document_type: str = Field(min_length=1, max_length=64)


class SubmitDraft(StrictModel):
    expected_version: int = Field(ge=1)
    declaration: Literal[True]
    precheck_id: str | None = Field(default=None, max_length=64)


class CatalogueView(BaseModel):
    id: str
    code: str
    academic_year: str
    display_name: str
    availability: Literal["enabled", "preview", "external"]
    ruleset_id: str
    rule_version: str
    definition: dict


class SnapshotView(BaseModel):
    id: str
    academic_year: str
    source_ref: str
    source_status: Literal["AUTHORIZED", "SYNTHETIC", "IMPORTED_UNVERIFIED", "REGISTRATION_PROFILE"]
    baseline_eligible: bool
    is_mock: bool
    payload: dict
    profile: dict


class RequirementView(BaseModel):
    id: str
    code: str
    label: str
    applicability: str
    mandatory: bool
    stage_due: str
    reason: str
    acceptable_alternatives: list[str]
    source: dict
    exception: dict | None = None
    evidence: dict | None = None
    satisfied: bool


class ChecklistView(BaseModel):
    version: int
    ruleset_id: str
    rule_version: str
    interpretation_status: str
    academic_year: str
    stage: str = "SUBMISSION"
    items: list[RequirementView]


class ReadinessView(BaseModel):
    precheck_id: str | None = None
    stale: bool = True
    version: int
    ready: bool
    blocking: list[dict]
    advisory: list[str]
    checklist: ChecklistView


class DraftView(BaseModel):
    application_id: str
    institution_id: str
    status: str
    version: int
    updated_at: int
    revision_id: str
    editable: bool
    can_submit: bool = False
    catalogue: CatalogueView
    baseline: SnapshotView
    details: DraftDetails
    changes: list[dict]
    checklist: ChecklistView
    receipt: dict | None = None


class AttachmentView(BaseModel):
    version_id: str
    document_id: str
    number: int
    status: str
    application_version: int
    is_mock: bool


class ReceiptView(BaseModel):
    receipt_id: str
    application_id: str
    revision_id: str
    acknowledgment: str
    submitted_at: int
    version: int
    rule_version: str
    manifest_sha256: str
    document_count: int
    is_mock: bool = True
    status: str = "SUBMITTED"
