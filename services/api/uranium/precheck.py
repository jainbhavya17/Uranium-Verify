"""Deterministic institution-safe checks over saved, versioned inputs."""

import re
import unicodedata
from datetime import date

from fastapi import HTTPException
from sqlalchemy import select

from .models import (
    ApplicationCatalogue,
    DocumentVersion,
    ProcessingJob,
    PrecheckSnapshot,
    Evaluation,
    EvidenceNode,
    EvidenceEdge,
    Finding,
    Institution,
    ApprovalSnapshot,
)
from .processing import job_view, latest_job, result_for
PRECHECK_VERSION = "precheck-2-originals-workflow"


def canonical(value):
    value = unicodedata.normalize("NFKC", value or "").casefold()
    return " ".join(re.findall(r"\w+", value))


def inputs(db, case, draft):
    from .institution_service import checklist_view, fingerprint

    checklist = checklist_view(db, case, draft)
    evidence = []
    for item in checklist["items"]:
        if item["evidence"]:
            version = db.get(DocumentVersion, item["evidence"]["id"])
            job = latest_job(db, version.id)
            result = result_for(db, job)
            evidence.append(
                [
                    item["id"],
                    version.id,
                    job.id if job else None,
                    job.state if job else None,
                    result.id if result else None,
                ]
            )
    return fingerprint(
        {
            "precheck_version": PRECHECK_VERSION,
            "details": draft.details,
            "baseline": draft.baseline_snapshot_id,
            "catalogue": draft.catalogue_id,
            "requirements": checklist["items"],
            "evidence": evidence,
        }
    )


