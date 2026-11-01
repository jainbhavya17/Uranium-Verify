"""Single gateway for reconciliation and certificate checks. No fixture becomes LIVE."""

import time
from fastapi import HTTPException
from sqlalchemy import select, func
from .models import Connector, VerificationAttempt, EvidenceNode


def verify(db, case, version, body):
    provider = db.get(Connector, body.provider_id)
    if not provider:
        raise HTTPException(404, "Connector unavailable.")
    count = db.scalar(
        select(func.count())
        .select_from(VerificationAttempt)
        .where(VerificationAttempt.version_id == version.id, VerificationAttempt.connector_id == provider.id)
    )
    if count >= 3:
        raise HTTPException(409, "Issuer retry budget exhausted; route a sourced manual task.")
    if provider.mode != "MOCK" or provider.status not in {"AVAILABLE", "MOCK_READY"}:
        status = "SOURCE_UNAVAILABLE"
        supported = False
    else:
        status = {
            "match": "MATCH",
            "conflict": "CONFLICT",
            "timeout": "TIMEOUT",
            "unsupported": "UNSUPPORTED",
        }[body.fixture]
        supported = status != "UNSUPPORTED"
    payload = {
        "provider": provider.name,
        "mode": provider.mode,
        "support_state": "SUPPORTED" if supported else "UNAVAILABLE_OR_UNSUPPORTED",
        "status": status,
        "source_time": int(time.time())
        if provider.mode == "MOCK" and status in {"MATCH", "CONFLICT"}
        else None,
        "checked_at": int(time.time()),
        "matched_fields": {"certificate_id": body.certificate_id} if status == "MATCH" else {},
        "proof_ref": f"MOCK-REGISTRY:{body.fixture}:{version.sha256[:12]}"
        if provider.mode == "MOCK" and supported
        else None,
        "external_confirmation": False,
        "is_mock": provider.mode == "MOCK",
        "attempt": count + 1,
        "meaning": "Synthetic registry response, not live issuer confirmation."
        if provider.mode == "MOCK"
        else "No authorized live adapter configured.",
        "version_id": version.id,
    }
    row = VerificationAttempt(
        application_id=case.id,
        version_id=version.id,
        connector_id=provider.id,
        status=status,
        mode=provider.mode,
        source_response=payload,
    )
    db.add(row)
    db.flush()
    db.add(
        EvidenceNode(
            revision_id=version.revision_id,
            kind="ISSUER_ATTEMPT",
            reference={
                "attempt_id": row.id,
                "version_id": version.id,
                "status": status,
                "mode": provider.mode,
            },
        )
    )
    return {"id": row.id, **payload}
