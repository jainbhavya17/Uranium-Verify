import copy
import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import func, select, text
from sqlalchemy.exc import SQLAlchemyError

from conftest import login
from uranium.institution_service import evaluate
from uranium.main import create_app
from uranium.models import (
    ApplicationTimeline,
    ApprovalSnapshot,
    Assignment,
    AuditEvent,
    Institution,
    InstitutionRouting,
    Membership,
    OutboxEvent,
    ReviewedException,
    Revision,
    SubmissionReceipt,
)
from uranium.seed import fixture_id


def key():
    return str(uuid.uuid4())


def post(client, path, payload, request_key=None):
    return client.post("/api/v1" + path, json=payload, headers={"Idempotency-Key": request_key or key()})


def world(client, government=False, extended=False):
    login(client)
    identifier = key()
    with client.app.state.session_factory() as db:
        db.add(
            Institution(
                id=identifier, permanent_id="MOCK-" + identifier, name="Phase 2 " + identifier, is_mock=True
            )
        )
        db.flush()
        for email, role in [
            ("admin.a@demo.uranium.test", "institution_admin"),
            ("submitter.a@demo.uranium.test", "institution_submitter"),
        ]:
            db.add(Membership(user_id=fixture_id(email), role_id=role, institution_id=identifier))
        for year, intake in [("2024-25", 45), ("2025-26", 60)]:
            db.add(
                ApprovalSnapshot(
                    institution_id=identifier,
                    academic_year=year,
                    version=1,
                    published=True,
                    is_mock=True,
                    source_ref="MOCK approval " + year,
                    payload={
                        "course": "Computer Science",
                        "approved_intake": intake,
                        "extended_eoa": extended,
                        "profile": {
                            "name": "Phase 2 " + identifier,
                            "address": "MOCK campus",
                            "affiliation": "MOCK university",
                            "institution_type": "government" if government else "self_financing",
                            "completion_date": "2000-01-01",
                        },
                    },
                )
            )
        db.add(InstitutionRouting(id=identifier, officer_id=fixture_id("officer.a@demo.uranium.test")))
        db.commit()
    return identifier


def cat(client, code="EOA", year="2026-27"):
    return next(
        r
        for r in client.get("/api/v1/catalog/applications", params={"year": year}).json()["data"]
        if r["code"] == code
    )


def create(client, institution, code="EOA", year="2026-27", request_key=None):
    r = post(
        client,
        "/applications",
        {"institution_id": institution, "catalogue_id": cat(client, code, year)["id"]},
        request_key,
    )
    assert r.status_code == 200, r.text
    return r.json()["data"]


def refresh(client, s):
    r = client.get(f"/api/v1/applications/{s['application_id']}/state")
    assert r.status_code == 200, r.text
    return r.json()["data"]


def save(client, s, **changes):
    r = client.patch(
        f"/api/v1/applications/{s['application_id']}/draft",
        json={"expected_version": s["version"], "details": {**s["details"], **changes}},
        headers={"Idempotency-Key": key()},
    )
    assert r.status_code == 200, r.text
    return r.json()["data"]


def attach(client, s, item, doc_type=None, request_key=None):
    r = post(
        client,
        f"/applications/{s['application_id']}/documents/fixtures",
        {
            "expected_version": s["version"],
            "requirement_id": item["id"],
            "document_type": doc_type or item["acceptable_alternatives"][0],
        },
        request_key,
    )
    assert r.status_code == 200, r.text
    return refresh(client, s), r.json()["data"]


def complete(client, s):
    s = save(client, s, signatory="Synthetic authorized signatory")
    for i in s["checklist"]["items"]:
        if i["mandatory"]:
            s, _ = attach(client, s, i, "COMPLETION" if i["code"] == "EOA-D03" else None)
    return s


