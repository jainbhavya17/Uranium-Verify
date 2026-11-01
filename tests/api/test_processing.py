"""Actual synthetic bytes and real parser/OCR; mocked scans are explicitly isolated."""

import importlib.util
import time
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.exc import SQLAlchemyError

from conftest import login
from test_institution import world, create, complete, refresh, save, post, key
from uranium.main import create_app
from uranium.models import DocumentVersion, ExtractedField, Finding, ProcessingJob
from uranium.processing import run_one, job_view
from uranium.processing_config import ProcessingPolicy
from uranium.processing_sandbox import extract_isolated
from uranium.scanner import ClamAVScanner

spec = importlib.util.spec_from_file_location(
    "processing_fixtures", Path("scripts/generate-processing-fixtures.py")
)
generator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(generator)


@pytest.fixture(scope="module")
def fixtures(tmp_path_factory):
    root = tmp_path_factory.mktemp("processing-files")
    generator.generate(root)
    return root


def policy(**overrides):
    local = Path("var/tools/tesseract/tesseract.exe").resolve()
    return ProcessingPolicy(
        scanner="mock-test", tesseract=str(local) if local.exists() else "tesseract", **overrides
    )


def upload(client, s, content, name="original.pdf", mime="application/pdf", slot="EOA-D05", request_key=None):
    item = next(i for i in s["checklist"]["items"] if i["code"] == slot)
    return client.post(
        f"/api/v1/applications/{s['application_id']}/documents/upload",
        params={
            "requirement_id": item["id"],
            "document_type": item["acceptable_alternatives"][0],
            "expected_version": s["version"],
            "filename": name,
        },
        content=content,
        headers={"Content-Type": mime, "Idempotency-Key": request_key or key()},
    )


def process(client, version, p=None):
    # Drain existing explicit fixtures' jobs as well; never fabricate a worker response.
    for _ in range(40):
        with client.app.state.session_factory() as db:
            v = db.get(DocumentVersion, version)
            result = job_view(db, v)
        if result["state"] not in {"UPLOADED", "REPROCESSING"}:
            return result
        assert run_one(client.app.state.session_factory, client.app.state.storage, p or policy())
    raise AssertionError("Queue did not drain")


@pytest.mark.parametrize(
    "name,expected",
    [
        ("digital.pdf", "READABLE"),
        ("scan.png", "READABLE"),
        ("scan.jpg", "READABLE"),
        ("scan.pdf", "READABLE"),
        ("rotated.png", "READABLE"),
        ("blurred.png", "UNREADABLE"),
        ("corrupt.pdf", "CORRUPT_FILE"),
        ("encrypted.pdf", "ENCRYPTED_PDF"),
        ("active.pdf", "UNSAFE_CONTENT"),
        ("embedded.pdf", "UNSAFE_CONTENT"),
        ("pages-51.pdf", "PAGE_LIMIT"),
    ],
)
def test_real_bounded_parser(fixtures, name, expected):
    result = extract_isolated(fixtures / name, policy())
    assert result.get("quality", result.get("code")) == expected, result
    if expected == "READABLE":
        fields = {f["field_key"]: f for f in result["fields"]}
        assert fields["institution_name"]["normalized"] == "MOCK Technical Institute"
        assert fields["expiry_date"]["normalized"] == "2027-06-30"
        assert fields["institution_name"]["page"] == 1
        assert len(fields["institution_name"]["bbox"]) == 4
        page = result["pages"][0]
        x0, y0, x1, y1 = fields["institution_name"]["bbox"]
        assert 0 <= x0 < x1 <= page["width"] and 0 <= y0 < y1 <= page["height"]
        if name == "digital.pdf":
            import pymupdf

            with pymupdf.open(fixtures / name) as original:
                assert "MOCK Technical Institute" in original[0].get_textbox(pymupdf.Rect(x0, y0, x1, y1))
        elif name in {"scan.png", "rotated.png"}:
            from PIL import Image, ImageStat

            crop = Image.open(fixtures / name).crop((x0, y0, x1, y1)).convert("L")
            assert ImageStat.Stat(crop).stddev[0] > 5


