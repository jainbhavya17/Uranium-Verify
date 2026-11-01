"""Portal-oriented views over the existing authorized, persistent workflow."""

from datetime import datetime
from fastapi import Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from .auth import allowed_case_ids, review_case_ids
from .models import (
    Application,
    Assignment,
    ApplicationDraft,
    Revision,
    Institution,
    PortalCaseRecord,
    PortalInstitutionProfile,
    Document,
    DocumentVersion,
    Clarification,
    ClarificationResponse,
    ResponseLineage,
    ClarificationResolution,
    ReportRequest,
    ReportPublication,
    ReportSnapshot,
    OfficerAction,
    ReviewState,
    ApplicationTimeline,
    User,
    SubmissionReceipt,
)
from .portal_documents import document_description
from .processing import job_view, previewable
from .officer_service import touch_review, action, priority
from .reports import report_view

STATUS = {
    "DRAFT": "Draft",
    "SUBMITTED": "Submitted",
    "UNDER_REVIEW": "Under Scrutiny",
    "CLARIFICATION_REQUESTED": "Deficiency Raised",
    "PENDING_VERIFICATION": "Verification Pending",
    "INSPECTION_RECOMMENDED": "Inspection Recommended",
    "REVIEW_COMPLETED": "Review Completed",
}


def reference_for(case, record=None):
    return record.reference if record else f"UV-{case.academic_year[:4]}-{case.id[:12].upper()}"


def case_row(db, case):
    record = db.get(PortalCaseRecord, case.id)
    extra = record.payload if record else {}
    draft = db.get(ApplicationDraft, case.id)
    revision = (
        db.get(Revision, draft.revision_id)
        if draft
        else db.scalar(
            select(Revision).where(Revision.application_id == case.id).order_by(Revision.number.desc())
        )
    )
    declared = draft.details if draft else revision.manifest.get("details", {}) if revision else {}
    inst = db.get(Institution, case.institution_id)
    profile = db.get(PortalInstitutionProfile, inst.id)
    details = {
        **extra.get("details", {}),
        "programme": declared.get("programme", extra.get("details", {}).get("programme", "")),
        "principal": declared.get("signatory", extra.get("details", {}).get("principal", "")),
        "address": declared.get("proposed_address", extra.get("details", {}).get("address", "")),
    }
    courses = declared.get("courses", [])
    if courses:
        details.update(
            course=", ".join(c["course"] for c in courses), intake=sum(c["requested_intake"] for c in courses)
        )
    for old, new in [
        ("landArea", "land_area_acres"),
        ("builtUpArea", "built_up_area_m2"),
        ("facultyCount", "faculty_count"),
    ]:
        if declared.get(new) is not None:
            details[old] = declared[new]
    outcome = extra.get("decision") if case.status == "REVIEW_COMPLETED" else None
    return {
        "id": case.id,
        "reference": reference_for(case, record),
        "institution": {
            "id": inst.id,
            "name": inst.name,
            "aicteId": inst.permanent_id,
            **(profile.payload if profile else {}),
        },
        "type": case.category,
        "academicYear": case.academic_year,
        "status": outcome["decision"] if outcome else STATUS.get(case.status, case.status),
        "state": case.status,
        "details": details,
        "decision": outcome,
        "recommendation": extra.get("recommendation"),
        "inspection": extra.get("inspection"),
        "assignedOfficer": db.scalar(
            select(User.name)
            .join(Assignment, Assignment.user_id == User.id)
            .where(Assignment.application_id == case.id, Assignment.scope.in_(["REVIEW", "SUPERVISE"]))
            .order_by(Assignment.scope)
        )
        or extra.get("assignedOfficer"),
        "submittedOn": extra.get("submittedOn")
        or (
            datetime.fromtimestamp(revision.submitted_at).isoformat()
            if revision and revision.submitted_at
            else None
        ),
        "createdOn": extra.get("createdOn") or datetime.fromtimestamp(case.created_at).isoformat(),
        "reviewVersion": db.get(ReviewState, case.id).version if db.get(ReviewState, case.id) else None,
    }


