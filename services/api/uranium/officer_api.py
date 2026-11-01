import os
import time
from pathlib import Path

from fastapi import Depends, HTTPException, Header, Query, Request
from sqlalchemy import select, update
from .contracts import Envelope
from .audit import append_audit
from .institution_service import idempotent
from .models import (
    Application,
    Institution,
    ReviewState,
    Assignment,
    DocumentVersion,
    ExtractedField,
    ExtractionCorrection,
    EvidenceNode,
    EvidenceEdge,
    Finding,
    Evaluation,
    OfficerAction,
    RoomRecord,
    RoomEvidence,
    SpecialistTask,
    TaskResponse,
    GovernedVersion,
    ProvenanceResult,
    VerificationAttempt,
    ReportRequest,
    User,
    Membership,
    Connector,
    AuditEvent,
    InspectionTask,
)
from .officer_contracts import (
    ReviewCommand,
    PriorityCommand,
    CorrectionCommand,
    RoomCommand,
    TaskCommand,
    TaskReply,
    ReviewActionCommand,
    IssuerCommand,
    GovernanceDraft,
    GovernanceAction,
    RetrievalQuery,
    UserAccessCommand,
    ConnectorCommand,
    AssignmentCommand,
    FindingReviewCommand,
    GovernanceReason,
)
from .officer_service import (
    scoped_cases,
    officer_case,
    revision_for,
    review_view,
    priority,
    touch_review,
    action,
    correction,
    route_task,
    human_action,
)
from .processing import job_view, previewable
from .processing_sandbox import extract_isolated
from .compliance import evaluate_rules, context_for, dry_run
from .knowledge import retrieve
from .governance import governance_view, create_version, govern, access_change
from .issuer_gateway import verify


