import time
from fastapi import HTTPException
from sqlalchemy import select, func
from .audit import append_audit
from .models import GovernedVersion, Membership, AuthSession, ContentGrant, Application, Institution
from .knowledge import index_source


def governance_view(row):
    import hashlib
    import json
    from sqlalchemy.orm import object_session
    from .models import AuditEvent

    db = object_session(row)

    def timestamp(operation):
        return (
            db.scalar(
                select(AuditEvent.created_at)
                .where(AuditEvent.target_id == row.id, AuditEvent.operation == operation)
                .order_by(AuditEvent.created_at)
                .limit(1)
            )
            if db
            else None
        )

    return {
        "approved_at": timestamp("GOVERNANCE_APPROVE"),
        "published_at": timestamp("GOVERNANCE_PUBLISH"),
        "checksum": hashlib.sha256(
            (
                row.payload["text"] if row.kind == "SOURCE" else json.dumps(row.payload, sort_keys=True)
            ).encode()
        ).hexdigest(),
        "checksum_scope": "CURATED_PASSAGE_TEXT" if row.kind == "SOURCE" else "CANONICAL_TYPED_RULE",
        "id": row.id,
        "kind": row.kind,
        "code": row.code,
        "number": row.number,
        "status": row.status,
        "author_id": row.author_id,
        "approver_id": row.approver_id,
        "source_id": row.source_id,
        "payload": row.payload,
        "created_at": row.created_at,
    }


def create_version(db, p, body, request_id):
    if body.kind == "RULE":
        source = db.get(GovernedVersion, body.source_id)
        if not source or source.kind != "SOURCE" or source.status != "APPROVED":
            raise HTTPException(409, "Rules require an approved source version.")
        a, b = body.payload["scope"], source.payload["scope"]
        if any(not set(a[k]) <= set(b[k]) for k in ["years", "categories", "programmes", "stages"]):
            raise HTTPException(422, "Rule scope cannot exceed its approved source.")
        if a["effective_from"] < b["effective_from"] or a["effective_until"] > b["effective_until"]:
            raise HTTPException(422, "Rule interval cannot exceed its approved source.")
    number = (
        db.scalar(
            select(func.max(GovernedVersion.number)).where(
                GovernedVersion.kind == body.kind, GovernedVersion.code == body.code
            )
        )
        or 0
    ) + 1
    row = GovernedVersion(
        kind=body.kind,
        code=body.code,
        number=number,
        author_id=p.user.id,
        source_id=body.source_id,
        payload=body.payload,
    )
    db.add(row)
    db.flush()
    append_audit(
        db,
        p.user.id,
        "GOVERNANCE_DRAFTED",
        row.id,
        request_id,
        {"kind": row.kind, "number": number, "rationale": body.rationale},
    )
    return governance_view(row)


