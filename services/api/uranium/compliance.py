"""Versioned deterministic arithmetic over saved reliable evidence, never RAG guesses."""

import hashlib

from sqlalchemy import select
from .models import (
    ApplicationDraft,
    GovernedVersion,
    RoomRecord,
    RoomEvidence,
    Evaluation,
    RuleRun,
    Finding,
    EvidenceNode,
    EvidenceEdge,
    ReviewedException,
    ApplicationCatalogue,
    GovernedRuleLink,
)
from .knowledge import applicable
from .officer_service import revision_for


def context_for(db, case, state=None):
    draft = db.get(ApplicationDraft, case.id)
    revision = revision_for(db, case)
    details = revision.manifest.get("details", draft.details if draft else {})
    catalogue = db.get(ApplicationCatalogue, draft.catalogue_id) if draft else None
    reference = catalogue.definition["reference_date"] if catalogue else case.academic_year[:4] + "-06-01"
    context = state.context if state else {}
    return {
        "academic_year": case.academic_year,
        "category": catalogue.code if catalogue else case.category,
        "programme": details.get("programme", "UNKNOWN"),
        "stage": context.get("stage", "SCRUTINY"),
        "reference_date": reference,
        "division": context.get("division"),
    }


def arithmetic(declared, certified, minimum, reliable=True):
    if declared is None or certified is None or not reliable:
        return {"state": "INSUFFICIENT_EVIDENCE", "mismatch": None, "deficiency": None}
    return {
        "state": "POTENTIAL_DEFICIENCY" if certified < minimum else "MET",
        "mismatch": round(abs(declared - certified), 4),
        "deficiency": round(max(0, minimum - certified), 4),
    }


def dry_run(rule):
    n = rule.payload["minimum"]
    result = arithmetic(75, 58, n)
    missing = arithmetic(75, None, n)
    return {
        "passed": result["mismatch"] == 17
        and result["deficiency"] == max(0, n - 58)
        and missing["state"] == "INSUFFICIENT_EVIDENCE",
        "operands": {"declared": 75, "certified": 58, "minimum": n},
        "result": result,
        "missing_evidence": missing,
        "division": rule.payload["division"],
        "official_validation": False,
    }


