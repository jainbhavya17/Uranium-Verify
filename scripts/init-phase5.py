"""Additive local release pack. Existing submissions, secrets and passwords are preserved."""

import copy
import hashlib
import importlib.util
import json
import os
import secrets
import sys
import time
from pathlib import Path
from types import SimpleNamespace
from sqlalchemy import select

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "services/api"))
from uranium.config import Settings
from uranium.db import make_engine, session_factory
from uranium.models import (
    Application,
    Assignment,
    Clarification,
    ClarificationScope,
    Document,
    DocumentVersion,
    GovernedVersion,
    Institution,
    Revision,
    User,
)
from uranium.storage import LocalPrivateStorage
from uranium.seed import fixture_id
from uranium.seed_officer import seed_officer
from uranium.officer_contracts import GovernanceDraft, GovernanceAction
from uranium.governance import create_version, govern


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


def initialize():
    settings = Settings()
    settings.validate()
    if settings.environment not in {"development", "test"}:
        raise SystemExit("Synthetic release seeding is local development/test only.")
    password = os.getenv("PHASE4_DEMO_PASSWORD") or os.getenv("DEMO_PASSWORD", "")
    if len(password) < 12:
        raise SystemExit(
            "Run scripts/init-phase4.py to configure a sufficiently long separate demo credential first."
        )
    storage = LocalPrivateStorage(settings.storage_root)
    root = Path("var/phase5-fixtures")
    root.mkdir(parents=True, exist_ok=True)
    generator = module("processing_fixture_setup", Path("scripts/generate-processing-fixtures.py"))
    generator.generate(root)
    provenance = root / "provenance"
    if not (provenance / "signed.jpg").exists():
        module("provenance_fixture_setup", Path("scripts/generate-provenance-fixtures.py")).generate(
            provenance
        )
    with session_factory(make_engine(settings.database_url))() as db:
        pack = seed_officer(db, storage, password, case_key="phase5-demo-case")
        case = db.get(Application, pack["case_id"])
        from uranium.models import ApprovalSnapshot
        from uranium.institution_service import snapshot_view

        institution = db.get(Institution, case.institution_id)
        baseline = db.scalar(
            select(ApprovalSnapshot)
            .where(ApprovalSnapshot.institution_id == institution.id, ApprovalSnapshot.published.is_(True))
            .order_by(ApprovalSnapshot.academic_year.desc(), ApprovalSnapshot.version.desc())
            .limit(1)
        )
        profile = snapshot_view(db, baseline)["profile"] if baseline else {"address": "MOCK Campus"}
        for name, expiry in [
            ("own-institution-fire.pdf", "2027-06-30"),
            ("own-institution-expired-fire.pdf", "2020-01-01"),
        ]:
            (root / name).write_bytes(
                generator.pdf_bytes(
                    name=institution.name,
                    permanent_id=institution.permanent_id,
                    address=profile.get("address", "MOCK Campus"),
                    expiry=expiry,
                )
            )
        import pymupdf
        from PIL import Image, ImageFilter

        with pymupdf.open(root / "own-institution-fire.pdf") as original:
            pixels = original[0].get_pixmap(dpi=200, alpha=False)
            Image.frombytes("RGB", (pixels.width, pixels.height), pixels.samples).filter(
                ImageFilter.GaussianBlur(6)
            ).save(root / "own-institution-blurred.png")
        parent = db.scalar(
            select(Revision)
            .where(Revision.application_id == case.id, Revision.frozen.is_(True))
            .order_by(Revision.number.desc())
            .limit(1)
        )
        identifier = fixture_id("phase5-focused-clarification")
        if not db.get(Clarification, identifier):
            db.add(
                Clarification(
                    id=identifier,
                    application_id=case.id,
                    actor_id=fixture_id("officer.a@demo.uranium.test"),
                    message="MOCK request: confirm the authorized signatory and supply a current readable fire safety original. Prior submissions and evidence must remain preserved.",
                    published=True,
                    allowed_until=int(time.time()) + 7 * 86400,
                )
            )
            db.flush()
            db.add(
                ClarificationScope(
                    id=identifier,
                    original_revision_id=parent.id,
                    allowed_fields=["signatory"],
                    document_types=["FIRE_SAFETY"],
                    required_documents=["FIRE_SAFETY"],
                )
            )
            case.status = "CLARIFICATION_REQUESTED"
        institution = db.get(Institution, case.institution_id)
        (root / "response-fire.pdf").write_bytes(
            generator.pdf_bytes(
                name=institution.name,
                permanent_id=institution.permanent_id,
                address="MOCK Campus, Demo City",
                expiry="2028-06-30",
            )
        )
        source = db.get(GovernedVersion, pack["source_id"])
        author = db.get(User, source.author_id)
        approver = db.get(User, source.approver_id)
        for code, supersede in [("MOCK_RELEASE_IRRELEVANT", False), ("MOCK_RELEASE_SUPERSEDED", True)]:
            if not db.scalar(select(GovernedVersion).where(GovernedVersion.code == code)):
                payload = copy.deepcopy(source.payload)
                if not supersede:
                    payload["scope"]["years"] = ["2024-25"]
                payload["title"] = "MOCK release retrieval exclusion fixture"
                created = create_version(
                    db,
                    SimpleNamespace(user=author),
                    GovernanceDraft(
                        kind="SOURCE",
                        code=code,
                        payload=payload,
                        rationale="Synthetic release fixture exercises irrelevant and superseded source exclusion.",
                    ),
                    "phase5-seed",
                )
                row = db.get(GovernedVersion, created["id"])
                govern(
                    db,
                    SimpleNamespace(user=approver),
                    row,
                    GovernanceAction(
                        action="APPROVE",
                        rationale="Independent synthetic source approval for release validation.",
                    ),
                    "phase5-seed",
                )
                if supersede:
                    govern(
                        db,
                        SimpleNamespace(user=approver),
                        row,
                        GovernanceAction(
                            action="SUPERSEDE",
                            rationale="Superseded synthetic source must remain excluded from retrieval.",
                        ),
                        "phase5-seed",
                    )
        provenance_case = fixture_id("phase5-provenance-case")
        if not db.get(Application, provenance_case):
            app = Application(
                id=provenance_case,
                institution_id=case.institution_id,
                category="EOA",
                academic_year="2026-27",
                status="SUBMITTED",
                is_mock=True,
            )
            db.add(app)
            db.flush()
            rev = Revision(
                application_id=app.id,
                number=1,
                actor_id=parent.actor_id,
                ruleset_id=parent.ruleset_id,
                manifest={},
            )
            db.add(rev)
            db.flush()
            ids = []
            for name, mime in [
                ("signed.jpg", "image/jpeg"),
                ("unsigned.jpg", "image/jpeg"),
                ("signed.pdf", "application/pdf"),
            ]:
                doc = Document(application_id=app.id, document_type="MOCK_PROVENANCE_FIXTURE")
                db.add(doc)
                db.flush()
                content = (provenance / name).read_bytes()
                key = secrets.token_hex(32)
                storage.write_once(key, content)
                version = DocumentVersion(
                    document_id=doc.id,
                    application_id=app.id,
                    revision_id=rev.id,
                    number=1,
                    sha256=hashlib.sha256(content).hexdigest(),
                    storage_key=key,
                    original_name="MOCK-" + name,
                    media_type=mime,
                    uploader_id=parent.actor_id,
                    status="SYNTHETIC_FIXTURE",
                    is_mock=True,
                )
                db.add(version)
                db.flush()
                ids.append(version.id)
            rev.manifest = {
                "is_mock": True,
                "details": {"programme": "Engineering & Technology"},
                "document_version_ids": ids,
                "fixture_note": "Controlled generated originals; no OCR or live issuer confirmation is claimed.",
            }
            rev.frozen = True
            rev.submitted_at = int(time.time())
            db.add(
                Assignment(
                    application_id=app.id,
                    user_id=fixture_id("officer.a@demo.uranium.test"),
                    scope="REVIEW",
                    active=True,
                )
            )
        db.commit()
        output = {**pack, "clarification_id": identifier, "provenance_case_id": provenance_case}
    (root / "manifest.json").write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    print("Additive MOCK Phase 5 fixtures ready. IDs:", json.dumps(output))
    print(
        "Existing passwords preserved. No credential values were printed. Trust test roots only in isolated verification."
    )


if __name__ == "__main__":
    initialize()