def case_detail(db, case, p):
    result = case_row(db, case)
    record = db.get(PortalCaseRecord, case.id)
    extra = record.payload if record else {}
    versions = db.scalars(
        select(DocumentVersion)
        .where(DocumentVersion.application_id == case.id)
        .order_by(DocumentVersion.number.desc(), DocumentVersion.created_at.desc())
    ).all()
    selected = {}
    for v in versions:
        doc = db.get(Document, v.document_id)
        if doc.document_type not in selected:
            selected[doc.document_type] = (doc, v)
    reviews = extra.get("document_reviews", {})
    documents = []
    for kind, (doc, v) in selected.items():
        title, description = document_description(kind)
        manual = reviews.get(v.id, {})
        processing = job_view(db, v)
        documents.append(
            {
                "id": doc.id,
                "versionId": v.id,
                "version": v.number,
                "name": title,
                "description": description,
                "type": kind,
                "fileName": v.original_name,
                "uploadedOn": v.created_at,
                "status": manual.get("status", "Awaiting review"),
                "reviewer": manual.get("reviewer"),
                "reviewedOn": manual.get("reviewed_on"),
                "findings": manual.get("finding", ""),
                "processingState": processing["state"],
                "previewable": previewable(db, v),
                "sha256": v.sha256,
            }
        )
    draft = db.get(ApplicationDraft, case.id)
    if draft:
        from .institution_service import checklist_view

        for requirement in checklist_view(db, case, draft)["items"]:
            kind = requirement["acceptable_alternatives"][0]
            if kind not in selected:
                title, description = document_description(kind)
                documents.append(
                    {
                        "id": requirement["id"],
                        "name": title,
                        "description": description,
                        "type": kind,
                        "status": "Not required"
                        if requirement["applicability"] in {"NOT_APPLICABLE", "NOT_DUE"}
                        else "Not uploaded",
                        "mandatory": requirement["mandatory"],
                        "applicability": requirement["applicability"],
                        "versionId": None,
                    }
                )
    result["documents"] = documents
    events = db.scalars(
        select(ApplicationTimeline)
        .where(ApplicationTimeline.application_id == case.id)
        .order_by(ApplicationTimeline.created_at, ApplicationTimeline.id)
    ).all()
    result["history"] = [
        {
            "id": e.id,
            "action": e.event_type.replace("_", " ").title(),
            "remark": e.summary,
            "at": e.payload.get("recorded_at") or datetime.fromtimestamp(e.created_at).isoformat(),
            "by": e.payload.get("recorded_by") or (db.get(User, e.actor_id).name if e.actor_id else "System"),
        }
        for e in events
    ]
    result["history"].sort(key=lambda e: e["at"])
    requests = db.scalars(
        select(Clarification)
        .where(Clarification.application_id == case.id, Clarification.published.is_(True))
        .order_by(Clarification.created_at.desc())
    ).all()
    result["queries"] = []
    for q in requests:
        responses = db.scalars(
            select(ClarificationResponse).where(ClarificationResponse.request_id == q.id)
        ).all()
        answers = []
        for r in responses:
            evidence = db.scalars(
                select(DocumentVersion).where(DocumentVersion.revision_id == r.revision_id)
            ).all()
            lineage = db.get(ResponseLineage, r.id)
            answers.append(
                {
                    "id": r.id,
                    "explanation": r.explanation,
                    "submittedAt": r.created_at,
                    "receipt": lineage.receipt if lineage else {},
                    "documents": [
                        {
                            "id": v.document_id,
                            "versionId": v.id,
                            "version": v.number,
                            "fileName": v.original_name,
                            "previewable": previewable(db, v),
                        }
                        for v in evidence
                    ],
                }
            )
        closed = db.scalar(
            select(ClarificationResolution.id).where(ClarificationResolution.request_id == q.id)
        )
        result["queries"].append(
            {
                "id": q.id,
                "message": q.message,
                "raisedOn": q.created_at,
                "dueOn": q.allowed_until,
                "status": "Closed" if closed else "Responded" if responses else "Open",
                "responses": answers,
            }
        )
    actions = db.scalars(
        select(OfficerAction)
        .where(OfficerAction.revision_id.in_(select(Revision.id).where(Revision.application_id == case.id)))
        .order_by(OfficerAction.created_at.desc())
    ).all()
    institution = bool(p.roles.intersection({"institution_admin", "institution_submitter"}))
    result["actions"] = [
        {
            "id": a.id,
            "action": a.action,
            "reason": a.rationale,
            "at": a.created_at,
            "by": db.get(User, a.actor_id).name,
        }
        for a in actions
        if not institution or a.publishable
    ]
    if not institution:
        result["priority"] = priority(db, case)
        result["reports"] = [
            report_view(db, r)
            for r in db.scalars(
                select(ReportRequest)
                .where(
                    ReportRequest.revision_id.in_(
                        select(Revision.id).where(Revision.application_id == case.id)
                    )
                )
                .order_by(ReportRequest.created_at.desc())
            )
        ]
    else:
        result["reports"] = []
        for pub in db.scalars(
            select(ReportPublication).where(
                ReportPublication.snapshot_id.in_(
                    select(ReportSnapshot.id).where(
                        ReportSnapshot.revision_id.in_(
                            select(Revision.id).where(Revision.application_id == case.id)
                        )
                    )
                )
            )
        ):
            result["reports"].append(
                {
                    "id": pub.id,
                    "state": "READY",
                    "download_url": f"/api/v1/applications/{case.id}/published-reports/{pub.id}/download",
                    "message": pub.manifest.get("rationale", "Published review summary"),
                }
            )
    result["receipt"] = (
        db.scalar(select(SubmissionReceipt).where(SubmissionReceipt.application_id == case.id)).payload
        if db.scalar(select(SubmissionReceipt).where(SubmissionReceipt.application_id == case.id))
        else None
    )
    return result


class DocumentReview(BaseModel):
    expected_version: int = Field(ge=1)
    version_id: str = Field(max_length=64)
    status: str = Field(pattern="^(Reviewed|Correction required|Awaiting review)$")
    reason: str = Field(min_length=10, max_length=2000)