def document_checks(db, case, draft, checklist):
    blocking, advisory = [], []
    reference = db.get(ApplicationCatalogue, draft.catalogue_id).definition["reference_date"]
    identity = db.get(Institution, case.institution_id)
    from .institution_service import snapshot_view

    baseline = snapshot_view(db, db.get(ApprovalSnapshot, draft.baseline_snapshot_id))["profile"]
    for item in checklist["items"]:
        evidence = item["evidence"]
        if not evidence or evidence["status"] == "SYNTHETIC_FIXTURE":
            continue
        version = db.get(DocumentVersion, evidence["id"])
        view = job_view(db, version)
        if view["state"] != "PROCESSED":
            blocking.append(
                {
                    "code": "FILE_NOT_READY",
                    "requirement_id": item["id"],
                    "message": item["label"] + ": " + (view["message"] or view["state"].replace("_", " ")),
                    "version_id": version.id,
                    "source": item["source"],
                }
            )
            continue
        if not item["mandatory"]:
            advisory.append(
                item["label"] + ": not due at this stage; later-stage content review remains pending."
            )
            continue
        fields = {f["key"]: f for f in view["fields"]}
        for key, expected in [
            ("institution_name", draft.details["proposed_name"]),
            ("address", draft.details["proposed_address"]),
            ("permanent_id", identity.permanent_id),
        ]:
            observations = [f for f in view["fields"] if f["key"] == key]
            for field in observations:
                if field["normalized"] is None or (field["confidence"] or 0) < 0.8:
                    continue
                historical = baseline.get(
                    {"institution_name": "name", "address": "address"}.get(key, "permanent_id")
                )
                if (
                    key != "permanent_id"
                    and canonical(expected) != canonical(historical)
                    and canonical(field["normalized"]) == canonical(historical)
                ):
                    advisory.append(
                        item["label"]
                        + ": evidence carries the approved historical "
                        + key.replace("_", " ")
                        + "; a proposed change is declared and needs human review. It is not automatically a discrepancy."
                    )
                    continue
                if canonical(field["normalized"]) != canonical(expected):
                    blocking.append(
                        {
                            "code": "FACTUAL_MISMATCH",
                            "requirement_id": item["id"],
                            "message": f"{item['label']}: {key.replace('_', ' ')} differs from the declared request. Correct the evidence or declaration; declared changes are compared against requested values.",
                            "field_id": field["id"],
                            "version_id": version.id,
                            "page": field["page"],
                            "bbox": field["bbox"],
                            "source": item["source"],
                            "human_review_required": True,
                        }
                    )
        if not any(
            f["key"] in {"institution_name", "permanent_id"}
            and f["normalized"]
            and (f["confidence"] or 0) >= 0.8
            for f in view["fields"]
        ):
            blocking.append(
                {
                    "code": "IDENTITY_UNKNOWN",
                    "requirement_id": item["id"],
                    "version_id": version.id,
                    "message": item["label"]
                    + ": institution identity could not be extracted; replace or request manual review.",
                }
            )
        for field in view["fields"]:
            if (
                field["key"] == "issue_date"
                and field["normalized"]
                and (field["confidence"] or 0) >= 0.8
                and field["normalized"] > reference
            ):
                blocking.append(
                    {
                        "code": "ISSUED_AFTER_REFERENCE",
                        "requirement_id": item["id"],
                        "version_id": version.id,
                        "field_id": field["id"],
                        "page": field["page"],
                        "bbox": field["bbox"],
                        "source": item["source"],
                        "message": item["label"]
                        + ": issue date is after the configured reference date "
                        + reference
                        + ". Check the dated evidence.",
                    }
                )
        if evidence["document_type"] == "AUDITED_ACCOUNTS":
            academic = fields.get("academic_year")
            year = int(case.academic_year[:4]) - 1
            previous = f"{year}-{str(year + 1)[-2:]}"
            if not academic or academic["normalized"] != previous or (academic["confidence"] or 0) < 0.8:
                blocking.append(
                    {
                        "code": "ACCOUNTS_YEAR_UNRESOLVED",
                        "requirement_id": item["id"],
                        "version_id": version.id,
                        "message": "Previous-year audited accounts must identify "
                        + previous
                        + ". Missing or different year needs correction/manual review.",
                        "source": item["source"],
                    }
                )
        if evidence["document_type"] == "FIRE_SAFETY":
            field = fields.get("expiry_date")
            if not field or not field["normalized"] or (field["confidence"] or 0) < 0.8:
                blocking.append(
                    {
                        "code": "DATE_UNKNOWN",
                        "requirement_id": item["id"],
                        "version_id": version.id,
                        "message": "Fire certificate expiry is unknown. This is an evidence gap, not an expired-certificate finding.",
                    }
                )
            elif date.fromisoformat(field["normalized"]) < date.fromisoformat(reference):
                blocking.append(
                    {
                        "code": "EXPIRED",
                        "requirement_id": item["id"],
                        "version_id": version.id,
                        "field_id": field["id"],
                        "page": field["page"],
                        "bbox": field["bbox"],
                        "source": item["source"],
                        "message": f"Fire certificate expires before the configured reference date {reference}. Upload a valid certificate.",
                    }
                )
        for field in view["fields"]:
            if field["normalized"] is None:
                advisory.append(f"{item['label']}: {field['key']} is unknown; no value was invented.")
        if view.get("scanner_mode") == "MOCK_TEST":
            advisory.append(
                "MOCK scanner configured: no real malware protection. Synthetic demonstration only."
            )
    return blocking, list(dict.fromkeys(advisory))


def current_snapshot(db, case, draft, checksum):
    return db.scalar(
        select(PrecheckSnapshot)
        .where(
            PrecheckSnapshot.revision_id == draft.revision_id,
            PrecheckSnapshot.application_version == draft.lock_version,
            PrecheckSnapshot.input_hash == checksum,
        )
        .order_by(PrecheckSnapshot.created_at.desc(), PrecheckSnapshot.id.desc())
        .limit(1)
    )


