"""Explicit opt-in, additive, repeatable synthetic fixture seeding. Never resets data."""

import hashlib
import os
import time
import uuid

from sqlalchemy import select

from .audit import append_audit
from .auth import ROLES, password_hash
from .config import Settings
from .db import make_engine, session_factory
from .models import (
    Application,
    ApprovalSnapshot,
    Assignment,
    Clarification,
    Connector,
    Document,
    DocumentVersion,
    Institution,
    Membership,
    Revision,
    Role,
    User,
)
from .storage import LocalPrivateStorage


def fixture_id(name):
    return str(uuid.uuid5(uuid.NAMESPACE_URL, "uranium-mock:" + name))


ACCOUNTS = [
    ("submitter.a@demo.uranium.test", "Ananya Rao", "institution_submitter", "a"),
    ("admin.a@demo.uranium.test", "Aarav Mehta", "institution_admin", "a"),
    ("admin.b@demo.uranium.test", "Bhavna Shah", "institution_admin", "b"),
    ("officer.a@demo.uranium.test", "Priya Nair", "officer", None),
    ("officer.b@demo.uranium.test", "Rohan Das", "officer", None),
    ("specialist@demo.uranium.test", "Meera Iyer", "specialist", None),
    ("supervisor@demo.uranium.test", "Vikram Sen", "supervisor", None),
    ("platform@demo.uranium.test", "Devika Patel", "admin", None),
    ("auditor@demo.uranium.test", "Kabir Ali", "auditor", None),
]


def mock_pdf():
    # Minimal valid one-page PDF. Synthetic fixture only; no extraction claims.
    content = b"BT /F1 18 Tf 40 740 Td (MOCK - URANIUM VERIFY) Tj 0 -32 Td /F1 12 Tf (Synthetic approval record. Not official evidence.) Tj ET"
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(content)).encode() + b" >>\nstream\n" + content + b"\nendstream",
    ]
    result = b"%PDF-1.4\n"
    offsets = [0]
    for i, obj in enumerate(objects, 1):
        offsets.append(len(result))
        result += f"{i} 0 obj\n".encode() + obj + b"\nendobj\n"
    xref = len(result)
    result += b"xref\n0 6\n0000000000 65535 f \n"
    result += b"".join(f"{offset:010d} 00000 n \n".encode() for offset in offsets[1:])
    result += f"trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    return result


def seed(settings=None, password=None):
    settings = settings or Settings()
    settings.validate()
    password = password or os.getenv("DEMO_PASSWORD", "")
    if len(password) < 12:
        raise RuntimeError("Set DEMO_PASSWORD to at least 12 characters before seeding.")
    engine = make_engine(settings.database_url)
    factory = session_factory(engine)
    storage = LocalPrivateStorage(settings.storage_root)
    with factory() as db:

        def add(model, identifier, **values):
            existing = db.get(model, identifier)
            if existing:
                return existing
            obj = model(id=identifier, **values)
            db.add(obj)
            db.flush()
            return obj

        for role, label in ROLES.items():
            add(Role, role, label=label)
        for key, name in [("a", "Northstar Institute of Technology"), ("b", "Riverbend Technical Institute")]:
            add(
                Institution,
                fixture_id("institution-" + key),
                name=name,
                permanent_id="MOCK-PID-" + key.upper(),
                is_mock=True,
            )
        for email, name, role, key in ACCOUNTS:
            user = add(User, fixture_id(email), email=email, name=name, password_hash=password_hash(password))
            add(
                Membership,
                fixture_id("membership-" + email),
                user_id=user.id,
                role_id=role,
                institution_id=fixture_id("institution-" + key) if key else None,
            )
        actor = fixture_id("admin.a@demo.uranium.test")
        for key in ["a", "b"]:
            institution_id = fixture_id("institution-" + key)
            add(
                ApprovalSnapshot,
                fixture_id("snapshot-" + key),
                institution_id=institution_id,
                academic_year="2025-26",
                version=1,
                published=True,
                is_mock=True,
                payload={"course": "Computer Science & Engineering", "approved_intake": 60},
                source_ref="MOCK historical approval; no live AICTE integration",
            )
            case = add(
                Application,
                fixture_id("application-" + key),
                institution_id=institution_id,
                category="Routine EoA",
                academic_year="2026-27",
                status="SUBMITTED",
                is_mock=True,
            )
            revision = add(
                Revision,
                fixture_id("revision-" + key),
                application_id=case.id,
                number=1,
                actor_id=actor if key == "a" else fixture_id("admin.b@demo.uranium.test"),
                frozen=False,
                manifest={"is_mock": True},
                submitted_at=int(time.time()),
            )
            add(
                Assignment,
                fixture_id("assignment-" + key),
                application_id=case.id,
                user_id=fixture_id(f"officer.{key}@demo.uranium.test"),
                scope="REVIEW",
            )
            doc = add(
                Document, fixture_id("document-" + key), application_id=case.id, document_type="MOCK_APPROVAL"
            )
            content = mock_pdf()
            checksum = hashlib.sha256(content).hexdigest()
            add(
                DocumentVersion,
                fixture_id("version-" + key),
                document_id=doc.id,
                application_id=case.id,
                revision_id=revision.id,
                number=1,
                sha256=checksum,
                storage_key=hashlib.sha256((checksum + key).encode()).hexdigest(),
                original_name="mock-approval.pdf",
                media_type="application/pdf",
                uploader_id=revision.actor_id,
                status="SYNTHETIC_FIXTURE",
                is_mock=True,
            )
            storage.write_once(hashlib.sha256((checksum + key).encode()).hexdigest(), content)
            if not revision.frozen:
                revision.manifest = {"is_mock": True, "document_version_ids": [fixture_id("version-" + key)]}
                revision.frozen = True
                db.flush()
        for user_email, scope in [
            ("specialist@demo.uranium.test", "VERIFY"),
            ("supervisor@demo.uranium.test", "SUPERVISE"),
        ]:
            add(
                Assignment,
                fixture_id(scope),
                application_id=fixture_id("application-a"),
                user_id=fixture_id(user_email),
                scope=scope,
            )
        add(
            Clarification,
            fixture_id("clarification-a"),
            application_id=fixture_id("application-a"),
            actor_id=fixture_id("officer.a@demo.uranium.test"),
            published=True,
            message="Legacy MOCK reference request: confirm the certificate reference. A current submitted application requires its own scoped response policy.",
            allowed_until=1893456000,
        )
        add(
            Connector,
            fixture_id("connector"),
            name="Synthetic issuer registry",
            mode="MOCK",
            status="NOT_CONFIGURED",
        )
        if not db.scalar(select(User).where(User.email == "platform@demo.uranium.test")):
            raise RuntimeError("Synthetic identities missing")
        # Additive audit: one event per explicit seed invocation; fixtures themselves are idempotent.
        from .seed_institution import seed_institution

        seed_institution(db, fixture_id)
        append_audit(db, fixture_id("platform@demo.uranium.test"), "DEMO_SEED", "synthetic-pack-v1", "seed")
        db.commit()
    engine.dispose()
    print("Synthetic fixture pack ready. Existing identities/passwords were not overwritten.")


if __name__ == "__main__":
    seed()
