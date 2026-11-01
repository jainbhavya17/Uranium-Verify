import copy
import secrets
import time
import uuid
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.exc import SQLAlchemyError
from conftest import login, TEST_PASSWORD
from uranium.main import create_app
from uranium.models import (
    Membership,
    ReviewedException,
    Institution,
    Application,
    Revision,
    RoomRecord,
    RoomEvidence,
    Document,
    DocumentVersion,
    Assignment,
    ReviewState,
    ExtractedField,
    ExtractionCorrection,
)
from uranium.seed import fixture_id
from uranium.seed_officer import seed_officer


def post(client, path, body, key=None):
    return client.post("/api/v1" + path, json=body, headers={"Idempotency-Key": key or str(uuid.uuid4())})


@pytest.fixture
def case(client):
    with client.app.state.session_factory() as db:
        pack = seed_officer(db, client.app.state.storage, TEST_PASSWORD)
        original = db.get(Application, pack["case_id"])
        old = db.scalar(select(Revision).where(Revision.application_id == original.id))
        app = Application(
            institution_id=original.institution_id,
            category="EOA",
            academic_year="2026-27",
            status="SUBMITTED",
            is_mock=True,
        )
        db.add(app)
        db.flush()
        revision = Revision(
            application_id=app.id,
            number=1,
            actor_id=old.actor_id,
            ruleset_id=old.ruleset_id,
            manifest=copy.deepcopy(old.manifest),
        )
        db.add(revision)
        db.flush()
        room = RoomRecord(revision_id=revision.id, room_code="C101", room_type="CLASSROOM", declared_area=75)
        doc = Document(application_id=app.id, document_type="MOCK_ARCHITECT_ROOM_SCHEDULE")
        db.add_all([room, doc])
        db.flush()
        source = db.scalar(select(DocumentVersion).where(DocumentVersion.application_id == original.id))
        key = secrets.token_hex(32)
        client.app.state.storage.write_once(key, client.app.state.storage.read(source.storage_key))
        version = DocumentVersion(
            application_id=app.id,
            document_id=doc.id,
            revision_id=revision.id,
            number=1,
            sha256=source.sha256,
            storage_key=key,
            original_name="MOCK-certified-schedule.pdf",
            media_type="application/pdf",
            uploader_id=old.actor_id,
            status="SYNTHETIC_FIXTURE",
            is_mock=True,
        )
        db.add(version)
        db.flush()
        field = ExtractedField(
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
            processor_version="mock-room-1",
        )
        db.add(field)
        db.add(
            RoomEvidence(
                room_id=room.id,
                version_id=version.id,
                page=1,
                bbox=[50, 110, 300, 145],
                certified_area=58,
                actor_id=fixture_id("officer.a@demo.uranium.test"),
                source_ref="MOCK certified schedule / page 1",
                reliable=True,
            )
        )
        db.add(
            ReviewState(
                id=app.id,
                revision_id=revision.id,
                version=1,
                due_at=int(time.time()) + 86400,
                context={"division": 60, "stage": "SCRUTINY"},
            )
        )
        db.add(
            Assignment(
                application_id=app.id,
                user_id=fixture_id("officer.a@demo.uranium.test"),
                scope="REVIEW",
                active=True,
            )
        )
        db.flush()
        revision.frozen = True
        revision.submitted_at = int(time.time())
        db.commit()
        result = {
            "id": app.id,
            "revision_id": revision.id,
            "version_id": version.id,
            "field_id": field.id,
            "room_id": room.id,
            **pack,
        }
    login(client, "officer.a")
    return result


def current(client, case):
    r = client.get("/api/v1/officer/cases/" + case["id"])
    assert r.status_code == 200, r.text
    return r.json()["data"]["review"]["version"]


def command(client, case, path, **values):
    return post(
        client,
        f"/officer/cases/{case['id']}/{path}",
        {
            "expected_version": current(client, case),
            "rationale": "Synthetic authorized review with source inspection.",
            **values,
        },
    )


