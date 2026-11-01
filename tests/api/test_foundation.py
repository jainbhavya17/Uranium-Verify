import json
import time
from pathlib import Path

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from conftest import login
from uranium.auth import digest
from uranium.config import Settings
from uranium.main import create_app
from uranium.models import (
    Application,
    ApprovalSnapshot,
    AuditEvent,
    AuthSession,
    Base,
    DocumentVersion,
    Membership,
    Revision,
    User,
)
from uranium.seed import fixture_id, seed
from conftest import TEST_PASSWORD


def fid(key):
    return fixture_id(key)


def test_health_contract_validation_and_openapi(client):
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["meta"]["request_id"] == response.headers["X-Request-ID"]
    assert client.get("/api/v1/me").status_code == 401
    invalid = client.post("/api/v1/auth/session", json={"email": "a", "password": ""})
    assert invalid.status_code == 422
    assert invalid.json()["error"]["field_errors"]
    assert "password" not in invalid.text.replace("body.password", "")
    schemas = client.get("/api/v1/openapi.json").json()["components"]["schemas"]
    assert "JobView" in schemas and "UserView" in schemas


@pytest.mark.parametrize(
    "account,roles,landing",
    [
        ("submitter.a", ["institution_submitter"], "/institution/dashboard"),
        ("admin.a", ["institution_admin"], "/institution/dashboard"),
        ("admin.b", ["institution_admin"], "/institution/dashboard"),
        ("officer.a", ["officer"], "/officer/dashboard"),
        ("officer.b", ["officer"], "/officer/dashboard"),
        ("specialist", ["specialist"], "/officer/verifications"),
        ("supervisor", ["supervisor"], "/officer/dashboard"),
        ("platform", ["admin"], "/admin/users-roles"),
        ("auditor", ["auditor"], "/admin/audit"),
    ],
)
def test_identity_role_resolution(client, account, roles, landing):
    user = login(client, account)
    assert user["roles"] == roles and user["landing"] == landing
    cookie = client.cookies.get("uv_session")
    assert cookie and len(cookie) > 32
    with client.app.state.session_factory() as db:
        saved = db.scalar(select(AuthSession).where(AuthSession.token_hash == digest(cookie)))
        assert saved and saved.token_hash != cookie


def test_cross_tenant_idor_list_and_preview(client):
    login(client)
    cases = client.get("/api/v1/applications").json()
    assert cases["meta"]["total"] == 1 and cases["data"][0]["id"] == fid("application-a")
    for path in [
        f"/applications/{fid('application-b')}",
        f"/applications/{fid('application-b')}/documents",
        f"/documents/{fid('document-b')}/versions/1",
        f"/institutions/{fid('institution-b')}/history",
    ]:
        assert client.get("/api/v1" + path).status_code == 404
    assert client.post(f"/api/v1/documents/{fid('document-b')}/versions/1/preview").status_code == 404
    assert (
        client.get("/api/v1/applications/not-real").json()["error"]["message"]
        == client.get(f"/api/v1/applications/{fid('application-b')}").json()["error"]["message"]
    )
    with client.app.state.session_factory() as db:
        assert db.scalar(
            select(func.count()).select_from(AuditEvent).where(AuditEvent.operation == "ACCESS_DENIED")
        )


def test_officer_assignment_and_specialist_scope(client):
    login(client, "officer.a")
    assert client.get(f"/api/v1/applications/{fid('application-a')}").status_code == 200
    assert client.get(f"/api/v1/applications/{fid('application-b')}").status_code == 404
    login(client, "specialist")
    assert client.get(f"/api/v1/applications/{fid('application-a')}/documents").status_code == 200
    assert (
        client.get(
            "/api/v1/shell/access?space=officer&section=review&case_id=" + fid("application-a")
        ).status_code
        == 403
    )
    assert (
        client.get(
            "/api/v1/shell/access?space=officer&section=authenticity&case_id=" + fid("application-a")
        ).status_code
        == 200
    )
    assert client.get(f"/api/v1/applications/{fid('application-b')}/documents").status_code == 404


