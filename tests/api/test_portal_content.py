"""Public notices are scoped, CSRF-protected, versioned, and audited."""

from datetime import date, timedelta
from sqlalchemy import select
from conftest import login
from uranium.models import AuditEvent


def test_notice_publication_role_csrf_validation_and_conflict(client):
    login(client, "platform")
    original = client.get("/api/v1/admin/portal/content").json()["data"]
    today = date.today().isoformat()

    def notice(identifier, status="Published", day=today):
        return dict(
            id=identifier,
            title="Test notice",
            summary="Public summary",
            body="Public guidance text",
            category="Guidance",
            status=status,
            publishedOn=day,
            pinned=False,
            link="/resources",
        )

    payload = dict(
        version=original["version"],
        notices=[
            notice("public"),
            notice("draft", "Draft"),
            notice("archived", "Archived"),
            notice("future", day=(date.today() + timedelta(days=1)).isoformat()),
        ],
        announcement=dict(enabled=True, text="Test update", link="/notices"),
    )
    csrf = client.headers.pop("X-CSRF-Token")
    assert client.put("/api/v1/admin/portal/content", json=payload).status_code == 403
    client.headers["X-CSRF-Token"] = csrf
    bad = {**payload, "notices": [{**notice("bad"), "link": "javascript:alert(1)"}]}
    assert client.put("/api/v1/admin/portal/content", json=bad).status_code == 422
    saved = client.put("/api/v1/admin/portal/content", json=payload)
    assert saved.status_code == 200
    assert client.put("/api/v1/admin/portal/content", json=payload).status_code == 409
    with client.app.state.session_factory() as db:
        assert db.scalar(select(AuditEvent).where(AuditEvent.operation == "PORTAL_CONTENT_UPDATED"))
    client.delete("/api/v1/auth/session")
    assert [n["id"] for n in client.get("/api/v1/portal/content").json()["data"]["notices"]] == ["public"]
    assert client.get("/api/v1/admin/portal/content").status_code == 401
    login(client, "admin.a")
    assert client.get("/api/v1/admin/portal/content").status_code == 403
    assert (
        client.put(
            "/api/v1/admin/portal/content", json={**payload, "version": payload["version"] + 1}
        ).status_code
        == 403
    )
    login(client, "platform")
    original["version"] = saved.json()["data"]["version"]
    assert client.put("/api/v1/admin/portal/content", json=original).status_code == 200