def view_precheck(db, case, draft, save=False):
    from .institution_service import readiness_view

    checksum = inputs(db, case, draft)
    old = current_snapshot(db, case, draft, checksum)
    if old and old.input_hash == checksum:
        return {**old.payload, "precheck_id": old.id, "stale": False}
    result = readiness_view(db, case, draft)
    if not save:
        return {**result, "precheck_id": None, "stale": True}
    evaluation = Evaluation(
        revision_id=draft.revision_id, ruleset_id=result["checklist"]["ruleset_id"], state="COMPLETED"
    )
    db.add(evaluation)
    db.flush()
    root = EvidenceNode(
        revision_id=draft.revision_id,
        kind="RULE_EVALUATION",
        reference={
            "evaluation_id": evaluation.id,
            "input_hash": checksum,
            "application_version": draft.lock_version,
            "ruleset_id": evaluation.ruleset_id,
            "processor_version": PRECHECK_VERSION,
        },
    )
    db.add(root)
    db.flush()
    # Immutable snapshots of the declaration and published baseline remain distinct graph nodes.
    for kind, ref in [
        ("DECLARATION", {"details": draft.details, "application_version": draft.lock_version}),
        ("APPROVED_SNAPSHOT", {"snapshot_id": draft.baseline_snapshot_id}),
    ]:
        node = EvidenceNode(revision_id=draft.revision_id, kind=kind, reference=ref)
        db.add(node)
        db.flush()
        db.add(
            EvidenceEdge(
                revision_id=draft.revision_id, from_node=node.id, to_node=root.id, relationship="DECLARES"
            )
        )
    for item in result["checklist"]["items"]:
        if item["evidence"]:
            node = EvidenceNode(
                revision_id=draft.revision_id,
                kind="CHECKED_VERSION",
                reference={
                    "version_id": item["evidence"]["id"],
                    "sha256": item["evidence"]["sha256"],
                    "requirement_id": item["id"],
                },
            )
            db.add(node)
            db.flush()
            db.add(
                EvidenceEdge(
                    revision_id=draft.revision_id, from_node=node.id, to_node=root.id, relationship="SUPPORTS"
                )
            )
    for finding in result["blocking"]:
        node = None
        if finding.get("version_id"):
            node = EvidenceNode(
                revision_id=draft.revision_id,
                kind="FINDING_INPUT",
                reference={k: finding[k] for k in ("version_id", "field_id", "page", "bbox") if k in finding},
            )
            db.add(node)
            db.flush()
            db.add(
                EvidenceEdge(
                    revision_id=draft.revision_id,
                    from_node=node.id,
                    to_node=root.id,
                    relationship="CONTRADICTS",
                )
            )
        db.add(
            Finding(
                evaluation_id=evaluation.id,
                evidence_node_id=node.id if node else None,
                evidence_gap=None if node else finding["message"][:500],
                method=PRECHECK_VERSION,
                visibility="INSTITUTION",
                severity="BLOCKING",
                human_review_required=True,
                payload=finding,
            )
        )
    saved = PrecheckSnapshot(
        revision_id=draft.revision_id,
        evaluation_id=evaluation.id,
        application_version=draft.lock_version,
        input_hash=checksum,
        payload=result,
    )
    db.add(saved)
    db.flush()
    return {**result, "precheck_id": saved.id, "stale": False}


def assert_current(db, case, draft, identifier, expected):
    # Phase 2 controlled fixtures retain their explicitly labelled checklist-only test path.
    has_processing = db.scalar(
        select(ProcessingJob.id)
        .join(DocumentVersion, DocumentVersion.id == ProcessingJob.version_id)
        .where(DocumentVersion.revision_id == draft.revision_id)
        .limit(1)
    )
    if not has_processing:
        return
    saved = db.get(PrecheckSnapshot, identifier) if identifier else None
    if (
        not saved
        or saved.revision_id != draft.revision_id
        or saved.application_version != expected
        or saved.input_hash != inputs(db, case, draft)
    ):
        raise HTTPException(
            409,
            "Precheck missing or stale. Run precheck against the latest saved revision and processing results.",
        )