def evaluate_rules(db, case, state, p=None):
    revision = revision_for(db, case)
    context = context_for(db, case, state)
    rules = db.scalars(
        select(GovernedVersion)
        .where(GovernedVersion.kind == "RULE", GovernedVersion.status == "PUBLISHED")
        .order_by(GovernedVersion.code, GovernedVersion.number.desc())
    ).all()
    evaluation = Evaluation(revision_id=revision.id, ruleset_id=revision.ruleset_id, state="COMPLETED")
    # Legacy submitted fixtures always carry their original ruleset; reject incomplete imports explicitly.
    if not revision.ruleset_id:
        from fastapi import HTTPException

        raise HTTPException(
            409, "Submitted revision has no rulepack; reconcile this legacy import before evaluation."
        )
    db.add(evaluation)
    db.flush()
    outcomes = []
    rooms = db.scalars(select(RoomRecord).where(RoomRecord.revision_id == revision.id)).all()
    for rule in rules:
        source = db.get(GovernedVersion, rule.source_id)
        if p and (
            not p.roles.intersection(rule.payload["scope"]["roles"])
            or (source and not p.roles.intersection(source.payload["scope"]["roles"]))
        ):
            continue
        spec = rule.payload
        base = {
            "rule_id": rule.id,
            "canonical_rule_id": (
                db.get(GovernedRuleLink, rule.id).rule_id if db.get(GovernedRuleLink, rule.id) else None
            ),
            "rule_code": rule.code,
            "rule_version": rule.number,
            "source_id": rule.source_id,
            "context": context,
            "method": "DETERMINISTIC_ROOM_AREA_V1",
            "human_review_required": True,
            "clause": source.payload["clause"] if source else None,
            "printed_page": source.payload["printed_page"] if source else None,
            "pdf_page": source.payload["pdf_page"] if source else None,
            "source_url": source.payload["source_url"] if source else None,
            "source_checksum": hashlib.sha256(source.payload["text"].encode()).hexdigest()
            if source
            else None,
            "source_checksum_kind": "CURATED_PASSAGE_TEXT",
            "is_mock": case.is_mock,
        }
        reason = None
        if not source or source.status != "APPROVED":
            reason = "Approved controlling source unavailable or superseded."
        elif not applicable(spec["scope"], context):
            reason = "Year/category/programme/stage/effective interval does not apply."
        elif context["division"] is not None and context["division"] != spec["division"]:
            reason = "Selected division does not match this rule."
        exception = (
            db.scalar(
                select(ReviewedException).where(
                    ReviewedException.institution_id == case.institution_id,
                    ReviewedException.academic_year == case.academic_year,
                    ReviewedException.code.in_(spec["exception_codes"]),
                )
            )
            if spec["exception_codes"]
            else None
        )
        if exception:
            reason = "Reviewed applicable exception: " + exception.code
        if reason:
            outcomes.append({**base, "state": "NOT_APPLICABLE", "reason": reason})
            continue
        if context["division"] is None or not rooms:
            outcomes.append(
                {
                    **base,
                    "state": "INSUFFICIENT_EVIDENCE",
                    "reason": "A sourced division and room schedule are required.",
                }
            )
            continue
        for room in rooms:
            if room.room_type != spec["room_type"]:
                continue
            evidence = db.scalar(
                select(RoomEvidence)
                .where(RoomEvidence.room_id == room.id)
                .order_by(RoomEvidence.created_at.desc(), RoomEvidence.id.desc())
                .limit(1)
            )
            result = arithmetic(
                room.declared_area,
                evidence.certified_area if evidence else None,
                spec["minimum"],
                bool(evidence and evidence.reliable),
            )
            value = {
                **base,
                **result,
                "room_id": room.id,
                "room_code": room.room_code,
                "declared_m2": room.declared_area,
                "certified_m2": evidence.certified_area if evidence else None,
                "minimum_m2": spec["minimum"],
                "evidence_id": evidence.id if evidence else None,
                "version_id": evidence.version_id if evidence else None,
                "page": evidence.page if evidence else None,
                "bbox": evidence.bbox if evidence else None,
            }
            outcomes.append(value)
    for outcome in outcomes:
        run = RuleRun(evaluation_id=evaluation.id, rule_id=outcome["rule_id"], payload=outcome)
        db.add(run)
        db.flush()
        rule_node = EvidenceNode(
            revision_id=revision.id, kind="RULE_RUN", reference={"run_id": run.id, **outcome}
        )
        db.add(rule_node)
        db.flush()
        if outcome.get("version_id"):
            node = EvidenceNode(
                revision_id=revision.id,
                kind="CERTIFIED_ROOM_INPUT",
                reference={
                    k: outcome[k]
                    for k in [
                        "room_id",
                        "evidence_id",
                        "version_id",
                        "page",
                        "bbox",
                        "declared_m2",
                        "certified_m2",
                    ]
                },
            )
            db.add(node)
            db.flush()
            db.add(
                EvidenceEdge(
                    revision_id=revision.id, from_node=node.id, to_node=rule_node.id, relationship="SUPPORTS"
                )
            )
        checks = []
        if outcome.get("mismatch"):
            checks.append(("FACTUAL_AREA_MISMATCH", outcome["mismatch"]))
        if outcome.get("deficiency"):
            checks.append(("POTENTIAL_AREA_DEFICIENCY", outcome["deficiency"]))
        if outcome["state"] == "INSUFFICIENT_EVIDENCE":
            checks.append(("INSUFFICIENT_EVIDENCE", None))
        for code, amount in checks:
            db.add(
                Finding(
                    evaluation_id=evaluation.id,
                    rule_id=outcome.get("canonical_rule_id"),
                    evidence_node_id=rule_node.id,
                    evidence_gap="Certified room/division evidence absent or unreliable"
                    if code == "INSUFFICIENT_EVIDENCE"
                    else None,
                    method="DETERMINISTIC_ROOM_AREA_V1",
                    visibility="OFFICER",
                    severity="ADVISORY",
                    human_review_required=True,
                    payload={
                        **outcome,
                        "code": code,
                        "amount_m2": amount,
                        "message": code.replace("_", " ") + (f": {amount} m²" if amount is not None else ""),
                    },
                )
            )
    state.latest_evaluation_id = evaluation.id
    return {
        "evaluation_id": evaluation.id,
        "context": context,
        "results": outcomes,
        "official_decision": False,
    }
