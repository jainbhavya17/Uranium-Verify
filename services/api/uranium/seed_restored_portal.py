"""Restore the original Lovable portal's sample cases additively, with real stored artifacts."""

from functools import partial
from reportlab.pdfgen.canvas import Canvas
import hashlib
import io
import json
import time
from pathlib import Path
from html import escape

from sqlalchemy import select
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from .models import (
    Application,
    Institution,
    PortalCaseRecord,
    PortalInstitutionProfile,
    Membership,
    ApprovalSnapshot,
    RuleSet,
    RequirementTemplate,
    ApplicationCatalogue,
    InstitutionRouting,
    ApplicationDraft,
    Revision,
    Document,
    DocumentVersion,
    Assignment,
    ReviewState,
    SubmissionReceipt,
    ApplicationTimeline,
    Clarification,
    ClarificationScope,
    ClarificationResponse,
    ResponseLineage,
    ReportRequest,
    User,
    Notification,
)
from .seed import fixture_id
from .institution_contracts import DraftDetails
from .institution_service import persist_claims, persist_requirements, checklist_view, fingerprint
from .portal_documents import DOCUMENTS
from .reports import capture_report
from .audit import append_audit

ROOT = Path(__file__).resolve().parents[3]
CATEGORIES = [
    ("NEW_INSTITUTION", "Establishment of New Technical Institution"),
    ("EOA", "Extension of Approval (EoA)"),
    ("INTAKE_INCREASE", "Increase in Intake"),
    ("NEW_COURSE", "Introduction of New Course"),
    ("CLOSURE", "Closure of Course / Institution"),
]
CATEGORY_DESCRIPTIONS = {
    "EOA": "Renew the institution's approval with current safety, affiliation, faculty and financial records.",
    "INTAKE_INCREASE": "Propose revised course intake with infrastructure, faculty and the applicable Affidavit 8 and resolution.",
    "NEW_COURSE": "Add a course with its proposed intake, supporting resources and applicable declarations.",
    "NEW_INSTITUTION": "Prepare a new technical-institution proposal with land, buildings, staffing and leased-land undertakings where applicable.",
    "CLOSURE": "Record the closure proposal, governing-body resolution and arrangements to protect existing students.",
}
TYPES = [
    "LAND_REGISTRATION",
    "COMPLETION",
    "FIRE_SAFETY",
    "AFFIDAVIT_2",
    "FACULTY_LIST",
    "AUDITED_ACCOUNTS",
    "AFFILIATION",
    "STRUCTURAL_STABILITY",
]
APH = "https://www.aicte.gov.in/sites/default/files/APH%20Final.pdf"


def pdf_document(title, institution, details, reference, document_type):
    output = io.BytesIO()
    styles = getSampleStyleSheet()
    story = [
        Paragraph("URANIUM VERIFY", styles["Title"]),
        Paragraph(escape(title), styles["Heading1"]),
        Spacer(1, 18),
    ]
    for label, value in [
        ("Institution Name", institution.name),
        ("Permanent ID", institution.permanent_id),
        ("Address", details.get("proposed_address", "")),
        ("Certificate ID", reference),
        ("Issue Date", "2026-06-01"),
        ("Expiry Date", "2027-06-30"),
        ("Academic Year", "2025-26" if document_type == "AUDITED_ACCOUNTS" else "2026-27"),
        ("Issuer", "Competent authority / institutional record"),
    ]:
        story.append(Paragraph(escape(f"{label}: {value}"), styles["Normal"]))
        story.append(Spacer(1, 10))
    story += [
        Spacer(1, 28),
        Paragraph(
            "Sample document supplied for the portal walkthrough. It is not an authority-issued certificate.",
            styles["Italic"],
        ),
    ]
    SimpleDocTemplate(output).build(story, canvasmaker=partial(Canvas, invariant=1))
    return output.getvalue()