def test_assigned_case_scopes_and_private_data(client, settings, case):
    root = f"/api/v1/officer/cases/{case['id']}"
    assert client.get(root).status_code == 200
    assert client.get(root + "/evidence").json()["data"]["fields"]
    for account in ["officer.b", "platform", "auditor", "admin.a"]:
        with TestClient(create_app(settings)) as other:
            login(other, account)
            assert other.get(root).status_code in {403, 404}
            assert other.get(root + "/evidence").status_code in {403, 404}
            assert other.get(root + "/authenticity").status_code in {403, 404}
    # Institutions keep their permitted precheck path, never this officer projection.
    with TestClient(create_app(settings)) as institution:
        login(institution)
        assert institution.get(root + "/compliance").status_code in {403, 404}


def test_room_arithmetic_exact_rule_and_evidence_lineage(client, case):
    r = command(client, case, "compliance")
    assert r.status_code == 200, r.text
    result = r.json()["data"]["results"][0]
    assert result["mismatch"] == 17 and result["deficiency"] == 8
    assert result["certified_m2"] == 58 and result["minimum_m2"] == 66
    assert result["version_id"] == case["version_id"] and result["page"] == 1
    assert result["rule_id"] == case["rule_id"] and result["printed_page"] == 87 and result["pdf_page"] == 103
    assert result["source_url"].startswith("https://") and len(result["source_checksum"]) == 64
    graph = client.get(f"/api/v1/officer/cases/{case['id']}/evidence").json()["data"]
    assert any(
        n["kind"] == "RULE_RUN" and n["reference"]["version_id"] == case["version_id"] for n in graph["nodes"]
    )
    assert any(e["relationship"] == "SUPPORTS" for e in graph["edges"])


@pytest.mark.parametrize(
    "context,state",
    [
        ({"division": 30}, "NOT_APPLICABLE"),
        ({"division": None}, "INSUFFICIENT_EVIDENCE"),
        ({"stage": "SUBMISSION"}, "NOT_APPLICABLE"),
    ],
)
def test_division_stage_and_unknown_protection(client, case, context, state):
    with client.app.state.session_factory() as db:
        review = db.get(ReviewState, case["id"])
        review.context = {**review.context, **context}
        db.commit()
    r = command(client, case, "compliance")
    assert r.status_code == 200, r.text
    assert r.json()["data"]["results"][0]["state"] == state


def test_corrections_append_and_stale_review_denial(client, case):
    old = current(client, case)
    r = command(client, case, "corrections", field_id=case["field_id"], normalized="59")
    assert r.status_code == 200, r.text
    with client.app.state.session_factory() as db:
        assert db.get(ExtractedField, case["field_id"]).value["normalized"] == "58"
        assert (
            db.scalar(
                select(ExtractionCorrection).where(ExtractionCorrection.field_id == case["field_id"])
            ).corrected_value["normalized"]
            == "59"
        )
    stale = post(
        client,
        f"/officer/cases/{case['id']}/priority",
        {
            "expected_version": old,
            "rationale": "A stale concurrent review override must be denied.",
            "priority": 99,
        },
    )
    assert stale.status_code == 409
    r = command(client, case, "priority", priority=70)
    assert r.status_code == 200 and r.json()["data"]["priority"]["score"] == 70


def test_specialist_routing_response_and_no_approval(client, case, settings):
    r = command(
        client,
        case,
        "tasks",
        assignee_id=fixture_id("specialist@demo.uranium.test"),
        kind="ISSUER",
        due_at=int(time.time()) + 86400,
        version_id=case["version_id"],
    )
    assert r.status_code == 200, r.text
    task = r.json()["data"]
    with TestClient(create_app(settings)) as specialist:
        login(specialist, "specialist")
        tasks = specialist.get("/api/v1/officer/tasks").json()["data"]
        assert any(t["id"] == task["id"] for t in tasks)
        assert specialist.get(f"/api/v1/officer/cases/{case['id']}/evidence").status_code == 200
        assert post(
            specialist,
            f"/officer/cases/{case['id']}/actions",
            {
                "expected_version": 1,
                "rationale": "Specialist cannot approve scrutiny cases.",
                "action": "COMPLETE",
            },
        ).status_code in {403, 404}
        r = post(
            specialist,
            f"/officer/tasks/{task['id']}/response",
            {
                "expected_version": task["version"],
                "outcome": "CONFIRMED",
                "source_ref": "MOCK manual issuer registry reference",
                "observed_at": int(time.time()),
                "rationale": "Manually checked synthetic registry result with saved reference.",
            },
        )
        assert r.status_code == 200, r.text
        assert r.json()["data"]["status"] == "RESOLVED"


