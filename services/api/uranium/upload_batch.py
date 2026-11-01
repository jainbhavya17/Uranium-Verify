"""Bounded multipart transport: at most ten files, per-part and aggregate byte caps."""

import asyncio
import hashlib

from fastapi import Depends, Header, HTTPException, Query, Request
from starlette.formparsers import MultiPartParser, MultiPartException

from .audit import append_audit
from .contracts import Envelope
from .institution_service import attach_workflow, idempotent, workflow_draft
from .models import ApplicationRequirement, RequirementSnapshot, UploadAttempt, DocumentVersion
from .processing import inspect_transport, enqueue


class BoundedMultipart(MultiPartParser):
    def __init__(self, headers, stream, policy):
        super().__init__(headers, stream, max_files=policy.files, max_fields=0, max_part_size=8192)
        self.policy = policy

    def on_part_begin(self):
        super().on_part_begin()
        self.part_bytes = 0
        self.header_bytes = 0

    def on_part_data(self, data, start, end):
        self.part_bytes += end - start
        file = self._current_part.file
        limit = (
            self.policy.pdf_bytes
            if file and file.content_type == "application/pdf"
            else self.policy.image_bytes
        )
        if self.part_bytes > limit:
            raise MultiPartException("File exceeds its engineering byte budget.")
        super().on_part_data(data, start, end)

    def header_budget(self, start, end):
        self.header_bytes += end - start
        if self.header_bytes > 8192:
            raise MultiPartException("File metadata exceeds its bounded header budget.")

    def on_header_field(self, data, start, end):
        self.header_budget(start, end)
        super().on_header_field(data, start, end)

    def on_header_value(self, data, start, end):
        self.header_budget(start, end)
        super().on_header_value(data, start, end)


def install_batch_api(app, *, db_session, principal, require_case, institution_write, envelope, storage):
    from .processing_api import UploadView

    policy = app.state.processing_policy

    @app.post(
        "/api/v1/applications/{case_id}/documents/batch",
        response_model=Envelope[list[UploadView]],
        openapi_extra={
            "requestBody": {
                "required": True,
                "content": {
                    "multipart/form-data": {
                        "schema": {
                            "type": "object",
                            "required": ["files"],
                            "properties": {
                                "files": {
                                    "type": "array",
                                    "minItems": 1,
                                    "maxItems": 10,
                                    "items": {"type": "string", "format": "binary"},
                                }
                            },
                        }
                    }
                },
            }
        },
    )
    async def batch(
        case_id: str,
        request: Request,
        requirement_id: str = Query(max_length=64),
        document_type: str = Query(max_length=64),
        expected_version: int = Query(ge=1),
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
        if case.status != "DRAFT":
            raise HTTPException(409, "Submitted evidence is immutable.")
        if not request.headers.get("content-type", "").lower().startswith("multipart/form-data;"):
            raise HTTPException(415, "Batch upload requires multipart file parts.")
        attempt = UploadAttempt(application_id=case.id, actor_id=p.user.id, state="UPLOADING")
        db.add(attempt)
        db.commit()
        total = 0

        async def bounded_stream():
            nonlocal total
            async for chunk in request.stream():
                total += len(chunk)
                if total > policy.files * max(policy.pdf_bytes, policy.image_bytes) + 65536:
                    raise MultiPartException("Request exceeds its aggregate byte budget.")
                yield chunk

        form = None
        try:
            async with asyncio.timeout(60):
                form = await BoundedMultipart(request.headers, bounded_stream(), policy).parse()
            files = form.getlist("files")
            if not files or len(files) != len(form.multi_items()):
                raise HTTPException(422, "Provide one to ten file parts named files.")
            metadata = []
            # Validate ALL transport metadata before any evidence write. Spooled file
            # bodies are read one at a time, bounded by the per-part stream cap.
            for file in files:
                content = await file.read()
                clean, mime = inspect_transport(content, file.filename or "", file.content_type or "", policy)
                metadata.append(
                    {"filename": clean, "mime": mime, "sha256": hashlib.sha256(content).hexdigest()}
                )
                await file.seek(0)
            payload = {
                "expected_version": expected_version,
                "requirement_id": requirement_id,
                "document_type": document_type,
                "files": metadata,
            }

            def execute(_):
                results = []
                for index, (file, meta) in enumerate(zip(files, metadata, strict=True)):
                    attached = attach_workflow(
                        db,
                        p,
                        case,
                        expected_version + index,
                        requirement_id,
                        document_type,
                        file.file.read(),
                        meta["filename"],
                        False,
                        storage,
                        request.state.request_id,
                        media_type=meta["mime"],
                    )
                    job = enqueue(db, db.get(DocumentVersion, attached["version_id"]))
                    results.append({**attached, "status": job.state, "job_id": job.id})
                return results

            result = idempotent(db, p, f"UPLOAD_BATCH:{case_id}", idempotency_key, payload, execute)
            attempt.state, attempt.bytes_received, attempt.version_id = (
                "UPLOADED",
                total,
                result[-1]["version_id"],
            )
            db.commit()
            return envelope(request, result)
        except Exception as exc:
            db.rollback()
            attempt = db.get(UploadAttempt, attempt.id)
            attempt.state, attempt.bytes_received = "UPLOAD_FAILED", total
            append_audit(db, p.user.id, "UPLOAD_FAILED", case.id, request.state.request_id)
            db.commit()
            if isinstance(exc, MultiPartException):
                raise HTTPException(
                    413, "Multipart file-count, metadata or byte budget exceeded; no file was accepted."
                )
            if isinstance(exc, TimeoutError):
                raise HTTPException(408, "Batch byte stream timed out.")
            raise
        finally:
            if form:
                await form.close()