class InspectionRecord(BaseModel):
    expected_version: int = Field(ge=1)
    date: str = Field(min_length=10, max_length=30)
    inspector: str = Field(min_length=3, max_length=160)
    observations: str = Field(min_length=10, max_length=2000)
    recommendation: str = Field(min_length=5, max_length=2000)


def install_restored_portal(app, *, db_session, principal, require_case, require_roles, envelope):
    @app.get("/api/v1/portal/applications")
    def applications(request: Request, p=Depends(principal), db=Depends(db_session)):
        require_roles(p, {"institution_admin", "institution_submitter", "officer", "supervisor"})
        cases = db.scalars(
            select(Application)
            .where(Application.id.in_(allowed_case_ids(db, p)))
            .order_by(Application.created_at.desc())
        ).all()
        cases = [c for c in cases if db.get(PortalCaseRecord, c.id) or db.get(ApplicationDraft, c.id)]
        items = [case_row(db, c) for c in cases]
        items.sort(key=lambda r: r["createdOn"], reverse=True)
        return envelope(request, items)

    @app.get("/api/v1/portal/applications/{case_id}")
    def details(case_id: str, request: Request, p=Depends(principal), db=Depends(db_session)):
        require_roles(p, {"institution_admin", "institution_submitter", "officer", "supervisor"})
        return envelope(request, case_detail(db, require_case(db, p, case_id, request), p))

    @app.get("/api/v1/portal/track/{reference:path}")
    def track(reference: str, request: Request, db=Depends(db_session)):
        import re

        if len(reference) > 100 or not re.fullmatch(r"[A-Za-z0-9/\-]+", reference):
            raise HTTPException(404, "Check the full application ID or reference and try again.")
        record = db.scalar(
            select(PortalCaseRecord).where(func.upper(PortalCaseRecord.reference) == reference.upper())
        )
        case = db.get(Application, record.id if record else reference.upper())
        if not case:
            match = re.fullmatch(r"UV-\d{4}-([A-F0-9-]{8,12})", reference.upper())
            if match:
                case = db.scalar(
                    select(Application).where(
                        func.upper(Application.id).like(match[1] + "%"), Application.status != "DRAFT"
                    )
                )
        if not case or case.status == "DRAFT":
            raise HTTPException(404, "No submitted application matches this reference.")
        row = case_row(db, case)
        # Public tracking deliberately excludes institution identity, personal details and evidence.
        return envelope(request, {k: row[k] for k in ["id", "reference", "type", "academicYear", "status"]})

    @app.post("/api/v1/portal/applications/{case_id}/document-review")
    def review_document(
        case_id: str, body: DocumentReview, request: Request, p=Depends(principal), db=Depends(db_session)
    ):
        require_roles(p, {"officer", "supervisor"})
        case = require_case(db, p, case_id, request, "review")
        if case.id not in set(db.scalars(review_case_ids(db, p))):
            raise HTTPException(404, "Case unavailable for review.")
        version = db.get(DocumentVersion, body.version_id)
        if not version or version.application_id != case.id:
            raise HTTPException(404, "Document unavailable in this case.")
        touch_review(db, case, body.expected_version, allow_completed=True)
        record = db.get(PortalCaseRecord, case.id)
        if not record:
            record = PortalCaseRecord(id=case.id, reference=reference_for(case), payload={})
            db.add(record)
        record.payload = {
            **record.payload,
            "document_reviews": {
                **record.payload.get("document_reviews", {}),
                version.id: {
                    "status": body.status,
                    "reviewer": p.user.name,
                    "reviewed_on": datetime.now().isoformat(),
                    "finding": body.reason,
                    "document_type": db.get(Document, version.document_id).document_type,
                },
            },
        }
        action(
            db,
            p,
            case,
            "DOCUMENT_REVIEW",
            body.reason,
            request.state.request_id,
            {"version_id": version.id, "status": body.status},
            True,
        )
        db.commit()
        return envelope(request, case_detail(db, case, p))

    @app.post("/api/v1/portal/applications/{case_id}/inspection")
    def inspection(
        case_id: str, body: InspectionRecord, request: Request, p=Depends(principal), db=Depends(db_session)
    ):
        require_roles(p, {"officer", "supervisor"})
        case = require_case(db, p, case_id, request, "inspection")
        if case.id not in set(db.scalars(review_case_ids(db, p))):
            raise HTTPException(404, "Case unavailable for review.")
        touch_review(db, case, body.expected_version, allow_completed=True)
        record = db.get(PortalCaseRecord, case.id)
        if not record:
            record = PortalCaseRecord(id=case.id, reference=reference_for(case), payload={})
            db.add(record)
        record.payload = {**record.payload, "inspection": body.model_dump(exclude={"expected_version"})}
        action(
            db,
            p,
            case,
            "INSPECTION_RECORDED",
            body.observations,
            request.state.request_id,
            body.model_dump(exclude={"expected_version"}),
            True,
        )
        db.commit()
        return envelope(request, case_detail(db, case, p))