def govern(db, p, row, body, request_id):
    if body.action in {"APPROVE", "PUBLISH"} and row.author_id == p.user.id:
        raise HTTPException(403, "Configured dual approval prohibits self-approval/publication.")
    if body.action == "APPROVE":
        if row.status != "DRAFT":
            raise HTTPException(409, "Only a draft can be approved.")
        row.approver_id = p.user.id
        row.status = "APPROVED"
        if row.kind == "SOURCE":
            index_source(db, row)
    elif body.action == "PUBLISH":
        if row.kind != "RULE" or row.status != "APPROVED":
            raise HTTPException(
                409, "Only an approved rule can be published; source ingestion never publishes rules."
            )
        source = db.get(GovernedVersion, row.source_id)
        if not source or source.status != "APPROVED":
            raise HTTPException(409, "Source no longer approved.")
        from .compliance import dry_run

        result = dry_run(row)
        if not result["passed"]:
            raise HTTPException(409, "Required synthetic rule fixtures did not pass.")
        row.status = "PUBLISHED"
        for previous in db.scalars(
            select(GovernedVersion).where(
                GovernedVersion.kind == "RULE",
                GovernedVersion.code == row.code,
                GovernedVersion.status == "PUBLISHED",
                GovernedVersion.id != row.id,
            )
        ):
            a, b = previous.payload["scope"], row.payload["scope"]
            if all(set(a[k]) & set(b[k]) for k in ["years", "categories", "programmes", "stages"]) and max(
                a["effective_from"], b["effective_from"]
            ) <= min(a["effective_until"], b["effective_until"]):
                previous.status = "SUPERSEDED"
                append_audit(
                    db,
                    p.user.id,
                    "GOVERNANCE_SUPERSEDED",
                    previous.id,
                    request_id,
                    {"replacement_id": row.id},
                )
        from .models import RuleSet, ComplianceRule, GovernedRuleLink

        ruleset = RuleSet(
            version=f"governed-{row.code}-{row.number}-{row.id[:8]}",
            status="DRAFT",
            source_ref=source.payload["source_url"],
            authored_by=row.author_id,
            approved_by=row.approver_id,
            effective_from=row.payload["scope"]["effective_from"],
        )
        db.add(ruleset)
        db.flush()
        canonical = ComplianceRule(
            ruleset_id=ruleset.id, code=row.code, clause=source.payload["clause"], definition=row.payload
        )
        db.add(canonical)
        db.flush()
        db.add(GovernedRuleLink(id=row.id, rule_id=canonical.id))
        ruleset.status = "PUBLISHED"
    else:
        if row.status not in {"APPROVED", "PUBLISHED"}:
            raise HTTPException(409, "Only an approved/published version can be superseded.")
        row.status = "SUPERSEDED"
    append_audit(
        db,
        p.user.id,
        "GOVERNANCE_" + body.action,
        row.id,
        request_id,
        {"rationale": body.rationale, "number": row.number},
    )
    from .models import OutboxEvent

    db.add(
        OutboxEvent(
            deduplication_key=f"governance:{row.id}:{body.action}",
            event_type="GOVERNANCE_UPDATED",
            payload={"kind": row.kind, "version_id": row.id},
        )
    )
    db.flush()
    return governance_view(row)


def access_change(db, p, target, body, request_id):
    if body.action in {"DEACTIVATE", "REVOKE_ROLE"} and target.id == p.user.id:
        raise HTTPException(409, "Use a separate administrator for self-suspension or privilege removal.")
    now = int(time.time())
    if body.action in {"ACTIVATE", "DEACTIVATE"}:
        target.active = body.action == "ACTIVATE"
    if body.action in {"DEACTIVATE", "REVOKE_SESSIONS", "REVOKE_ROLE"}:
        for s in db.scalars(
            select(AuthSession).where(AuthSession.user_id == target.id, AuthSession.revoked_at.is_(None))
        ):
            s.revoked_at = now
    if body.action in {"GRANT_ROLE", "REVOKE_ROLE"}:
        if not body.role:
            raise HTTPException(422, "Choose a role.")
        if body.role.startswith("institution_") and not body.institution_id:
            raise HTTPException(422, "Institution roles require an explicit tenant.")
        if body.institution_id and not db.get(Institution, body.institution_id):
            raise HTTPException(422, "Choose an existing institution scope.")
        q = select(Membership).where(
            Membership.user_id == target.id,
            Membership.role_id == body.role,
            Membership.institution_id == body.institution_id,
        )
        row = db.scalar(q)
        if body.action == "GRANT_ROLE":
            if row:
                row.valid_until = None
            else:
                db.add(Membership(user_id=target.id, role_id=body.role, institution_id=body.institution_id))
        elif row:
            row.valid_until = now
    elif body.action == "GRANT_CONTENT":
        if not body.application_id or not db.get(Application, body.application_id):
            raise HTTPException(404, "Application unavailable.")
        row = db.scalar(
            select(ContentGrant).where(
                ContentGrant.user_id == target.id, ContentGrant.application_id == body.application_id
            )
        )
        if row:
            row.expires_at = now + 3600
        else:
            db.add(
                ContentGrant(
                    user_id=target.id,
                    application_id=body.application_id,
                    granted_by=p.user.id,
                    expires_at=now + 3600,
                )
            )
    append_audit(
        db,
        p.user.id,
        "USER_" + body.action,
        target.id,
        request_id,
        {"role": body.role, "institution_id": body.institution_id, "rationale": body.rationale},
    )
    return {"id": target.id, "active": target.active, "action": body.action}
