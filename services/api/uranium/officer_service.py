"""Scoped, human-controlled review operations over immutable submitted inputs."""

import time
from fastapi import HTTPException
from sqlalchemy import select, update, func
from .audit import append_audit
from .models import (
    Application,
    Revision,
    Assignment,
    Membership,
    ReviewState,
    OfficerAction,
    ReviewActionContext,
    SpecialistTask,
    ExtractionCorrection,
    ExtractedField,
    DocumentVersion,
    EvidenceNode,
    EvidenceEdge,
    Clarification,
    ClarificationResolution,
    Finding,
    ApplicationTimeline,
    User,
    Evaluation,
    InspectionTask,
)


def supervisor_institutions(db, p):
    return select(Membership.institution_id).where(
        Membership.user_id == p.user.id,
        Membership.role_id == "supervisor",
        Membership.institution_id.is_not(None),
        (Membership.valid_until.is_(None)) | (Membership.valid_until > int(time.time())),
    )


def scoped_cases(db, p, scope="read"):
    roles = {"officer", "specialist", "supervisor"}
    if not p.roles & roles:
        raise HTTPException(403, "This operation requires an assigned scrutiny role.")
    scopes = []
    if "officer" in p.roles:
        scopes.append("REVIEW")
    if "supervisor" in p.roles:
        scopes.append("SUPERVISE")
    if "specialist" in p.roles and scope in {"read", "evidence", "authenticity", "inspection"}:
        scopes.append("VERIFY")
    assigned = select(Assignment.application_id).where(
        Assignment.user_id == p.user.id, Assignment.active.is_(True), Assignment.scope.in_(scopes)
    )
    permitted = Application.id.in_(assigned)
    if "supervisor" in p.roles:
        permitted = permitted | Application.institution_id.in_(supervisor_institutions(db, p))
    return select(Application).where(permitted, Application.status != "DRAFT")


def officer_case(db, p, case_id, scope="read", write=False):
    case = db.scalar(scoped_cases(db, p, scope).where(Application.id == case_id))
    if not case:
        import uuid

        append_audit(db, p.user.id, "ACCESS_DENIED", case_id[:100], str(uuid.uuid4()), {"scope": scope})
        db.commit()
        raise HTTPException(404, "Record unavailable in your authorized scope.")
    if write and not p.roles & {"officer", "supervisor"}:
        raise HTTPException(403, "A routed specialist cannot perform scrutiny or final review actions.")
    return case


def revision_for(db, case):
    revision = db.scalar(
        select(Revision)
        .where(Revision.application_id == case.id, Revision.frozen.is_(True))
        .order_by(Revision.number.desc())
        .limit(1)
    )
    if not revision:
        raise HTTPException(409, "A frozen submitted revision is required.")
    return revision


def review_view(db, case):
    state = db.get(ReviewState, case.id)
    return {
        "version": state.version if state else 1,
        "due_at": state.due_at if state else case.created_at + 7 * 86400,
        "priority_override": state.priority_override if state else None,
        "priority_reason": state.priority_reason if state else None,
        "latest_evaluation_id": state.latest_evaluation_id if state else None,
    }


def touch_review(db, case, expected, allow_completed=False):
    if case.status == "REVIEW_COMPLETED" and not allow_completed:
        raise HTTPException(409, "Review is complete. A supervisor must explicitly reopen it.")
    state = db.get(ReviewState, case.id)
    if not state:
        state = ReviewState(
            id=case.id, revision_id=revision_for(db, case).id, version=1, due_at=case.created_at + 7 * 86400
        )
        db.add(state)
        db.flush()
    result = db.execute(
        update(ReviewState)
        .where(ReviewState.id == case.id, ReviewState.version == expected)
        .values(version=ReviewState.version + 1)
        .execution_options(synchronize_session="fetch")
    )
    if result.rowcount != 1:
        raise HTTPException(409, "Review changed. Reload the current case before retrying.")
    if case.status == "SUBMITTED":
        case.status = "UNDER_REVIEW"
    return state


def action(db, p, case, kind, rationale, request_id, payload=None, publishable=False):
    revision = revision_for(db, case)
    row = OfficerAction(
        revision_id=revision.id, actor_id=p.user.id, action=kind, rationale=rationale, publishable=publishable
    )
    db.add(row)
    db.flush()
    db.add(ReviewActionContext(id=row.id, payload=payload or {}))
    append_audit(db, p.user.id, kind, case.id, request_id, {"action_id": row.id, "revision_id": revision.id})
    return row


