"""Focused response revisions; frozen applications and old evidence are never edited."""

import copy
import hashlib
import secrets
from time import time
from fastapi import HTTPException
from sqlalchemy import select, update, func
from .models import (
    Application,
    Clarification,
    ClarificationScope,
    ResponseDraft,
    Revision,
    ClarificationResponse,
    ResponseLineage,
    ClarificationResolution,
    DocumentVersion,
    Document,
    ReviewState,
    CourseIntake,
    RoomRecord,
    RoomEvidence,
    ApplicationTimeline,
    OutboxEvent,
    Claim,
)
from .audit import append_audit
from .institution_contracts import DraftDetails
from .processing import accepted, job_view, previewable
from .institution_service import fingerprint


def published(db, p, identifier):
    row = db.get(Clarification, identifier)
    case = db.get(Application, row.application_id) if row else None
    if not row or not row.published or not case or case.institution_id not in p.institution_ids:
        raise HTTPException(404, "Published clarification unavailable in your institution.")
    return row, case


def open_window(db, row, case):
    if db.scalar(select(ClarificationResolution.id).where(ClarificationResolution.request_id == row.id)):
        raise HTTPException(409, "This request was reviewed or withdrawn. Its history remains read-only.")
    if db.scalar(select(ClarificationResponse.id).where(ClarificationResponse.request_id == row.id)):
        raise HTTPException(
            409, "A response has already been submitted. The saved receipt remains available."
        )
    if row.allowed_until <= int(time()) or case.status != "CLARIFICATION_REQUESTED":
        raise HTTPException(409, "The response window is closed. Contact the assigned officer.")
    scope = db.get(ClarificationScope, row.id)
    if not scope:
        raise HTTPException(
            409, "Legacy request has no correction policy. The officer must publish a scoped request."
        )
    return scope


def touch_response(db, row, case, expected):
    scope = open_window(db, row, case)
    draft = db.get(ResponseDraft, row.id)
    if not draft:
        raise HTTPException(409, "Start a response before editing.")
    result = db.execute(
        update(ResponseDraft)
        .where(ResponseDraft.id == row.id, ResponseDraft.version == expected)
        .values(version=expected + 1)
        .execution_options(synchronize_session="fetch")
    )
    if result.rowcount != 1:
        raise HTTPException(409, "The response changed in another tab. Reload before saving.")
    return scope, draft


def begin_response(db, p, row, case, request_id):
    scope = open_window(db, row, case)
    draft = db.get(ResponseDraft, row.id)
    if not draft:
        parent = db.get(Revision, scope.original_revision_id)
        number = db.scalar(select(func.max(Revision.number)).where(Revision.application_id == case.id)) or 0
        revision = Revision(
            application_id=case.id,
            number=number + 1,
            actor_id=p.user.id,
            ruleset_id=parent.ruleset_id,
            frozen=False,
            manifest={"parent_revision_id": parent.id, "clarification_id": row.id},
        )
        db.add(revision)
        db.flush()
        draft = ResponseDraft(id=row.id, revision_id=revision.id)
        db.add(draft)
        append_audit(db, p.user.id, "RESPONSE_STARTED", row.id, request_id)
        db.flush()
    return response_view(db, row, case)