def test_catalogue_availability_create_replay_and_duplicate_warning(client):
    institution = world(client)
    entries = client.get("/api/v1/catalog/applications").json()["data"]
    assert len(entries) == 24
    assert {x["code"] for x in entries if x["availability"] == "enabled"} == {"EOA", "INTAKE_INCREASE"}
    external = cat(client, "NEW_INSTITUTION")
    assert external["availability"] == "external" and "NSWS" in external["definition"]["submission_channel"]
    assert (
        post(
            client, "/applications", {"institution_id": institution, "catalogue_id": external["id"]}
        ).status_code
        == 409
    )
    request_key = key()
    s = create(client, institution, request_key=request_key)
    assert create(client, institution, request_key=request_key) == s
    assert (
        post(
            client, "/applications", {"institution_id": institution, "catalogue_id": cat(client)["id"]}
        ).status_code
        == 409
    )
    assert (
        post(
            client,
            "/applications",
            {"institution_id": institution, "catalogue_id": cat(client, "INTAKE_INCREASE")["id"]},
            request_key,
        ).status_code
        == 409
    )
    assert (
        s["baseline"]["profile"]["courses"][0]["approved_intake"]
        == s["details"]["courses"][0]["requested_intake"]
        == 60
    )


def test_save_refresh_stale_counter_and_schema_validation(client):
    s = create(client, world(client))
    old = copy.deepcopy(s)
    s = save(
        client,
        s,
        signatory="MOCK signatory",
        proposed_address="New declared campus",
        rooms=[{"room_id": "C101", "room_type": "CLASSROOM", "declared_area": 75}],
    )
    assert refresh(client, s) == s and s["version"] == old["version"] + 1
    assert any(c["field"] == "Campus address" and not c["is_discrepancy"] for c in s["changes"])
    assert (
        client.patch(
            f"/api/v1/applications/{s['application_id']}/draft",
            json={"expected_version": old["version"], "details": old["details"]},
            headers={"Idempotency-Key": key()},
        ).status_code
        == 409
    )
    assert refresh(client, s)["details"]["signatory"] == "MOCK signatory"
    invalid = {**s["details"], "rooms": [{"room_id": "x", "room_type": "CLASSROOM", "declared_area": -1}]}
    assert (
        client.patch(
            f"/api/v1/applications/{s['application_id']}/draft",
            json={"expected_version": s["version"], "details": invalid},
            headers={"Idempotency-Key": key()},
        ).status_code
        == 422
    )


def test_payment_structural_age_boundary_year_and_type_change(client):
    s = create(client, world(client))
    items = {i["code"]: i for i in s["checklist"]["items"]}
    assert (
        len(items) == 7
        and items["EOA-D02"]["applicability"] == items["EOA-D04"]["applicability"] == "NOT_APPLICABLE"
    )
    s = save(client, s, payment_applicable=True, completion_date="1995-06-01")
    items = {i["code"]: i for i in s["checklist"]["items"]}
    assert items["EOA-D02"]["mandatory"] and items["EOA-D04"]["mandatory"]
    assert len(items["EOA-D03"]["acceptable_alternatives"]) == 4
    r = client.patch(
        f"/api/v1/applications/{s['application_id']}/draft",
        json={
            "expected_version": s["version"],
            "details": s["details"],
            "catalogue_id": cat(client, year="2025-26")["id"],
        },
        headers={"Idempotency-Key": key()},
    )
    assert r.status_code == 200, r.text
    s = r.json()["data"]
    assert s["checklist"]["rule_version"] == "demo-aph-2025-26-v1"
    assert (
        next(i for i in s["checklist"]["items"] if i["code"] == "EOA-D04")["applicability"]
        == "NOT_APPLICABLE"
    )
    s = save(client, s, completion_date=None)
    assert next(i for i in s["checklist"]["items"] if i["code"] == "EOA-D04")["applicability"] == "UNRESOLVED"
    r = client.patch(
        f"/api/v1/applications/{s['application_id']}/draft",
        json={
            "expected_version": s["version"],
            "details": s["details"],
            "catalogue_id": cat(client, "INTAKE_INCREASE")["id"],
        },
        headers={"Idempotency-Key": key()},
    )
    assert r.status_code == 200 and all(
        i["code"].startswith("INTAKE") for i in r.json()["data"]["checklist"]["items"]
    )


