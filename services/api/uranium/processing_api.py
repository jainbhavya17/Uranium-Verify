import hashlib
import asyncio
from typing import Literal

from fastapi import Depends, Header, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import select

from .audit import append_audit
from .contracts import Envelope
from .institution_contracts import StrictModel, AttachmentView
from .institution_service import attach_workflow, idempotent, touch, workflow_draft
from .models import (
    DocumentVersion,
    ProcessingEvent,
    ApplicationRequirement,
    RequirementSnapshot,
    UploadAttempt,
    Document,
)
from .processing import enqueue, inspect_transport, job_view, latest_job


class ProcessingFieldView(BaseModel):
    id: str
    version_id: str
    page: int
    key: str
    raw: str
    normalized: str | None
    uncertainty: str
    bbox: list[float]
    confidence: float | None
    method: str
    extracted_at: int


class UploadView(AttachmentView):
    job_id: str


class UploadPolicyView(BaseModel):
    pdf_bytes: int
    image_bytes: int
    max_files: int
    max_pages: int
    preferred_dpi: list[int]
    minimum_guidance_dpi: int
    engineering_limits: Literal[True]
    scanner_mode: str
    language: str


class ProcessingView(BaseModel):
    id: str | None = None
    version_id: str
    state: str
    attempt: int = 0
    processor_version: str | None = None
    engine_versions: dict[str, str] = {}
    updated_at: int | None = None
    scanner_mode: str | None = None
    scan_status: str | None = None
    accepted: bool
    message: str
    result_id: str | None = None
    events: list[dict]
    pages: list[dict]
    fields: list[ProcessingFieldView]
    unknown_fields: list[str] = []


class RetryBody(StrictModel):
    expected_version: int = Field(ge=1)


class ManualReviewBody(RetryBody):
    action: Literal["REQUEST_REVIEW"] = "REQUEST_REVIEW"