def test_issuer_outcomes_distinct_labelled_and_retry_bounded(client, case):
    for fixture, status in [
        ("match", "MATCH"),
        ("conflict", "CONFLICT"),
        ("timeout", "TIMEOUT"),
        ("unsupported", "UNSUPPORTED"),
    ]:
        r = command(
            client,
            case,
            "issuer",
            version_id=case["version_id"],
            provider_id=fixture_id("phase4-issuer-" + fixture),
            fixture=fixture,
            certificate_id="MOCK-CERT",
        )
        assert r.status_code == 200, r.text
        data = r.json()["data"]
        assert (
            data["status"] == status
            and data["is_mock"]
            and data["mode"] == "MOCK"
            and not data["external_confirmation"]
        )


def test_dual_publication_source_filters_and_abstention(client, case, settings):
    login(client, "platform")
    versions = client.get("/api/v1/governance/versions").json()["data"]
    source = next(v for v in versions if v["id"] == case["source_id"])
    code = "TEST_" + uuid.uuid4().hex[:12].upper()
    r = post(
        client,
        "/governance/versions",
        {
            "kind": "SOURCE",
            "code": code,
            "payload": source["payload"],
            "rationale": "Register a bounded synthetic reviewed passage for dual approval.",
        },
    )
    assert r.status_code == 200, r.text
    draft = r.json()["data"]
    denied = post(
        client,
        f"/governance/versions/{draft['id']}/action",
        {"action": "APPROVE", "rationale": "Self approval must be rejected by the configured dual policy."},
    )
    assert denied.status_code == 403
    with TestClient(create_app(settings)) as approver:
        login(approver, "approver")
        assert (
            post(
                approver,
                f"/governance/versions/{draft['id']}/action",
                {
                    "action": "APPROVE",
                    "rationale": "Separate synthetic regulatory owner reviewed the source.",
                },
            ).status_code
            == 200
        )
    query = {
        "query": "engineering classroom carpet area minimum",
        "academic_year": "2026-27",
        "category": "EOA",
        "programme": "Engineering & Technology",
        "stage": "SCRUTINY",
        "reference_date": "2026-06-01",
    }
    result = post(client, "/knowledge/retrieve", query).json()["data"]
    assert result["citations"] and result["mode"] in {
        "KEYWORD_ONLY_FALLBACK",
        "POSTGRES_FULLTEXT_ONLY",
        "HYBRID_POSTGRES_FTS_PGVECTOR_BGE_SMALL",
    }
    absent = post(client, "/knowledge/retrieve", {**query, "programme": "Management"}).json()["data"]
    assert not absent["citations"] and absent["answer"] is None


def test_clarification_visibility_completion_guard_and_reports_pending(client, case):
    assert command(client, case, "actions", action="COMPLETE").status_code == 409
    assert command(client, case, "compliance").status_code == 200
    private = command(client, case, "actions", action="OBSERVATION", publishable=False)
    assert private.status_code == 200
    assert command(client, case, "reports").json()["data"]["state"] == "PENDING_GENERATION"
    r = command(
        client, case, "actions", action="CLARIFICATION", publishable=True, due_at=int(time.time()) + 86400
    )
    assert r.status_code == 200, r.text
    assert r.json()["data"]["status"] == "CLARIFICATION_REQUESTED"
    assert command(client, case, "actions", action="COMPLETE").status_code == 409


def test_governed_payload_and_machine_evidence_immutable(client, case):
    with client.app.state.session_factory() as db:
        with pytest.raises(SQLAlchemyError):
            db.execute(
                text("UPDATE governed_versions SET payload='{}' WHERE id=:id"), {"id": case["rule_id"]}
            )
            db.commit()