def test_not_due_programme_and_extended_eoa_do_not_block(client):
    s = create(client, world(client, extended=True), "INTAKE_INCREASE")
    s = save(
        client,
        s,
        signatory="Mock signatory",
        programme="Management",
        courses=[{"course": "Computer Science", "level": "FELLOW", "requested_intake": 120}],
    )
    items = {i["code"]: i for i in s["checklist"]["items"]}
    assert items["INTAKE-D01"]["applicability"] == "NOT_APPLICABLE"
    assert items["INTAKE-D02"]["applicability"] == items["INTAKE-D03"]["applicability"] == "NOT_DUE"
    assert client.get(f"/api/v1/applications/{s['application_id']}/precheck").json()["data"]["ready"]
    assert (
        client.patch(
            f"/api/v1/applications/{s['application_id']}/draft",
            json={"expected_version": s["version"], "details": {**s["details"], "extended_eoa": True}},
            headers={"Idempotency-Key": key()},
        ).status_code
        == 422
    )


def test_exception_requires_review_and_alternative_evidence(client):
    institution = world(client, government=True)
    s = create(client, institution)
    s = save(client, s, completion_date="1960-01-01", originals_unavailable=True)
    structural = next(i for i in s["checklist"]["items"] if i["code"] == "EOA-D04")
    assert structural["mandatory"] and "GOV_NORMS_LETTER" not in structural["acceptable_alternatives"]
    with client.app.state.session_factory() as db:
        db.add(
            ReviewedException(
                institution_id=institution,
                academic_year="2026-27",
                code="GOVERNMENT_OVER_50_ALTERNATIVE",
                approved_by=fixture_id("supervisor@demo.uranium.test"),
                source_ref="MOCK reviewed exception",
                is_mock=True,
            )
        )
        db.commit()
    s = save(client, s)
    structural = next(i for i in s["checklist"]["items"] if i["code"] == "EOA-D04")
    assert (
        structural["mandatory"]
        and structural["exception"]["is_mock"]
        and "GOV_NORMS_LETTER" in structural["acceptable_alternatives"]
    )
    s, _ = attach(client, s, structural, "GOV_NORMS_LETTER")
    assert next(i for i in s["checklist"]["items"] if i["code"] == "EOA-D04")["satisfied"]


def test_full_eoa_alternatives_freeze_receipt_idempotency_and_queue(client):
    s = create(client, world(client))
    case_id = s["application_id"]
    assert not client.get(f"/api/v1/applications/{case_id}/precheck").json()["data"]["ready"]
    s = complete(client, s)
    building = next(i for i in s["checklist"]["items"] if i["code"] == "EOA-D03")
    original = building["evidence"]["id"]
    s, attachment = attach(client, s, building, "FORM_D")
    assert (
        next(i for i in s["checklist"]["items"] if i["code"] == "EOA-D03")["evidence"]["id"]
        == attachment["version_id"]
    )
    body = {"expected_version": s["version"], "declaration": True}
    request_key = key()
    response = post(client, f"/applications/{case_id}/submit", body, request_key)
    assert response.status_code == 200, response.text
    receipt = response.json()["data"]
    assert receipt["document_count"] == 5 and receipt["is_mock"]
    assert post(client, f"/applications/{case_id}/submit", body, request_key).json()["data"] == receipt
    assert post(client, f"/applications/{case_id}/submit", body).json()["data"] == receipt
    assert not refresh(client, s)["editable"] and refresh(client, s)["status"] == "SUBMITTED"
    assert client.get(f"/api/v1/applications/{case_id}/receipt").json()["data"] == receipt
    ack = client.get(f"/api/v1/applications/{case_id}/acknowledgment")
    assert ack.json() == receipt and "attachment" in ack.headers["Content-Disposition"]
    assert (
        client.patch(
            f"/api/v1/applications/{case_id}/draft",
            json={"expected_version": receipt["version"], "details": s["details"]},
            headers={"Idempotency-Key": key()},
        ).status_code
        == 409
    )
    with client.app.state.session_factory() as db:
        revision = db.get(Revision, s["revision_id"])
        assert revision.frozen and original not in revision.manifest["document_version_ids"]
        assert attachment["version_id"] in revision.manifest["document_version_ids"]
        assert db.get(ApprovalSnapshot, s["baseline"]["id"]).payload["approved_intake"] == 60
        for model, predicate in [
            (SubmissionReceipt, SubmissionReceipt.application_id == case_id),
            (OutboxEvent, OutboxEvent.deduplication_key == f"application.submitted:{case_id}"),
            (
                AuditEvent,
                (AuditEvent.target_id == case_id) & (AuditEvent.operation == "APPLICATION_SUBMITTED"),
            ),
            (
                ApplicationTimeline,
                (ApplicationTimeline.application_id == case_id)
                & (ApplicationTimeline.event_type == "SUBMITTED"),
            ),
            (Assignment, Assignment.application_id == case_id),
        ]:
            assert db.scalar(select(func.count()).select_from(model).where(predicate)) == 1
    for stmt in [
        f"UPDATE application_drafts SET details='{{}}' WHERE id='{case_id}'",
        f"UPDATE requirement_snapshots SET active=false WHERE id='{building['id']}'",
        f"UPDATE documents SET document_type='UNTRUSTED' WHERE id='{attachment['document_id']}'",
    ]:
        with pytest.raises(SQLAlchemyError):
            with client.app.state.engine.begin() as connection:
                connection.execute(text(stmt))


