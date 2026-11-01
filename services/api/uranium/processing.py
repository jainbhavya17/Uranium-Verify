"""Persistent queue with leased claims, bounded attempts and immutable observations."""

import re
import time
from pathlib import Path

from fastapi import HTTPException
from sqlalchemy import select, update

from .audit import append_audit
from .models import (
    Document,
    DocumentVersion,
    EvidenceNode,
    EvidenceEdge,
    ExtractedField,
    ProcessingJob,
    ProcessingEvent,
    ProcessingResult,
    ResultField,
    UploadAttempt,
)
from .processing_config import PROCESSOR
from .processing_sandbox import extract_isolated
from .scanner import scanner_for

MESSAGES = {
    "FILE_INTEGRITY": "Stored bytes no longer match the immutable original hash. Processing stopped; contact the local administrator.",
    "SCANNER_UNAVAILABLE": "Malware scanner unavailable. File remains quarantined; retry after service recovery.",
    "MALWARE_DETECTED": "Safety validation rejected this file. Replace it with a safe original.",
    "UNSAFE_CONTENT": "Active or embedded PDF content is unsupported. Export a flattened original and reupload.",
    "ENCRYPTED_PDF": "Password-protected/encrypted PDF is unsupported. Upload an authorized unencrypted copy.",
    "CORRUPT_FILE": "File cannot be decoded reliably. Export a new readable copy.",
    "PAGE_LIMIT": "PDF exceeds the configured 50-page engineering budget.",
    "RESOURCE_LIMIT": "File exceeded worker time, memory, decoding or output budgets.",
    "OCR_UNAVAILABLE": "OCR executable or configured language unavailable. Retry after OCR setup.",
    "LOW_QUALITY": "Text is unreadable or marginal. Reupload a clearer scan (prefer 200–300 DPI) or request manual review.",
    "TYPE_UNCERTAIN": "Document type could not be classified reliably. Check the selected slot or request manual review.",
    "INTERRUPTED": "Worker interrupted; a bounded retry is required.",
    "PROCESSING_FAILED": "Processing failed. Retry or replace the file; previous versions remain available.",
}
STATE_MESSAGES = {
    "UPLOADED": "Original is queued for the document worker; processing has not started.",
    "REPROCESSING": "A bounded reprocessing attempt is queued.",
    "SAFETY_SCANNING": "The worker is running the configured malware scanner. No clean result is claimed yet.",
    "QUALITY_ASSESSMENT": "The worker is assessing readability and supported content.",
    "QUEUED": "Safety validation finished; extraction is queued.",
    "PROCESSING": "The worker is performing bounded local text/OCR extraction.",
    "PROCESSED": "The processed result and source references are saved.",
}


