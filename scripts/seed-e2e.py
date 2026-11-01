"""Add isolated synthetic browser identities per run; never reset an existing institution."""

import json
import os
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "services/api"))
from uranium.auth import password_hash
from uranium.config import Settings
from uranium.db import make_engine, session_factory
from uranium.models import ApprovalSnapshot, Institution, InstitutionRouting, Membership, User
from uranium.seed import fixture_id, seed

settings = Settings()
password = os.environ.get("DEMO_PASSWORD", "")
seed(settings, password)
fixtures = {}
with session_factory(make_engine(settings.database_url))() as db:
    for scenario in [
        "journey",
        "intake",
        "quarantine",
        "conflict",
        "responsive",
        "processing",
        "release",
        "account",
        "performance",
    ]:
        institution_id = str(uuid.uuid4())
        email = f"e2e-{scenario}-{institution_id[:8]}@demo.uranium.test"
        institution = Institution(
            id=institution_id,
            name=f"MOCK {scenario.title()} Institute",
            permanent_id=f"MOCK-E2E-{institution_id[:8]}",
            is_mock=True,
        )
        user = User(email=email, name=f"Mock {scenario.title()} Admin", password_hash=password_hash(password))
        db.add_all([institution, user])
        db.flush()
        db.add(Membership(user_id=user.id, role_id="institution_admin", institution_id=institution_id))
        db.add(InstitutionRouting(id=institution_id, officer_id=fixture_id("officer.a@demo.uranium.test")))
        for year, intake in [("2024-25", 45), ("2025-26", 60)]:
            db.add(
                ApprovalSnapshot(
                    institution_id=institution_id,
                    academic_year=year,
                    version=1,
                    published=True,
                    is_mock=True,
                    source_ref="MOCK browser-test approval reference",
                    payload={
                        "course": "Computer Science & Engineering",
                        "approved_intake": intake,
                        "approval_reference": f"MOCK-E2E-{year}",
                        "profile": {
                            "name": institution.name,
                            "address": "MOCK Campus, Demo City",
                            "affiliation": "Mock State Technical University",
                            "institution_type": "self_financing",
                            "completion_date": "2000-01-01",
                        },
                    },
                )
            )
        fixtures[scenario] = {"email": email, "institution_id": institution_id}
        if scenario in {"processing", "release"}:
            import importlib.util

            spec = importlib.util.spec_from_file_location(
                "generator", Path("scripts/generate-processing-fixtures.py")
            )
            generator = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(generator)
            output = Path(
                "var/phase3-browser-fixtures" if scenario == "processing" else "var/phase5-browser-fixtures"
            )
            output.mkdir(parents=True, exist_ok=True)
            for file, expiry in [("fire.pdf", "2027-06-30"), ("expired.pdf", "2020-01-01")]:
                (output / file).write_bytes(
                    generator.pdf_bytes(
                        name=institution.name,
                        permanent_id=institution.permanent_id,
                        address="MOCK Campus, Demo City",
                        expiry=expiry,
                    )
                )
            if scenario == "release":
                from PIL import Image, ImageFilter
                import pymupdf

                with pymupdf.open(output / "fire.pdf") as document:
                    pix = document[0].get_pixmap(dpi=200, alpha=False)
                    Image.frombytes("RGB", (pix.width, pix.height), pix.samples).filter(
                        ImageFilter.GaussianBlur(6)
                    ).save(output / "blurred.png")
        if scenario == "performance":
            from uranium.models import Application, Assignment, Revision, ApplicationCatalogue
            from sqlalchemy import select

            catalogue = db.scalar(
                select(ApplicationCatalogue).where(
                    ApplicationCatalogue.code == "EOA", ApplicationCatalogue.academic_year == "2026-27"
                )
            )
            for n in range(100):
                case = Application(
                    institution_id=institution_id,
                    category="EOA",
                    academic_year="2026-27",
                    status="SUBMITTED",
                    is_mock=True,
                )
                db.add(case)
                db.flush()
                db.add(
                    Revision(
                        application_id=case.id,
                        number=1,
                        actor_id=user.id,
                        ruleset_id=catalogue.ruleset_id,
                        frozen=True,
                        manifest={"is_mock": True, "benchmark": True, "document_version_ids": []},
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
    from uranium.seed_officer import seed_officer
    from uranium.storage import LocalPrivateStorage

    fixtures["officer"] = seed_officer(
        db, LocalPrivateStorage(settings.storage_root), password, case_key="phase4-e2e-" + uuid.uuid4().hex
    )
    db.commit()
Path("var").mkdir(exist_ok=True)
Path("var/phase2-e2e-fixtures.json").write_text(json.dumps(fixtures, indent=2) + "\n", encoding="utf-8")
print("Created isolated synthetic browser fixtures. Passwords were not printed or exported.")