def test_actual_c2pa_and_pdf_signature_trust_no_signal_and_method(tmp_path):
    import importlib.util
    from uranium.processing_sandbox import extract_isolated
    from uranium.processing_config import ProcessingPolicy

    spec = importlib.util.spec_from_file_location(
        "provenance_fixtures", Path("scripts/generate-provenance-fixtures.py")
    )
    generator = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(generator)
    generator.generate(tmp_path)
    policy = ProcessingPolicy()
    root = (tmp_path / "test-root.pem").read_text()

    def inspect(name, mime, **extra):
        result = extract_isolated(
            tmp_path / name, policy, operation="provenance", options={"media_type": mime, **extra}
        )
        assert result.get("ok"), result
        return result["checks"]

    trusted = inspect("signed.jpg", "image/jpeg", c2pa_anchors=root)["c2pa"]
    assert trusted["outcome"] == "TRUSTED" and trusted["method"].startswith("c2pa-python/")
    assert not trusted["issuer_authenticity_confirmed"] and not trusted["remote_fetch"]
    assert inspect("signed.jpg", "image/jpeg")["c2pa"]["outcome"] == "VALID_UNTRUSTED"
    assert inspect("unsigned.jpg", "image/jpeg")["c2pa"]["outcome"] == "NO_SIGNAL"
    pdf = inspect("signed.pdf", "application/pdf", pdf_anchors=root)["pdf_signature"]
    assert pdf["outcome"] == "CHECKED" and pdf["signatures"][0]["outcome"] == "TRUSTED"
    assert (
        inspect("signed.pdf", "application/pdf")["pdf_signature"]["signatures"][0]["outcome"]
        == "VALID_UNTRUSTED"
    )
    assert inspect("unsigned.pdf", "application/pdf")["pdf_signature"]["outcome"] == "NO_SIGNATURE"


def test_programme_year_reliability_exception_and_human_review_history(client, case, settings):
    # Year is application metadata, independent of a frozen manifest's historical year.
    with client.app.state.session_factory() as db:
        app = db.get(Application, case["id"])
        app.academic_year = "2025-26"
        db.commit()
    assert command(client, case, "compliance").json()["data"]["results"][0]["state"] == "NOT_APPLICABLE"
    with client.app.state.session_factory() as db:
        app = db.get(Application, case["id"])
        app.academic_year = "2026-27"
        institution = Institution(
            name="MOCK independent exception jurisdiction",
            permanent_id="MOCK-EXCEPTION-" + str(uuid.uuid4()),
            is_mock=True,
        )
        db.add(institution)
        db.flush()
        app.institution_id = institution.id
        db.add(
            ReviewedException(
                institution_id=app.institution_id,
                academic_year=app.academic_year,
                code="MOCK_CLASSROOM_EXEMPTION",
                approved_by=fixture_id("platform@demo.uranium.test"),
                source_ref="MOCK explicit classroom exception for this test institution",
                is_mock=True,
            )
        )
        db.commit()
    result = command(client, case, "compliance").json()["data"]["results"][0]
    assert result["state"] == "NOT_APPLICABLE" and "exception" in result["reason"]


def test_audited_finding_review_completion_and_private_communication(client, case, settings):
    assert command(client, case, "compliance").status_code == 200
    q = client.get(f"/api/v1/officer/cases/{case['id']}/compliance").json()["data"]
    finding = q["findings"][0]
    r = command(client, case, f"findings/{finding['id']}/review", disposition="ACKNOWLEDGED")
    assert r.status_code == 200 and r.json()["data"]["machine_result_preserved"]
    assert command(client, case, "actions", action="RECOMMENDATION").status_code == 200
    r = command(client, case, "actions", action="COMPLETE")
    assert r.status_code == 200 and r.json()["data"]["status"] == "REVIEW_COMPLETED"
    assert command(client, case, "priority", priority=10).status_code == 409
    # Institution timeline never contains the private recommendation or observation.
    with TestClient(create_app(settings)) as institution:
        login(institution)
        timeline = institution.get(f"/api/v1/applications/{case['id']}/timeline")
        assert timeline.status_code == 200 and "RECOMMENDATION" not in timeline.text


