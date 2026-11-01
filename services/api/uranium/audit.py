import hashlib
import json

from .models import AuditEvent


def append_audit(db, actor_id, operation, target_id, request_id, metadata=None):
    # Hash a bounded caller-selected summary. No passwords, tokens or document content.
    checksum = hashlib.sha256(json.dumps(metadata or {}, sort_keys=True).encode()).hexdigest()
    db.add(
        AuditEvent(
            actor_id=actor_id,
            operation=operation,
            target_id=target_id,
            request_id=request_id,
            metadata_digest=checksum,
        )
    )
