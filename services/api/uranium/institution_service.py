"""Versioned institution workflow. No OCR, source verification or legal approval occurs here."""

import hashlib
import json
import re
import secrets
import time
from datetime import date
from typing import Literal

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy import delete, select, update
from sqlalchemy.exc import IntegrityError, OperationalError

from .audit import append_audit
from .institution_contracts import DraftDetails
from .models import (
    Application,
    ApplicationCatalogue,
    ApplicationDraft,
    ApplicationRequirement,
    ApplicationTimeline,
    ApprovalSnapshot,
    Assignment,
    Claim,
    CourseIntake,
    Document,
    DocumentVersion,
    Institution,
    InstitutionRouting,
    Membership,
    MutationReceipt,
    OutboxEvent,
    RequirementSnapshot,
    RequirementTemplate,
    ReviewedException,
    Revision,
    RoomRecord,
    RuleSet,
    SubmissionReceipt,
    User,
    new_id,
)

INTERPRETATION = "SRS_TRANSCRIBED_DEMO_NOT_OFFICIALLY_APPROVED"
TRUSTED_FIXTURE = "SYNTHETIC_FIXTURE"
QUARANTINE = "QUARANTINED_PENDING_SAFETY"


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


class Condition(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    op: Literal["always", "eq", "all", "not"]
    field: (
        Literal[
            "programme", "level", "payment_applicable", "structural_over_30", "extended_eoa", "land_leased"
        ]
        | None
    ) = None
    value: bool | str | None = None
    conditions: list["Condition"] = Field(default_factory=list, max_length=10)


def evaluate(condition, context, depth=0):
    if depth > 8:
        raise HTTPException(503, "Requirement predicate exceeds the supported depth; rule review required.")
    try:
        item = Condition.model_validate(condition) if isinstance(condition, dict) else condition
    except ValidationError:
        raise HTTPException(503, "Requirement predicate is unsupported; rule review required.")
    if item.op == "always":
        return True
    if item.op == "eq" and item.field:
        observed = context[item.field]
        return None if observed is None else type(observed) is type(item.value) and observed == item.value
    if item.op == "not" and len(item.conditions) == 1:
        result = evaluate(item.conditions[0], context, depth + 1)
        return None if result is None else not result
    if item.op == "all" and item.conditions:
        results = [evaluate(child, context, depth + 1) for child in item.conditions]
        return False if False in results else None if None in results else True
    raise HTTPException(503, "Requirement predicate has an invalid shape; rule review required.")


def older_than(completion, reference, years):
    if not completion:
        return None
    start = date.fromisoformat(str(completion))
    try:
        anniversary = start.replace(year=start.year + years)
    except ValueError:
        anniversary = start.replace(year=start.year + years, day=28)
    return date.fromisoformat(reference) > anniversary


def snapshot_view(db, snapshot):
    institution = db.get(Institution, snapshot.institution_id)
    payload = snapshot.payload
    # Older explicit profile data is a labelled prefill source, never silently a newer approval.
    older = db.scalars(
        select(ApprovalSnapshot)
        .where(
            ApprovalSnapshot.institution_id == institution.id,
            ApprovalSnapshot.published.is_(True),
            ApprovalSnapshot.academic_year <= snapshot.academic_year,
        )
        .order_by(ApprovalSnapshot.academic_year.desc(), ApprovalSnapshot.version.desc())
    ).all()
    profile_source = next((s for s in older if s.payload.get("profile")), None)
    profile = {
        "name": institution.name,
        "permanent_id": institution.permanent_id,
        **(profile_source.payload.get("profile", {}) if profile_source else {}),
        **payload.get("profile", {}),
    }
    courses = (
        payload.get("courses", [])
        if "courses" in payload
        else [
            {
                "course": payload["course"],
                "level": "UG",
                "approved_intake": payload.get("approved_intake", 0),
            }
        ]
        if payload.get("course")
        else []
    )
    profile["courses"] = courses
    profile["extended_eoa"] = bool(payload.get("extended_eoa", False))
    profile["prefill_source"] = profile_source.id if profile_source else "SYNTHETIC_DIRECTORY_METADATA"
    profile["prefill_source_year"] = profile_source.academic_year if profile_source else None
    unverified = payload.get("source_status") == "IMPORTED_UNVERIFIED" or not snapshot.published
    return {
        "id": snapshot.id,
        "academic_year": snapshot.academic_year,
        "source_ref": snapshot.source_ref,
        "source_status": "REGISTRATION_PROFILE"
        if payload.get("source_status") == "REGISTRATION_PROFILE"
        else "IMPORTED_UNVERIFIED"
        if unverified
        else "SYNTHETIC"
        if snapshot.is_mock
        else "AUTHORIZED",
        "baseline_eligible": snapshot.published and not unverified,
        "is_mock": snapshot.is_mock,
        "payload": payload,
        "profile": profile,
    }


def historical_rows(db, institution_id):
    rows = db.scalars(
        select(ApprovalSnapshot)
        .where(ApprovalSnapshot.institution_id == institution_id)
        .order_by(ApprovalSnapshot.academic_year.desc(), ApprovalSnapshot.version.desc(), ApprovalSnapshot.id)
    ).all()
    return [
        snapshot_view(db, s)
        for s in rows
        if s.published or s.payload.get("source_status") == "IMPORTED_UNVERIFIED"
    ]


def baseline_for(db, institution_id, academic_year):
    rows = historical_rows(db, institution_id)
    row = next((r for r in rows if r["baseline_eligible"] and r["academic_year"] < academic_year), None)
    if not row:
        raise HTTPException(
            409, "An approved or labelled synthetic baseline from an earlier academic year is required."
        )
    return db.get(ApprovalSnapshot, row["id"])


def catalogue_view(db, item):
    return {
        "id": item.id,
        "code": item.code,
        "display_name": item.display_name,
        "academic_year": item.academic_year,
        "availability": item.availability,
        "ruleset_id": item.ruleset_id,
        "rule_version": db.get(RuleSet, item.ruleset_id).version,
        "definition": item.definition,
    }


def available_catalogue(db, identifier):
    item = db.get(ApplicationCatalogue, identifier)
    if not item:
        raise HTTPException(404, "Application category/year unavailable.")
    pack = db.get(RuleSet, item.ruleset_id)
    if item.availability != "enabled":
        raise HTTPException(
            409, "This category is preview/external guidance only; local submission is not enabled."
        )
    if pack.status != "DEMO_REVIEWED" or not item.definition.get("is_mock"):
        raise HTTPException(
            409, "Only the reviewed synthetic demonstration rule packs are enabled in this phase."
        )
    return item


def workflow_draft(db, case, editable=False):
    draft = db.get(ApplicationDraft, case.id)
    if not draft:
        raise HTTPException(
            409, "Read-only Phase 1 fixture. Start a new application to use the Phase 2 workflow."
        )
    if editable and (case.status != "DRAFT" or db.get(Revision, draft.revision_id).frozen):
        raise HTTPException(
            409, "This submitted revision is locked. Its evidence and details cannot be edited."
        )
    return draft


def touch(db, case, expected):
    draft = workflow_draft(db, case, editable=True)
    result = db.execute(
        update(ApplicationDraft)
        .where(
            ApplicationDraft.id == case.id,
            ApplicationDraft.lock_version == expected,
            ApplicationDraft.id.in_(select(Application.id).where(Application.status == "DRAFT")),
        )
        .values(lock_version=expected + 1, updated_at=int(time.time()))
        .execution_options(synchronize_session="fetch")
    )
    if result.rowcount != 1:
        raise HTTPException(
            409, "This draft changed in another request. Reload the latest version before saving."
        )
    return draft


def idempotent(db, principal, operation, key, payload, callback):
    if not key or not re.fullmatch(r"[A-Za-z0-9._:-]{8,100}", key):
        raise HTTPException(
            422, "Supply an Idempotency-Key of 8-100 letters, numbers, dots, colons, underscores or hyphens."
        )
    checksum = fingerprint(payload)

    def existing():
        return db.scalar(
            select(MutationReceipt).where(
                MutationReceipt.actor_id == principal.user.id,
                MutationReceipt.operation == operation,
                MutationReceipt.request_key == key,
            )
        )

    def replay(row):
        if row.request_hash != checksum:
            raise HTTPException(409, "This idempotency key was already used with different request content.")
        if not row.complete:
            raise HTTPException(409, "The request is still pending. Retry the same request key.")
        return row.result

    row = existing()
    if row:
        return replay(row)
    try:
        row = MutationReceipt(
            actor_id=principal.user.id,
            operation=operation,
            request_key=key,
            request_hash=checksum,
            complete=False,
            result={},
        )
        db.add(row)
        db.flush()
        result = callback(checksum)
        row.result, row.complete = result, True
        db.commit()
        return result
    except IntegrityError:
        db.rollback()
        previous = existing()
        if previous:
            return replay(previous)
        raise HTTPException(
            409, "An active draft or conflicting write already exists. Refresh My Applications and resume it."
        )
    except OperationalError as exc:
        db.rollback()
        if "locked" in str(exc).lower() or "serializ" in str(exc).lower():
            raise HTTPException(409, "A concurrent write is in progress. Retry with the same request key.")
        raise
    except Exception:
        db.rollback()
        raise


def changes_for(profile, details):
    changes = []
    for field, old, new in [
        ("Institution name", profile.get("name"), details.get("proposed_name")),
        ("Campus address", profile.get("address"), details.get("proposed_address")),
        ("Affiliation", profile.get("affiliation"), details.get("affiliation")),
    ]:
        if new and old != new:
            changes.append(
                {
                    "field": field,
                    "approved": old,
                    "requested": new,
                    "interpretation": "PROPOSED_CHANGE",
                    "is_discrepancy": False,
                }
            )
    approved = {c["course"].casefold(): c["approved_intake"] for c in profile["courses"]}
    for course in details.get("courses", []):
        old = approved.get(course["course"].casefold(), 0)
        if old != course["requested_intake"]:
            changes.append(
                {
                    "field": f"Intake: {course['course']}",
                    "approved": old,
                    "requested": course["requested_intake"],
                    "interpretation": "PROPOSED_CHANGE",
                    "is_discrepancy": False,
                }
            )
    requested_names = {c["course"].casefold() for c in details.get("courses", [])}
    for course in profile["courses"]:
        if course["course"].casefold() not in requested_names and course["approved_intake"]:
            changes.append(
                {
                    "field": f"Removed course: {course['course']}",
                    "approved": course["approved_intake"],
                    "requested": 0,
                    "interpretation": "PROPOSED_CHANGE",
                    "is_discrepancy": False,
                }
            )
    return changes


def persist_claims(db, draft, profile):
    for model in [Claim, CourseIntake, RoomRecord]:
        db.execute(delete(model).where(model.revision_id == draft.revision_id))
    for key, value in draft.details.items():
        db.add(Claim(revision_id=draft.revision_id, field_key=key, value={"declared": value}))
    approved = {c["course"].casefold(): c["approved_intake"] for c in profile["courses"]}
    for course in draft.details["courses"]:
        db.add(
            CourseIntake(
                revision_id=draft.revision_id,
                programme=draft.details["programme"],
                course=course["course"],
                approved_intake=approved.get(course["course"].casefold(), 0),
                requested_intake=course["requested_intake"],
            )
        )
    for room in draft.details["rooms"]:
        db.add(
            RoomRecord(
                revision_id=draft.revision_id,
                room_code=room["room_id"],
                room_type=room["room_type"],
                declared_area=room["declared_area"],
            )
        )


def persist_requirements(db, case, draft):
    catalogue = available_catalogue(db, draft.catalogue_id)
    profile = snapshot_view(db, db.get(ApprovalSnapshot, draft.baseline_snapshot_id))["profile"]
    reference = catalogue.definition["reference_date"]
    details = draft.details
    context = {
        "programme": details["programme"],
        "level": "FELLOW" if any(c["level"] == "FELLOW" for c in details["courses"]) else "UG",
        "payment_applicable": details["payment_applicable"],
        "structural_over_30": older_than(details.get("completion_date"), reference, 30),
        "extended_eoa": profile.get("extended_eoa", False),
        "land_leased": details.get("land_tenure") == "LEASED",
    }
    exception = None
    if (
        profile.get("institution_type") == "government"
        and details["originals_unavailable"]
        and older_than(details.get("completion_date"), reference, 50)
    ):
        exception = db.scalar(
            select(ReviewedException).where(
                ReviewedException.institution_id == case.institution_id,
                ReviewedException.academic_year == case.academic_year,
                ReviewedException.code == "GOVERNMENT_OVER_50_ALTERNATIVE",
            )
        )
    old = db.scalars(
        select(ApplicationRequirement).where(ApplicationRequirement.revision_id == draft.revision_id)
    ).all()
    by_template = {r.template_id: r for r in old}
    for row in old:
        snapshot = db.get(RequirementSnapshot, row.id)
        if snapshot:
            snapshot.active = False
    templates = db.scalars(
        select(RequirementTemplate)
        .where(
            RequirementTemplate.ruleset_id == catalogue.ruleset_id,
            RequirementTemplate.category == catalogue.code,
        )
        .order_by(RequirementTemplate.code)
    ).all()
    if not templates:
        raise HTTPException(409, "No reviewed document package is available for this category.")
    for template in templates:
        spec = template.field_schema
        applicable = evaluate(template.predicate, context)
        conditional = template.predicate["op"] != "always"
        reason = "Required for this application."
        if applicable is False:
            state, mandatory, reason = (
                "NOT_APPLICABLE",
                False,
                "Not required for the details you have saved.",
            )
        elif template.stage_due != "SUBMISSION":
            state, mandatory, reason = (
                "NOT_DUE",
                False,
                f"Due at {template.stage_due}; not missing at initial submission.",
            )
        elif applicable is None:
            state, mandatory, reason = (
                "UNRESOLVED",
                True,
                "Completion-certificate date is needed to resolve the age condition.",
            )
        else:
            state, mandatory = "CONDITIONAL" if conditional else "REQUIRED", True
            if template.code == "EOA-D04":
                reason = (
                    f"More than 30 years since completion-certificate issue at reference date {reference}."
                )
            elif template.code == "EOA-D02":
                reason = "A relevant-year payment receipt was declared applicable."
        alternatives = list(spec["alternatives"])
        exception_view = None
        if exception and template.code in {"EOA-D03", "EOA-D04"} and applicable is not False:
            alternatives.append("GOV_NORMS_LETTER")
            exception_view = {
                "id": exception.id,
                "source_ref": exception.source_ref,
                "reviewed_by": exception.approved_by,
                "reviewed_at": exception.created_at,
                "is_mock": exception.is_mock,
            }
            reason += " A reviewed alternative permits a competent-authority letter; supporting evidence is still required."
        row = by_template.get(template.id)
        if not row:
            row = ApplicationRequirement(
                revision_id=draft.revision_id, template_id=template.id, applicability=state
            )
            db.add(row)
            db.flush()
        row.applicability = state
        payload = {
            "id": row.id,
            "code": template.code,
            "label": spec["label"],
            "applicability": state,
            "mandatory": mandatory,
            "stage_due": template.stage_due,
            "reason": reason,
            "acceptable_alternatives": alternatives,
            "source": {
                "url": spec["source_url"],
                "clause": spec["clause"],
                "printed_page": spec["printed_page"],
                "pdf_page": spec["pdf_page"],
                "interpretation_status": INTERPRETATION,
            },
            "exception": exception_view,
        }
        saved = db.get(RequirementSnapshot, row.id)
        if saved:
            saved.active, saved.computed_version, saved.payload = True, draft.lock_version, payload
        else:
            db.add(
                RequirementSnapshot(
                    id=row.id, active=True, computed_version=draft.lock_version, payload=payload
                )
            )
    db.flush()


def checklist_view(db, case, draft):
    catalogue = db.get(ApplicationCatalogue, draft.catalogue_id)
    rows = db.scalars(
        select(RequirementSnapshot)
        .join(ApplicationRequirement, RequirementSnapshot.id == ApplicationRequirement.id)
        .where(ApplicationRequirement.revision_id == draft.revision_id, RequirementSnapshot.active.is_(True))
    ).all()
    items = []
    for row in sorted(rows, key=lambda r: r.payload["code"]):
        latest = db.get(DocumentVersion, row.selected_version_id) if row.selected_version_id else None
        evidence = (
            {
                "id": latest.id,
                "document_id": latest.document_id,
                "number": latest.number,
                "name": latest.original_name,
                "status": latest.status,
                "sha256": latest.sha256,
                "is_mock": latest.is_mock,
                "document_type": db.get(Document, latest.document_id).document_type,
            }
            if latest
            else None
        )
        acceptable = evidence and evidence["document_type"] in row.payload["acceptable_alternatives"]
        from .processing import accepted, latest_job

        job = latest_job(db, latest.id) if latest else None
        if evidence and job:
            evidence["status"] = job.state
        satisfied = bool(acceptable and accepted(db, latest))
        items.append({**row.payload, "evidence": evidence, "satisfied": satisfied})
    return {
        "version": draft.lock_version,
        "ruleset_id": catalogue.ruleset_id,
        "rule_version": db.get(RuleSet, catalogue.ruleset_id).version,
        "interpretation_status": INTERPRETATION,
        "academic_year": case.academic_year,
        "stage": "SUBMISSION",
        "items": items,
    }


def readiness_view(db, case, draft):
    checklist = checklist_view(db, case, draft)
    blocking = []
    details = draft.details
    for key, label in [
        ("proposed_name", "Institution name"),
        ("proposed_address", "Campus address"),
        ("affiliation", "Affiliation"),
        ("signatory", "Authorized signatory"),
    ]:
        if not details.get(key):
            blocking.append({"code": "DETAIL_REQUIRED", "field": key, "message": label + " is required."})
    if not details.get("courses"):
        blocking.append(
            {"code": "COURSE_REQUIRED", "field": "courses", "message": "Add at least one course/intake row."}
        )
    catalogue = db.get(ApplicationCatalogue, draft.catalogue_id)
    if details.get("completion_date") and details["completion_date"] > catalogue.definition["reference_date"]:
        blocking.append(
            {
                "code": "DATE_AFTER_REFERENCE",
                "field": "completion_date",
                "message": "The completion date is after the reference date used for these checks.",
            }
        )
    for item in checklist["items"]:
        if item["evidence"] and item["evidence"]["status"] == QUARANTINE:
            blocking.append(
                {
                    "code": "FILE_PENDING_SAFETY",
                    "requirement_id": item["id"],
                    "message": item["label"]
                    + ": safety checks must finish before this document can be submitted.",
                }
            )
        if item["applicability"] == "UNRESOLVED" or (item["mandatory"] and not item["satisfied"]):
            blocking.append(
                {
                    "code": "REQUIREMENT_UNRESOLVED"
                    if item["applicability"] == "UNRESOLVED"
                    else "EVIDENCE_REQUIRED",
                    "requirement_id": item["id"],
                    "message": item["label"]
                    + ": "
                    + (
                        "provide the missing information so this requirement can be determined."
                        if item["applicability"] == "UNRESOLVED"
                        else "upload an original document and wait for its safety and readability checks."
                    ),
                    "source": item["source"],
                }
            )
    profile = snapshot_view(db, db.get(ApprovalSnapshot, draft.baseline_snapshot_id))["profile"]
    approved = {c["course"].casefold(): c["approved_intake"] for c in profile["courses"]}
    if catalogue.code in {"EOA", "PORTAL_EOA"} and any(
        c["requested_intake"] != approved.get(c["course"].casefold(), 0) for c in details["courses"]
    ):
        blocking.append(
            {
                "code": "CATEGORY_MISMATCH",
                "field": "courses",
                "message": "Use the intake-change category for a proposed course/intake change. The change itself is not a fraud finding.",
            }
        )
    if catalogue.code in {"INTAKE_INCREASE", "PORTAL_INTAKE_INCREASE"} and not any(
        c["requested_intake"] > approved.get(c["course"].casefold(), 0) for c in details["courses"]
    ):
        blocking.append(
            {
                "code": "INCREASE_REQUIRED",
                "field": "courses",
                "message": "Enter at least one proposed intake increase or additional course for this application category.",
            }
        )
    from .precheck import document_checks

    file_blocks, file_advice = document_checks(db, case, draft, checklist)
    blocking.extend(file_blocks)
    return {
        "version": draft.lock_version,
        "ready": not blocking,
        "blocking": blocking,
        "advisory": [
            "These checks assess your saved details and processed documents. Issuer authentication and officer review are separate steps.",
            "Documents due at a later review stage do not block this submission.",
            "Rule interpretation and reference dates require domain-owner confirmation before live use.",
        ]
        + file_advice,
        "checklist": checklist,
    }


def can_submit(db, principal, institution_id):
    if not principal:
        return False
    return bool(
        db.scalar(
            select(Membership.id)
            .where(
                Membership.user_id == principal.user.id,
                Membership.institution_id == institution_id,
                Membership.role_id == "institution_admin",
                ((Membership.valid_until.is_(None)) | (Membership.valid_until > int(time.time()))),
            )
            .limit(1)
        )
    )


def state_view(db, case, principal=None):
    draft = workflow_draft(db, case)
    baseline = snapshot_view(db, db.get(ApprovalSnapshot, draft.baseline_snapshot_id))
    receipt = db.scalar(select(SubmissionReceipt).where(SubmissionReceipt.application_id == case.id))
    return {
        "application_id": case.id,
        "institution_id": case.institution_id,
        "status": case.status,
        "version": draft.lock_version,
        "updated_at": draft.updated_at,
        "revision_id": draft.revision_id,
        "editable": case.status == "DRAFT",
        "can_submit": can_submit(db, principal, case.institution_id),
        "catalogue": catalogue_view(db, db.get(ApplicationCatalogue, draft.catalogue_id)),
        "baseline": baseline,
        "details": draft.details,
        "changes": changes_for(baseline["profile"], draft.details),
        "checklist": checklist_view(db, case, draft),
        "receipt": receipt.payload if receipt else None,
    }


def timeline_event(db, case, principal, event_type, summary, version):
    db.add(
        ApplicationTimeline(
            application_id=case.id,
            actor_id=principal.user.id,
            event_key=f"{case.id}:{event_type}:{version}",
            event_type=event_type,
            summary=summary,
            payload={"version": version, "is_mock": True},
        )
    )


def create_workflow(db, principal, body, request_id):
    catalogue = available_catalogue(db, body.catalogue_id)
    institution = db.get(Institution, body.institution_id)
    if not institution or not institution.is_mock:
        raise HTTPException(409, "Only controlled synthetic institutions are enabled in this phase.")
    if catalogue.code in {"NEW_INSTITUTION", "PORTAL_NEW_INSTITUTION"}:
        registration_source = (
            "Registration profile for a new-institution proposal; no previous approval is asserted."
        )
        previous_year = f"{int(catalogue.academic_year[:4]) - 1}-{int(catalogue.academic_year[:4]) % 100:02d}"
        baseline = db.scalar(
            select(ApprovalSnapshot).where(
                ApprovalSnapshot.institution_id == institution.id,
                ApprovalSnapshot.academic_year == previous_year,
                ApprovalSnapshot.source_ref == registration_source,
            )
        )
        if not baseline:
            existing_versions = db.scalars(
                select(ApprovalSnapshot.version).where(
                    ApprovalSnapshot.institution_id == institution.id,
                    ApprovalSnapshot.academic_year == previous_year,
                )
            ).all()
            baseline = ApprovalSnapshot(
                institution_id=institution.id,
                academic_year=previous_year,
                version=max(existing_versions, default=0) + 1,
                published=False,
                is_mock=True,
                source_ref=registration_source,
                payload={
                    "source_status": "REGISTRATION_PROFILE",
                    "profile": {"name": institution.name, "permanent_id": institution.permanent_id},
                    "courses": [],
                },
            )
            db.add(baseline)
            db.flush()
    else:
        baseline = baseline_for(db, institution.id, catalogue.academic_year)
    profile = snapshot_view(db, baseline)["profile"]
    case = Application(
        institution_id=institution.id,
        category=catalogue.display_name,
        academic_year=catalogue.academic_year,
        status="DRAFT",
        is_mock=True,
    )
    db.add(case)
    db.flush()
    revision = Revision(
        application_id=case.id,
        number=1,
        actor_id=principal.user.id,
        ruleset_id=catalogue.ruleset_id,
        frozen=False,
        manifest={},
    )
    db.add(revision)
    db.flush()
    details = DraftDetails(
        proposed_name=profile["name"],
        proposed_address=profile.get("address", ""),
        affiliation=profile.get("affiliation", ""),
        completion_date=profile.get("completion_date"),
        courses=[
            {"course": c["course"], "level": c.get("level", "UG"), "requested_intake": c["approved_intake"]}
            for c in profile["courses"]
        ],
    )
    draft = ApplicationDraft(
        id=case.id,
        revision_id=revision.id,
        catalogue_id=catalogue.id,
        baseline_snapshot_id=baseline.id,
        draft_key=f"{institution.id}:{catalogue.id}",
        lock_version=1,
        updated_at=int(time.time()),
        details=details.model_dump(mode="json"),
    )
    db.add(draft)
    db.flush()
    persist_claims(db, draft, profile)
    persist_requirements(db, case, draft)
    timeline_event(db, case, principal, "DRAFT_CREATED", "Application draft created.", 1)
    append_audit(db, principal.user.id, "DRAFT_CREATED", case.id, request_id)
    db.flush()
    return state_view(db, case, principal)


def save_workflow(db, principal, case, body, request_id):
    draft = touch(db, case, body.expected_version)
    if body.catalogue_id and body.catalogue_id != draft.catalogue_id:
        catalogue = available_catalogue(db, body.catalogue_id)
        baseline = baseline_for(db, case.institution_id, catalogue.academic_year)
        draft.catalogue_id, draft.baseline_snapshot_id = catalogue.id, baseline.id
        draft.draft_key = f"{case.institution_id}:{catalogue.id}"
        case.category, case.academic_year = catalogue.display_name, catalogue.academic_year
        db.get(Revision, draft.revision_id).ruleset_id = catalogue.ruleset_id
    draft.details = body.details.model_dump(mode="json")
    profile = snapshot_view(db, db.get(ApprovalSnapshot, draft.baseline_snapshot_id))["profile"]
    persist_claims(db, draft, profile)
    persist_requirements(db, case, draft)
    append_audit(db, principal.user.id, "DRAFT_SAVED", case.id, request_id, {"version": draft.lock_version})
    db.flush()
    return state_view(db, case, principal)


def synthetic_pdf(document_type):
    # Controlled server-generated fixture. No uploaded bytes are parsed or blessed here.
    label = "MOCK sample: " + document_type.replace("_", " ") + ". No official validity."
    text = f"BT /F1 18 Tf 40 740 Td (MOCK - URANIUM VERIFY) Tj 0 -32 Td /F1 12 Tf ({label}) Tj ET".encode(
        "ascii"
    )
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        f"<< /Length {len(text)} >>\nstream\n".encode() + text + b"\nendstream",
    ]
    result, offsets = b"%PDF-1.4\n", []
    for index, obj in enumerate(objects, 1):
        offsets.append(len(result))
        result += f"{index} 0 obj\n".encode() + obj + b"\nendobj\n"
    xref = len(result)
    result += b"xref\n0 6\n0000000000 65535 f \n" + b"".join(f"{x:010d} 00000 n \n".encode() for x in offsets)
    return result + f"trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()


