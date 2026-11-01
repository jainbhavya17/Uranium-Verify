import json
from pathlib import Path

from sqlalchemy import select

from .models import (
    ApplicationCatalogue,
    ApprovalSnapshot,
    Institution,
    InstitutionRouting,
    RequirementTemplate,
    ReviewedException,
    RuleSet,
)

APH_URL = "https://www.aicte.gov.in/sites/default/files/APH%20Final.pdf"
NOTICE_URL = (
    "https://dteapengg.in/Documents/NOTIFICATIONS/AICTE%20Approval%20Process%202026-"
    "27_Fair%20Copy%20and%20Public%20notice%20for%20approval%20process%202026-27%20Merged_20251201_044937.pdf"
)


def seed_institution(db, fid):
    definitions = json.loads(
        (Path(__file__).resolve().parents[3] / "config/rules/phase2-demo.json").read_text()
    )

    def add(model, identifier, **values):
        row = db.get(model, identifier)
        if not row:
            row = model(id=identifier, **values)
            db.add(row)
            db.flush()
        return row

    for year in ["2025-26", "2026-27"]:
        ruleset_id = fid("demo-rulepack-" + year)
        pack = add(
            RuleSet,
            ruleset_id,
            version=f"demo-aph-{year}-v1",
            status="DRAFT",
            source_ref=APH_URL,
            authored_by=fid("platform@demo.uranium.test"),
            approved_by=fid("supervisor@demo.uranium.test"),
            effective_from=year[:4] + "-01-01",
        )
        if pack.status == "DRAFT":
            for rule in definitions["rules"]:
                add(
                    RequirementTemplate,
                    fid(year + rule["code"]),
                    ruleset_id=ruleset_id,
                    code=rule["code"],
                    category=rule["category"],
                    stage_due=rule["stage"],
                    predicate=rule["condition"],
                    field_schema={
                        **rule,
                        "source_url": APH_URL,
                        "interpretation_status": definitions["interpretation_status"],
                    },
                )
            pack.status = "DEMO_REVIEWED"
            db.flush()
        entries = [
            ("EOA", "Routine Extension of Approval", "enabled", "Chapter II; Annexure 2.1"),
            (
                "INTAKE_INCREASE",
                "Increase in intake / additional courses",
                "enabled",
                "Chapter II 2.6; Annexure 2.6",
            ),
            (
                "EOA_RESTORATION",
                "EoA after a break / restoration / hibernation",
                "preview",
                "Annexure 2.1; Table 2.3",
            ),
            ("NEW_PROGRAMME", "New programme / level", "preview", "Annexure 2.3; Table 2.3"),
            ("SITE_CHANGE", "Change of site / location", "preview", "Annexure 2.3; Annexure 1"),
            ("NAME_CHANGE", "Change of institution name", "preview", "Annexure 2.10"),
            ("AFFILIATION_CHANGE", "Change of affiliating university / board", "preview", "Annexure 2.11"),
            ("BANK_CHANGE", "Change of bank details", "preview", "Annexure 2.12"),
            ("COURSE_CHANGE", "Course name / reduction / closure", "preview", "Annexure 2.9"),
            (
                "MERGER_CLOSURE",
                "Institutional merger / conversion / closure",
                "preview",
                "Annexures 2.4 / 2.7 / 2.8",
            ),
            (
                "NEW_INSTITUTION",
                "New technical institution",
                "external",
                "Chapter I; Annexure 1; 2026-27 notice",
            ),
            (
                "ODL_ONLINE",
                "ODL / online and specialized approvals",
                "preview",
                "Chapter V; category-specific regulations",
            ),
        ]
        for code, label, availability, clause in entries:
            add(
                ApplicationCatalogue,
                fid(year + "-catalogue-" + code),
                code=code,
                academic_year=year,
                display_name=label,
                availability=availability,
                ruleset_id=ruleset_id,
                definition={
                    "is_mock": True,
                    "interpretation_status": definitions["interpretation_status"],
                    "eligibility": "Existing institution with a synthetic Permanent ID"
                    if code != "NEW_INSTITUTION"
                    else "Separate official process; no local submission",
                    "programmes": ["Engineering & Technology", "Management"],
                    "procedural_stages": ["SUBMISSION", "SCRUTINY", "EVC"]
                    if code != "EOA"
                    else ["SUBMISSION", "DOCUMENT_CHECK"],
                    "document_package": "Annexure 2.1"
                    if code == "EOA"
                    else "Annexure 2.6"
                    if code == "INTAKE_INCREASE"
                    else clause,
                    "source": {"url": APH_URL, "clause": clause, "notice_url": NOTICE_URL},
                    "submission_channel": "NSWS external guidance (SRS-referenced 2026-27 notice)"
                    if code == "NEW_INSTITUTION"
                    else "Local demo; AICTE existing-institution channel requires approved integration",
                    "external_url": NOTICE_URL if code == "NEW_INSTITUTION" else None,
                    "reference_date": year[:4] + "-06-01",
                    "reference_date_status": "CONFIGURABLE_DEMO_REFERENCE_NOT_STATUTORY_DEADLINE",
                    "window_label": "Historical demo year; not an official open application window"
                    if year == "2025-26"
                    else "Synthetic application window; not an official deadline",
                    "depth": "Core demo"
                    if code == "EOA"
                    else "Limited extended demo"
                    if code == "INTAKE_INCREASE"
                    else "Guidance only",
                },
            )
    for key in ["a", "b"]:
        institution_id = fid("institution-" + key)
        institution = db.get(Institution, institution_id)
        if not institution:
            continue
        add(InstitutionRouting, institution_id, officer_id=fid(f"officer.{key}@demo.uranium.test"))
        add(
            ApprovalSnapshot,
            fid("snapshot-2024-" + key),
            institution_id=institution_id,
            academic_year="2024-25",
            version=1,
            published=True,
            is_mock=True,
            source_ref="MOCK historical approval reference; no official synchronization",
            payload={
                "approval_reference": f"MOCK-EOA-{key.upper()}-2024",
                "course": "Computer Science & Engineering",
                "approved_intake": 45,
                "profile": {
                    "name": institution.name,
                    "address": f"Campus {key.upper()}, Sector 8, Demo City",
                    "affiliation": "Mock State Technical University",
                    "institution_type": "government" if key == "b" else "self_financing",
                    "completion_date": "2000-01-01",
                },
                "changes": ["MOCK: intake subsequently recorded as 60 in the 2025-26 fixture"],
                "prior_findings": [
                    {
                        "summary": "MOCK: certificate reference clarification",
                        "corrective_action": "Reference confirmed in synthetic record",
                    }
                ],
            },
        )
        add(
            ApprovalSnapshot,
            fid("snapshot-unverified-" + key),
            institution_id=institution_id,
            academic_year="2023-24",
            version=1,
            published=False,
            is_mock=True,
            source_ref="MOCK imported record awaiting verification",
            payload={
                "source_status": "IMPORTED_UNVERIFIED",
                "approved_intake": 30,
                "course": "Computer Science & Engineering",
            },
        )
        for year in ["2025-26", "2026-27"]:
            if key == "b":
                add(
                    ReviewedException,
                    fid("government-exception-" + year),
                    institution_id=institution_id,
                    academic_year=year,
                    code="GOVERNMENT_OVER_50_ALTERNATIVE",
                    approved_by=fid("supervisor@demo.uranium.test"),
                    source_ref="MOCK reviewed Annexure 2.1 exception fixture: competent-authority letter alternative, not a universal waiver",
                    is_mock=True,
                )
    db.flush()
    assert db.scalar(select(ApplicationCatalogue.id))