def test_admin_no_implicit_content_access_and_auditor_readonly(client):
    login(client, "platform")
    assert client.get("/api/v1/admin/users").status_code == 200
    assert client.get("/api/v1/applications").json()["data"] == []
    assert client.get(f"/api/v1/applications/{fid('application-a')}/documents").status_code == 404
    assert client.post(f"/api/v1/documents/{fid('document-a')}/versions/1/preview").status_code == 404
    login(client, "auditor")
    assert client.get("/api/v1/admin/audit").status_code == 200
    assert client.get("/api/v1/admin/users").status_code == 403
    assert client.get("/api/v1/shell/access?space=admin&section=rules").status_code == 403
    assert client.post("/api/v1/admin/audit", json={"operation": "tamper"}).status_code == 405
    assert client.delete("/api/v1/admin/audit").status_code == 405


def test_client_role_tampering_never_changes_authority(client):
    payload = {"email": "admin.a@demo.uranium.test", "password": TEST_PASSWORD, "role": "admin"}
    assert client.post("/api/v1/auth/session", json=payload).status_code == 422
    login(client)
    client.headers["X-Role"] = "admin"
    client.cookies.set("role", "admin")
    assert client.get("/api/v1/me").json()["data"]["roles"] == ["institution_admin"]
    assert client.get("/api/v1/admin/users").status_code == 403
    assert client.get("/api/v1/shell/access?space=admin&section=users-roles").status_code == 403


def test_csrf_session_expiry_revocation_and_disabled_user(client):
    login(client)
    token = client.cookies.get("uv_session")
    csrf = client.headers.pop("X-CSRF-Token")
    assert client.delete("/api/v1/auth/session").status_code == 403
    client.headers["X-CSRF-Token"] = csrf
    assert client.delete("/api/v1/auth/session").status_code == 200
    client.cookies.set("uv_session", token)
    assert client.get("/api/v1/me").status_code == 401
    client.cookies.clear()
    login(client)
    token = client.cookies.get("uv_session")
    with client.app.state.session_factory() as db:
        session = db.scalar(select(AuthSession).where(AuthSession.token_hash == digest(token)))
        session.expires_at = int(time.time()) - 1
        db.commit()
    assert client.get("/api/v1/me").status_code == 401
    login(client)
    with client.app.state.session_factory() as db:
        user = db.get(User, fid("admin.a@demo.uranium.test"))
        user.active = False
        db.commit()
    assert client.get("/api/v1/me").status_code == 401
    with client.app.state.session_factory() as db:
        db.get(User, fid("admin.a@demo.uranium.test")).active = True
        db.commit()


def test_membership_changes_take_effect_without_new_login(client):
    login(client)
    with client.app.state.session_factory() as db:
        member = db.get(Membership, fid("membership-admin.a@demo.uranium.test"))
        member.valid_until = int(time.time()) - 1
        db.commit()
    assert client.get("/api/v1/applications").json()["data"] == []
    with client.app.state.session_factory() as db:
        db.get(Membership, fid("membership-admin.a@demo.uranium.test")).valid_until = None
        db.commit()


def test_private_preview_rechecks_session_expiry_and_assignment(client):
    login(client, "officer.a")
    response = client.post(f"/api/v1/documents/{fid('document-a')}/versions/1/preview")
    assert response.status_code == 200
    url = response.json()["data"]["url"]
    preview = client.get(url)
    assert preview.status_code == 200 and preview.content.startswith(b"%PDF")
    assert preview.headers["Cache-Control"] == "no-store"
    assert client.get("/private/" + fid("version-a")).status_code == 404
    from uranium.models import Assignment, PreviewTicket

    with client.app.state.session_factory() as db:
        db.get(Assignment, fid("assignment-a")).active = False
        db.commit()
    assert client.get(url).status_code == 404
    with client.app.state.session_factory() as db:
        db.get(Assignment, fid("assignment-a")).active = True
        ticket = db.scalar(
            select(PreviewTicket).where(PreviewTicket.token_hash == digest(url.split("/")[-1]))
        )
        ticket.expires_at = int(time.time()) - 1
        db.commit()
    assert client.get(url).status_code == 404
    url2 = client.post(f"/api/v1/documents/{fid('document-a')}/versions/1/preview").json()["data"]["url"]
    login(client, "platform")
    assert client.get(url2).status_code == 404


def test_stable_pagination_and_safe_metadata(client):
    login(client)
    a = client.get("/api/v1/applications?page_size=1").json()
    b = client.get("/api/v1/applications?page_size=1").json()
    assert a["data"] == b["data"] and a["meta"]["total"] == 1
    assert client.get("/api/v1/applications?page=0").status_code == 422
    assert client.get("/api/v1/applications?page_size=101").status_code == 422
    assert client.get("/api/v1/applications?page=2").json()["data"] == []
    docs = client.get(f"/api/v1/applications/{fid('application-a')}/documents").json()["data"]
    assert "storage_key" not in docs[0]


