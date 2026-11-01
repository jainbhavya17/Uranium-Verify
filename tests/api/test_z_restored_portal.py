"""Restored portal records must remain useful, scoped and connected to real stored files."""

import uuid
from urllib.parse import quote
import pytest
from sqlalchemy import select, func
from conftest import login
from uranium.models import PortalCaseRecord, Application
from uranium.seed_restored_portal import seed_restored_portal


@pytest.fixture
def restored(client):
    with client.app.state.session_factory() as db:
        seed_restored_portal(db, client.app.state.storage)
    return client


def request(client, path, body):
    return client.post("/api/v1" + path, json=body, headers={"Idempotency-Key": str(uuid.uuid4())})


def test_restored_cases_are_additive_and_scoped(restored):
    client = restored
    with client.app.state.session_factory() as db:
        before = db.scalar(select(func.count()).select_from(Application))
        seed_restored_portal(db, client.app.state.storage)
        assert db.scalar(select(func.count()).select_from(Application)) == before
        assert db.scalar(select(func.count()).select_from(PortalCaseRecord)) == 7
    login(client)
    rows = client.get("/api/v1/portal/applications").json()["data"]
    assert {"APP-01482", "APP-01377"} <= {x["id"] for x in rows}
    assert client.get("/api/v1/portal/applications/APP-01519").status_code == 404
    login(client, "officer.a")
    assert len(client.get("/api/v1/portal/applications").json()["data"]) >= 6
    login(client, "officer.b")
    assert client.get("/api/v1/portal/applications/APP-01482").status_code == 404
    login(client, "specialist")
    assert client.get("/api/v1/portal/applications").status_code == 403


def test_public_tracking_excludes_private_data_and_drafts(restored):
    c = restored
    for ref in ["APP-01482", "AICTE/2026/APP/01482"]:
        r = c.get("/api/v1/portal/track/" + quote(ref, safe=""))
        assert r.status_code == 200, r.text
        assert set(r.json()["data"]) == {"id", "reference", "type", "academicYear", "status"}
        assert r.json()["data"]["status"] == "Deficiency Raised"
    assert c.get("/api/v1/portal/track/APP-01603").status_code == 404


def test_submitted_response_retains_text_and_attachment_without_draft(restored):
    c = restored
    login(c)
    r = c.get("/api/v1/clarifications/DEF-0931")
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["draft"] is None
    assert "FY 2025-26" in data["responses"][0]["explanation"]
    assert len(data["documents"]) == 1
    case = c.get("/api/v1/portal/applications/APP-01482").json()["data"]
    answer = next(q for q in case["queries"] if q["id"] == "DEF-0931")["responses"][0]
    assert answer["documents"][0]["fileName"].endswith(".pdf")
    doc = answer["documents"][0]
    preview = request(c, f"/documents/{doc['id']}/versions/{doc['version']}/preview", {})
    assert preview.status_code == 200, preview.text
    content = c.get(preview.json()["data"]["url"])
    assert content.content.startswith(b"%PDF")


def test_all_five_categories_and_conditional_affidavits(restored):
    c = restored
    login(c)
    cats = [
        x
        for x in c.get("/api/v1/catalog/applications").json()["data"]
        if x["definition"].get("portal_revision") == 2 and x["academic_year"] == "2026-27"
    ]
    assert len(cats) == 5
    for catalogue in cats:
        r = request(c, "/applications", {"institution_id": "INS-1-4412", "catalogue_id": catalogue["id"]})
        assert r.status_code in (200, 201), r.text
        state = r.json()["data"]
        assert state["checklist"]["items"]
        check = c.post("/api/v1/applications/" + state["application_id"] + "/precheck")
        assert check.status_code == 200, check.text
        assert check.json()["data"]["blocking"]
        if catalogue["code"] == "PORTAL_NEW_INSTITUTION":
            assert state["baseline"]["source_status"] == "REGISTRATION_PROFILE"
            details = {**state["details"], "land_tenure": "LEASED"}
            updated = c.patch(
                "/api/v1/applications/" + state["application_id"] + "/draft",
                json={"expected_version": state["version"], "details": details},
                headers={"Idempotency-Key": str(uuid.uuid4())},
            )
            assert updated.status_code == 200, updated.text
            items = updated.json()["data"]["checklist"]["items"]
            item = next(x for x in items if "AFFIDAVIT_7" in x["acceptable_alternatives"])
            assert item["mandatory"]


def test_officer_document_review_inspection_and_reports_are_real(restored):
    c = restored
    login(c, "officer.a")
    case = c.get("/api/v1/portal/applications/APP-01482").json()["data"]
    version = next(d["versionId"] for d in case["documents"] if d["versionId"])
    r = request(
        c,
        "/portal/applications/APP-01482/document-review",
        {
            "expected_version": case["reviewVersion"],
            "version_id": version,
            "status": "Reviewed",
            "reason": "Original document checked against institution details.",
        },
    )
    assert r.status_code == 200, r.text
    version2 = r.json()["data"]["reviewVersion"]
    assert version2 > case["reviewVersion"]
    duplicate = request(
        c,
        "/portal/applications/APP-01482/document-review",
        {
            "expected_version": case["reviewVersion"],
            "version_id": version,
            "status": "Reviewed",
            "reason": "Original document checked against institution details.",
        },
    )
    assert duplicate.status_code == 409
    inspection = request(
        c,
        "/portal/applications/APP-01482/inspection",
        {
            "expected_version": version2,
            "date": "2026-11-02",
            "inspector": "Reviewing officer",
            "observations": "Certified built-up area needs confirmation at inspection.",
            "recommendation": "Check room dimensions and sanctioned plan.",
        },
    )
    assert inspection.status_code == 200, inspection.text
    assert inspection.json()["data"]["inspection"]["date"] == "2026-11-02"
    from uranium.reports import run_report_one

    for _ in range(12):
        if not run_report_one(c.app.state.session_factory, c.app.state.storage):
            break
    detail = c.get("/api/v1/portal/applications/APP-01482").json()["data"]
    report = next(x for x in detail["reports"] if x["download_url"])
    report_bytes = c.get(report["download_url"]).content
    assert report_bytes.startswith(b"%PDF")
    import pymupdf

    with pymupdf.open(stream=report_bytes, filetype="pdf") as pdf:
        text = "".join(page.get_text() for page in pdf)
    assert "APP-01482" in text
    assert "Venkateshwara" in text