def test_unknown_and_unavailable_ocr(fixtures):
    result = extract_isolated(fixtures / "unknown-date.pdf", policy())
    expiry = next(f for f in result["fields"] if f["field_key"] == "expiry_date")
    assert expiry["normalized"] is None and expiry["raw"] == "illegible"
    p = policy()
    p.tesseract = "missing-tesseract-executable"
    assert extract_isolated(fixtures / "scan.png", p) == {"ok": False, "code": "OCR_UNAVAILABLE"}
    assert extract_isolated(fixtures / "digital.pdf", p, "0" * 64) == {"ok": False, "code": "FILE_INTEGRITY"}


def test_authoritative_upload_rejections_and_failed_attempts(client, fixtures):
    s = create(client, world(client))
    for name, mime, status in [
        ("unsupported.svg", "image/svg+xml", 415),
        ("mismatch.pdf", "application/pdf", 415),
        ("digital.pdf", "image/png", 415),
        ("oversized.pdf", "application/pdf", 413),
    ]:
        r = upload(client, s, (fixtures / name).read_bytes(), name, mime)
        assert r.status_code == status, r.text
    attempts = client.get(f"/api/v1/applications/{s['application_id']}/upload-attempts").json()["data"]
    assert len(attempts) == 4 and all(
        a["state"] == "UPLOAD_FAILED" and a["version_id"] is None for a in attempts
    )
    assert refresh(client, s)["version"] == s["version"]


def test_scanner_fail_closed_no_parsing_then_retry(client, fixtures):
    s = create(client, world(client))
    r = upload(client, s, (fixtures / "digital.pdf").read_bytes())
    assert r.status_code == 200, r.text
    v = r.json()["data"]
    p = policy()
    p.scanner = "unavailable"
    with patch("uranium.processing.extract_isolated", side_effect=AssertionError("unsafe parse")):
        result = process(client, v["version_id"], p)
    assert result["state"] == "SAFETY_UNAVAILABLE" and not result["accepted"]
    assert (
        client.post(f"/api/v1/documents/{v['document_id']}/versions/{v['number']}/preview").status_code == 409
    )
    s = refresh(client, s)
    r = post(
        client,
        f"/applications/{s['application_id']}/documents/{v['version_id']}/retry",
        {"expected_version": s["version"]},
    )
    assert r.status_code == 200, r.text
    result = process(client, v["version_id"])
    assert result["state"] == "PROCESSED" and result["scanner_mode"] == "MOCK_TEST"
    assert result["attempt"] == 2 and result["fields"]
    # Old failed job and current immutable result coexist.
    with client.app.state.session_factory() as db:
        assert (
            len(db.scalars(select(ProcessingJob).where(ProcessingJob.version_id == v["version_id"])).all())
            == 2
        )


def test_malware_never_parsed(client, fixtures):
    s = create(client, world(client))
    r = upload(client, s, (fixtures / "mock-malware.pdf").read_bytes())
    assert r.status_code == 200
    with patch("uranium.processing.extract_isolated", side_effect=AssertionError("unsafe parse")):
        result = process(client, r.json()["data"]["version_id"])
    assert result["state"] == "NEEDS_REUPLOAD" and result["scan_status"] == "INFECTED"
    assert not result["fields"] and result["result_id"] is None


def matching(s, expiry="2027-06-30", name=None, address=None):
    return generator.pdf_bytes(
        name=name or s["details"]["proposed_name"],
        permanent_id="MOCK-" + s["institution_id"],
        address=address or s["details"]["proposed_address"],
        expiry=expiry,
    )