def test_database_immutable_boundaries_and_ownership(client):
    engine = client.app.state.engine
    mutations = [
        "UPDATE audit_events SET operation='tampered'",
        "DELETE FROM audit_events",
        "UPDATE document_versions SET original_name='tampered'",
        "DELETE FROM document_versions",
        "UPDATE historical_approval_snapshots SET academic_year='tampered'",
        "UPDATE application_revisions SET frozen=false",
        "INSERT INTO application_claims (id,created_at,revision_id,field_key,value) "
        f"VALUES ('forbidden-child',0,'{fid('revision-a')}','x','{{}}')",
    ]
    for statement in mutations:
        with pytest.raises(SQLAlchemyError):
            with engine.begin() as conn:
                conn.execute(text(statement))
    with client.app.state.session_factory() as db:
        draft_revision = Revision(
            application_id=fid("application-b"),
            number=2,
            actor_id=fid("admin.b@demo.uranium.test"),
            frozen=False,
            manifest={},
        )
        db.add(draft_revision)
        db.commit()
        draft_id = draft_revision.id
    with pytest.raises(IntegrityError):
        with client.app.state.session_factory() as db:
            db.add(
                DocumentVersion(
                    document_id=fid("document-a"),
                    application_id=fid("application-b"),
                    revision_id=draft_id,
                    number=2,
                    sha256="0" * 64,
                    storage_key="a" * 64,
                    original_name="cross.pdf",
                    media_type="application/pdf",
                    uploader_id=fid("admin.a@demo.uranium.test"),
                    status="UPLOADED",
                )
            )
            db.commit()


def test_new_file_cannot_be_attached_to_frozen_submission(client):
    with pytest.raises(SQLAlchemyError, match="Frozen revision evidence"):
        with client.app.state.session_factory() as db:
            db.add(
                DocumentVersion(
                    document_id=fid("document-a"),
                    application_id=fid("application-a"),
                    revision_id=fid("revision-a"),
                    number=2,
                    sha256="e" * 64,
                    storage_key="e" * 64,
                    original_name="late.pdf",
                    media_type="application/pdf",
                    uploader_id=fid("admin.a@demo.uranium.test"),
                    status="UPLOADED",
                    is_mock=True,
                )
            )
            db.commit()


def test_seed_is_additive_and_idempotent(client, settings):
    def counts():
        with client.app.state.session_factory() as db:
            return [
                db.scalar(select(func.count()).select_from(m))
                for m in [User, Application, ApprovalSnapshot, Revision, DocumentVersion, Membership]
            ]

    before = counts()
    seed(settings, TEST_PASSWORD)
    seed(settings, TEST_PASSWORD)
    assert counts() == before
    assert len(Base.metadata.tables) >= 35


def test_snapshot_can_publish_once_then_locks(client):
    with client.app.state.session_factory() as db:
        snapshot = ApprovalSnapshot(
            institution_id=fid("institution-a"),
            academic_year="2099-00",
            version=1,
            payload={"is_mock": True},
            source_ref="MOCK test",
            published=False,
        )
        db.add(snapshot)
        db.commit()
        snapshot.published = True
        db.commit()
        snapshot.source_ref = "tampered after publication"
        with pytest.raises(ValueError, match="immutable"):
            db.commit()
        db.rollback()


def test_storage_path_traversal_and_write_once(client):
    storage = client.app.state.storage
    for key in ["../secret", "a" * 64 + "/../file", "C:\\secret"]:
        with pytest.raises(ValueError):
            storage.read(key)
    storage.write_once("f" * 64, b"original")
    storage.write_once("f" * 64, b"original")
    with pytest.raises(ValueError):
        storage.write_once("f" * 64, b"replacement")


def test_demo_adapter_fails_closed_for_production():
    with pytest.raises(RuntimeError, match="Production is disabled"):
        create_app(Settings(environment="production"))


def test_registry_matches_srs_prompt():
    routes = json.loads(Path("packages/contracts/routes.json").read_text())
    assert len(routes) == len({r["path"] for r in routes}) == 33
    source = Path("srs-route-map.md").read_text(encoding="utf-8")
    assert all(f"| {r['id']} | `{r['path']}`" in source for r in routes)