def test_governance_access_revocation_audit_export_and_connector_guard(client, case, settings):
    login(client, "platform")
    user_id = fixture_id("officer.b@demo.uranium.test")
    with TestClient(create_app(settings)) as target:
        login(target, "officer.b")
        r = post(
            client,
            f"/governance/users/{user_id}",
            {
                "action": "REVOKE_SESSIONS",
                "rationale": "Synthetic administrator explicitly revokes existing target sessions.",
            },
        )
        assert r.status_code == 200, r.text
        assert target.get("/api/v1/me").status_code == 401
    r = post(
        client,
        f"/governance/connectors/{fixture_id('phase4-issuer-match')}",
        {
            "mode": "LIVE",
            "status": "AVAILABLE",
            "rationale": "Live mode cannot claim healthy without an authorized implementation.",
        },
    )
    assert r.status_code == 409
    export = client.get("/api/v1/governance/audit/export?operation=USER_REVOKE_SESSIONS")
    assert export.status_code == 200 and "USER_REVOKE_SESSIONS" in export.text
    assert "password" not in export.text.lower() and "storage_key" not in export.text


def test_supervisor_jurisdiction_unassigned_scope_and_reassignment(client, case, settings):
    with client.app.state.session_factory() as db:
        assigned = db.scalar(
            select(Assignment).where(Assignment.application_id == case["id"], Assignment.scope == "REVIEW")
        )
        assigned.active = False
        db.commit()
    assert client.get("/api/v1/officer/queue?unassigned=true").status_code == 403
    assert client.get(f"/api/v1/officer/cases/{case['id']}").status_code == 404
    with TestClient(create_app(settings)) as supervisor:
        login(supervisor, "supervisor")
        assert supervisor.get(f"/api/v1/officer/cases/{case['id']}").status_code == 404
        with client.app.state.session_factory() as db:
            app = db.get(Application, case["id"])
            membership = Membership(
                user_id=fixture_id("supervisor@demo.uranium.test"),
                role_id="supervisor",
                institution_id=app.institution_id,
            )
            db.add(membership)
            db.commit()
            membership_id = membership.id
        r = supervisor.get("/api/v1/officer/queue?unassigned=true")
        assert r.status_code == 200 and any(c["id"] == case["id"] for c in r.json()["data"])
        r = post(
            supervisor,
            f"/officer/cases/{case['id']}/assignment",
            {
                "expected_version": 1,
                "assignee_id": fixture_id("officer.b@demo.uranium.test"),
                "rationale": "Scoped supervisor reassigns this unassigned synthetic scrutiny case.",
            },
        )
        assert r.status_code == 200, r.text
        with client.app.state.session_factory() as db:
            db.get(Membership, membership_id).valid_until = int(time.time())
            db.commit()
    with TestClient(create_app(settings)) as assigned_b:
        login(assigned_b, "officer.b")
        assert assigned_b.get(f"/api/v1/officer/cases/{case['id']}/evidence").status_code == 200
    assert client.get(f"/api/v1/officer/cases/{case['id']}/evidence").status_code == 404


def test_unrelated_programme_never_runs_classroom_arithmetic(client, case):
    from unittest.mock import patch

    with client.app.state.session_factory() as db:
        old = db.get(Revision, case["revision_id"])
        payload = copy.deepcopy(old.manifest)
        payload["details"]["programme"] = "Management"
        new = Revision(
            application_id=case["id"],
            number=2,
            actor_id=old.actor_id,
            ruleset_id=old.ruleset_id,
            manifest=payload,
        )
        db.add(new)
        db.flush()
        db.add(RoomRecord(revision_id=new.id, room_code="C101", room_type="CLASSROOM", declared_area=75))
        db.flush()
        new.frozen = True
        new.submitted_at = int(time.time())
        db.get(ReviewState, case["id"]).revision_id = new.id
        db.commit()
    with patch(
        "uranium.compliance.arithmetic",
        side_effect=AssertionError("Unrelated programme must not run this numeric rule"),
    ):
        r = command(client, case, "compliance")
    assert r.status_code == 200, r.text
    assert r.json()["data"]["results"][0]["state"] == "NOT_APPLICABLE"