def test_real_evidence_precheck_correction_versions_staleness_submission(client):
    s = complete(client, create(client, world(client)))
    bad = upload(client, s, matching(s, expiry="2020-01-01"))
    assert bad.status_code == 200, bad.text
    first = bad.json()["data"]
    result = process(client, first["version_id"])
    assert result["state"] == "PROCESSED", result
    metadata = client.get(f"/api/v1/applications/{s['application_id']}/documents").json()["data"]
    assert next(v for v in metadata if v["id"] == first["version_id"])["status"] == "PROCESSED"
    s = refresh(client, s)
    check = post(client, f"/applications/{s['application_id']}/precheck", {}).json()["data"]
    expiry = next(b for b in check["blocking"] if b["code"] == "EXPIRED")
    assert expiry["version_id"] == first["version_id"] and expiry["page"] == 1 and expiry["field_id"]
    corrected = upload(client, s, matching(s))
    assert corrected.status_code == 200, corrected.text
    second = corrected.json()["data"]
    assert second["number"] == first["number"] + 1
    process(client, second["version_id"])
    s = refresh(client, s)
    assert (
        post(
            client,
            f"/applications/{s['application_id']}/submit",
            {"expected_version": s["version"], "declaration": True, "precheck_id": check["precheck_id"]},
        ).status_code
        == 409
    )
    check = post(client, f"/applications/{s['application_id']}/precheck", {}).json()["data"]
    assert check["ready"] and not check["stale"], check
    # A later edit invalidates saved readiness even when the file stays identical.
    s = save(client, s, signatory="Revised synthetic signatory")
    assert (
        post(
            client,
            f"/applications/{s['application_id']}/submit",
            {"expected_version": s["version"], "declaration": True, "precheck_id": check["precheck_id"]},
        ).status_code
        == 409
    )
    check = post(client, f"/applications/{s['application_id']}/precheck", {}).json()["data"]
    payload = {"expected_version": s["version"], "declaration": True, "precheck_id": check["precheck_id"]}
    request_key = key()
    r = post(client, f"/applications/{s['application_id']}/submit", payload, request_key)
    assert r.status_code == 200, r.text
    assert (
        post(client, f"/applications/{s['application_id']}/submit", payload, request_key).json()["data"]
        == r.json()["data"]
    )
    with client.app.state.session_factory() as db:
        assert db.get(DocumentVersion, first["version_id"]) and db.get(DocumentVersion, second["version_id"])
        field = db.get(ExtractedField, expiry["field_id"])
        assert field.version_id == first["version_id"] and field.value["normalized"] == "2020-01-01"
        findings = db.scalars(select(Finding).where(Finding.payload["code"].as_string() == "EXPIRED")).all()
        assert findings and all(f.evidence_node_id or f.evidence_gap for f in findings)


def test_unknown_date_not_expired_factual_mismatch_legitimate_change(client):
    s = complete(client, create(client, world(client)))
    r = upload(client, s, matching(s, expiry="illegible", name="Wrong MOCK Institute"))
    assert r.status_code == 200
    process(client, r.json()["data"]["version_id"])
    s = refresh(client, s)
    check = post(client, f"/applications/{s['application_id']}/precheck", {}).json()["data"]
    codes = {b["code"] for b in check["blocking"]}
    assert {"DATE_UNKNOWN", "FACTUAL_MISMATCH"} <= codes and "EXPIRED" not in codes
    s = save(client, s, proposed_name="MOCK Renamed Institute", proposed_address="MOCK declared new site")
    r = upload(client, s, matching(s))
    assert r.status_code == 200
    process(client, r.json()["data"]["version_id"])
    s = refresh(client, s)
    check = post(client, f"/applications/{s['application_id']}/precheck", {}).json()["data"]
    assert "FACTUAL_MISMATCH" not in {b["code"] for b in check["blocking"]}


def test_processing_scope_preview_and_deduplication(client, settings):
    s = create(client, world(client))
    content = matching(s)
    request_key = key()
    r = upload(client, s, content, request_key=request_key)
    assert r.status_code == 200, r.text
    assert upload(client, s, content, request_key=request_key).json()["data"] == r.json()["data"]
    v = r.json()["data"]
    process(client, v["version_id"])
    s = refresh(client, s)
    duplicate = upload(client, s, content)
    assert duplicate.status_code == 200 and duplicate.json()["data"]["version_id"] == v["version_id"]
    path = f"/api/v1/applications/{s['application_id']}/documents/{v['version_id']}/processing"
    body = client.get(path).json()["data"]
    assert body["fields"] and "storage_key" not in str(body) and "forensic" not in str(body)
    preview = f"/api/v1/documents/{v['document_id']}/versions/{v['number']}/preview"
    ticket = client.post(preview).json()["data"]["url"]
    assert client.get(ticket).status_code == 200
    for account in ["admin.b", "officer.b", "platform"]:
        with TestClient(create_app(settings)) as other:
            login(other, account)
            assert other.get(path).status_code in {403, 404}
            assert other.post(preview).status_code in {403, 404}
            assert other.get(ticket).status_code == 404