def response_view(db, row, case):
    scope = db.get(ClarificationScope, row.id)
    draft = db.get(ResponseDraft, row.id)
    responses = db.scalars(
        select(ClarificationResponse)
        .where(ClarificationResponse.request_id == row.id)
        .order_by(ClarificationResponse.created_at, ClarificationResponse.id)
    ).all()
    original = db.get(Revision, scope.original_revision_id) if scope else None
    prior_ids = original.manifest.get("document_version_ids") if original else []
    if prior_ids is None:
        prior_ids = list(
            db.scalars(select(DocumentVersion.id).where(DocumentVersion.revision_id == original.id))
        )
    prior_versions = [db.get(DocumentVersion, identifier) for identifier in prior_ids]
    response_revision_id = draft.revision_id if draft else responses[-1].revision_id if responses else None
    versions = (
        db.scalars(
            select(DocumentVersion)
            .where(DocumentVersion.revision_id == response_revision_id)
            .order_by(DocumentVersion.created_at, DocumentVersion.id)
        ).all()
        if response_revision_id
        else []
    )
    return {
        "id": row.id,
        "application_id": case.id,
        "message": row.message,
        "published_at": row.created_at,
        "deadline": row.allowed_until,
        "is_mock": case.is_mock,
        "allowed_fields": scope.allowed_fields if scope else [],
        "document_types": scope.document_types if scope else [],
        "required_documents": scope.required_documents if scope else [],
        "original_revision_id": original.id if original else None,
        "original": original.manifest.get("details", {}) if original else {},
        "prior_version_ids": prior_ids,
        "original_evidence": [
            {
                "id": v.id,
                "document_id": v.document_id,
                "number": v.number,
                "name": v.original_name,
                "sha256": v.sha256,
                "type": db.get(Document, v.document_id).document_type,
                "previewable": previewable(db, v),
            }
            for v in prior_versions
            if v and v.application_id == case.id
        ],
        "draft": {
            "version": draft.version,
            "revision_id": draft.revision_id,
            "changes": draft.changes,
            "explanation": draft.explanation,
            "selected": draft.selected,
        }
        if draft
        else None,
        "documents": [
            {
                "id": v.id,
                "document_id": v.document_id,
                "number": v.number,
                "name": v.original_name,
                "type": db.get(Document, v.document_id).document_type,
                "sha256": v.sha256,
                "processing": job_view(db, v),
                "previewable": previewable(db, v),
            }
            for v in versions
        ],
        "responses": [
            {
                "id": r.id,
                "revision_id": r.revision_id,
                "explanation": r.explanation,
                "at": r.created_at,
                "receipt": db.get(ResponseLineage, r.id).receipt if db.get(ResponseLineage, r.id) else None,
            }
            for r in responses
        ],
        "closed": bool(
            db.scalar(select(ClarificationResolution.id).where(ClarificationResolution.request_id == row.id))
        ),
        "can_respond": bool(
            scope
            and not responses
            and row.allowed_until > int(time())
            and case.status == "CLARIFICATION_REQUESTED"
        ),
    }


def save_response(db, p, row, case, body, request_id):
    scope, draft = touch_response(db, row, case, body.expected_version)
    if set(body.changes) - set(scope.allowed_fields):
        raise HTTPException(422, "Only the fields explicitly requested by the officer may change.")
    parent = db.get(Revision, scope.original_revision_id)
    DraftDetails.model_validate({**parent.manifest.get("details", {}), **body.changes})
    draft.changes, draft.explanation = body.changes, body.explanation
    append_audit(db, p.user.id, "RESPONSE_SAVED", row.id, request_id, {"version": draft.version})
    db.flush()
    return response_view(db, row, case)


def attach_response(db, p, row, case, expected, kind, content, name, mime, storage, request_id):
    scope, draft = touch_response(db, row, case, expected)
    if kind not in scope.document_types:
        raise HTTPException(422, "This document type is outside the published correction scope.")
    doc = db.scalar(
        select(Document)
        .where(Document.application_id == case.id, Document.document_type == kind)
        .order_by(Document.created_at, Document.id)
        .limit(1)
    )
    if not doc:
        doc = Document(application_id=case.id, document_type=kind)
        db.add(doc)
        db.flush()
    count = db.scalar(
        select(func.count())
        .select_from(DocumentVersion)
        .where(DocumentVersion.revision_id == draft.revision_id)
    )
    if count >= 10:
        raise HTTPException(
            409, "A response supports ten evidence versions. Ask for a new scoped request if needed."
        )
    number = (
        db.scalar(select(func.max(DocumentVersion.number)).where(DocumentVersion.document_id == doc.id)) or 0
    ) + 1
    key = secrets.token_hex(32)
    storage.write_once(key, content)
    v = DocumentVersion(
        document_id=doc.id,
        application_id=case.id,
        revision_id=draft.revision_id,
        number=number,
        sha256=hashlib.sha256(content).hexdigest(),
        storage_key=key,
        original_name=name,
        media_type=mime,
        uploader_id=p.user.id,
        status="QUARANTINED_PENDING_SAFETY",
        is_mock=case.is_mock,
    )
    db.add(v)
    db.flush()
    from .processing import enqueue

    job = enqueue(db, v)
    draft.selected = {**draft.selected, kind: v.id}
    append_audit(db, p.user.id, "RESPONSE_EVIDENCE_UPLOADED", v.id, request_id)
    return {"version_id": v.id, "job_id": job.id, "response_version": draft.version, "state": job.state}


