"""Immutable, attributed review snapshots rendered by the local worker."""

import hashlib
import io
import json
import secrets
import time
from html import escape
from sqlalchemy import select, update, func
from .models import (
    ReportRequest,
    ReportJob,
    ReportSnapshot,
    ReportPublication,
    Revision,
    ReviewState,
    Finding,
    OfficerAction,
    RuleRun,
    DocumentVersion,
    Clarification,
    ClarificationResponse,
    Institution,
    User,
    OutboxEvent,
    ApprovalSnapshot,
)
from .audit import append_audit


def capture_report(db, row, case, state):
    revision = db.get(Revision, row.revision_id)
    evaluation = state.latest_evaluation_id
    baseline = (
        db.get(ApprovalSnapshot, revision.manifest.get("baseline_snapshot_id"))
        if revision.manifest.get("baseline_snapshot_id")
        else None
    )
    runs = db.scalars(select(RuleRun).where(RuleRun.evaluation_id == evaluation)).all() if evaluation else []
    findings = (
        db.scalars(select(Finding).where(Finding.evaluation_id == evaluation)).all() if evaluation else []
    )
    actions = db.scalars(
        select(OfficerAction)
        .where(OfficerAction.revision_id == revision.id)
        .order_by(OfficerAction.created_at, OfficerAction.id)
    ).all()
    versions = db.scalars(select(DocumentVersion).where(DocumentVersion.application_id == case.id)).all()
    manifest = {
        "schema": "URANIUM_REVIEW_REPORT_V1",
        "application_id": case.id,
        "revision_id": revision.id,
        "revision_number": revision.number,
        "captured_at": int(time.time()),
        "review_version": state.version,
        "institution": db.get(Institution, case.institution_id).name,
        "academic_year": case.academic_year,
        "category": case.category,
        "status": case.status,
        "is_mock": case.is_mock,
        "official_decision": False,
        "requested": revision.manifest.get("details", {}),
        "approved_history": baseline.payload if baseline else None,
        "reviewer": {"id": row.actor_id, "name": db.get(User, row.actor_id).name},
        "rationale": row.payload["rationale"],
        "rule_results": [{"id": r.id, "at": r.created_at, **r.payload} for r in runs],
        "machine_findings": [
            {
                "id": f.id,
                "method": f.method,
                "at": f.created_at,
                "evidence_node_id": f.evidence_node_id,
                "evidence_gap": f.evidence_gap,
                **f.payload,
            }
            for f in findings
        ],
        "human_actions": [
            {
                "id": a.id,
                "actor_id": a.actor_id,
                "action": a.action,
                "at": a.created_at,
                "rationale": a.rationale,
                "published": a.publishable,
            }
            for a in actions
        ],
        "evidence": [
            {
                "id": v.id,
                "revision_id": v.revision_id,
                "name": v.original_name,
                "sha256": v.sha256,
                "number": v.number,
                "is_mock": v.is_mock,
            }
            for v in versions
        ],
        "clarifications": [
            {
                "id": c.id,
                "message": c.message,
                "deadline": c.allowed_until,
                "responses": [
                    {"id": r.id, "revision_id": r.revision_id, "explanation": r.explanation}
                    for r in db.scalars(
                        select(ClarificationResponse).where(ClarificationResponse.request_id == c.id)
                    )
                ],
            }
            for c in db.scalars(
                select(Clarification).where(
                    Clarification.application_id == case.id, Clarification.published.is_(True)
                )
            )
        ],
        "limitations": [
            "Preliminary human review only; no regulatory approval or rejection.",
            "Synthetic sources/issuer fixtures are MOCK; no live official verification is implied.",
            "Selected deterministic rules only. Missing/no-signal evidence is inconclusive.",
            "This snapshot preserves the saved inputs at capture time; later case changes make it stale.",
        ],
    }
    db.add(ReportJob(id=row.id, input_version=state.version, manifest=manifest))


def report_view(db, row):
    job = db.get(ReportJob, row.id)
    revision = db.get(Revision, row.revision_id)
    state = db.get(ReviewState, revision.application_id)
    latest = db.scalar(
        select(func.max(Revision.number)).where(
            Revision.application_id == revision.application_id, Revision.frozen.is_(True)
        )
    )
    snapshot = db.get(ReportSnapshot, job.snapshot_id) if job and job.snapshot_id else None
    stale = bool(job and ((state and state.version != job.input_version) or latest != revision.number))
    publication = (
        db.scalar(select(ReportPublication.id).where(ReportPublication.snapshot_id == snapshot.id))
        if snapshot
        else None
    )
    return {
        "id": row.id,
        "application_id": revision.application_id,
        "revision_id": revision.id,
        "created_at": row.created_at,
        "state": "STALE" if snapshot and stale else row.state,
        "generation_state": row.state,
        "stale": stale,
        "attempt": job.attempt if job else 0,
        "code": job.code if job else "LEGACY_REGENERATE",
        "snapshot_id": snapshot.id if snapshot else None,
        "version": snapshot.version if snapshot else None,
        "sha256": snapshot.manifest.get("pdf_sha256") if snapshot else None,
        "payload": row.payload,
        "download_url": f"/api/v1/reports/{row.id}/download" if snapshot else None,
        "publication_id": publication,
    }