def install_officer_api(app, *, db_session, principal, envelope, case_view, require_roles, storage):
    def commit(request, db, data):
        db.commit()
        return envelope(request, data)

    @app.get("/api/v1/officer/routing-users", response_model=Envelope[list[dict]])
    def routing_users(request: Request, p=Depends(principal), db=Depends(db_session)):
        require_roles(p, {"officer", "supervisor"})
        users = db.scalars(
            select(User)
            .where(
                User.active.is_(True),
                User.id.in_(
                    select(Membership.user_id).where(
                        Membership.role_id.in_(["specialist", "supervisor", "officer"]),
                        (Membership.valid_until.is_(None)) | (Membership.valid_until > int(time.time())),
                    )
                ),
            )
            .order_by(User.name)
        ).all()
        return envelope(
            request,
            [
                {
                    "id": u.id,
                    "name": u.name,
                    "roles": db.scalars(
                        select(Membership.role_id).where(
                            Membership.user_id == u.id,
                            Membership.role_id.in_(["specialist", "supervisor", "officer"]),
                            (Membership.valid_until.is_(None)) | (Membership.valid_until > int(time.time())),
                        )
                    ).all(),
                }
                for u in users
            ],
        )

    @app.post("/api/v1/officer/cases/{case_id}/assignment", response_model=Envelope[dict])
    def reassign(
        case_id: str,
        body: AssignmentCommand,
        request: Request,
        idempotency_key: str | None = Header(None),
        p=Depends(principal),
        db=Depends(db_session),
    ):
        require_roles(p, {"supervisor"})
        case = officer_case(db, p, case_id, "review", True)

        def execute():
            target = db.get(User, body.assignee_id)
            if (
                not target
                or not target.active
                or not db.scalar(
                    select(Membership.id).where(
                        Membership.user_id == target.id,
                        Membership.role_id == "officer",
                        (Membership.valid_until.is_(None)) | (Membership.valid_until > int(time.time())),
                    )
                )
            ):
                raise HTTPException(422, "An active scrutiny officer is required.")
            touch_review(db, case, body.expected_version)
            for a in db.scalars(
                select(Assignment).where(Assignment.application_id == case.id, Assignment.scope == "REVIEW")
            ):
                a.active = False
            assigned = db.scalar(
                select(Assignment).where(
                    Assignment.application_id == case.id,
                    Assignment.user_id == target.id,
                    Assignment.scope == "REVIEW",
                )
            )
            if assigned:
                assigned.active = True
            else:
                db.add(Assignment(application_id=case.id, user_id=target.id, scope="REVIEW", active=True))
            action(
                db,
                p,
                case,
                "CASE_REASSIGNED",
                body.rationale,
                request.state.request_id,
                {"assignee_id": target.id},
            )
            return {"assignee_id": target.id, "case_id": case.id}

        return mutation(db, p, case, request, idempotency_key, body, "REASSIGN", execute)

    @app.get("/api/v1/governance/audit", response_model=Envelope[list[dict]])
    @app.get("/api/v1/governance/audit/export")
    def audit_records(
        request: Request,
        page: int = Query(1, ge=1),
        operation: str = Query("", max_length=100),
        actor_id: str = Query("", max_length=64),
        p=Depends(principal),
        db=Depends(db_session),
    ):
        require_roles(p, {"admin", "auditor"})
        query = select(AuditEvent)
        if operation:
            query = query.where(AuditEvent.operation == operation)
        if actor_id:
            query = query.where(AuditEvent.actor_id == actor_id)
        query = query.order_by(AuditEvent.created_at.desc(), AuditEvent.id)
        if request.url.path.endswith("export"):
            import csv
            import io
            from fastapi import Response

            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(["id", "actor_id", "operation", "target_id", "created_at", "metadata_digest"])
            for r in db.scalars(query.limit(2000)):
                values = [r.id, r.actor_id, r.operation, r.target_id, r.created_at, r.metadata_digest]
                writer.writerow(
                    [
                        ("'" + v if v and v[0] in "=+-@\t\r" else v) if isinstance(v, str) else v
                        for v in values
                    ]
                )
            append_audit(
                db,
                p.user.id,
                "AUDIT_EXPORTED",
                "filtered-metadata",
                request.state.request_id,
                {"operation": operation, "actor_id": actor_id},
            )
            db.commit()
            return Response(
                output.getvalue(),
                media_type="text/csv",
                headers={
                    "Content-Disposition": 'attachment; filename="uranium-audit-metadata.csv"',
                    "Cache-Control": "no-store",
                },
            )
        from sqlalchemy import func

        total = db.scalar(select(func.count()).select_from(query.subquery()))
        result = [
            {
                "id": r.id,
                "actor_id": r.actor_id,
                "operation": r.operation,
                "target_id": r.target_id,
                "created_at": r.created_at,
                "metadata_digest": r.metadata_digest,
            }
            for r in db.scalars(query.offset((page - 1) * 20).limit(20))
        ]
        return envelope(request, result, page=page, page_size=20, total=total)

    def mutation(db, p, case, request, key, body, kind, callback):
        return envelope(
            request,
            idempotent(db, p, f"{kind}:{case.id}", key, body.model_dump(mode="json"), lambda _: callback()),
        )

    @app.post("/api/v1/officer/cases/{case_id}/findings/{finding_id}/review", response_model=Envelope[dict])
    def finding_review(
        case_id: str,
        finding_id: str,
        body: FindingReviewCommand,
        request: Request,
        idempotency_key: str | None = Header(None),
        p=Depends(principal),
        db=Depends(db_session),
    ):
        case = officer_case(db, p, case_id, "review", True)
        finding = db.get(Finding, finding_id)
        evaluation = db.get(Evaluation, finding.evaluation_id) if finding else None
        if not evaluation or evaluation.revision_id != revision_for(db, case).id:
            raise HTTPException(404, "Finding unavailable in this revision.")

        def execute():
            touch_review(db, case, body.expected_version)
            if body.disposition == "RESOLVED" and not body.evidence_version_id:
                raise HTTPException(422, "Resolving a finding requires a saved evidence version.")
            if body.evidence_version_id:
                version = db.get(DocumentVersion, body.evidence_version_id)
                if not version or version.application_id != case.id or not previewable(db, version):
                    raise HTTPException(404, "Reviewed evidence unavailable.")
            row = action(
                db,
                p,
                case,
                "FINDING_REVIEW",
                body.rationale,
                request.state.request_id,
                {
                    "finding_id": finding.id,
                    "disposition": body.disposition,
                    "evidence_version_id": body.evidence_version_id,
                },
            )
            node = EvidenceNode(
                revision_id=evaluation.revision_id,
                kind="HUMAN_FINDING_REVIEW",
                reference={"action_id": row.id, "finding_id": finding.id, "disposition": body.disposition},
            )
            db.add(node)
            db.flush()
            if finding.evidence_node_id:
                db.add(
                    EvidenceEdge(
                        revision_id=evaluation.revision_id,
                        from_node=node.id,
                        to_node=finding.evidence_node_id,
                        relationship="VERIFIED_BY",
                    )
                )
            return {
                "action_id": row.id,
                "finding_id": finding.id,
                "disposition": body.disposition,
                "machine_result_preserved": True,
            }

        return mutation(db, p, case, request, idempotency_key, body, "FINDING_REVIEW:" + finding_id, execute)

    @app.get("/api/v1/officer/workload", response_model=Envelope[dict])
    @app.get("/api/v1/officer/queue", response_model=Envelope[list[dict]])
    def queue(
        request: Request,
        page: int = Query(1, ge=1),
        year: str | None = None,
        category: str | None = None,
        status: str | None = None,
        search: str = Query("", max_length=100),
        unassigned: bool = False,
        p=Depends(principal),
        db=Depends(db_session),
    ):
        if request.url.path.endswith("queue"):
            require_roles(p, {"officer", "supervisor"})
        q = scoped_cases(db, p, "read" if request.url.path.endswith("workload") else "review")
        if unassigned:
            require_roles(p, {"supervisor"})
            q = q.where(
                ~Application.id.in_(
                    select(Assignment.application_id).where(
                        Assignment.scope == "REVIEW", Assignment.active.is_(True)
                    )
                )
            )
        if year:
            q = q.where(Application.academic_year == year)
        if category:
            q = q.where(Application.category == category)
        if status:
            q = q.where(Application.status == status)
        if search:
            q = q.join(Institution).where(Institution.name.ilike("%" + search + "%"))
        cases = db.scalars(q.order_by(Application.created_at, Application.id)).all()
        rows = [
            {
                **case_view(db, c),
                "review": review_view(db, c),
                "priority": priority(db, c),
                "assignment_ids": db.scalars(
                    select(Assignment.user_id).where(
                        Assignment.application_id == c.id,
                        Assignment.scope == "REVIEW",
                        Assignment.active.is_(True),
                    )
                ).all(),
            }
            for c in cases
        ]
        rows.sort(key=lambda x: (-x["priority"]["score"], x["id"]))
        if request.url.path.endswith("workload"):
            return envelope(
                request,
                {
                    "assigned": len(rows),
                    "overdue": sum(r["review"]["due_at"] < int(time.time()) for r in rows),
                    "pending_verification": sum(r["status"] == "PENDING_VERIFICATION" for r in rows),
                    "cases": rows[:5],
                    "partial": True,
                    "limitation": "Issuer services may be MOCK/unavailable; workload does not imply verification.",
                },
            )
        return envelope(request, rows[(page - 1) * 20 : page * 20], page=page, page_size=20, total=len(rows))

    @app.get("/api/v1/officer/cases/{case_id}", response_model=Envelope[dict])
    def overview(case_id: str, request: Request, p=Depends(principal), db=Depends(db_session)):
        case = officer_case(db, p, case_id, "review")
        revision = revision_for(db, case)
        from .institution_service import state_view
        from .models import ApplicationDraft, ApplicationTimeline

        draft = state_view(db, case) if db.get(ApplicationDraft, case.id) else None
        evaluations = select(Evaluation.id).where(Evaluation.revision_id == revision.id)
        findings = db.scalars(select(Finding).where(Finding.evaluation_id.in_(evaluations))).all()
        versions = db.scalars(select(DocumentVersion).where(DocumentVersion.application_id == case.id)).all()
        from .processing import latest_job

        jobs = [latest_job(db, v.id) for v in versions]
        issuer_attempts = db.scalars(
            select(VerificationAttempt).where(VerificationAttempt.application_id == case.id)
        ).all()
        services = [
            {
                "service": "Safety/extraction",
                "state": "NO_EVIDENCE"
                if not versions
                else "MOCK_FIXTURES_NO_OCR"
                if not any(jobs)
                else "PARTIAL_OR_PROCESSING"
                if any(not j or j.state != "PROCESSED" for j in jobs)
                else "PROCESSED",
                "versions": [
                    {"version_id": v.id, "state": j.state if j else v.status}
                    for v, j in zip(versions, jobs, strict=True)
                ],
            },
            {
                "service": "Issuer gateway",
                "state": "NOT_RUN" if not issuer_attempts else "RECORDED_ATTEMPTS",
                "outcomes": [{"status": a.status, "mode": a.mode} for a in issuer_attempts],
            },
            {
                "service": "Rule evaluation",
                "state": "EVALUATED" if review_view(db, case)["latest_evaluation_id"] else "NOT_RUN",
            },
        ]
        return envelope(
            request,
            {
                "case": case_view(db, case),
                "revision_id": revision.id,
                "review": review_view(db, case),
                "priority": priority(db, case),
                "services": services,
                "requested": revision.manifest.get("details", {}),
                "workflow": draft,
                "findings": [
                    {
                        "id": f.id,
                        "evaluation_id": f.evaluation_id,
                        "method": f.method,
                        "visibility": f.visibility,
                        "payload": f.payload,
                        "evidence_node_id": f.evidence_node_id,
                        "evidence_gap": f.evidence_gap,
                    }
                    for f in findings
                ],
                "actions": [
                    {
                        "id": a.id,
                        "actor_id": a.actor_id,
                        "action": a.action,
                        "rationale": a.rationale,
                        "publishable": a.publishable,
                        "created_at": a.created_at,
                    }
                    for a in db.scalars(
                        select(OfficerAction)
                        .where(OfficerAction.revision_id == revision.id)
                        .order_by(OfficerAction.created_at, OfficerAction.id)
                    )
                ],
                "timeline": [
                    {"event_type": r.event_type, "summary": r.summary, "created_at": r.created_at}
                    for r in db.scalars(
                        select(ApplicationTimeline).where(ApplicationTimeline.application_id == case.id)
                    )
                ],
            },
        )

    @app.get("/api/v1/officer/cases/{case_id}/evidence", response_model=Envelope[dict])
    def evidence(case_id: str, request: Request, p=Depends(principal), db=Depends(db_session)):
        case = officer_case(db, p, case_id, "evidence")
        revision = revision_for(db, case)
        versions = db.scalars(
            select(DocumentVersion)
            .where(DocumentVersion.application_id == case.id)
            .order_by(DocumentVersion.document_id, DocumentVersion.number)
        ).all()
        fields = db.scalars(
            select(ExtractedField).where(ExtractedField.version_id.in_([v.id for v in versions]))
        ).all()
        corrections = db.scalars(
            select(ExtractionCorrection)
            .where(ExtractionCorrection.field_id.in_([f.id for f in fields]))
            .order_by(ExtractionCorrection.created_at, ExtractionCorrection.id)
        ).all()
        return envelope(
            request,
            {
                "review": review_view(db, case),
                "versions": [
                    {
                        "id": v.id,
                        "document_id": v.document_id,
                        "number": v.number,
                        "name": v.original_name,
                        "sha256": v.sha256,
                        "media_type": v.media_type,
                        "previewable": previewable(db, v),
                        "processing": job_view(db, v),
                    }
                    for v in versions
                ],
                "fields": [
                    {
                        "id": f.id,
                        "version_id": f.version_id,
                        "key": f.field_key,
                        "machine": f.value,
                        "page": f.page,
                        "bbox": f.bounding_box,
                        "confidence": f.confidence,
                    }
                    for f in fields
                ],
                "corrections": [
                    {
                        "id": c.id,
                        "field_id": c.field_id,
                        "value": c.corrected_value,
                        "rationale": c.rationale,
                        "actor_id": c.actor_id,
                        "created_at": c.created_at,
                    }
                    for c in corrections
                ],
                "nodes": [
                    {"id": n.id, "kind": n.kind, "reference": n.reference}
                    for n in db.scalars(select(EvidenceNode).where(EvidenceNode.revision_id == revision.id))
                ],
                "edges": [
                    {"id": e.id, "from": e.from_node, "to": e.to_node, "relationship": e.relationship}
                    for e in db.scalars(select(EvidenceEdge).where(EvidenceEdge.revision_id == revision.id))
                ],
            },
        )

    @app.get(
        "/api/v1/officer/cases/{case_id}/evidence/{version_id}/pages/{number}", response_model=Envelope[dict]
    )
    def page_image(
        case_id: str,
        version_id: str,
        number: int,
        request: Request,
        p=Depends(principal),
        db=Depends(db_session),
    ):
        officer_case(db, p, case_id, "evidence")
        v = db.get(DocumentVersion, version_id)
        if not v or v.application_id != case_id:
            raise HTTPException(404, "Evidence unavailable.")
        if not previewable(db, v):
            raise HTTPException(409, "Evidence remains quarantined.")
        result = extract_isolated(
            storage.path(v.storage_key),
            app.state.processing_policy,
            v.sha256,
            operation="render",
            options={"media_type": v.media_type, "page": number},
        )
        if not result.get("ok"):
            raise HTTPException(409, "Page cannot be rendered within resource limits.")
        append_audit(db, p.user.id, "OFFICER_PAGE_PREVIEW", v.id, request.state.request_id, {"page": number})
        return commit(request, db, result)

    @app.post("/api/v1/officer/cases/{case_id}/priority", response_model=Envelope[dict])
    def override(
        case_id: str,
        body: PriorityCommand,
        request: Request,
        idempotency_key: str | None = Header(None),
        p=Depends(principal),
        db=Depends(db_session),
    ):
        case = officer_case(db, p, case_id, "review", True)

        def execute():
            s = touch_review(db, case, body.expected_version)
            s.priority_override = body.priority
            s.priority_reason = body.rationale
            action(
                db,
                p,
                case,
                "PRIORITY_OVERRIDDEN",
                body.rationale,
                request.state.request_id,
                {"priority": body.priority},
            )
            return {"review": review_view(db, case), "priority": priority(db, case)}

        return mutation(db, p, case, request, idempotency_key, body, "PRIORITY", execute)

    @app.post("/api/v1/officer/cases/{case_id}/corrections", response_model=Envelope[dict])
    def correct(
        case_id: str,
        body: CorrectionCommand,
        request: Request,
        idempotency_key: str | None = Header(None),
        p=Depends(principal),
        db=Depends(db_session),
    ):
        case = officer_case(db, p, case_id, "review", True)
        return mutation(
            db,
            p,
            case,
            request,
            idempotency_key,
            body,
            "CORRECT",
            lambda: correction(db, p, case, body, request.state.request_id),
        )

    @app.post("/api/v1/officer/cases/{case_id}/tasks", response_model=Envelope[dict])
    def route(
        case_id: str,
        body: TaskCommand,
        request: Request,
        idempotency_key: str | None = Header(None),
        p=Depends(principal),
        db=Depends(db_session),
    ):
        case = officer_case(db, p, case_id, "review", True)
        return mutation(
            db,
            p,
            case,
            request,
            idempotency_key,
            body,
            "ROUTE",
            lambda: route_task(db, p, case, body, request.state.request_id),
        )

    @app.post("/api/v1/officer/cases/{case_id}/actions", response_model=Envelope[dict])
    def review_action(
        case_id: str,
        body: ReviewActionCommand,
        request: Request,
        idempotency_key: str | None = Header(None),
        p=Depends(principal),
        db=Depends(db_session),
    ):
        case = officer_case(db, p, case_id, "review", True)
        return mutation(
            db,
            p,
            case,
            request,
            idempotency_key,
            body,
            "REVIEW_ACTION",
            lambda: human_action(db, p, case, body, request.state.request_id),
        )

    @app.get("/api/v1/officer/tasks", response_model=Envelope[list[dict]])
    def tasks(request: Request, p=Depends(principal), db=Depends(db_session)):
        query = select(SpecialistTask).where(
            SpecialistTask.application_id.in_(scoped_cases(db, p).with_only_columns(Application.id))
        )
        if not p.roles & {"officer", "supervisor"}:
            query = query.where(SpecialistTask.assignee_id == p.user.id)
        return envelope(
            request,
            [
                {
                    "id": t.id,
                    "application_id": t.application_id,
                    "assignee_id": t.assignee_id,
                    "kind": t.kind,
                    "status": t.status,
                    "due_at": t.due_at,
                    "version": t.version,
                    "attempts": t.attempts,
                    "evidence": t.evidence,
                    "responses": [
                        {"actor_id": r.actor_id, "created_at": r.created_at, "payload": r.payload}
                        for r in db.scalars(select(TaskResponse).where(TaskResponse.task_id == t.id))
                    ],
                }
                for t in db.scalars(query.order_by(SpecialistTask.due_at, SpecialistTask.id))
            ],
        )

    @app.post("/api/v1/officer/tasks/{task_id}/response", response_model=Envelope[dict])
    def task_response(
        task_id: str,
        body: TaskReply,
        request: Request,
        idempotency_key: str | None = Header(None),
        p=Depends(principal),
        db=Depends(db_session),
    ):
        task = db.get(SpecialistTask, task_id)
        if not task:
            raise HTTPException(404, "Task unavailable.")
        case = officer_case(db, p, task.application_id)
        if task.assignee_id != p.user.id:
            raise HTTPException(403, "Only the routed assignee may respond.")

        def execute():
            if body.observed_at > int(time.time()) + 60:
                raise HTTPException(422, "Source observation time cannot be in the future.")
            result = db.execute(
                update(SpecialistTask)
                .where(
                    SpecialistTask.id == task.id,
                    SpecialistTask.version == body.expected_version,
                    SpecialistTask.attempts < 3,
                    SpecialistTask.status != "RESOLVED",
                )
                .values(
                    version=SpecialistTask.version + 1,
                    attempts=SpecialistTask.attempts + 1,
                    status="RESOLVED" if body.outcome in {"CONFIRMED", "CONFLICT"} else "PENDING_MANUAL",
                )
                .execution_options(synchronize_session="fetch")
            )
            if result.rowcount != 1:
                raise HTTPException(409, "Task changed, resolved, or retry budget exhausted.")
            db.add(TaskResponse(task_id=task.id, actor_id=p.user.id, payload=body.model_dump()))
            inspection = db.get(InspectionTask, task.id)
            if inspection:
                inspection.status = "COMPLETED" if task.status == "RESOLVED" else "PENDING_MANUAL"
            if (
                task.status == "RESOLVED"
                and not db.scalar(
                    select(SpecialistTask.id)
                    .where(SpecialistTask.application_id == case.id, SpecialistTask.status != "RESOLVED")
                    .limit(1)
                )
                and case.status in {"PENDING_VERIFICATION", "INSPECTION_RECOMMENDED"}
            ):
                case.status = "UNDER_REVIEW"
            action(
                db,
                p,
                case,
                "SPECIALIST_RESPONSE",
                body.rationale,
                request.state.request_id,
                {"task_id": task.id, "source_ref": body.source_ref, "outcome": body.outcome},
            )
            return {"status": task.status, "version": task.version, "attempts": task.attempts}

        return mutation(db, p, case, request, idempotency_key, body, "TASK_RESPONSE:" + task.id, execute)

    @app.get("/api/v1/officer/cases/{case_id}/compliance", response_model=Envelope[dict])
    def compliance(case_id: str, request: Request, p=Depends(principal), db=Depends(db_session)):
        from .models import RuleRun

        case = officer_case(db, p, case_id, "review")
        state = db.get(ReviewState, case.id)
        runs = (
            db.scalars(select(RuleRun).where(RuleRun.evaluation_id == state.latest_evaluation_id)).all()
            if state and state.latest_evaluation_id
            else []
        )
        return envelope(
            request,
            {
                "review": review_view(db, case),
                "context": context_for(db, case, state),
                "results": [{"id": r.id, "evaluation_id": r.evaluation_id, **r.payload} for r in runs],
                "findings": [
                    {"id": f.id, **f.payload}
                    for f in db.scalars(
                        select(Finding).where(Finding.evaluation_id == state.latest_evaluation_id)
                    )
                ]
                if state and state.latest_evaluation_id
                else [],
                "state": "EVALUATED" if state and state.latest_evaluation_id else "NOT_RUN",
                "limitation": "Only published, applicable rules in the limited source-reviewed demo pack are evaluated; no full regulatory approval is implied.",
            },
        )

    @app.post("/api/v1/officer/cases/{case_id}/compliance", response_model=Envelope[dict])
    def recheck(
        case_id: str,
        body: ReviewCommand,
        request: Request,
        idempotency_key: str | None = Header(None),
        p=Depends(principal),
        db=Depends(db_session),
    ):
        case = officer_case(db, p, case_id, "review", True)

        def execute():
            state = touch_review(db, case, body.expected_version)
            result = evaluate_rules(db, case, state, p)
            action(
                db,
                p,
                case,
                "RULES_RECHECKED",
                body.rationale,
                request.state.request_id,
                {"evaluation_id": result["evaluation_id"]},
            )
            return result

        return mutation(db, p, case, request, idempotency_key, body, "RECHECK", execute)

    @app.get("/api/v1/officer/cases/{case_id}/infrastructure", response_model=Envelope[dict])
    def infrastructure(case_id: str, request: Request, p=Depends(principal), db=Depends(db_session)):
        case = officer_case(db, p, case_id, "inspection")
        rows = db.scalars(select(RoomRecord).where(RoomRecord.revision_id == revision_for(db, case).id)).all()
        return envelope(
            request,
            {
                "review": review_view(db, case),
                "rooms": [
                    {
                        "id": r.id,
                        "room_code": r.room_code,
                        "room_type": r.room_type,
                        "declared_area": r.declared_area,
                        "certified": [
                            {
                                "id": e.id,
                                "version_id": e.version_id,
                                "page": e.page,
                                "bbox": e.bbox,
                                "area": e.certified_area,
                                "reliable": e.reliable,
                                "source_ref": e.source_ref,
                            }
                            for e in db.scalars(select(RoomEvidence).where(RoomEvidence.room_id == r.id))
                        ],
                    }
                    for r in rows
                ],
            },
        )

    @app.post("/api/v1/officer/cases/{case_id}/infrastructure", response_model=Envelope[dict])
    def room_input(
        case_id: str,
        body: RoomCommand,
        request: Request,
        idempotency_key: str | None = Header(None),
        p=Depends(principal),
        db=Depends(db_session),
    ):
        case = officer_case(db, p, case_id, "inspection", True)

        def execute():
            room = db.get(RoomRecord, body.room_id)
            v = db.get(DocumentVersion, body.version_id)
            if (
                not room
                or room.revision_id != revision_for(db, case).id
                or not v
                or v.application_id != case.id
            ):
                raise HTTPException(404, "Room/source unavailable in this revision.")
            if not previewable(db, v):
                raise HTTPException(409, "Source has not passed safety validation.")
            rendered = extract_isolated(
                storage.path(v.storage_key),
                app.state.processing_policy,
                v.sha256,
                operation="render",
                options={"media_type": v.media_type, "page": body.page},
            )
            x0, y0, x1, y1 = body.bbox
            if not rendered.get("ok") or not (
                0 <= x0 < x1 <= rendered["width"] and 0 <= y0 < y1 <= rendered["height"]
            ):
                raise HTTPException(
                    422,
                    "The certified reference must resolve to a real page and bounded original-space region.",
                )
            state = touch_review(db, case, body.expected_version)
            row = RoomEvidence(
                room_id=room.id,
                version_id=v.id,
                page=body.page,
                bbox=body.bbox,
                certified_area=body.certified_area,
                actor_id=p.user.id,
                source_ref=body.source_ref,
                reliable=body.reliable,
            )
            db.add(row)
            state.latest_evaluation_id = None
            state.context = {
                **state.context,
                "division": body.division,
                "division_source": {"version_id": v.id, "page": body.page, "source_ref": body.source_ref},
            }
            action(
                db,
                p,
                case,
                "ROOM_EVIDENCE_RECORDED",
                body.rationale,
                request.state.request_id,
                {"room_id": room.id, "version_id": v.id, "page": body.page},
            )
            db.flush()
            return {"id": row.id, "context": state.context}

        return mutation(db, p, case, request, idempotency_key, body, "ROOM_INPUT", execute)

    @app.get("/api/v1/officer/cases/{case_id}/authenticity", response_model=Envelope[dict])
    def authenticity(case_id: str, request: Request, p=Depends(principal), db=Depends(db_session)):
        officer_case(db, p, case_id, "authenticity")
        versions = select(DocumentVersion.id).where(DocumentVersion.application_id == case_id)
        return envelope(
            request,
            {
                "issuer": [
                    {"id": r.id, **r.source_response}
                    for r in db.scalars(
                        select(VerificationAttempt).where(VerificationAttempt.application_id == case_id)
                    )
                ],
                "provenance": [
                    {
                        "id": r.id,
                        "version_id": r.version_id,
                        "method": r.method,
                        "outcome": r.outcome,
                        "created_at": r.created_at,
                        "payload": r.payload,
                    }
                    for r in db.scalars(
                        select(ProvenanceResult).where(ProvenanceResult.version_id.in_(versions))
                    )
                ],
                "connectors": [
                    {"id": c.id, "name": c.name, "mode": c.mode, "status": c.status}
                    for c in db.scalars(select(Connector))
                ],
                "review": review_view(db, db.get(Application, case_id)),
            },
        )

    @app.post("/api/v1/officer/cases/{case_id}/issuer", response_model=Envelope[dict])
    def issuer(
        case_id: str,
        body: IssuerCommand,
        request: Request,
        idempotency_key: str | None = Header(None),
        p=Depends(principal),
        db=Depends(db_session),
    ):
        case = officer_case(db, p, case_id, "authenticity", True)

        def execute():
            v = db.get(DocumentVersion, body.version_id)
            if not v or v.application_id != case.id:
                raise HTTPException(404, "Evidence unavailable.")
            touch_review(db, case, body.expected_version)
            result = verify(db, case, v, body)
            action(
                db,
                p,
                case,
                "ISSUER_CHECK",
                body.rationale,
                request.state.request_id,
                {"attempt_id": result["id"]},
            )
            return result

        return mutation(db, p, case, request, idempotency_key, body, "ISSUER", execute)

    @app.post("/api/v1/officer/cases/{case_id}/provenance/{version_id}", response_model=Envelope[dict])
    def provenance(
        case_id: str,
        version_id: str,
        body: ReviewCommand,
        request: Request,
        idempotency_key: str | None = Header(None),
        p=Depends(principal),
        db=Depends(db_session),
    ):
        case = officer_case(db, p, case_id, "authenticity", True)

        def execute():
            v = db.get(DocumentVersion, version_id)
            if not v or v.application_id != case.id:
                raise HTTPException(404, "Evidence unavailable.")
            if not previewable(db, v):
                raise HTTPException(409, "Evidence remains quarantined.")
            touch_review(db, case, body.expected_version)
            options = {"media_type": v.media_type}
            for key, env in [("c2pa_anchors", "C2PA_TRUST_ANCHORS"), ("pdf_anchors", "PDF_TRUST_ANCHORS")]:
                path = os.getenv(env)
                if path and Path(path).is_file():
                    options[key] = Path(path).read_text()[:50000]
            result = extract_isolated(
                storage.path(v.storage_key),
                app.state.processing_policy,
                v.sha256,
                operation="provenance",
                options=options,
            )
            checks = result.get(
                "checks", {"verifier": {"outcome": "UNAVAILABLE", "method": "bounded local verifier"}}
            )
            duplicates = db.scalars(
                select(DocumentVersion).where(
                    DocumentVersion.sha256 == v.sha256,
                    DocumentVersion.application_id.in_(scoped_cases(db, p).with_only_columns(Application.id)),
                    DocumentVersion.id != v.id,
                )
            ).all()
            checks["duplicate_hash"] = {
                "outcome": "MATCHES_FOUND" if duplicates else "NO_SIGNAL",
                "method": "SHA-256 within authorized cases",
                "matches": [{"version_id": d.id, "application_id": d.application_id} for d in duplicates],
                "authenticity_confirmed": False,
            }
            for method, value in checks.items():
                db.add(
                    ProvenanceResult(
                        version_id=v.id,
                        actor_id=p.user.id,
                        method=method,
                        outcome=value["outcome"],
                        payload=value,
                    )
                )
            action(
                db,
                p,
                case,
                "PROVENANCE_CHECKED",
                body.rationale,
                request.state.request_id,
                {"version_id": v.id, "methods": list(checks)},
            )
            return {"version_id": v.id, "checks": checks}

        return mutation(db, p, case, request, idempotency_key, body, "PROVENANCE", execute)

    @app.get("/api/v1/officer/reports", response_model=Envelope[list[dict]])
    def reports(request: Request, p=Depends(principal), db=Depends(db_session)):
        from .auth import review_case_ids

        require_roles(p, {"officer", "supervisor", "admin", "auditor"})
        allowed = review_case_ids(db, p)
        from .models import Revision

        revisions = select(Revision.id).where(Revision.application_id.in_(allowed))
        return envelope(
            request,
            [
                {
                    "id": r.id,
                    "revision_id": r.revision_id,
                    "state": r.state,
                    "created_at": r.created_at,
                    "payload": r.payload,
                }
                for r in db.scalars(select(ReportRequest).where(ReportRequest.revision_id.in_(revisions)))
            ],
        )

    @app.post("/api/v1/officer/cases/{case_id}/reports", response_model=Envelope[dict])
    def report_request(
        case_id: str,
        body: ReviewCommand,
        request: Request,
        idempotency_key: str | None = Header(None),
        p=Depends(principal),
        db=Depends(db_session),
    ):
        case = officer_case(db, p, case_id, "review", True)

        def execute():
            touch_review(db, case, body.expected_version, allow_completed=True)
            row = ReportRequest(
                revision_id=revision_for(db, case).id,
                actor_id=p.user.id,
                payload={
                    "rationale": body.rationale,
                    "limitation": "Preliminary human review snapshot; no official decision. Local worker generates the immutable report.",
                },
            )
            db.add(row)
            db.flush()
            from .reports import capture_report

            capture_report(db, row, case, db.get(ReviewState, case.id))
            action(
                db,
                p,
                case,
                "REPORT_REQUESTED",
                body.rationale,
                request.state.request_id,
                {"report_request_id": row.id},
            )
            return {"id": row.id, "state": row.state}

        return mutation(db, p, case, request, idempotency_key, body, "REPORT_REQUEST", execute)

    @app.get("/api/v1/governance/versions", response_model=Envelope[list[dict]])
    def versions(request: Request, p=Depends(principal), db=Depends(db_session)):
        require_roles(p, {"admin"})
        return envelope(
            request,
            [
                governance_view(r)
                for r in db.scalars(
                    select(GovernedVersion).order_by(
                        GovernedVersion.kind, GovernedVersion.code, GovernedVersion.number.desc()
                    )
                )
            ],
        )

    @app.post("/api/v1/governance/versions", response_model=Envelope[dict])
    def draft(
        body: GovernanceDraft,
        request: Request,
        idempotency_key: str | None = Header(None),
        p=Depends(principal),
        db=Depends(db_session),
    ):
        require_roles(p, {"admin"})
        return envelope(
            request,
            idempotent(
                db,
                p,
                "GOVERNANCE_DRAFT",
                idempotency_key,
                body.model_dump(mode="json"),
                lambda _: create_version(db, p, body, request.state.request_id),
            ),
        )

    @app.post("/api/v1/governance/versions/{version_id}/action", response_model=Envelope[dict])
    def governance_action(
        version_id: str,
        body: GovernanceAction,
        request: Request,
        p=Depends(principal),
        db=Depends(db_session),
    ):
        require_roles(p, {"admin"})
        row = db.get(GovernedVersion, version_id)
        if not row:
            raise HTTPException(404, "Version unavailable.")
        return commit(request, db, govern(db, p, row, body, request.state.request_id))

    @app.get("/api/v1/governance/versions/{version_id}/dry-run", response_model=Envelope[dict])
    def dryrun(version_id: str, request: Request, p=Depends(principal), db=Depends(db_session)):
        require_roles(p, {"admin"})
        row = db.get(GovernedVersion, version_id)
        if not row or row.kind != "RULE":
            raise HTTPException(404, "Rule unavailable.")
        return envelope(request, dry_run(row))

    @app.get("/api/v1/governance/knowledge-health", response_model=Envelope[dict])
    def knowledge_health(request: Request, p=Depends(principal), db=Depends(db_session)):
        require_roles(p, {"admin"})
        from sqlalchemy import func, text
        from .models import KnowledgePassage

        vector = (
            bool(db.scalar(text("SELECT EXISTS(SELECT 1 FROM pg_extension WHERE extname='vector')")))
            if db.bind.dialect.name == "postgresql"
            else False
        )
        return envelope(
            request,
            {
                "database": db.bind.dialect.name,
                "pgvector_available": vector,
                "embedding_configured": os.getenv("RAG_EMBEDDINGS_ENABLED", "false") == "true",
                "model": "BAAI/bge-small-en-v1.5 (local cache only)",
                "approved_sources": db.scalar(
                    select(func.count())
                    .select_from(GovernedVersion)
                    .where(GovernedVersion.kind == "SOURCE", GovernedVersion.status == "APPROVED")
                ),
                "passages": db.scalar(select(func.count()).select_from(KnowledgePassage)),
                "embedded_passages": db.scalar(
                    select(func.count())
                    .select_from(KnowledgePassage)
                    .where(KnowledgePassage.embedding_model.is_not(None))
                ),
                "retrieval_mode": "HYBRID_CAPABLE_IF_LOCAL_MODEL_READY"
                if vector
                else "POSTGRES_FULLTEXT_ONLY"
                if db.bind.dialect.name == "postgresql"
                else "KEYWORD_ONLY_FALLBACK",
            },
        )

    @app.post("/api/v1/governance/versions/{version_id}/reindex", response_model=Envelope[dict])
    def reindex(
        version_id: str,
        body: GovernanceReason,
        request: Request,
        p=Depends(principal),
        db=Depends(db_session),
    ):
        require_roles(p, {"admin"})
        source = db.get(GovernedVersion, version_id)
        if not source or source.kind != "SOURCE" or source.status != "APPROVED":
            raise HTTPException(409, "Only approved source passages may be indexed.")
        from .knowledge import index_source

        index_source(db, source)
        append_audit(
            db,
            p.user.id,
            "SOURCE_REINDEXED",
            source.id,
            request.state.request_id,
            {"rationale": body.rationale},
        )
        return commit(
            request,
            db,
            {
                "source_id": source.id,
                "state": "INDEXED",
                "limitation": "Vector retrieval requires the pgvector extension and configured local model.",
            },
        )

    @app.post("/api/v1/knowledge/retrieve", response_model=Envelope[dict])
    def retrieval(body: RetrievalQuery, request: Request, p=Depends(principal), db=Depends(db_session)):
        require_roles(p, {"officer", "specialist", "supervisor", "admin"})
        return envelope(request, retrieve(db, p, body))

    @app.get("/api/v1/governance/users", response_model=Envelope[list[dict]])
    def users(request: Request, p=Depends(principal), db=Depends(db_session)):
        require_roles(p, {"admin"})
        return envelope(
            request,
            [
                {
                    "id": u.id,
                    "name": u.name,
                    "email": u.email,
                    "active": u.active,
                    "memberships": [
                        {
                            "id": m.id,
                            "role": m.role_id,
                            "institution_id": m.institution_id,
                            "valid_until": m.valid_until,
                        }
                        for m in db.scalars(select(Membership).where(Membership.user_id == u.id))
                    ],
                }
                for u in db.scalars(select(User).order_by(User.email))
            ],
        )

    @app.post("/api/v1/governance/users/{user_id}", response_model=Envelope[dict])
    def user_access(
        user_id: str, body: UserAccessCommand, request: Request, p=Depends(principal), db=Depends(db_session)
    ):
        require_roles(p, {"admin"})
        u = db.get(User, user_id)
        if not u:
            raise HTTPException(404, "User unavailable.")
        return commit(request, db, access_change(db, p, u, body, request.state.request_id))

    @app.post("/api/v1/governance/connectors/{connector_id}", response_model=Envelope[dict])
    def connector_update(
        connector_id: str,
        body: ConnectorCommand,
        request: Request,
        p=Depends(principal),
        db=Depends(db_session),
    ):
        require_roles(p, {"admin"})
        c = db.get(Connector, connector_id)
        if not c:
            raise HTTPException(404, "Connector unavailable.")
        if body.mode == "LIVE" and body.status == "AVAILABLE":
            raise HTTPException(
                409,
                "No authorized live issuer implementation is installed. Live mode cannot claim availability.",
            )
        c.mode, c.status, c.secret_reference = body.mode, body.status, body.secret_reference
        append_audit(
            db,
            p.user.id,
            "CONNECTOR_CONFIGURED",
            c.id,
            request.state.request_id,
            {"mode": c.mode, "status": c.status, "rationale": body.rationale},
        )
        return commit(
            request,
            db,
            {
                "id": c.id,
                "mode": c.mode,
                "status": c.status,
                "has_secret_reference": bool(c.secret_reference),
            },
        )