def test_rag_access_filter_before_ranking_superseded_exclusion_and_abstention(client, case, settings):
    login(client, "platform")
    source = next(
        s for s in client.get("/api/v1/governance/versions").json()["data"] if s["id"] == case["source_id"]
    )
    payload = copy.deepcopy(source["payload"])
    payload["scope"]["roles"] = ["admin"]
    payload["text"] = (
        "Private needle classroom area source is restricted to the governance role for this synthetic access-filter test."
    )
    r = post(
        client,
        "/governance/versions",
        {
            "kind": "SOURCE",
            "code": "PRIVATE_" + uuid.uuid4().hex[:12].upper(),
            "payload": payload,
            "rationale": "Synthetic source access is restricted before either ranking method.",
        },
    )
    assert r.status_code == 200, r.text
    identifier = r.json()["data"]["id"]
    with TestClient(create_app(settings)) as approver:
        login(approver, "approver")
        assert (
            post(
                approver,
                f"/governance/versions/{identifier}/action",
                {
                    "action": "APPROVE",
                    "rationale": "Independent synthetic source owner approves the restricted passage.",
                },
            ).status_code
            == 200
        )
    query = {
        "query": "private needle",
        "academic_year": "2026-27",
        "category": "EOA",
        "programme": "Engineering & Technology",
        "stage": "SCRUTINY",
        "reference_date": "2026-06-01",
    }
    assert (
        post(client, "/knowledge/retrieve", query).json()["data"]["citations"][0]["source_id"] == identifier
    )
    with TestClient(create_app(settings)) as officer:
        login(officer, "officer.a")
        result = post(officer, "/knowledge/retrieve", query).json()["data"]
        assert result["answer"] is None and not result["citations"]
    assert (
        post(
            client,
            f"/governance/versions/{identifier}/action",
            {
                "action": "SUPERSEDE",
                "rationale": "This synthetic source is decommissioned and excluded from retrieval.",
            },
        ).status_code
        == 200
    )
    result = post(client, "/knowledge/retrieve", query).json()["data"]
    assert not result["citations"] and result["answer"] is None


def test_corrected_room_evidence_rechecks_and_preserves_old_inputs(client, case):
    assert command(client, case, "compliance").status_code == 200
    first = client.get(f"/api/v1/officer/cases/{case['id']}/compliance").json()["data"]
    r = command(
        client,
        case,
        "infrastructure",
        room_id=case["room_id"],
        version_id=case["version_id"],
        page=1,
        bbox=[50, 110, 300, 145],
        certified_area=58,
        source_ref="MOCK reviewed C101 schedule remains uncertain",
        reliable=False,
        division=60,
    )
    assert r.status_code == 200, r.text
    assert client.get(f"/api/v1/officer/cases/{case['id']}/compliance").json()["data"]["state"] == "NOT_RUN"
    r = command(client, case, "compliance")
    assert r.json()["data"]["results"][0]["state"] == "INSUFFICIENT_EVIDENCE"
    with client.app.state.session_factory() as db:
        from uranium.models import RuleRun

        assert db.get(RuleRun, first["results"][0]["id"]).payload["deficiency"] == 8
        assert len(db.scalars(select(RoomEvidence).where(RoomEvidence.room_id == case["room_id"])).all()) == 2


def test_actual_provenance_observations_persist_with_source_and_actor(client, case):
    r = command(client, case, f"provenance/{case['version_id']}")
    assert r.status_code == 200, r.text
    checks = r.json()["data"]["checks"]
    assert checks["pdf_signature"]["outcome"] == "NO_SIGNATURE"
    assert checks["duplicate_hash"]["authenticity_confirmed"] is False
    saved = client.get(f"/api/v1/officer/cases/{case['id']}/authenticity").json()["data"]["provenance"]
    assert any(
        x["version_id"] == case["version_id"]
        and x["method"] == "pdf_signature"
        and x["outcome"] == "NO_SIGNATURE"
        for x in saved
    )
    assert command(client, case, "provenance/unowned-version").status_code == 404