def attach_workflow(
    db,
    principal,
    case,
    expected,
    requirement_id,
    document_type,
    content,
    filename,
    is_fixture,
    storage,
    request_id,
    media_type=None,
):
    draft = touch(db, case, expected)
    requirement = db.get(ApplicationRequirement, requirement_id)
    snapshot = db.get(RequirementSnapshot, requirement_id)
    if not requirement or requirement.revision_id != draft.revision_id or not snapshot or not snapshot.active:
        raise HTTPException(404, "Document slot unavailable in this draft revision.")
    if document_type not in snapshot.payload["acceptable_alternatives"]:
        raise HTTPException(422, "This document type is not an acceptable alternative for the selected slot.")
    doc = db.scalar(
        select(Document).where(Document.application_id == case.id, Document.requirement_id == requirement_id)
    )
    if not doc:
        doc = Document(application_id=case.id, requirement_id=requirement_id, document_type=document_type)
        db.add(doc)
        db.flush()
    # A replacement can use another allowed alternative. Original version identity stays immutable;
    # its type is stored independently below through a new document when the alternative changes.
    if doc.document_type != document_type:
        doc = db.scalar(
            select(Document).where(
                Document.application_id == case.id,
                Document.requirement_id == requirement_id,
                Document.document_type == document_type,
            )
        )
        if not doc:
            doc = Document(application_id=case.id, requirement_id=requirement_id, document_type=document_type)
            db.add(doc)
            db.flush()
    latest = db.scalar(
        select(DocumentVersion)
        .where(DocumentVersion.document_id == doc.id)
        .order_by(DocumentVersion.number.desc())
        .limit(1)
    )
    key = secrets.token_hex(32)
    storage.write_once(key, content)
    clean_name = (
        re.sub(r"[\x00-\x1f\x7f]", "", filename.replace("\\", "/").split("/")[-1])[:180] or "quarantined.bin"
    )
    version = DocumentVersion(
        application_id=case.id,
        document_id=doc.id,
        revision_id=draft.revision_id,
        number=latest.number + 1 if latest else 1,
        sha256=hashlib.sha256(content).hexdigest(),
        storage_key=key,
        original_name=clean_name,
        media_type=media_type or ("application/pdf" if is_fixture else "application/octet-stream"),
        uploader_id=principal.user.id,
        status=TRUSTED_FIXTURE if is_fixture else QUARANTINE,
        is_mock=is_fixture,
    )
    db.add(version)
    db.flush()
    snapshot.selected_version_id = version.id
    persist_requirements(db, case, draft)
    append_audit(
        db,
        principal.user.id,
        "FIXTURE_ATTACHED" if is_fixture else "UPLOAD_QUARANTINED",
        case.id,
        request_id,
        {"version": draft.lock_version},
    )
    db.flush()
    return {
        "version_id": version.id,
        "document_id": doc.id,
        "number": version.number,
        "status": version.status,
        "application_version": draft.lock_version,
        "is_mock": is_fixture,
    }