def test_quarantined_bytes_never_satisfy_or_preview_and_replacement_preserves_original(client):
    s = create(client, world(client))
    case_id = s["application_id"]
    item = s["checklist"]["items"][0]
    params = {
        "requirement_id": item["id"],
        "document_type": item["acceptable_alternatives"][0],
        "expected_version": s["version"],
        "filename": "../../unsafe.pdf",
        "trusted": "true",
    }
    r = client.post(
        f"/api/v1/applications/{case_id}/documents/quarantine",
        params=params,
        content=b"%PDF unscanned /JavaScript",
        headers={"Idempotency-Key": key(), "Content-Type": "application/octet-stream"},
    )
    assert r.status_code == 200, r.text
    evidence = r.json()["data"]
    assert evidence["status"] == "QUARANTINED_PENDING_SAFETY" and not evidence["is_mock"]
    s = refresh(client, s)
    assert not s["checklist"]["items"][0]["satisfied"]
    assert (
        client.post(
            f"/api/v1/documents/{evidence['document_id']}/versions/{evidence['number']}/preview"
        ).status_code
        == 409
    )
    assert any(
        b["code"] == "FILE_PENDING_SAFETY"
        for b in client.get(f"/api/v1/applications/{case_id}/precheck").json()["data"]["blocking"]
    )
    params["expected_version"] = s["version"]
    assert (
        client.post(
            f"/api/v1/applications/{case_id}/documents/quarantine",
            params=params,
            content=b"x" * (1024 * 1024 + 1),
            headers={"Idempotency-Key": key()},
        ).status_code
        == 413
    )
    s, replacement = attach(client, s, s["checklist"]["items"][0])
    assert replacement["number"] == 2 and s["checklist"]["items"][0]["satisfied"]
    assert (
        client.get(f"/api/v1/documents/{evidence['document_id']}/versions/1").json()["data"]["status"]
        == "QUARANTINED_PENDING_SAFETY"
    )


def test_optional_later_stage_quarantine_cannot_enter_submission(client):
    s = create(client, world(client), "INTAKE_INCREASE")
    s = save(
        client,
        s,
        signatory="Mock admin",
        courses=[{"course": "Computer Science", "level": "UG", "requested_intake": 120}],
    )
    item = next(i for i in s["checklist"]["items"] if i["code"] == "INTAKE-D01")
    assert (
        client.post(
            f"/api/v1/applications/{s['application_id']}/documents/quarantine",
            params={
                "requirement_id": item["id"],
                "document_type": "AFFIDAVIT_8",
                "expected_version": s["version"],
                "filename": "pending.pdf",
            },
            content=b"unknown",
            headers={"Idempotency-Key": key()},
        ).status_code
        == 200
    )
    s = refresh(client, s)
    assert (
        post(
            client,
            f"/applications/{s['application_id']}/submit",
            {"expected_version": s["version"], "declaration": True},
        ).status_code
        == 409
    )