def inspect_transport(content, filename, mime, policy):
    clean = re.sub(r"[^\w. ()-]", "_", Path(filename.replace("\\", "/")).name)[:150]
    ext = Path(clean).suffix.lower()
    allowed = {".pdf": "application/pdf", ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg"}
    actual = (
        "application/pdf"
        if content.startswith(b"%PDF-")
        else "image/png"
        if content.startswith(b"\x89PNG\r\n\x1a\n")
        else "image/jpeg"
        if content.startswith(b"\xff\xd8\xff")
        else "unknown"
    )
    if ext not in allowed or allowed[ext] != actual or mime.split(";")[0].strip() != actual:
        raise HTTPException(
            415, "Only matching PDF/PNG/JPEG extension, MIME and file signatures are allowed."
        )
    if len(content) > (policy.pdf_bytes if ext == ".pdf" else policy.image_bytes):
        raise HTTPException(413, "File exceeds the configured engineering byte limit.")
    return clean, actual


def latest_job(db, version_id):
    return db.scalar(
        select(ProcessingJob)
        .where(ProcessingJob.version_id == version_id)
        .order_by(ProcessingJob.attempt.desc())
        .limit(1)
    )


def result_for(db, job):
    return db.scalar(select(ProcessingResult).where(ProcessingResult.job_id == job.id)) if job else None


def accepted(db, version):
    if version.status == "SYNTHETIC_FIXTURE" and version.is_mock:
        return True
    job = latest_job(db, version.id)
    return bool(job and job.state == "PROCESSED" and job.scan_status == "CLEAN" and result_for(db, job))


def previewable(db, version):
    if version.status == "SYNTHETIC_FIXTURE" and version.is_mock:
        return True
    job = latest_job(db, version.id)
    return bool(job and job.scan_status == "CLEAN" and result_for(db, job))


def event(db, job, state, code=""):
    job.state, job.code, job.updated_at = state, code, int(time.time())
    db.add(ProcessingEvent(job_id=job.id, state=state, code=code))


def enqueue(db, version, reprocess=False):
    old = latest_job(db, version.id)
    if old and not reprocess:
        return old
    if old and (
        old.attempt >= 3
        or old.state
        in {"UPLOADED", "SAFETY_SCANNING", "QUEUED", "PROCESSING", "QUALITY_ASSESSMENT", "REPROCESSING"}
    ):
        raise HTTPException(
            409, "Job already active or retry budget exhausted. Replace the file if necessary."
        )
    job = ProcessingJob(
        version_id=version.id,
        attempt=old.attempt + 1 if old else 1,
        state="REPROCESSING" if old else "UPLOADED",
        processor_version=PROCESSOR,
    )
    db.add(job)
    db.flush()
    for state in ["REPROCESSING"] if old else ["UPLOADING", "UPLOADED"]:
        db.add(ProcessingEvent(job_id=job.id, state=state, code=""))
    return job


def job_view(db, version, attempt=None):
    job = (
        db.scalar(
            select(ProcessingJob).where(
                ProcessingJob.version_id == version.id, ProcessingJob.attempt == attempt
            )
        )
        if attempt
        else latest_job(db, version.id)
    )
    if not job:
        return {
            "version_id": version.id,
            "state": version.status,
            "events": [],
            "fields": [],
            "pages": [],
            "accepted": accepted(db, version),
            "message": (
                "Sample attachment; automated extraction has not been run."
                if version.is_mock
                else "This file has not been processed. Upload it again to run safety and readability checks."
            ),
        }
    result = result_for(db, job)
    fields = (
        db.scalars(
            select(ExtractedField)
            .join(ResultField, ResultField.field_id == ExtractedField.id)
            .where(ResultField.result_id == result.id)
            .order_by(ExtractedField.page, ExtractedField.id)
        ).all()
        if result
        else []
    )
    # Explicit institution-safe projection. Never serialize scanner stdout or arbitrary findings.
    return {
        "id": job.id,
        "version_id": version.id,
        "state": job.state,
        "attempt": job.attempt,
        "processor_version": job.processor_version,
        "engine_versions": result.payload.get("libraries", {}) if result else {},
        "updated_at": job.updated_at,
        "scan_status": job.scan_status,
        "scanner_mode": job.scanner_mode,
        "accepted": accepted(db, version),
        "message": MESSAGES.get(job.code, STATE_MESSAGES.get(job.state, "")),
        "events": [
            {"state": e.state, "at": e.created_at}
            for e in db.scalars(
                select(ProcessingEvent)
                .where(ProcessingEvent.job_id == job.id)
                .order_by(ProcessingEvent.created_at, ProcessingEvent.id)
            ).all()
        ],
        "result_id": result.id if result else None,
        "pages": result.payload["pages"] if result else [],
        "unknown_fields": result.payload["unknown_fields"] if result else [],
        "fields": [
            {
                "id": f.id,
                "version_id": version.id,
                "page": f.page,
                "key": f.field_key,
                "raw": f.value["raw"],
                "normalized": f.value["normalized"],
                "uncertainty": f.value["uncertainty"],
                "bbox": f.bounding_box,
                "confidence": f.confidence,
                "method": f.value["method"],
                "extracted_at": f.created_at,
            }
            for f in fields
        ],
    }


def run_one(factory, storage, policy):
    """One claim per invocation. Compare-and-swap prevents two workers processing a lease."""
    now = int(time.time())
    with factory() as db:
        for upload in db.scalars(
            select(UploadAttempt).where(
                UploadAttempt.state == "UPLOADING", UploadAttempt.created_at < now - 300
            )
        ):
            upload.state = "UPLOAD_FAILED"
        for expired in db.scalars(
            select(ProcessingJob).where(ProcessingJob.lease_until > 0, ProcessingJob.lease_until < now)
        ).all():
            event(db, expired, "PROCESSING_FAILED", "INTERRUPTED")
            expired.lease_until = 0
        db.commit()
        job = db.scalar(
            select(ProcessingJob)
            .where(ProcessingJob.state.in_(["UPLOADED", "REPROCESSING"]))
            .order_by(ProcessingJob.created_at, ProcessingJob.id)
            .limit(1)
        )
        if not job:
            return False
        claimed = db.execute(
            update(ProcessingJob)
            .where(ProcessingJob.id == job.id, ProcessingJob.state.in_(["UPLOADED", "REPROCESSING"]))
            .values(state="SAFETY_SCANNING", lease_until=now + policy.timeout + 90)
        )
        if claimed.rowcount != 1:
            db.rollback()
            return True
        db.add(ProcessingEvent(job_id=job.id, state="SAFETY_SCANNING", code=""))
        version = db.get(DocumentVersion, job.version_id)
        path = storage.path(version.storage_key)
        identifier = job.id
        db.commit()
    outcome = scanner_for(policy).scan(path)
    with factory() as db:
        job = db.get(ProcessingJob, identifier)
        job.scanner_mode, job.scan_status = outcome.mode, outcome.status
        if outcome.status != "CLEAN":
            event(
                db,
                job,
                "NEEDS_REUPLOAD" if outcome.status == "INFECTED" else "SAFETY_UNAVAILABLE",
                "MALWARE_DETECTED" if outcome.status == "INFECTED" else "SCANNER_UNAVAILABLE",
            )
            job.lease_until = 0
            from .notifications import processing_notice

            processing_notice(db, job, version)
            db.commit()
            return True
        event(db, job, "QUALITY_ASSESSMENT")
        event(db, job, "QUEUED")
        event(db, job, "PROCESSING")
        db.commit()
    # Safety structure, quality and extraction all execute inside the resource-limited process.
    result = extract_isolated(path, policy, version.sha256)
    with factory() as db:
        job = db.get(ProcessingJob, identifier)
        version = db.get(DocumentVersion, job.version_id)
        if result.get("ok"):
            doc = db.get(Document, version.document_id)
            saved = ProcessingResult(
                job_id=job.id, payload={k: v for k, v in result.items() if k not in {"fields", "ok"}}
            )
            db.add(saved)
            db.flush()
            root = EvidenceNode(
                revision_id=version.revision_id,
                kind="DOCUMENT_VERSION",
                reference={"version_id": version.id, "sha256": version.sha256, "result_id": saved.id},
            )
            db.add(root)
            db.flush()
            for f in result["fields"]:
                field = ExtractedField(
                    version_id=version.id,
                    page=f["page"],
                    field_key=f["field_key"],
                    value={k: f[k] for k in ["raw", "normalized", "method", "uncertainty"]},
                    bounding_box=f["bbox"],
                    confidence=f["confidence"],
                    processor_version=PROCESSOR,
                )
                db.add(field)
                db.flush()
                db.add(ResultField(result_id=saved.id, field_id=field.id))
                node = EvidenceNode(
                    revision_id=version.revision_id,
                    kind="EXTRACTED_FIELD",
                    reference={
                        "version_id": version.id,
                        "field_id": field.id,
                        "result_id": saved.id,
                        "page": field.page,
                        "bbox": field.bounding_box,
                    },
                )
                db.add(node)
                db.flush()
                db.add(
                    EvidenceEdge(
                        revision_id=version.revision_id,
                        from_node=root.id,
                        to_node=node.id,
                        relationship="SUPPORTS",
                    )
                )
            if result["quality"] != "READABLE":
                event(
                    db,
                    job,
                    "MANUAL_REVIEW" if result["quality"] == "MARGINAL" else "NEEDS_REUPLOAD",
                    "LOW_QUALITY",
                )
            elif doc.document_type not in result["detected_types"]:
                event(db, job, "MANUAL_REVIEW", "TYPE_UNCERTAIN")
            else:
                event(db, job, "PROCESSED")
        else:
            code = result.get("code", "PROCESSING_FAILED")
            event(
                db,
                job,
                "PROCESSING_FAILED"
                if code in {"OCR_UNAVAILABLE", "PROCESSING_FAILED", "RESOURCE_LIMIT"}
                else "NEEDS_REUPLOAD",
                code,
            )
        job.lease_until = 0
        # Result fingerprint invalidates prechecks even without mutating a frozen revision.
        append_audit(
            db, None, "DOCUMENT_PROCESSED", version.id, job.id, {"state": job.state, "processor": PROCESSOR}
        )
        from .notifications import processing_notice

        processing_notice(db, job, version)
        db.commit()
    return True


def worker_loop(factory, storage, policy, stop):
    while not stop.is_set():
        try:
            worked = run_one(factory, storage, policy)
        except Exception:
            # No private exception strings. Lease recovery exposes interrupted jobs.
            worked = False
        stop.wait(0.2 if worked else 1)
