"""Idempotent, conspicuously synthetic scrutiny pack. Never rotates existing identities."""

import hashlib
import os
import secrets
import time
from sqlalchemy import select
from .models import (
    User,
    Membership,
    Application,
    ApplicationCatalogue,
    Revision,
    RoomRecord,
    Document,
    DocumentVersion,
    ExtractedField,
    Assignment,
    ReviewState,
    GovernedVersion,
    RoomEvidence,
    Connector,
)
from .auth import password_hash
from .seed import fixture_id
from .audit import append_audit
from .officer_contracts import GovernanceDraft, GovernanceAction
from .governance import create_version, govern


def seed_officer(db, storage, password, case_key="phase4-room-case"):
    if len(password) < 12:
        raise RuntimeError("Phase 4 initial demo identities require a configured >=12-character password.")
    author = db.scalar(select(User).where(User.email == "platform@demo.uranium.test"))
    reviewer = db.scalar(select(User).where(User.email == "approver@demo.uranium.test"))
    if not reviewer:
        reviewer = User(
            id=fixture_id("phase4-approver"),
            email="approver@demo.uranium.test",
            name="MOCK Rule Approver",
            password_hash=password_hash(password),
        )
        db.add(reviewer)
        db.flush()
        db.add(Membership(user_id=reviewer.id, role_id="admin"))
    from types import SimpleNamespace

    author_p = SimpleNamespace(user=author)
    reviewer_p = SimpleNamespace(user=reviewer)
    drafter = db.scalar(select(User).where(User.email == "drafter@demo.uranium.test"))
    if not drafter:
        drafter = User(
            id=fixture_id("phase4-drafter"),
            email="drafter@demo.uranium.test",
            name="MOCK Governance Drafter",
            password_hash=password_hash(password),
        )
        db.add(drafter)
        db.flush()
        db.add(Membership(user_id=drafter.id, role_id="admin"))
    scope = {
        "years": ["2026-27"],
        "categories": ["EOA", "INTAKE_INCREASE"],
        "programmes": ["Engineering & Technology"],
        "stages": ["SCRUTINY", "EVC"],
        "effective_from": "2026-01-01",
        "effective_until": "2027-12-31",
        "roles": ["officer", "specialist", "supervisor", "admin"],
    }
    source = db.scalar(
        select(GovernedVersion).where(
            GovernedVersion.code == "MOCK_APH_CLASSROOM", GovernedVersion.kind == "SOURCE"
        )
    )
    if not source:
        body = GovernanceDraft(
            kind="SOURCE",
            code="MOCK_APH_CLASSROOM",
            rationale="Seed reviewed SRS classroom demonstration source; no live regulatory approval.",
            payload={
                "scope": scope,
                "title": "MOCK APH classroom selected passage",
                "source_url": "https://www.aicte.gov.in/sites/default/files/APH%20Final.pdf",
                "publication_date": "2024-01-01",
                "clause": "Annexure 3.2.1 — SRS demonstration transcription",
                "printed_page": 87,
                "pdf_page": 103,
                "text": "SRS DEMO: Engineering & Technology classroom carpet area reference for a division of 60 is 66 square metres. A certified schedule of 58 square metres compared with declared 75 creates distinct factual mismatch 17 and potential deficiency 8. Verify programme, division, stage, exceptions and effective rule version. This is a reviewed synthetic test transcription, not current official approval.",
                "interpretation": "SRS_DEMO_TRANSCRIPTION",
            },
        )
        created = create_version(db, author_p, body, "phase4-seed")
        source = db.get(GovernedVersion, created["id"])
        govern(
            db,
            reviewer_p,
            source,
            GovernanceAction(
                action="APPROVE",
                rationale="Separate synthetic rule-owner identity reviewed the SRS demonstration passage.",
            ),
            "phase4-seed",
        )
    rule = db.scalar(
        select(GovernedVersion).where(
            GovernedVersion.code == "MOCK_ENG_CLASSROOM_60", GovernedVersion.kind == "RULE"
        )
    )
    if not rule:
        created = create_version(
            db,
            author_p,
            GovernanceDraft(
                kind="RULE",
                code="MOCK_ENG_CLASSROOM_60",
                source_id=source.id,
                rationale="Selected SRS demo rule; limited to Engineering classroom division 60.",
                payload={
                    "scope": scope,
                    "metric": "CLASSROOM_AREA_MINIMUM",
                    "minimum": 66,
                    "division": 60,
                    "exception_codes": ["MOCK_CLASSROOM_EXEMPTION"],
                },
            ),
            "phase4-seed",
        )
        rule = db.get(GovernedVersion, created["id"])
        govern(
            db,
            reviewer_p,
            rule,
            GovernanceAction(
                action="APPROVE",
                rationale="Separate reviewer approved typed scope and synthetic classroom arithmetic.",
            ),
            "phase4-seed",
        )
        govern(
            db,
            reviewer_p,
            rule,
            GovernanceAction(
                action="PUBLISH", rationale="Synthetic 75/58/66 and insufficient-evidence dry-runs passed."
            ),
            "phase4-seed",
        )
    case = db.get(Application, fixture_id(case_key))
    if not case:
        import pymupdf

        institution_id = fixture_id("institution-a")
        actor = fixture_id("admin.a@demo.uranium.test")
        case = Application(
            id=fixture_id(case_key),
            institution_id=institution_id,
            category="EOA",
            academic_year="2026-27",
            status="SUBMITTED",
            is_mock=True,
        )
        db.add(case)
        db.flush()
        catalogue = db.scalar(
            select(ApplicationCatalogue).where(
                ApplicationCatalogue.code == "EOA", ApplicationCatalogue.academic_year == "2026-27"
            )
        )
        rev = Revision(
            application_id=case.id,
            number=1,
            actor_id=actor,
            ruleset_id=catalogue.ruleset_id,
            manifest={
                "is_mock": True,
                "details": {
                    "programme": "Engineering & Technology",
                    "proposed_name": "MOCK Engineering Classroom Institution",
                    "courses": [{"course": "Engineering", "requested_intake": 60}],
                    "rooms": [{"room_id": "C101", "declared_area": 75}],
                },
            },
        )
        db.add(rev)
        db.flush()
        room = RoomRecord(revision_id=rev.id, room_code="C101", room_type="CLASSROOM", declared_area=75)
        db.add(room)
        doc = Document(application_id=case.id, document_type="MOCK_ARCHITECT_ROOM_SCHEDULE")
        db.add(doc)
        db.flush()
        pdf = pymupdf.open()
        page = pdf.new_page()
        page.insert_text(
            (50, 65),
            "MOCK / SYNTHETIC ARCHITECT SCHEDULE\nRoom C101\nProgramme: Engineering & Technology\nDivision size: 60\nCertified area: 58 m2\nDeclared area: 75 m2",
            fontsize=12,
        )
        data = pdf.tobytes()
        key = secrets.token_hex(32)
        storage.write_once(key, data)
        version = DocumentVersion(
            application_id=case.id,
            document_id=doc.id,
            revision_id=rev.id,
            number=1,
            sha256=hashlib.sha256(data).hexdigest(),
            storage_key=key,
            original_name="MOCK-architect-room-C101.pdf",
            media_type="application/pdf",
            uploader_id=actor,
            status="SYNTHETIC_FIXTURE",
            is_mock=True,
        )
        db.add(version)
        db.flush()
        # Explicit reviewed fixture observation, never represented as live OCR.
        db.add(
            ExtractedField(
                version_id=version.id,
                page=1,
                field_key="room_area_m2",
                value={
                    "raw": "58 m2",
                    "normalized": "58",
                    "method": "MOCK_REVIEWED_FIXTURE",
                    "uncertainty": "SYNTHETIC",
                },
                bounding_box=[50, 110, 300, 145],
                confidence=1,
                processor_version="mock-room-schedule-1",
            )
        )
        db.add(
            RoomEvidence(
                room_id=room.id,
                version_id=version.id,
                page=1,
                bbox=[50, 110, 300, 145],
                certified_area=58,
                actor_id=fixture_id("officer.a@demo.uranium.test"),
                source_ref="MOCK architect schedule C101 / page 1",
                reliable=True,
            )
        )
        db.add(
            ReviewState(
                id=case.id,
                revision_id=rev.id,
                version=1,
                due_at=int(time.time()) + 7 * 86400,
                context={
                    "division": 60,
                    "stage": "SCRUTINY",
                    "division_source": {"version_id": version.id, "page": 1},
                },
            )
        )
        db.add(
            Assignment(
                application_id=case.id,
                user_id=fixture_id("officer.a@demo.uranium.test"),
                scope="REVIEW",
                active=True,
            )
        )
        db.add(
            Assignment(
                application_id=case.id,
                user_id=fixture_id("supervisor@demo.uranium.test"),
                scope="SUPERVISE",
                active=True,
            )
        )
        db.flush()
        rev.frozen = True
        rev.submitted_at = int(time.time())
    for code, annexure, printed, text, categories, stages in [
        (
            "MOCK_APH_EOA",
            "Annexure 2.1",
            81,
            "SRS DEMO EoA self-disclosure evidence includes Affidavit 2, conditional relevant-year payment receipt, one appropriate occupancy/completion/building-license/Form D alternative, conditional structural stability, valid fire safety certificate, satellite location map and previous-year audited accounts. Building age and reviewed government exceptions control the structural condition; current-year applicability requires domain-owner review.",
            ["EOA"],
            ["SUBMISSION", "SCRUTINY"],
        ),
        (
            "MOCK_APH_INTAKE",
            "Annexure 2.6",
            82,
            "SRS DEMO intake increase scrutiny uses Affidavit 8 unless Extended EoA applies, Format 3 organizational resolution and conditional Fellow Programme faculty evidence for Management. Approved intake 60 and requested intake 120 are distinct legitimate records, not automatic forgery. Review category, programme and due stage before checking evidence.",
            ["INTAKE_INCREASE"],
            ["SCRUTINY"],
        ),
    ]:
        if not db.scalar(
            select(GovernedVersion.id).where(GovernedVersion.kind == "SOURCE", GovernedVersion.code == code)
        ):
            created = create_version(
                db,
                author_p,
                GovernanceDraft(
                    kind="SOURCE",
                    code=code,
                    rationale="Curated SRS demonstration passage, separate from live official regulatory approval.",
                    payload={
                        "scope": {
                            **scope,
                            "categories": categories,
                            "stages": stages,
                            "programmes": ["Engineering & Technology", "Management"],
                        },
                        "title": "MOCK SRS-curated " + annexure,
                        "source_url": "https://www.aicte.gov.in/sites/default/files/APH%20Final.pdf",
                        "publication_date": "2024-01-01",
                        "clause": annexure,
                        "printed_page": printed,
                        "pdf_page": printed + 16,
                        "text": text,
                        "interpretation": "SRS_DEMO_TRANSCRIPTION",
                    },
                ),
                "phase4-seed",
            )
            govern(
                db,
                reviewer_p,
                db.get(GovernedVersion, created["id"]),
                GovernanceAction(
                    action="APPROVE",
                    rationale="Separate synthetic source owner reviewed the bounded cited SRS transcription.",
                ),
                "phase4-seed",
            )
    for scenario in ["match", "conflict", "timeout", "unsupported"]:
        identifier = fixture_id("phase4-issuer-" + scenario)
        if not db.get(Connector, identifier):
            db.add(
                Connector(
                    id=identifier,
                    name="MOCK issuer demonstration / " + scenario,
                    mode="MOCK",
                    status="AVAILABLE",
                )
            )
    append_audit(db, author.id, "PHASE4_SYNTHETIC_SEED", case.id, "phase4-seed")
    db.flush()
    return {"case_id": case.id, "approver_email": reviewer.email, "source_id": source.id, "rule_id": rule.id}


def main():
    from .config import Settings
    from .db import make_engine, session_factory
    from .storage import LocalPrivateStorage

    settings = Settings()
    settings.validate()
    with session_factory(make_engine(settings.database_url))() as db:
        result = seed_officer(
            db,
            LocalPrivateStorage(settings.storage_root),
            os.getenv("PHASE4_DEMO_PASSWORD") or os.getenv("DEMO_PASSWORD", ""),
        )
        db.commit()
    print("Synthetic Phase 4 pack ready; no passwords were printed.", result)


if __name__ == "__main__":
    main()