def test_history_comparisons_and_unverified_baseline_separation(client):
    institution = world(client)
    s = create(client, institution, "INTAKE_INCREASE")
    s = save(client, s, courses=[{"course": "Computer Science", "level": "UG", "requested_intake": 120}])
    history = client.get(f"/api/v1/institutions/{institution}/history").json()["data"]
    comparison = client.get(
        f"/api/v1/institutions/{institution}/history/compare",
        params={"left_id": history[1]["id"], "right_id": history[0]["id"]},
    )
    assert comparison.status_code == 200 and comparison.json()["data"]["changes"][0]["approved"] == 45
    comparison = client.get(
        f"/api/v1/institutions/{institution}/history/compare",
        params={"left_id": s["baseline"]["id"], "application_id": s["application_id"]},
    ).json()["data"]
    assert (
        comparison["changes"][0]["approved"] == 60
        and comparison["changes"][0]["requested"] == 120
        and not comparison["changes"][0]["is_discrepancy"]
    )
    assert client.get(f"/api/v1/institutions/{institution}/history/{history[0]['id']}").status_code == 200
    with client.app.state.session_factory() as db:
        db.add(
            ApprovalSnapshot(
                institution_id=institution,
                academic_year="2025-26",
                version=2,
                published=False,
                is_mock=True,
                source_ref="MOCK unverified import",
                payload={"source_status": "IMPORTED_UNVERIFIED", "approved_intake": 999},
            )
        )
        db.commit()
    imported = client.get(f"/api/v1/institutions/{institution}/history").json()["data"][0]
    assert not imported["baseline_eligible"] and imported["source_status"] == "IMPORTED_UNVERIFIED"
    assert imported["profile"]["courses"] == []  # Missing source fields are not invented.
    assert (
        client.get(
            f"/api/v1/institutions/{institution}/history/compare",
            params={"left_id": imported["id"], "right_id": history[1]["id"]},
        ).status_code
        == 404
    )


def test_server_filters_pagination_and_resume_metadata(client):
    institution = world(client)
    create(client, institution)
    create(client, institution, "INTAKE_INCREASE")
    create(client, institution, year="2025-26")
    all_rows = client.get("/api/v1/applications", params={"search": institution, "page_size": 1}).json()
    assert (
        all_rows["meta"]["total"] == 3 and len(all_rows["data"]) == 1 and all_rows["data"][0]["catalogue_id"]
    )
    assert (
        client.get(
            "/api/v1/applications", params={"search": institution, "year": "2026-27", "status": "DRAFT"}
        ).json()["meta"]["total"]
        == 2
    )
    assert (
        client.get(
            "/api/v1/applications", params={"search": institution, "category": cat(client)["display_name"]}
        ).json()["meta"]["total"]
        == 2
    )
    assert (
        client.get("/api/v1/applications", params={"search": institution, "status": "SUBMITTED"}).json()[
            "meta"
        ]["total"]
        == 0
    )


def test_tenant_write_scope_submit_role_and_scoped_officer_queue(client):
    institution = world(client)
    s = create(client, institution, "INTAKE_INCREASE")
    s = save(
        client,
        s,
        signatory="Mock admin",
        courses=[{"course": "Computer Science", "level": "UG", "requested_intake": 120}],
    )
    path = f"/applications/{s['application_id']}"
    body = {"expected_version": s["version"], "declaration": True}
    login(client, "submitter.a")
    assert post(client, path + "/submit", body).status_code == 403
    login(client, "officer.a")
    assert client.get("/api/v1" + path + "/state").status_code == 404
    login(client, "admin.b")
    assert (
        client.patch(
            "/api/v1" + path + "/draft",
            json={"expected_version": s["version"], "details": s["details"]},
            headers={"Idempotency-Key": key()},
        ).status_code
        == 404
    )
    assert (
        post(
            client, "/applications", {"institution_id": institution, "catalogue_id": s["catalogue"]["id"]}
        ).status_code
        == 404
    )
    login(client)
    assert post(client, path + "/submit", body).status_code == 200
    login(client, "officer.a")
    assert client.get("/api/v1" + path + "/state").status_code == 200
    login(client, "officer.b")
    assert client.get("/api/v1" + path + "/state").status_code == 404
    login(client, "platform")
    assert client.get("/api/v1" + path + "/state").status_code == 404