def test_interrupted_jobs_recover_and_immutable_results(client):
    s = create(client, world(client))
    r = upload(client, s, matching(s))
    assert r.status_code == 200
    v = r.json()["data"]["version_id"]
    with client.app.state.session_factory() as db:
        job = db.scalar(select(ProcessingJob).where(ProcessingJob.version_id == v))
        job.state, job.lease_until = "PROCESSING", int(time.time()) - 5
        db.commit()
    run_one(client.app.state.session_factory, client.app.state.storage, policy())
    with client.app.state.session_factory() as db:
        assert job_view(db, db.get(DocumentVersion, v))["state"] == "PROCESSING_FAILED"
    s = refresh(client, s)
    assert (
        post(
            client,
            f"/applications/{s['application_id']}/documents/{v}/retry",
            {"expected_version": s["version"]},
        ).status_code
        == 200
    )
    result = process(client, v)
    with client.app.state.session_factory() as db:
        with pytest.raises(SQLAlchemyError):
            db.execute(
                text("UPDATE processing_results SET payload='{}' WHERE id=:id"), {"id": result["result_id"]}
            )
            db.commit()


def test_real_clamav_local_integration(fixtures):
    root = Path("var/tools/clamav/clamav-1.5.4.win.x64").resolve()
    if not (root / "database/main.cvd").exists():
        pytest.skip("Real ClamAV definitions not installed on this host; fail-closed adapter is covered")
    p = policy()
    p.scanner = "clamav"
    p.clamscan = str(root / "clamscan.exe")
    p.database = str(root / "database")
    outcome = ClamAVScanner(p).scan(fixtures / "digital.pdf")
    assert outcome.status == "CLEAN" and outcome.mode == "CLAMAV"
    p.clamscan = "unavailable-clamscan"
    assert ClamAVScanner(p).scan(fixtures / "digital.pdf").status == "UNAVAILABLE"


def test_marginal_scan_manual_review_and_bounded_retries(client, fixtures):
    s = create(client, world(client))
    r = upload(client, s, (fixtures / "marginal.png").read_bytes(), "marginal.png", "image/png")
    assert r.status_code == 200, r.text
    v = r.json()["data"]
    result = process(client, v["version_id"])
    assert result["state"] == "MANUAL_REVIEW" and result["fields"] and not result["accepted"]
    s = refresh(client, s)
    r = post(
        client,
        f"/applications/{s['application_id']}/documents/{v['version_id']}/manual-review",
        {"expected_version": s["version"]},
    )
    assert r.status_code == 200 and not r.json()["data"]["accepted"]
    assert (
        client.post(f"/api/v1/documents/{v['document_id']}/versions/{v['number']}/preview").status_code == 200
    )
    p = policy()
    p.scanner = "unavailable"
    for attempt in [2, 3]:
        s = refresh(client, s)
        r = post(
            client,
            f"/applications/{s['application_id']}/documents/{v['version_id']}/retry",
            {"expected_version": s["version"]},
        )
        assert r.status_code == 200, r.text
        assert process(client, v["version_id"], p)["attempt"] == attempt
    s = refresh(client, s)
    assert (
        post(
            client,
            f"/applications/{s['application_id']}/documents/{v['version_id']}/retry",
            {"expected_version": s["version"]},
        ).status_code
        == 409
    )
    prior = client.get(
        f"/api/v1/applications/{s['application_id']}/documents/{v['version_id']}/processing?attempt=1"
    ).json()["data"]
    assert prior["fields"] and prior["state"] == "MANUAL_REVIEW"


def test_real_scanner_signature_detection_without_parsing(fixtures, tmp_path):
    root = Path("var/tools/clamav/clamav-1.5.4.win.x64").resolve()
    if not (root / "clamscan.exe").exists():
        pytest.skip("ClamAV binary absent on this host")
    # A harmless synthetic marker and a TEST-ONLY database exercise ClamAV exit status 1.
    # This database is never installed/configured for application safety decisions.
    (tmp_path / "test.ndb").write_text("Uranium.Demo.Marker:0:*:" + b"MOCK_MALWARE_TEST".hex() + "\n")
    p = policy()
    p.clamscan = str(root / "clamscan.exe")
    p.database = str(tmp_path)
    assert ClamAVScanner(p).scan(fixtures / "mock-malware.pdf").status == "INFECTED"