def priority(db, case):
    count = db.scalar(
        select(func.count())
        .select_from(SpecialistTask)
        .where(SpecialistTask.application_id == case.id, SpecialistTask.status != "RESOLVED")
    )
    findings = db.scalar(
        select(func.count())
        .select_from(Finding)
        .join(Evaluation)
        .where(
            Evaluation.id == review_view(db, case)["latest_evaluation_id"],
            Finding.severity == "BLOCKING",
        )
    )
    view = review_view(db, case)
    reasons = []
    if count:
        reasons.append(
            {"factor": "Unresolved specialist tasks", "count": count, "points": min(30, count * 10)}
        )
    if findings:
        reasons.append(
            {"factor": "Findings requiring human review", "count": findings, "points": min(40, findings * 5)}
        )
    if view["due_at"] < int(time.time()):
        reasons.append({"factor": "Configured review due date passed", "count": 1, "points": 20})
    score = min(100, sum(x["points"] for x in reasons))
    return {
        "score": view["priority_override"] if view["priority_override"] is not None else score,
        "computed": score,
        "reasons": reasons,
        "override_rationale": view["priority_reason"],
        "meaning": "Work ordering only; not a fraud or approval score.",
    }


def correction(db, p, case, body, request_id):
    field = db.get(ExtractedField, body.field_id)
    version = db.get(DocumentVersion, field.version_id) if field else None
    if not version or version.application_id != case.id:
        raise HTTPException(404, "Field unavailable in this case.")
    reviewstate = touch_review(db, case, body.expected_version)
    reviewstate.latest_evaluation_id = None
    old = db.scalar(
        select(ExtractionCorrection)
        .where(ExtractionCorrection.field_id == field.id)
        .order_by(ExtractionCorrection.created_at.desc(), ExtractionCorrection.id.desc())
        .limit(1)
    )
    value = body.normalized
    if field.field_key.endswith("date") and value is not None:
        from datetime import date

        try:
            value = date.fromisoformat(value).isoformat()
        except ValueError:
            raise HTTPException(422, "Corrected dates require YYYY-MM-DD or unknown/null.")
    row = ExtractionCorrection(
        field_id=field.id,
        actor_id=p.user.id,
        supersedes_id=old.id if old else None,
        corrected_value={"normalized": value},
        rationale=body.rationale,
    )
    db.add(row)
    db.flush()
    machine = EvidenceNode(
        revision_id=version.revision_id,
        kind="MACHINE_FIELD",
        reference={
            "field_id": field.id,
            "version_id": version.id,
            "page": field.page,
            "bbox": field.bounding_box,
        },
    )
    revised = EvidenceNode(
        revision_id=version.revision_id,
        kind="HUMAN_CORRECTION",
        reference={"correction_id": row.id, "field_id": field.id, "normalized": value},
    )
    db.add_all([machine, revised])
    db.flush()
    db.add(
        EvidenceEdge(
            revision_id=version.revision_id,
            from_node=revised.id,
            to_node=machine.id,
            relationship="SUPERSEDES",
        )
    )
    action(
        db,
        p,
        case,
        "EXTRACTION_CORRECTED",
        body.rationale,
        request_id,
        {"field_id": field.id, "correction_id": row.id},
    )
    return {"id": row.id, "machine_value": field.value, "corrected_value": row.corrected_value}


def route_task(db, p, case, body, request_id):
    target = db.get(User, body.assignee_id)
    wanted = "supervisor" if body.kind == "SUPERVISION" else "specialist"
    if (
        not target
        or not target.active
        or not db.scalar(
            select(Membership.id).where(
                Membership.user_id == target.id,
                Membership.role_id == wanted,
                (Membership.valid_until.is_(None)) | (Membership.valid_until > int(time.time())),
            )
        )
    ):
        raise HTTPException(422, "Choose an active user with the required routing role.")
    if not int(time.time()) < body.due_at < int(time.time()) + 90 * 86400:
        raise HTTPException(422, "Task due date must be within the next 90 days.")
    if body.version_id:
        version = db.get(DocumentVersion, body.version_id)
        if not version or version.application_id != case.id:
            raise HTTPException(404, "Evidence unavailable in this case.")
    touch_review(db, case, body.expected_version)
    task = SpecialistTask(
        application_id=case.id,
        revision_id=revision_for(db, case).id,
        assignee_id=target.id,
        creator_id=p.user.id,
        kind=body.kind,
        due_at=body.due_at,
        evidence={"version_id": body.version_id, "rationale": body.rationale},
    )
    db.add(task)
    db.flush()
    if body.kind == "INSPECTION":
        db.add(
            InspectionTask(
                id=task.id,
                application_id=case.id,
                assignee_id=target.id,
                status="REQUESTED",
                evidence={"task_id": task.id, "version_id": body.version_id, "reason": body.rationale},
            )
        )
    scope = "SUPERVISE" if wanted == "supervisor" else "VERIFY"
    assignment = db.scalar(
        select(Assignment).where(
            Assignment.application_id == case.id, Assignment.user_id == target.id, Assignment.scope == scope
        )
    )
    if assignment:
        assignment.active = True
    else:
        db.add(Assignment(application_id=case.id, user_id=target.id, scope=scope, active=True))
    case.status = "INSPECTION_RECOMMENDED" if body.kind == "INSPECTION" else "PENDING_VERIFICATION"
    action(
        db, p, case, "TASK_ROUTED", body.rationale, request_id, {"assignee_id": target.id, "kind": body.kind}
    )
    db.flush()
    from .models import OutboxEvent

    db.add(
        OutboxEvent(
            deduplication_key="task:" + task.id,
            event_type="TASK_ROUTED",
            payload={"application_id": case.id, "task_id": task.id, "assignee_id": target.id},
        )
    )
    return {"id": task.id, "status": task.status, "version": task.version}


