"""Transactional, idempotent in-app delivery. No email/SMS provider is enabled."""

import time
from sqlalchemy import select, update, event, inspect
from sqlalchemy.orm import Session
from .models import (
    OutboxEvent,
    Notification,
    Application,
    Membership,
    Assignment,
    User,
    AccountPreference,
    ApplicationTimeline,
)
from .auth import digest, allowed_case_ids
from .audit import append_audit


LABELS = {
    "DRAFT": "Draft",
    "SUBMITTED": "Submitted",
    "UNDER_REVIEW": "Under Preliminary Review",
    "CLARIFICATION_REQUESTED": "Clarification Requested",
    "PENDING_VERIFICATION": "Pending Source Verification",
    "INSPECTION_RECOMMENDED": "Referred for Inspection",
    "REVIEW_COMPLETED": "Review Completed",
}


@event.listens_for(Session, "before_flush")
def lifecycle_events(db, context, instances):
    for case in list(db.dirty):
        if not isinstance(case, Application):
            continue
        changed = inspect(case).attrs.status.history
        if not changed.has_changes():
            continue
        previous = changed.deleted[0] if changed.deleted else None
        # The initial submission already has its canonical transactional event/timeline.
        if case.status == "SUBMITTED":
            continue
        key = "transition:" + case.id + ":" + str(time.time_ns())
        payload = {"application_id": case.id, "status": case.status, "previous_status": previous}
        db.add(OutboxEvent(deduplication_key=key, event_type="APPLICATION_STATUS_CHANGED", payload=payload))
        db.add(
            ApplicationTimeline(
                application_id=case.id,
                actor_id=db.info.get("actor_id"),
                event_key=key,
                event_type="STATUS_CHANGED",
                summary=LABELS.get(case.status, case.status),
                payload=payload,
            )
        )
        append_audit(
            db,
            db.info.get("actor_id"),
            "LIFECYCLE_TRANSITION",
            case.id,
            db.info.get("request_id", "system-worker"),
            payload,
        )


def target_allowed(db, p, target):
    if target.get("governance_kind") in {"SOURCE", "RULE"}:
        return "admin" in p.roles
    identifier = target.get("application_id")
    if not identifier:
        return False
    return bool(
        db.scalar(
            select(Application.id).where(
                Application.id == identifier, Application.id.in_(allowed_case_ids(db, p))
            )
        )
    )


def target_url(p, target):
    if target.get("governance_kind"):
        return "/admin/knowledge" if target["governance_kind"] == "SOURCE" else "/admin/rules"
    identifier = target["application_id"]
    if p.roles.intersection({"institution_admin", "institution_submitter"}):
        if target.get("request_id"):
            return "/institution/deficiencies/" + target["request_id"]
        if target.get("version_id"):
            return f"/institution/applications/{identifier}/documents"
        return f"/institution/applications/{identifier}/status"
    if target.get("task_id") or (
        "specialist" in p.roles and not p.roles.intersection({"officer", "supervisor"})
    ):
        return "/officer/verifications"
    if target.get("report_id"):
        return "/officer/reports"
    if target.get("version_id"):
        return f"/officer/applications/{identifier}/evidence?version={target['version_id']}"
    return f"/officer/applications/{identifier}/overview"


def dispatch_one(factory):
    now = int(time.time())
    with factory() as db:
        row = db.scalar(
            select(OutboxEvent)
            .where(OutboxEvent.delivered_at.is_(None))
            .order_by(OutboxEvent.created_at, OutboxEvent.id)
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        if not row:
            return False
        claimed = db.execute(
            update(OutboxEvent)
            .where(OutboxEvent.id == row.id, OutboxEvent.delivered_at.is_(None))
            .values(delivered_at=now)
        )
        if claimed.rowcount != 1:
            db.rollback()
            return False
        data = row.payload
        case = db.get(Application, data.get("application_id", ""))
        if row.event_type == "GOVERNANCE_UPDATED":
            recipients = set(
                db.scalars(
                    select(Membership.user_id).where(
                        Membership.role_id == "admin",
                        (Membership.valid_until.is_(None)) | (Membership.valid_until > now),
                    )
                )
            )
            _deliver(
                db,
                row,
                recipients,
                {"governance_kind": data["kind"], "event_type": row.event_type},
                "Governed source/rule index metadata was updated.",
                True,
            )
            return True
        if not case:
            append_audit(db, None, "NOTIFICATION_SKIPPED", row.id, "outbox-worker")
            db.commit()
            return True
        members = set(
            db.scalars(
                select(Membership.user_id).where(
                    Membership.institution_id == case.institution_id,
                    Membership.role_id.in_(["institution_admin", "institution_submitter"]),
                    (Membership.valid_until.is_(None)) | (Membership.valid_until > now),
                )
            )
        )
        staff = set(
            db.scalars(
                select(Assignment.user_id).where(
                    Assignment.application_id == case.id,
                    Assignment.active.is_(True),
                    Assignment.scope.in_(["REVIEW", "SUPERVISE"]),
                )
            )
        )
        recipients = members | staff
        if row.event_type in {"CLARIFICATION_PUBLISHED", "REPORT_SUMMARY_PUBLISHED"}:
            recipients = members
        if data.get("assignee_id"):
            recipients = {data["assignee_id"]}
        if row.event_type == "REPORT_READY":
            recipients = staff | {data["actor_id"]}
        summary = {
            "APPLICATION_SUBMITTED": "Application submitted for preliminary review.",
            "CLARIFICATION_PUBLISHED": "A published clarification requires your response.",
            "CLARIFICATION_RESPONDED": "A clarification response is ready for human review.",
            "TASK_ROUTED": "A verification task was routed to you.",
            "REPORT_READY": "A review report snapshot is ready.",
            "REPORT_SUMMARY_PUBLISHED": "A separate report summary was published to your institution.",
            "DOCUMENT_PROCESSING_UPDATED": "Document processing updated. Open the authorized record for actionable status.",
        }.get(row.event_type, "Application status: " + LABELS.get(data.get("status"), "updated"))
        target = {
            k: data[k]
            for k in ["application_id", "request_id", "task_id", "report_id", "version_id"]
            if data.get(k)
        }
        target["event_type"] = row.event_type
        _deliver(db, row, recipients, target, summary, case.is_mock)
    return True


def _deliver(db, row, recipients, target, summary, is_mock):
    for identifier in sorted(recipients):
        user = db.get(User, identifier)
        pref = db.get(AccountPreference, identifier)
        if not user or not user.active or (pref and not pref.in_app):
            continue
        key = digest(row.id + ":" + identifier)
        if not db.scalar(select(Notification.id).where(Notification.deduplication_key == key)):
            db.add(
                Notification(
                    user_id=identifier,
                    deduplication_key=key,
                    summary=("MOCK / DEMO · " if is_mock else "") + summary,
                    target=target,
                )
            )
    append_audit(db, None, "NOTIFICATION_EVENT_DELIVERED", row.id, "outbox-worker")
    db.commit()


def processing_notice(db, job, version):
    from .models import ResponseDraft

    response = db.scalar(select(ResponseDraft).where(ResponseDraft.revision_id == version.revision_id))
    data = {"application_id": version.application_id, "version_id": version.id}
    if response:
        data["request_id"] = response.id
    db.add(
        OutboxEvent(
            deduplication_key=f"processing:{job.id}:{job.state}",
            event_type="DOCUMENT_PROCESSING_UPDATED",
            payload=data,
        )
    )