def test_parallel_edits_and_duplicate_submit(client, settings):
    s = create(client, world(client), "INTAKE_INCREASE")
    s = save(
        client,
        s,
        signatory="Mock admin",
        courses=[{"course": "Computer Science", "level": "UG", "requested_intake": 120}],
    )
    case_id = s["application_id"]
    with TestClient(create_app(settings)) as other:
        login(other)

        def edit(pair):
            c, name = pair
            return c.patch(
                f"/api/v1/applications/{case_id}/draft",
                json={"expected_version": s["version"], "details": {**s["details"], "signatory": name}},
                headers={"Idempotency-Key": key()},
            ).status_code

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(edit, [(client, "Writer A"), (other, "Writer B")]))
        assert sorted(results) == [200, 409]
        s = refresh(client, s)
        body = {"expected_version": s["version"], "declaration": True}
        request_key = key()
        with ThreadPoolExecutor(max_workers=2) as pool:
            responses = list(
                pool.map(
                    lambda c: post(c, f"/applications/{case_id}/submit", body, request_key), [client, other]
                )
            )
        assert [r.status_code for r in responses] == [200, 200], [r.text for r in responses]
        assert responses[0].json()["data"] == responses[1].json()["data"]
    with client.app.state.session_factory() as db:
        assert (
            db.scalar(
                select(func.count())
                .select_from(SubmissionReceipt)
                .where(SubmissionReceipt.application_id == case_id)
            )
            == 1
        )
        assert (
            db.scalar(
                select(func.count())
                .select_from(OutboxEvent)
                .where(OutboxEvent.deduplication_key == f"application.submitted:{case_id}")
            )
            == 1
        )


def test_safe_predicates_and_locked_rule_definitions(client):
    for bad in [
        {"op": "eval", "field": "__import__", "value": "os.system"},
        {"op": "eq", "field": "arbitrary", "value": True},
        {"op": "not", "conditions": []},
    ]:
        with pytest.raises(HTTPException):
            evaluate(bad, {})
    login(client)
    catalogue = cat(client)
    for stmt in [
        "UPDATE requirement_templates SET predicate='{}' WHERE ruleset_id=:id",
        "UPDATE rule_sets SET status='DRAFT' WHERE id=:id",
    ]:
        with pytest.raises(SQLAlchemyError):
            with client.app.state.engine.begin() as connection:
                connection.execute(text(stmt), {"id": catalogue["ruleset_id"]})


def test_membership_roles_remain_scoped_to_their_institution(client):
    institution = world(client)
    s = create(client, institution, "INTAKE_INCREASE")
    s = save(
        client,
        s,
        signatory="MOCK signatory",
        courses=[{"course": "Computer Science", "level": "UG", "requested_intake": 120}],
    )
    with client.app.state.session_factory() as db:
        # Admin in B does not upgrade a submitter membership in the new institution.
        db.add(
            Membership(
                user_id=fixture_id("submitter.a@demo.uranium.test"),
                role_id="institution_admin",
                institution_id=fixture_id("institution-b"),
            )
        )
        # An officer/jurisdiction membership is not an institution-edit membership.
        db.add(
            Membership(
                user_id=fixture_id("admin.a@demo.uranium.test"),
                role_id="officer",
                institution_id=fixture_id("institution-b"),
            )
        )
        db.commit()
    login(client, "submitter.a")
    assert not refresh(client, s)["can_submit"]
    assert (
        post(
            client,
            f"/applications/{s['application_id']}/submit",
            {"expected_version": s["version"], "declaration": True},
        ).status_code
        == 403
    )
    login(client)
    assert fixture_id("institution-b") not in client.get("/api/v1/me").json()["data"]["institution_ids"]
    assert client.get(f"/api/v1/applications/{fixture_id('application-b')}").status_code == 404