def install_processing_api(app, *, db_session, principal, require_case, institution_write, envelope, storage):
    policy = app.state.processing_policy
    from .upload_batch import install_batch_api

    install_batch_api(
        app,
        db_session=db_session,
        principal=principal,
        require_case=require_case,
        institution_write=institution_write,
        envelope=envelope,
        storage=storage,
    )

    @app.get("/api/v1/processing/policy", response_model=Envelope[UploadPolicyView])
    def upload_policy(request: Request, p=Depends(principal)):
        return envelope(
            request,
            {
                "pdf_bytes": policy.pdf_bytes,
                "image_bytes": policy.image_bytes,
                "max_files": policy.files,
                "max_pages": policy.pages,
                "preferred_dpi": [200, 300],
                "minimum_guidance_dpi": 150,
                "engineering_limits": True,
                "scanner_mode": policy.scanner,
                "language": policy.language,
            },
        )

    @app.post("/api/v1/applications/{case_id}/documents/upload", response_model=Envelope[UploadView])
    async def upload(
        case_id: str,
        request: Request,
        requirement_id: str = Query(max_length=64),
        document_type: str = Query(max_length=64),
        expected_version: int = Query(ge=1),
        filename: str = Query(max_length=200),
        idempotency_key: str | None = Header(None),
        p=Depends(principal),
        db=Depends(db_session),
    ):
        case = require_case(db, p, case_id, request, "evidence")
        institution_write(db, p, case.institution_id)
        draft = workflow_draft(db, case)
        slot = db.get(RequirementSnapshot, requirement_id)
        requirement = db.get(ApplicationRequirement, requirement_id)
        if not slot or not slot.active or not requirement or requirement.revision_id != draft.revision_id:
            raise HTTPException(404, "Document slot unavailable in this revision.")
        # This endpoint accepts exactly ONE file/request. The UI batch cap is ten, sent as
        # sequential one-file requests with refreshed CAS versions; no multipart parser/spooling.
        limit = policy.pdf_bytes if filename.lower().endswith(".pdf") else policy.image_bytes
        if case.status != "DRAFT":
            raise HTTPException(409, "Submitted evidence is immutable.")
        content = bytearray()
        attempt = UploadAttempt(application_id=case.id, actor_id=p.user.id, state="UPLOADING")
        db.add(attempt)
        db.commit()
        try:
            async with asyncio.timeout(60):
                async for chunk in request.stream():
                    if len(content) + len(chunk) > limit:
                        raise HTTPException(413, "File exceeds the configured engineering byte limit.")
                    content.extend(chunk)
            clean, mime = inspect_transport(
                content, filename, request.headers.get("content-type", ""), policy
            )
        except Exception as exc:
            attempt.state = "UPLOAD_FAILED"
            attempt.bytes_received = len(content)
            append_audit(db, p.user.id, "UPLOAD_FAILED", case.id, request.state.request_id)
            db.commit()
            if isinstance(exc, TimeoutError):
                raise HTTPException(408, "Upload byte stream timed out. Retry with a stable connection.")
            raise
        payload = {
            "expected_version": expected_version,
            "requirement_id": requirement_id,
            "document_type": document_type,
            "filename": clean,
            "mime": mime,
            "sha256": hashlib.sha256(content).hexdigest(),
        }

        def execute(_):
            selected = db.get(DocumentVersion, slot.selected_version_id) if slot.selected_version_id else None
            if (
                selected
                and selected.sha256 == payload["sha256"]
                and db.get(Document, selected.document_id).document_type == document_type
            ):
                if draft.lock_version != expected_version:
                    raise HTTPException(409, "Draft changed. Refresh before retrying upload.")
                job = latest_job(db, selected.id)
                if job:
                    return {
                        "version_id": selected.id,
                        "document_id": selected.document_id,
                        "number": selected.number,
                        "application_version": draft.lock_version,
                        "is_mock": selected.is_mock,
                        "job_id": job.id,
                        "status": job.state,
                    }
            result = attach_workflow(
                db,
                p,
                case,
                expected_version,
                requirement_id,
                document_type,
                bytes(content),
                clean,
                False,
                storage,
                request.state.request_id,
                media_type=mime,
            )
            version = db.get(DocumentVersion, result["version_id"])
            job = enqueue(db, version)
            return {**result, "job_id": job.id, "status": job.state}

        try:
            result = idempotent(db, p, f"UPLOAD:{case_id}", idempotency_key, payload, execute)
            attempt.state, attempt.bytes_received, attempt.version_id = (
                "UPLOADED",
                len(content),
                result["version_id"],
            )
            db.commit()
            return envelope(request, result)
        except Exception:
            db.rollback()
            attempt = db.get(UploadAttempt, attempt.id)
            attempt.state, attempt.bytes_received = "UPLOAD_FAILED", len(content)
            db.commit()
            raise

    @app.get("/api/v1/applications/{case_id}/upload-attempts", response_model=Envelope[list[dict]])
    def attempts(case_id: str, request: Request, p=Depends(principal), db=Depends(db_session)):
        require_case(db, p, case_id, request, "evidence")
        return envelope(
            request,
            [
                {
                    "id": r.id,
                    "state": r.state,
                    "at": r.created_at,
                    "bytes_received": r.bytes_received,
                    "version_id": r.version_id,
                }
                for r in db.scalars(
                    select(UploadAttempt)
                    .where(UploadAttempt.application_id == case_id)
                    .order_by(UploadAttempt.created_at.desc(), UploadAttempt.id)
                    .limit(30)
                )
            ],
        )

    def authorized(db, p, case_id, version_id, request, write=False):
        case = require_case(db, p, case_id, request, "evidence")
        version = db.get(DocumentVersion, version_id)
        if not version or version.application_id != case.id:
            raise HTTPException(404, "Record unavailable in your authorized scope.")
        if write:
            institution_write(db, p, case.institution_id)
        return case, version

    @app.get(
        "/api/v1/applications/{case_id}/documents/{version_id}/processing",
        response_model=Envelope[ProcessingView],
    )
    def processing(
        case_id: str,
        version_id: str,
        request: Request,
        attempt: int | None = Query(default=None, ge=1, le=3),
        p=Depends(principal),
        db=Depends(db_session),
    ):
        _, version = authorized(db, p, case_id, version_id, request)
        return envelope(request, job_view(db, version, attempt))

    @app.post(
        "/api/v1/applications/{case_id}/documents/{version_id}/retry", response_model=Envelope[ProcessingView]
    )
    def retry(
        case_id: str,
        version_id: str,
        body: RetryBody,
        request: Request,
        idempotency_key: str | None = Header(None),
        p=Depends(principal),
        db=Depends(db_session),
    ):
        case, version = authorized(db, p, case_id, version_id, request, True)
        if version.media_type not in {"application/pdf", "image/png", "image/jpeg"}:
            raise HTTPException(
                409, "Reupload legacy quarantine bytes using the validated Phase 3 transport."
            )

        def execute(_):
            draft = touch(db, case, body.expected_version)
            if version.revision_id != draft.revision_id:
                raise HTTPException(409, "Only current draft originals can be reprocessed.")
            enqueue(db, version, True)
            append_audit(db, p.user.id, "REPROCESSING_REQUESTED", version.id, request.state.request_id)
            return job_view(db, version)

        return envelope(
            request, idempotent(db, p, f"RETRY:{version_id}", idempotency_key, body.model_dump(), execute)
        )

    @app.post(
        "/api/v1/applications/{case_id}/documents/{version_id}/manual-review", response_model=Envelope[dict]
    )
    def manual(
        case_id: str,
        version_id: str,
        body: ManualReviewBody,
        request: Request,
        p=Depends(principal),
        db=Depends(db_session),
    ):
        case, version = authorized(db, p, case_id, version_id, request, True)
        job = latest_job(db, version.id)
        if not job or job.state != "MANUAL_REVIEW":
            raise HTTPException(
                409, "Only marginal readable/type-uncertain files support a manual-review request."
            )
        touch(db, case, body.expected_version)
        if not db.scalar(
            select(ProcessingEvent.id).where(
                ProcessingEvent.job_id == job.id, ProcessingEvent.code == "REVIEW_REQUESTED"
            )
        ):
            db.add(ProcessingEvent(job_id=job.id, state="MANUAL_REVIEW", code="REVIEW_REQUESTED"))
            append_audit(db, p.user.id, "MANUAL_REVIEW_REQUESTED", version.id, request.state.request_id)
        db.commit()
        return envelope(
            request,
            {
                "requested": True,
                "accepted": False,
                "message": "Manual review requested. An assigned officer can inspect the private original and record a sourced correction. A clearer processed replacement is required for automatic submission acceptance.",
            },
        )