def submit_response(db, p, row, case, body, request_id):
    scope, draft = touch_response(db, row, case, body.expected_version)
    if len(draft.explanation.strip()) < 10:
        raise HTTPException(422, "Provide an explanation of at least ten characters.")
    if set(scope.required_documents) - set(draft.selected):
        raise HTTPException(409, "Supply every document required by the published request.")
    for kind, identifier in draft.selected.items():
        v = db.get(DocumentVersion, identifier)
        if not v or v.revision_id != draft.revision_id or not accepted(db, v):
            raise HTTPException(
                409, "All selected response evidence must finish safety validation and processing."
            )
        # Date/identity problems remain human findings, never silently change an official history.
    parent = db.get(Revision, scope.original_revision_id)
    revision = db.get(Revision, draft.revision_id)
    manifest = copy.deepcopy(parent.manifest)
    prior_ids = parent.manifest.get("document_version_ids")
    legacy_recovery = prior_ids is None
    if prior_ids is None:
        prior_ids = list(
            db.scalars(select(DocumentVersion.id).where(DocumentVersion.revision_id == parent.id))
        )
    active_ids = []
    for identifier in prior_ids:
        original = db.get(DocumentVersion, identifier)
        if original and db.get(Document, original.document_id).document_type not in draft.selected:
            active_ids.append(identifier)
    details = DraftDetails.model_validate({**manifest.get("details", {}), **draft.changes}).model_dump(
        mode="json"
    )
    manifest.update(
        {
            "revision_id": revision.id,
            "parent_revision_id": parent.id,
            "clarification_id": row.id,
            "details": details,
            "response_changes": draft.changes,
            "response_explanation": draft.explanation,
            "response_documents": draft.selected,
            "document_version_ids": list(dict.fromkeys(active_ids + list(draft.selected.values()))),
            "prior_document_version_ids": prior_ids,
            "legacy_manifest_evidence_recovery": legacy_recovery,
        }
    )
    for course in db.scalars(select(CourseIntake).where(CourseIntake.revision_id == parent.id)):
        db.add(
            CourseIntake(
                revision_id=revision.id,
                programme=course.programme,
                course=course.course,
                approved_intake=course.approved_intake,
                requested_intake=course.requested_intake,
            )
        )
    for room in db.scalars(select(RoomRecord).where(RoomRecord.revision_id == parent.id)):
        carried = RoomRecord(
            revision_id=revision.id,
            room_code=room.room_code,
            room_type=room.room_type,
            declared_area=room.declared_area,
        )
        db.add(carried)
        db.flush()
        for evidence in db.scalars(
            select(RoomEvidence)
            .where(RoomEvidence.room_id == room.id)
            .order_by(RoomEvidence.created_at, RoomEvidence.id)
        ):
            db.add(
                RoomEvidence(
                    room_id=carried.id,
                    version_id=evidence.version_id,
                    page=evidence.page,
                    bbox=evidence.bbox,
                    certified_area=evidence.certified_area,
                    actor_id=evidence.actor_id,
                    source_ref="Carried from " + evidence.id + ": " + evidence.source_ref[:200],
                    reliable=evidence.reliable,
                )
            )
    for key, value in details.items():
        db.add(
            Claim(
                revision_id=revision.id,
                field_key=key,
                value={"declared": value, "parent_revision_id": parent.id},
            )
        )
    revision.manifest, revision.frozen, revision.submitted_at = manifest, True, int(time())
    response = ClarificationResponse(
        request_id=row.id, revision_id=revision.id, actor_id=p.user.id, explanation=draft.explanation
    )
    db.add(response)
    db.flush()
    receipt = {
        "response_id": response.id,
        "request_id": row.id,
        "application_id": case.id,
        "revision_id": revision.id,
        "parent_revision_id": parent.id,
        "submitted_at": revision.submitted_at,
        "manifest_sha256": fingerprint(manifest),
        "is_mock": case.is_mock,
    }
    db.add(ResponseLineage(id=response.id, original_revision_id=parent.id, receipt=receipt))
    state = db.get(ReviewState, case.id)
    if state:
        state.version += 1
        state.revision_id = revision.id
        state.latest_evaluation_id = None
    case.status = "UNDER_REVIEW"
    db.add(
        ApplicationTimeline(
            application_id=case.id,
            actor_id=p.user.id,
            event_key="response:" + response.id,
            event_type="CLARIFICATION_RESPONSE_SUBMITTED",
            summary="Institution response submitted; awaiting human review.",
            payload=receipt,
        )
    )
    db.add(
        OutboxEvent(
            deduplication_key="response:" + response.id,
            event_type="CLARIFICATION_RESPONDED",
            payload={"application_id": case.id, "request_id": row.id},
        )
    )
    append_audit(db, p.user.id, "CLARIFICATION_RESPONSE_SUBMITTED", response.id, request_id, receipt)
    return receipt