def human_action(db, p, case, body, request_id):
    if body.action == "REOPEN" and "supervisor" not in p.roles:
        raise HTTPException(403, "Only a scoped supervisor may reopen a completed review.")
    state = touch_review(db, case, body.expected_version, allow_completed=body.action == "REOPEN")
    if body.publishable and body.action != "CLARIFICATION":
        raise HTTPException(422, "Only explicit clarification communication can be published here.")
    if body.action == "COMPLETE":
        pending = db.scalar(
            select(SpecialistTask.id)
            .where(SpecialistTask.application_id == case.id, SpecialistTask.status != "RESOLVED")
            .limit(1)
        )
        open_request = db.scalar(
            select(Clarification.id)
            .where(
                Clarification.application_id == case.id,
                Clarification.published.is_(True),
                ~Clarification.id.in_(select(ClarificationResolution.request_id)),
            )
            .limit(1)
        )
        if pending or open_request:
            raise HTTPException(
                409,
                "Resolve outstanding routed tasks and published clarification requests before completion.",
            )
        if not state.latest_evaluation_id:
            raise HTTPException(409, "Run and inspect a saved rule evaluation before completing review.")
        from .models import RuleRun, GovernedVersion

        for run in db.scalars(select(RuleRun).where(RuleRun.evaluation_id == state.latest_evaluation_id)):
            rule = db.get(GovernedVersion, run.rule_id)
            source = db.get(GovernedVersion, rule.source_id) if rule else None
            if not rule or rule.status != "PUBLISHED" or not source or source.status != "APPROVED":
                raise HTTPException(
                    409,
                    "Governing rule/source changed. Recheck the current applicable versions before completion.",
                )
        if not db.scalar(
            select(OfficerAction.id)
            .where(
                OfficerAction.revision_id == revision_for(db, case).id,
                OfficerAction.action == "RECOMMENDATION",
            )
            .limit(1)
        ):
            raise HTTPException(409, "Record a human draft recommendation before completing the review.")
        case.status = "REVIEW_COMPLETED"
    elif body.action == "REOPEN":
        if case.status != "REVIEW_COMPLETED":
            raise HTTPException(409, "Only completed reviews can be reopened.")
        case.status = "UNDER_REVIEW"
    elif body.action == "CLARIFICATION":
        if not body.publishable or not body.due_at or body.due_at <= int(time.time()):
            raise HTTPException(
                422, "Publishing requires explicit visibility and a future response deadline."
            )
        from .models import ClarificationScope, OutboxEvent

        if db.scalar(
            select(Clarification.id)
            .where(
                Clarification.application_id == case.id,
                Clarification.published.is_(True),
                ~Clarification.id.in_(select(ClarificationResolution.request_id)),
            )
            .limit(1)
        ):
            raise HTTPException(
                409, "Review and close the outstanding clarification before publishing another."
            )
        from .document_parser import TYPES

        if set(body.required_documents) - set(body.document_types) or set(body.document_types) - set(TYPES):
            raise HTTPException(
                422, "Use supported document types and a required subset of the permitted types."
            )
        row = Clarification(
            application_id=case.id,
            actor_id=p.user.id,
            message=body.rationale,
            published=True,
            allowed_until=body.due_at,
        )
        db.add(row)
        db.flush()
        db.add(
            ClarificationScope(
                id=row.id,
                original_revision_id=revision_for(db, case).id,
                allowed_fields=body.allowed_fields,
                document_types=body.document_types,
                required_documents=body.required_documents,
            )
        )
        db.add(
            OutboxEvent(
                deduplication_key="clarification:" + row.id,
                event_type="CLARIFICATION_PUBLISHED",
                payload={"application_id": case.id, "request_id": row.id},
            )
        )
        case.status = "CLARIFICATION_REQUESTED"
        db.add(
            ApplicationTimeline(
                application_id=case.id,
                actor_id=p.user.id,
                event_key=f"clarification:{time.time_ns()}",
                event_type="CLARIFICATION_PUBLISHED",
                summary=body.rationale,
                payload={"allowed_until": body.due_at},
            )
        )
    row = action(
        db, p, case, body.action, body.rationale, request_id, {"state": case.status}, body.publishable
    )
    return {"id": row.id, "status": case.status, "version": state.version, "official_decision": False}
