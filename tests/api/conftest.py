import os
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient

from uranium.config import Settings
from uranium.main import create_app
from uranium.seed import seed

TEST_PASSWORD = "Test-fixtures-only-472!"


@pytest.fixture(scope="session")
def settings(tmp_path_factory):
    root = tmp_path_factory.mktemp("api")
    url = os.getenv("TEST_DATABASE_URL", f"sqlite:///{(root / 'test.db').as_posix()}")
    settings = Settings(environment="test", database_url=url, storage_root=Path(root / "private"))
    previous = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = url
    command.upgrade(Config("alembic.ini"), "head")
    if previous is None:
        os.environ.pop("DATABASE_URL", None)
    else:
        os.environ["DATABASE_URL"] = previous
    seed(settings, TEST_PASSWORD)
    yield settings


@pytest.fixture
def client(settings):
    with TestClient(create_app(settings)) as client:
        yield client


def login(client, account="admin.a"):
    response = client.post(
        "/api/v1/auth/session", json={"email": account + "@demo.uranium.test", "password": TEST_PASSWORD}
    )
    assert response.status_code == 200, response.text
    client.headers["X-CSRF-Token"] = response.json()["data"]["csrf_token"]
    return response.json()["data"]