def seed_restored_portal(db, storage):
    pack = json.loads((ROOT / "config/portal-samples.json").read_text(encoding="utf-8"))
    owner = db.scalar(select(User).where(User.email == "admin.a@demo.uranium.test"))
    officer = db.scalar(select(User).where(User.email == "officer.a@demo.uranium.test"))
    supervisor = db.scalar(select(User).where(User.email == "supervisor@demo.uranium.test"))
    admin = db.scalar(select(User).where(User.email == "platform@demo.uranium.test"))
    if not all([owner, officer, supervisor, admin]):
        raise RuntimeError("Run the normal sample setup first.")
    db.info.update(actor_id=admin.id, request_id="restored-portal-setup")
    catalogues = {}
    for year in ["2025-26", "2026-27"]:
        rules_id = fixture_id("restored-portal-rules-" + year)
        rules = db.get(RuleSet, rules_id)
        if not rules:
            rules = RuleSet(
                id=rules_id,
                version="portal-reference-" + year + "-v2",
                status="DRAFT",
                source_ref="/resources#documents",
                authored_by=admin.id,
                approved_by=supervisor.id,
                effective_from=year[:4] + "-01-01",
            )
            db.add(rules)
            db.flush()
            for code, name in CATEGORIES:
                kinds = (
                    TYPES.copy()
                    if code != "CLOSURE"
                    else ["CLOSURE_RESOLUTION", "AFFILIATION", "AUDITED_ACCOUNTS"]
                )
                if code in ["INTAKE_INCREASE", "NEW_COURSE"]:
                    kinds += ["AFFIDAVIT_8", "FORMAT_3"]
                if code == "NEW_INSTITUTION":
                    kinds += ["AFFIDAVIT_7"]
                for index, kind in enumerate(kinds):
                    condition = {"op": "always"}
                    if kind == "STRUCTURAL_STABILITY":
                        condition = {"op": "eq", "field": "structural_over_30", "value": True}
                    if kind == "AFFIDAVIT_7":
                        condition = {"op": "eq", "field": "land_leased", "value": True}
                    if kind == "AFFIDAVIT_8":
                        condition = {
                            "op": "not",
                            "conditions": [{"op": "eq", "field": "extended_eoa", "value": True}],
                        }
                    title, description = DOCUMENTS[kind]
                    affidavit = kind.startswith("AFFIDAVIT")
                    spec = {
                        "code": code + "-DOC-" + str(index + 1).zfill(2),
                        "label": title,
                        "description": description,
                        "alternatives": [kind],
                        "source_url": APH if affidavit else "/resources#documents",
                        "clause": (
                            "Annexure 2.6 / Affidavit 8"
                            if kind == "AFFIDAVIT_8"
                            else "Annexure 1 / Joint Affidavit 7"
                            if kind == "AFFIDAVIT_7"
                            else "Annexure 1 / Annexure 2.1 / Affidavit 2"
                            if kind == "AFFIDAVIT_2"
                            else "Portal supporting-document checklist"
                        ),
                        "printed_page": 82
                        if kind == "AFFIDAVIT_8"
                        else 78
                        if kind == "AFFIDAVIT_7"
                        else 81
                        if kind == "AFFIDAVIT_2"
                        else 0,
                        "pdf_page": 98
                        if kind == "AFFIDAVIT_8"
                        else 94
                        if kind == "AFFIDAVIT_7"
                        else 97
                        if kind == "AFFIDAVIT_2"
                        else 0,
                    }
                    db.add(
                        RequirementTemplate(
                            id=fixture_id(year + code + kind + "portal-v2"),
                            ruleset_id=rules_id,
                            code=spec["code"],
                            category="PORTAL_" + code,
                            stage_due="SUBMISSION",
                            predicate=condition,
                            field_schema=spec,
                        )
                    )
            db.flush()
            rules.status = "DEMO_REVIEWED"
            db.flush()
        for code, name in CATEGORIES:
            cid = fixture_id("portal-catalogue-" + year + code)
            row = db.get(ApplicationCatalogue, cid)
            if not row:
                row = ApplicationCatalogue(
                    id=cid,
                    code="PORTAL_" + code,
                    display_name=name,
                    academic_year=year,
                    availability="enabled",
                    ruleset_id=rules_id,
                    definition={
                        "portal_revision": 2,
                        "is_mock": True,
                        "interpretation_status": "PORTAL_REFERENCE_CHECKLIST",
                        "eligibility": CATEGORY_DESCRIPTIONS[code],
                        "programmes": ["Engineering & Technology", "Management"],
                        "procedural_stages": ["SUBMISSION", "SCRUTINY", "REVIEW"],
                        "document_package": CATEGORY_DESCRIPTIONS[code],
                        "source": {
                            "url": APH,
                            "clause": "Relevant application annexure; supporting checklist restored from the portal",
                            "notice_url": APH,
                        },
                        "submission_channel": "Uranium Verify application workspace",
                        "external_url": None,
                        "reference_date": "2026-11-02",
                        "window_label": "Academic year " + year,
                        "depth": "Application workflow",
                    },
                )
                db.add(row)
                db.flush()
            catalogues[(year, name)] = row
    for inst in pack["institutions"]:
        entity = db.get(Institution, inst["id"])
        if not entity:
            entity = Institution(id=inst["id"], permanent_id=inst["aicteId"], name=inst["name"], is_mock=True)
            db.add(entity)
            db.flush()
        if not db.get(PortalInstitutionProfile, entity.id):
            db.add(PortalInstitutionProfile(id=entity.id, payload=inst))
        if not db.get(InstitutionRouting, entity.id):
            db.add(InstitutionRouting(id=entity.id, officer_id=officer.id))
        if entity.id == "INS-1-4412" and not db.scalar(
            select(Membership.id).where(
                Membership.user_id == owner.id, Membership.institution_id == entity.id
            )
        ):
            db.add(Membership(user_id=owner.id, institution_id=entity.id, role_id="institution_admin"))
        baseline_id = fixture_id("restored-baseline-" + entity.id)
        if not db.get(ApprovalSnapshot, baseline_id):
            source_app = next(a for a in pack["applications"] if a["institutionId"] == entity.id)
            details = source_app["details"]
            db.add(
                ApprovalSnapshot(
                    id=baseline_id,
                    institution_id=entity.id,
                    academic_year="2025-26",
                    published=True,
                    is_mock=True,
                    source_ref="Earlier portal sample approval record",
                    payload={
                        "approval_reference": "EOA/2025/" + entity.permanent_id,
                        "profile": {
                            "name": entity.name,
                            "permanent_id": entity.permanent_id,
                            "address": details["address"],
                            "affiliation": "Affiliating University / Technical Education Board",
                            "institution_type": "government"
                            if "Government" in inst["type"]
                            else "self_financing",
                            "completion_date": "2012-04-01",
                        },
                        "courses": [
                            {
                                "course": details["course"],
                                "level": "PG" if details["course"].startswith("M.") else "UG",
                                "approved_intake": min(details["intake"], 120),
                            }
                        ],
                    },
                )
            )
    db.flush()
    status_map = {
        "Draft": "DRAFT",
        "Submitted": "SUBMITTED",
        "Under Scrutiny": "UNDER_REVIEW",
        "Deficiency Raised": "CLARIFICATION_REQUESTED",
        "Approved": "REVIEW_COMPLETED",
        "Rejected": "REVIEW_COMPLETED",
    }
    for original in pack["applications"]:
        if db.get(Application, original["id"]):
            continue
        inst = db.get(Institution, original["institutionId"])
        cat = catalogues[("2026-27", original["type"])]
        case = Application(
            id=original["id"],
            institution_id=inst.id,
            category=cat.display_name,
            academic_year="2026-27",
            status="DRAFT",
            is_mock=True,
        )
        db.add(case)
        db.flush()
        rev = Revision(
            id=fixture_id("restored-revision-" + case.id),
            application_id=case.id,
            number=1,
            actor_id=owner.id,
            ruleset_id=cat.ruleset_id,
            frozen=False,
            manifest={},
        )
        db.add(rev)
        db.flush()
        d = original["details"]
        details = DraftDetails(
            proposed_name=inst.name,
            proposed_address=d["address"],
            affiliation="Affiliating University / Technical Education Board",
            signatory=d["principal"] or "Institution Authorized Signatory",
            programme=d["programme"],
            courses=[
                {
                    "course": d["course"],
                    "requested_intake": d["intake"],
                    "level": "PG" if d["course"].startswith("M.") else "UG",
                }
            ],
            completion_date="2012-04-01",
            land_area_acres=d["landArea"],
            built_up_area_m2=d["builtUpArea"],
            faculty_count=d["facultyCount"],
        ).model_dump(mode="json")
        draft = ApplicationDraft(
            id=case.id,
            revision_id=rev.id,
            catalogue_id=cat.id,
            baseline_snapshot_id=fixture_id("restored-baseline-" + inst.id),
            draft_key=(inst.id + ":" + cat.id) if original["status"] == "Draft" else None,
            lock_version=1,
            updated_at=int(time.time()),
            details=details,
        )
        db.add(draft)
        db.flush()
        from .institution_service import snapshot_view

        persist_claims(
            db, draft, snapshot_view(db, db.get(ApprovalSnapshot, draft.baseline_snapshot_id))["profile"]
        )
        persist_requirements(db, case, draft)
        requirements = checklist_view(db, case, draft)["items"]
        version_ids = []
        reviews = {}
        for index, doc in enumerate(original["documents"]):
            kind = TYPES[index]
            if doc["status"] == "Not Submitted":
                continue
            requirement = next((r for r in requirements if kind in r["acceptable_alternatives"]), None)
            record = Document(
                id=fixture_id(case.id + kind),
                application_id=case.id,
                document_type=kind,
                requirement_id=requirement["id"] if requirement else None,
            )
            db.add(record)
            db.flush()
            content = pdf_document(DOCUMENTS[kind][0], inst, details, case.id + "-" + doc["code"], kind)
            key = hashlib.sha256(content).hexdigest()
            storage.write_once(key, content)
            version = DocumentVersion(
                id=fixture_id(case.id + kind + "-v1"),
                document_id=record.id,
                application_id=case.id,
                revision_id=rev.id,
                number=1,
                sha256=hashlib.sha256(content).hexdigest(),
                storage_key=key,
                original_name=doc.get("fileName") or kind.lower() + ".pdf",
                media_type="application/pdf",
                uploader_id=owner.id,
                status="SYNTHETIC_FIXTURE",
                is_mock=True,
            )
            db.add(version)
            db.flush()
            version_ids.append(version.id)
            reviews[version.id] = {
                "status": "Reviewed"
                if doc["status"] == "Verified"
                else "Correction required"
                if doc["status"] == "Mismatch Found"
                else "Awaiting review",
                "reviewer": doc.get("checkedBy") or original.get("assignedOfficer") or officer.name,
                "reviewed_on": doc.get("checkedOn"),
                "finding": doc.get("findings", "")
                if doc["status"] != "Verified"
                else "Document review recorded in the earlier portal sample.",
                "document_type": kind,
            }
        db.flush()
        manifest = {
            "application_id": case.id,
            "revision_id": rev.id,
            "details": details,
            "baseline_snapshot_id": draft.baseline_snapshot_id,
            "ruleset_id": cat.ruleset_id,
            "rule_version": db.get(RuleSet, cat.ruleset_id).version,
            "checklist": checklist_view(db, case, draft),
            "document_version_ids": version_ids,
            "declaration": True,
            "is_mock": True,
        }
        submitted = original["status"] != "Draft"
        rev.manifest = manifest
        rev.submitted_at = int(time.time()) if submitted else None
        rev.frozen = submitted
        case.status = status_map[original["status"]]
        metadata = {
            **original,
            "document_reviews": reviews,
            "source": "Earlier Lovable portal sample",
            "original_status": original["status"],
        }
        db.add(PortalCaseRecord(id=case.id, reference=original["ref"], payload=metadata))
        if submitted:
            db.add(Assignment(application_id=case.id, user_id=officer.id, scope="REVIEW"))
            db.add(Assignment(application_id=case.id, user_id=supervisor.id, scope="SUPERVISE"))
            state = ReviewState(
                id=case.id,
                revision_id=rev.id,
                version=1,
                due_at=int(time.time()) + 7 * 86400,
                context={"stage": "SCRUTINY", "division": 60},
            )
            db.add(state)
            receipt = {
                "receipt_id": fixture_id(case.id + "-receipt"),
                "application_id": case.id,
                "revision_id": rev.id,
                "acknowledgment": case.id,
                "submitted_at": int(time.time()),
                "version": 1,
                "rule_version": manifest["rule_version"],
                "manifest_sha256": fingerprint(manifest),
                "document_count": len(version_ids),
                "is_mock": True,
                "status": "SUBMITTED",
            }
            db.add(
                SubmissionReceipt(
                    id=receipt["receipt_id"],
                    application_id=case.id,
                    revision_id=rev.id,
                    actor_id=owner.id,
                    request_hash=fingerprint(receipt),
                    payload=receipt,
                )
            )
            db.flush()
            report = ReportRequest(
                id=fixture_id(case.id + "-initial-report"),
                revision_id=rev.id,
                actor_id=officer.id,
                payload={
                    "rationale": original.get("decision", {}).get("reason")
                    or "Preliminary document and institutional review summary for " + case.id + "."
                },
            )
            db.add(report)
            db.flush()
            capture_report(db, report, case, state)
        for i, event in enumerate(original.get("history", [])):
            db.add(
                ApplicationTimeline(
                    application_id=case.id,
                    actor_id=owner.id
                    if "Draft" in event["action"] or "submitted" in event["action"]
                    else officer.id,
                    event_key=case.id + "-restored-" + str(i),
                    event_type=event["action"].upper().replace(" ", "_"),
                    summary=(event["action"] + (": " + event["remark"] if event.get("remark") else ""))[:300],
                    payload={"recorded_at": event["at"], "recorded_by": event["by"]},
                )
            )
    db.flush()
    for item in pack["deficiencies"]:
        if db.get(Clarification, item["id"]):
            continue
        case = db.get(Application, item["appId"])
        draft = db.get(ApplicationDraft, case.id)
        query = Clarification(
            id=item["id"],
            application_id=case.id,
            actor_id=officer.id,
            message=item["description"],
            published=True,
            allowed_until=int(time.time()) + 10 * 86400,
        )
        db.add(query)
        db.flush()
        kind = "COMPLETION" if item["category"] == "Infrastructure" else "FACULTY_LIST"
        db.add(
            ClarificationScope(
                id=query.id,
                original_revision_id=draft.revision_id,
                allowed_fields=[],
                document_types=[kind],
                required_documents=[kind],
            )
        )
        if item.get("response"):
            response_rev = Revision(
                id=fixture_id(query.id + "response-revision"),
                application_id=case.id,
                number=2,
                actor_id=owner.id,
                ruleset_id=db.get(Revision, draft.revision_id).ruleset_id,
                manifest={
                    "parent_revision_id": draft.revision_id,
                    "clarification_id": query.id,
                    "details": draft.details,
                },
                frozen=True,
                submitted_at=int(time.time()),
            )
            db.add(response_rev)
            db.flush()
            response = ClarificationResponse(
                id=fixture_id(query.id + "-response"),
                request_id=query.id,
                revision_id=response_rev.id,
                actor_id=owner.id,
                explanation=item["response"],
            )
            db.add(response)
            db.flush()
            db.add(
                ResponseLineage(
                    id=response.id,
                    original_revision_id=draft.revision_id,
                    receipt={
                        "acknowledgment": "RESP-" + query.id,
                        "submitted_at": int(time.time()),
                        "application_id": case.id,
                        "request_id": query.id,
                        "version": 1,
                        "document_count": 0,
                    },
                )
            )
            if item["status"] == "Closed":
                from .models import ClarificationResolution

                db.add(
                    ClarificationResolution(
                        request_id=query.id,
                        response_id=response.id,
                        actor_id=officer.id,
                        rationale=item.get("closeRemark", "Response reviewed."),
                    )
                )
    # A submitted response on the main institution's case makes the review handoff visible.
    if not db.get(Clarification, "DEF-0931"):
        case = db.get(Application, "APP-01482")
        draft = db.get(ApplicationDraft, case.id)
        query = Clarification(
            id="DEF-0931",
            application_id=case.id,
            actor_id=officer.id,
            message="Confirm the previous financial year and attach the audited financial statement for the sponsoring body.",
            published=True,
            allowed_until=int(time.time()) + 10 * 86400,
        )
        db.add(query)
        db.flush()
        db.add(
            ClarificationScope(
                id=query.id,
                original_revision_id=draft.revision_id,
                allowed_fields=[],
                document_types=["AUDITED_ACCOUNTS"],
                required_documents=["AUDITED_ACCOUNTS"],
            )
        )
        rev = Revision(
            id=fixture_id("DEF-0931-revision"),
            application_id=case.id,
            number=2,
            actor_id=owner.id,
            ruleset_id=db.get(Revision, draft.revision_id).ruleset_id,
            frozen=False,
            manifest={},
        )
        db.add(rev)
        db.flush()
        original_doc = db.get(Document, fixture_id(case.id + "AUDITED_ACCOUNTS"))
        content = pdf_document(
            "Audited Financial Statement — FY 2025-26",
            db.get(Institution, case.institution_id),
            draft.details,
            "RESP-DEF-0931",
            "AUDITED_ACCOUNTS",
        )
        key = hashlib.sha256(content).hexdigest()
        storage.write_once(key, content)
        v = DocumentVersion(
            id=fixture_id("DEF-0931-financial-v2"),
            document_id=original_doc.id,
            application_id=case.id,
            revision_id=rev.id,
            number=2,
            sha256=hashlib.sha256(content).hexdigest(),
            storage_key=key,
            original_name="Audited_Financial_Statement_FY_2025-26.pdf",
            media_type="application/pdf",
            uploader_id=owner.id,
            status="SYNTHETIC_FIXTURE",
            is_mock=True,
        )
        db.add(v)
        db.flush()
        rev.manifest = {
            "parent_revision_id": draft.revision_id,
            "clarification_id": query.id,
            "details": draft.details,
            "document_version_ids": [v.id],
        }
        rev.frozen = True
        rev.submitted_at = int(time.time())
        response = ClarificationResponse(
            id=fixture_id("DEF-0931-response"),
            request_id=query.id,
            revision_id=rev.id,
            actor_id=owner.id,
            explanation="The audited financial statements cover FY 2025-26. The balance sheet, income and expenditure statement, and signed auditor’s report have been provided as a replacement document. Please review the attached statement.",
        )
        db.add(response)
        db.flush()
        db.add(
            ResponseLineage(
                id=response.id,
                original_revision_id=draft.revision_id,
                receipt={
                    "acknowledgment": "RESP-DEF-0931",
                    "submitted_at": int(time.time()),
                    "application_id": case.id,
                    "request_id": query.id,
                    "version": 1,
                    "document_count": 1,
                },
            )
        )
    db.flush()
    for user in [owner, officer]:
        for i, (app_id, message) in enumerate(
            [
                (
                    "APP-01482",
                    "Response submitted for DEF-0931. Audited financial statements are ready for review.",
                ),
                (
                    "APP-01482",
                    "Document correction requested: check the built-up area in the Building Completion Certificate.",
                ),
                (
                    "APP-01377",
                    "Review completed for Extension of Approval. Open the application to view the recorded outcome.",
                ),
            ]
        ):
            key = "restored-notice-" + user.id + "-" + str(i)
            if not db.scalar(select(Notification.id).where(Notification.deduplication_key == key)):
                db.add(
                    Notification(
                        user_id=user.id,
                        deduplication_key=key,
                        summary=message,
                        target={"application_id": app_id, "request_id": "DEF-0931"}
                        if i == 0
                        else {"application_id": app_id},
                    )
                )
    append_audit(
        db,
        admin.id,
        "PORTAL_SAMPLE_RESTORED",
        "lovable-reference",
        "restored-portal-setup",
        {"applications": len(pack["applications"])},
    )
    db.commit()
    return {"applications": len(pack["applications"]), "institution_id": "INS-1-4412"}