def submit_workflow(db, principal, case, body, checksum, request_id):
    existing = db.scalar(select(SubmissionReceipt).where(SubmissionReceipt.application_id == case.id))
    if existing:
        if existing.request_hash == checksum:
            return existing.payload
        raise HTTPException(409, "This application is already submitted with a different revision/request.")
    from .precheck import assert_current

    assert_current(db, case, workflow_draft(db, case), body.precheck_id, body.expected_version)
    draft = touch(db, case, body.expected_version)
    # Recompute from the saved catalogue/year and latest evidence inside this write transaction.
    persist_requirements(db, case, draft)
    readiness = readiness_view(db, case, draft)
    if not readiness["ready"]:
        raise HTTPException(
            409, "Submission blocked. Resolve the current checklist and detail issues before retrying."
        )
    routing = db.get(InstitutionRouting, case.institution_id)
    officer = db.get(User, routing.officer_id) if routing else None
    role = (
        db.scalar(
            select(Membership).where(
                Membership.user_id == officer.id,
                Membership.role_id == "officer",
                ((Membership.valid_until.is_(None)) | (Membership.valid_until > int(time.time()))),
            )
        )
        if officer
        else None
    )
    if not routing or not officer or not officer.active or not role:
        raise HTTPException(
            409, "A valid synthetic officer-routing policy must be configured before submission."
        )
    revision = db.get(Revision, draft.revision_id)
    manifest = {
        "application_id": case.id,
        "precheck_id": body.precheck_id,
        "revision_id": revision.id,
        "details": draft.details,
        "baseline_snapshot_id": draft.baseline_snapshot_id,
        "ruleset_id": readiness["checklist"]["ruleset_id"],
        "rule_version": readiness["checklist"]["rule_version"],
        "checklist": readiness["checklist"],
        "declaration": True,
        "is_mock": True,
        "document_version_ids": [
            i["evidence"]["id"] for i in readiness["checklist"]["items"] if i["evidence"] and i["satisfied"]
        ],
    }
    now, receipt_id = int(time.time()), new_id()
    receipt = {
        "receipt_id": receipt_id,
        "application_id": case.id,
        "revision_id": revision.id,
        "acknowledgment": f"UV-{case.academic_year}-{case.id[:8].upper()}",
        "submitted_at": now,
        "version": draft.lock_version,
        "rule_version": manifest["rule_version"],
        "manifest_sha256": fingerprint(manifest),
        "document_count": len(manifest["document_version_ids"]),
        "is_mock": True,
        "status": "SUBMITTED",
    }
    draft.draft_key = None
    db.flush()
    revision.manifest, revision.submitted_at, revision.frozen = manifest, now, True
    case.status = "SUBMITTED"
    db.add(
        SubmissionReceipt(
            id=receipt_id,
            application_id=case.id,
            revision_id=revision.id,
            actor_id=principal.user.id,
            request_hash=checksum,
            payload=receipt,
        )
    )
    db.add(Assignment(application_id=case.id, user_id=officer.id, scope="REVIEW", active=True))
    db.add(
        OutboxEvent(
            deduplication_key=f"application.submitted:{case.id}",
            event_type="APPLICATION_SUBMITTED",
            payload={
                "application_id": case.id,
                "revision_id": revision.id,
                "officer_id": officer.id,
                "is_mock": True,
            },
        )
    )
    timeline_event(
        db,
        case,
        principal,
        "SUBMITTED",
        "Application submitted; preliminary review pending.",
        draft.lock_version,
    )
    append_audit(
        db,
        principal.user.id,
        "APPLICATION_SUBMITTED",
        case.id,
        request_id,
        {"revision_id": revision.id, "manifest_sha256": receipt["manifest_sha256"]},
    )
    db.flush()
    return receipt