def test_reference_dates_and_previous_year_accounts(client):
    s = complete(client, create(client, world(client)))

    def bytes_for(kind, **values):
        return generator.pdf_bytes(
            document_type=kind,
            name=s["details"]["proposed_name"],
            permanent_id="MOCK-" + s["institution_id"],
            address=s["details"]["proposed_address"],
            **values,
        )

    r = upload(client, s, bytes_for("FIRE_SAFETY", issue="2030-01-01"))
    assert r.status_code == 200, r.text
    process(client, r.json()["data"]["version_id"])
    s = refresh(client, s)
    check = post(client, f"/applications/{s['application_id']}/precheck", {}).json()["data"]
    assert "ISSUED_AFTER_REFERENCE" in {b["code"] for b in check["blocking"]}
    r = upload(client, s, bytes_for("AUDITED_ACCOUNTS"), slot="EOA-D07")
    assert r.status_code == 200, r.text
    process(client, r.json()["data"]["version_id"])
    s = refresh(client, s)
    check = post(client, f"/applications/{s['application_id']}/precheck", {}).json()["data"]
    assert "ACCOUNTS_YEAR_UNRESOLVED" in {b["code"] for b in check["blocking"]}
    r = upload(client, s, bytes_for("AUDITED_ACCOUNTS", academic_year="2025-26"), slot="EOA-D07")
    process(client, r.json()["data"]["version_id"])
    s = refresh(client, s)
    check = post(client, f"/applications/{s['application_id']}/precheck", {}).json()["data"]
    assert "ACCOUNTS_YEAR_UNRESOLVED" not in {b["code"] for b in check["blocking"]}


def test_bounded_ten_file_request_and_replay(client):
    s = create(client, world(client))
    item = next(i for i in s["checklist"]["items"] if i["code"] == "EOA-D05")
    params = {"requirement_id": item["id"], "document_type": "FIRE_SAFETY", "expected_version": s["version"]}
    files = [
        ("files", (f"mock-{i}.pdf", matching(s) + f"\n% MOCK {i}".encode(), "application/pdf"))
        for i in range(10)
    ]
    headers = {"Idempotency-Key": key()}
    path = f"/api/v1/applications/{s['application_id']}/documents/batch"
    r = client.post(path, params=params, files=files, headers=headers)
    assert r.status_code == 200, r.text
    versions = r.json()["data"]
    assert len(versions) == 10 and len({v["version_id"] for v in versions}) == 10
    assert versions[-1]["number"] == 10 and versions[-1]["application_version"] == s["version"] + 10
    replay = client.post(path, params=params, files=files, headers=headers)
    assert replay.status_code == 200 and replay.json()["data"] == versions
    assert len(client.get(f"/api/v1/applications/{s['application_id']}/documents").json()["data"]) == 10


def test_multipart_file_count_size_and_atomic_rejection(client):
    s = create(client, world(client))
    item = next(i for i in s["checklist"]["items"] if i["code"] == "EOA-D05")
    params = {"requirement_id": item["id"], "document_type": "FIRE_SAFETY", "expected_version": s["version"]}
    path = f"/api/v1/applications/{s['application_id']}/documents/batch"
    valid = ("files", ("mock.pdf", matching(s), "application/pdf"))
    assert (
        client.post(path, params=params, files=[valid] * 11, headers={"Idempotency-Key": key()}).status_code
        == 413
    )
    assert (
        client.post(
            path,
            params=params,
            files=[valid, ("files", ("wrong.png", b"not-a-png", "image/png"))],
            headers={"Idempotency-Key": key()},
        ).status_code
        == 415
    )
    policy = client.app.state.processing_policy
    previous = policy.pdf_bytes
    try:
        policy.pdf_bytes = 100
        assert (
            client.post(path, params=params, files=[valid], headers={"Idempotency-Key": key()}).status_code
            == 413
        )
    finally:
        policy.pdf_bytes = previous
    assert refresh(client, s)["version"] == s["version"]
    assert not client.get(f"/api/v1/applications/{s['application_id']}/documents").json()["data"]