def render_report(manifest, version):
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, KeepTogether

    stream = io.BytesIO()
    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            name="ReportBody",
            fontName="Helvetica",
            fontSize=9,
            leading=13,
            spaceAfter=5,
            wordWrap="CJK",
            allowWidows=0,
            allowOrphans=0,
        )
    )
    styles["Heading1"].textColor = colors.HexColor("#153946")
    styles["Heading1"].keepWithNext = True
    styles["Heading2"].keepWithNext = True
    document = SimpleDocTemplate(
        stream,
        pagesize=(595.28, 841.89),
        rightMargin=44,
        leftMargin=44,
        topMargin=55,
        bottomMargin=48,
        title="URANIUM VERIFY preliminary review",
        author="URANIUM VERIFY local review service",
    )
    story = []

    def para(text, style="ReportBody"):
        story.append(Paragraph(escape(str(text)).replace("\n", "<br/>"), styles[style]))

    def detail(label, value):
        if label in {"Captured At", "At"} and isinstance(value, (int, float)):
            from datetime import datetime, timezone

            value = datetime.fromtimestamp(value, timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        para(
            label
            + ": "
            + (
                json.dumps(value, ensure_ascii=True, sort_keys=True)
                if isinstance(value, (dict, list))
                else str(value)
            )
        )

    para("URANIUM VERIFY", "Title")
    para("PRELIMINARY REVIEW SNAPSHOT", "Heading1")
    para(
        "MOCK / SYNTHETIC DEMONSTRATION"
        if manifest["is_mock"]
        else "HUMAN REVIEW - NOT AN OFFICIAL DECISION",
        "Heading2",
    )
    for key in [
        "institution",
        "application_id",
        "academic_year",
        "category",
        "revision_number",
        "revision_id",
        "status",
        "captured_at",
    ]:
        detail(key.replace("_", " ").title(), manifest[key])
    detail("Report version", version)
    detail("Reviewer", manifest["reviewer"])
    detail("Reviewer rationale", manifest["rationale"])
    para("Approved history and requested values", "Heading1")
    detail("Approved baseline", manifest["approved_history"])
    detail("Requested", manifest["requested"])
    para("Deterministic machine findings and saved rule operands", "Heading1")
    if not manifest["rule_results"]:
        para(
            "Private machine-review detail is excluded from this institution-published summary."
            if manifest.get("visibility") == "INSTITUTION_PUBLISHED_SUMMARY"
            else "No saved applicable rule evaluation was captured. This is an explicit evidence gap, not a passed check."
        )
    for r in manifest["rule_results"]:
        for k in [
            "rule_code",
            "rule_version",
            "state",
            "room_code",
            "declared_m2",
            "certified_m2",
            "minimum_m2",
            "mismatch",
            "deficiency",
            "reason",
            "version_id",
            "page",
            "bbox",
            "clause",
            "printed_page",
            "pdf_page",
            "source_url",
            "source_checksum",
            "at",
        ]:
            if k in r:
                detail(k.replace("_", " ").title(), r[k])
        story.append(Spacer(1, 10))
    for f in manifest["machine_findings"]:
        detail(
            "Machine finding",
            {k: f.get(k) for k in ["id", "message", "method", "at", "evidence_node_id", "evidence_gap"]},
        )
    para("Attributed human actions - separate from machine results", "Heading1")
    for a in manifest["human_actions"]:
        detail("Human action", a)
    if not manifest["human_actions"]:
        para(
            "Private human actions are excluded from this summary."
            if manifest.get("visibility") == "INSTITUTION_PUBLISHED_SUMMARY"
            else "No prior human action was captured."
        )
    para("Clarifications and retained response revisions", "Heading1")
    for c in manifest["clarifications"]:
        detail("Published request / responses", c)
    para("Original evidence manifest", "Heading1")
    for v in manifest["evidence"]:
        detail("Original version", {key: v[key] for key in ["id", "name", "number", "sha256", "is_mock"]})
    limitations_start = len(story)
    para("Limitations", "Heading1")
    for limitation in manifest["limitations"]:
        para(limitation)
    story[limitations_start:] = [KeepTogether(story[limitations_start:])]

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#445866"))
        canvas.drawString(44, 25, "URANIUM VERIFY | Private review snapshot | No official approval")
        canvas.drawRightString(551, 25, f"Page {doc.page}")
        canvas.restoreState()

    document.build(story, onFirstPage=footer, onLaterPages=footer)
    return stream.getvalue()


def run_report_one(factory, storage):
    now = int(time.time())
    with factory() as db:
        expired = db.scalars(
            select(ReportJob)
            .join(ReportRequest, ReportRequest.id == ReportJob.id)
            .where(
                ReportJob.snapshot_id.is_(None),
                ReportJob.lease_until < now,
                ReportRequest.state == "GENERATING",
            )
        ).all()
        for interrupted in expired:
            request = db.get(ReportRequest, interrupted.id)
            request.state = "FAILED" if interrupted.attempt >= 3 else "PENDING_GENERATION"
            interrupted.code = "INTERRUPTED"
            append_audit(
                db,
                None,
                "REPORT_LEASE_RECOVERED",
                request.id,
                "report-worker",
                {"attempt": interrupted.attempt},
            )
        db.commit()
        job = db.scalar(
            select(ReportJob)
            .join(ReportRequest, ReportRequest.id == ReportJob.id)
            .where(
                ReportJob.snapshot_id.is_(None),
                ReportJob.attempt < 3,
                ReportJob.lease_until < now,
                ReportRequest.state.in_(["PENDING_GENERATION", "GENERATING"]),
            )
            .order_by(ReportRequest.created_at, ReportRequest.id)
            .limit(1)
        )
        if not job:
            return False
        claimed = db.execute(
            update(ReportJob)
            .where(
                ReportJob.id == job.id,
                ReportJob.attempt == job.attempt,
                ReportJob.lease_until < now,
                ReportJob.snapshot_id.is_(None),
                ReportJob.id.in_(
                    select(ReportRequest.id).where(
                        ReportRequest.state.in_(["PENDING_GENERATION", "GENERATING"])
                    )
                ),
            )
            .values(attempt=job.attempt + 1, lease_until=now + 120)
        )
        if claimed.rowcount != 1:
            db.rollback()
            return False
        row = db.get(ReportRequest, job.id)
        row.state = "GENERATING"
        identifier, attempt, manifest, revision_id, actor = (
            job.id,
            job.attempt,
            job.manifest,
            row.revision_id,
            row.actor_id,
        )
        db.commit()
    try:
        with factory() as db:
            row = db.get(ReportRequest, identifier)
            job = db.scalar(select(ReportJob).where(ReportJob.id == identifier).with_for_update())
            if job.attempt != attempt or job.snapshot_id:
                return True
            # Serialize snapshot numbering for this revision on PostgreSQL; SQLite serializes the write.
            db.scalar(select(Revision).where(Revision.id == revision_id).with_for_update())
            number = (
                db.scalar(
                    select(func.max(ReportSnapshot.version)).where(ReportSnapshot.revision_id == revision_id)
                )
                or 0
            ) + 1
            content = render_report(manifest, number)
            key = secrets.token_hex(32)
            storage.write_once(key, content)
            snapshot = ReportSnapshot(
                revision_id=revision_id,
                reviewer_id=actor,
                version=number,
                storage_key=key,
                manifest={
                    **manifest,
                    "pdf_sha256": hashlib.sha256(content).hexdigest(),
                    "report_request_id": identifier,
                },
            )
            db.add(snapshot)
            db.flush()
            job.snapshot_id = snapshot.id
            job.lease_until = 0
            job.code = ""
            row.state = "READY"
            db.add(
                OutboxEvent(
                    deduplication_key="report:" + identifier,
                    event_type="REPORT_READY",
                    payload={
                        "application_id": manifest["application_id"],
                        "report_id": identifier,
                        "actor_id": actor,
                    },
                )
            )
            append_audit(
                db,
                actor,
                "REPORT_GENERATED",
                snapshot.id,
                identifier,
                {"sha256": snapshot.manifest["pdf_sha256"], "version": number},
            )
            db.commit()
    except Exception:
        with factory() as db:
            row = db.get(ReportRequest, identifier)
            job = db.get(ReportJob, identifier)
            if not job.snapshot_id:
                job.code = "RENDER_FAILED"
                job.lease_until = 0
                row.state = "FAILED"
                append_audit(
                    db, actor, "REPORT_GENERATION_FAILED", identifier, identifier, {"attempt": attempt}
                )
                db.commit()
    return True
