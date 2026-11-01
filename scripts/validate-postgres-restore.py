"""Create an isolated synthetic PostgreSQL source and restore it without touching existing databases."""

import importlib.util
import os
import subprocess
import sys
import uuid
from pathlib import Path
from urllib.parse import quote
import psycopg
from psycopg import sql
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "services/api"))
from uranium.config import Settings
from uranium.seed import seed
from uranium.seed_officer import seed_officer
from uranium.db import make_engine, session_factory
from uranium.storage import LocalPrivateStorage
from uranium.main import create_app
from uranium.reports import run_report_one


def run():
    password = os.getenv("POSTGRES_PASSWORD", "")
    if not password:
        raise RuntimeError("Set POSTGRES_PASSWORD for the local restore administrator.")
    port = int(os.getenv("POSTGRES_PORT", "5433"))
    name = "uranium_backup_source_" + uuid.uuid4().hex[:12]
    with psycopg.connect(
        host="127.0.0.1", port=port, user="uranium", password=password, dbname="postgres", autocommit=True
    ) as db:
        db.execute(
            sql.SQL("CREATE DATABASE {} TEMPLATE template0 ENCODING 'UTF8'").format(sql.Identifier(name))
        )
    url = f"postgresql+psycopg://uranium:{quote(password, safe='')}@127.0.0.1:{port}/{name}"
    root = Path("var/backup-sources") / name
    root.mkdir(parents=True, exist_ok=False)
    env = {**os.environ, "DATABASE_URL": url, "PYTHONPATH": "services/api"}
    migrated = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"], env=env, capture_output=True, timeout=120
    )
    if migrated.returncode:
        raise RuntimeError("Isolated backup source migrations failed.")
    settings = Settings(database_url=url, storage_root=root / "private")
    credential = "Synthetic-backup-only-472!"
    seed(settings, credential)
    storage = LocalPrivateStorage(settings.storage_root)
    factory = session_factory(make_engine(url))
    with factory() as db:
        pack = seed_officer(db, storage, credential)
        db.commit()
    with TestClient(create_app(settings)) as client:
        r = client.post(
            "/api/v1/auth/session", json={"email": "officer.a@demo.uranium.test", "password": credential}
        )
        assert r.status_code == 200
        client.headers["X-CSRF-Token"] = r.json()["data"]["csrf_token"]
        r = client.post(
            f"/api/v1/officer/cases/{pack['case_id']}/reports",
            json={
                "expected_version": 1,
                "rationale": "MOCK captured review snapshot for independent backup and restore validation.",
            },
            headers={"Idempotency-Key": str(uuid.uuid4())},
        )
        assert r.status_code == 200
        identifier = r.json()["data"]["id"]
        assert run_report_one(factory, storage)
        r = client.post(
            f"/api/v1/reports/{identifier}/publish-summary",
            json={
                "public_message": "MOCK institution-safe snapshot used to verify restored public and private report bytes."
            },
            headers={"Idempotency-Key": str(uuid.uuid4())},
        )
        assert r.status_code == 200
    spec = importlib.util.spec_from_file_location(
        "backup_validation", Path("scripts/validate-backup-restore.py")
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.validate(url, settings.storage_root)


if __name__ == "__main__":
    try:
        run()
    except Exception as error:
        print(
            "Isolated PostgreSQL restore validation failed:",
            type(error).__name__,
            "(private diagnostics not logged)",
        )
        raise SystemExit(1)
