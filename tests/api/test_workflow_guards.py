from dataclasses import replace
from fastapi.testclient import TestClient
from conftest import login
from test_institution import create, world
from uranium.main import create_app


def test_development_disables_legacy_shortcuts(client, settings):
    saved = create(client, world(client))
    slot = saved["checklist"]["items"][0]
    body = {
        "expected_version": saved["version"],
        "requirement_id": slot["id"],
        "document_type": slot["acceptable_alternatives"][0],
    }
    with TestClient(create_app(replace(settings, environment="development"))) as browser_api:
        login(browser_api)
        assert (
            browser_api.post(
                f"/api/v1/applications/{saved['application_id']}/documents/fixtures", json=body
            ).status_code
            == 404
        )
        assert (
            browser_api.post(
                f"/api/v1/applications/{saved['application_id']}/documents/quarantine",
                params={**body, "filename": "example.pdf"},
                content=b"example",
            ).status_code
            == 404
        )
