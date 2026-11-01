"""Restore a consistent backup into NEW disposable paths/database; never overwrite a source."""

import argparse
import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import uuid
from pathlib import Path
from sqlalchemy import create_engine, inspect, text, select, and_
from sqlalchemy.engine import make_url

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "services/api"))
from uranium.config import Settings
from uranium.models import Base, DocumentVersion, ReportSnapshot, ReportPublication
from uranium.storage import LocalPrivateStorage


def counts(engine):
    quote = engine.dialect.identifier_preparer.quote
    with engine.connect() as db:
        return {
            name: db.scalar(text("SELECT count(*) FROM " + quote(name)))
            for name in inspect(engine).get_table_names()
        }


def logical_restore(source_url, restore_url, root):
    source = create_engine(source_url)
    with source.connect().execution_options(isolation_level="REPEATABLE READ") as connection:
        with connection.begin():
            rows = {
                table.name: [dict(row) for row in connection.execute(select(table)).mappings()]
                for table in Base.metadata.sorted_tables
            }
    backup = root / "logical-backup.json"
    backup.write_text(json.dumps(rows, ensure_ascii=True), encoding="utf-8")
    env = {**os.environ, "DATABASE_URL": restore_url, "PYTHONPATH": "services/api"}
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        env=env,
        capture_output=True,
        timeout=120,
        check=False,
    )
    if result.returncode:
        raise RuntimeError("Disposable restore migrations failed; private diagnostics were not logged.")
    restored = create_engine(restore_url)
    assert make_url(restore_url).database.startswith("uranium_restore_")
    data = json.loads(backup.read_text(encoding="utf-8"))
    with restored.begin() as db:
        # Local restore administrator only, on the NEW disposable database. Source guards stay enabled.
        db.execute(text("SET LOCAL session_replication_role = 'replica'"))
        for table in Base.metadata.sorted_tables:
            if data[table.name]:
                db.execute(table.insert(), data[table.name])
        db.execute(text("SET LOCAL session_replication_role = 'origin'"))
    # Revalidate every FK with an explicit orphan query, including previously frozen evidence.
    with restored.connect() as db:
        for table in Base.metadata.sorted_tables:
            for constraint in table.foreign_key_constraints:
                remote = constraint.referred_table.alias("parent")
                conditions = [
                    table.c[element.parent.name] == remote.c[element.column.name]
                    for element in constraint.elements
                ]
                nonnull = [table.c[element.parent.name].is_not(None) for element in constraint.elements]
                query = (
                    select(table.c[next(iter(table.primary_key.columns)).name])
                    .select_from(table.outerjoin(remote, and_(*conditions)))
                    .where(*nonnull, remote.c[constraint.elements[0].column.name].is_(None))
                    .limit(1)
                )
                assert db.execute(query).first() is None, "Restored foreign key orphan."
    source.dispose()
    restored.dispose()


def validate(url, storage_root, pg_bin=None):
    source_url = make_url(url)
    root = (Path("var/backup-validation") / uuid.uuid4().hex).resolve()
    root.mkdir(parents=True, exist_ok=False)
    if source_url.drivername.startswith("sqlite"):
        source = Path(source_url.database).resolve()
        backup = root / "backup.db"
        restored = root / "restored.db"
        with sqlite3.connect(source) as original, sqlite3.connect(backup) as target:
            original.backup(target)
        shutil.copyfile(backup, restored)
        backup_url = "sqlite:///" + backup.as_posix()
        restore_url = "sqlite:///" + restored.as_posix()
    else:
        import psycopg
        from psycopg import sql

        name = "uranium_restore_" + uuid.uuid4().hex[:12]
        password = source_url.password or os.getenv("POSTGRES_PASSWORD", "")
        parameters = {
            "host": source_url.host or "127.0.0.1",
            "port": source_url.port or 5432,
            "user": source_url.username,
            "password": password,
        }
        with psycopg.connect(dbname="postgres", autocommit=True, **parameters) as admin:
            admin.execute(
                sql.SQL("CREATE DATABASE {} TEMPLATE template0 ENCODING 'UTF8'").format(sql.Identifier(name))
            )
        flags = [
            "--host",
            parameters["host"],
            "--port",
            str(parameters["port"]),
            "--username",
            parameters["user"],
        ]
        env = {**os.environ, "PGPASSWORD": password}
        restore_url = source_url.set(database=name).render_as_string(hide_password=False)
        if not pg_bin:
            logical_restore(url, restore_url, root)
        backup = root / "backup.dump"
        suffix = ".exe" if os.name == "nt" else ""
        for command in (
            [
                [
                    str(Path(pg_bin) / ("pg_dump" + suffix)),
                    *flags,
                    "--format=custom",
                    "--no-owner",
                    "--no-acl",
                    "--file",
                    str(backup),
                    source_url.database,
                ],
                [
                    str(Path(pg_bin) / ("pg_restore" + suffix)),
                    *flags,
                    "--no-owner",
                    "--no-acl",
                    "--exit-on-error",
                    "--dbname",
                    name,
                    str(backup),
                ],
            ]
            if pg_bin
            else []
        ):
            # Keep diagnostics bounded and private; never echo a DSN or environment secrets.
            result = subprocess.run(command, env=env, capture_output=True, timeout=120, check=False)
            if result.returncode:
                raise RuntimeError("Local PostgreSQL backup/restore command failed; no secrets logged.")
        backup_url = url
    original = create_engine(backup_url)
    restored = create_engine(restore_url)
    before, after = counts(original), counts(restored)
    assert before == after, "Restored row counts differ."
    original_storage = LocalPrivateStorage(Path(storage_root))
    new_storage = LocalPrivateStorage(root / "private")
    from sqlalchemy.orm import Session

    files = []
    with Session(restored) as db:
        for value in db.scalars(select(DocumentVersion)):
            files.append(
                {"kind": "original", "id": value.id, "key": value.storage_key, "sha256": value.sha256}
            )
        for model, kind in [(ReportSnapshot, "review_report"), (ReportPublication, "published_summary")]:
            for value in db.scalars(select(model)):
                files.append(
                    {
                        "kind": kind,
                        "id": value.id,
                        "key": value.storage_key,
                        "sha256": value.manifest["pdf_sha256"],
                    }
                )
        for item in files:
            data = original_storage.read(item["key"])
            assert hashlib.sha256(data).hexdigest() == item["sha256"], "Source manifest hash mismatch."
            new_storage.write_once(item["key"], data)
            assert hashlib.sha256(new_storage.read(item["key"])).hexdigest() == item["sha256"], (
                "Restored file hash mismatch."
            )
        if restored.dialect.name == "sqlite":
            assert db.execute(text("PRAGMA foreign_key_check")).all() == []
            assert db.scalar(text("PRAGMA integrity_check")) == "ok"
        else:
            assert (
                db.scalar(text("SELECT count(*) FROM pg_constraint WHERE contype='f' AND NOT convalidated"))
                == 0
            )
    (root / "document-manifest.json").write_text(json.dumps(files, indent=2), encoding="utf-8")
    result = {
        "database": restored.dialect.name,
        "status": "PASS",
        "new_disposable_restore": True,
        "tables": len(after),
        "row_counts_match": True,
        "foreign_keys_valid": True,
        "immutable_files_verified": len(files),
        "originals_verified": sum(i["kind"] == "original" for i in files),
        "report_files_verified": sum(i["kind"] != "original" for i in files),
        "source_untouched": True,
        "method": "SQLite online backup"
        if restored.dialect.name == "sqlite"
        else "PostgreSQL custom pg_dump/pg_restore"
        if pg_bin
        else "PostgreSQL repeatable-read logical JSON backup; migrations into NEW disposable DB; local restore role; every FK explicitly checked",
    }
    original.dispose()
    restored.dispose()
    report = Path("docs/verification/phase5-backup-restore.json")
    prior = json.loads(report.read_text(encoding="utf-8")) if report.exists() else []
    report.write_text(
        json.dumps([r for r in prior if r["database"] != result["database"]] + [result], indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--pg-bin")
    args = parser.parse_args()
    settings = Settings()
    try:
        validate(settings.database_url, settings.storage_root, args.pg_bin)
    except Exception as error:
        print(
            "Backup validation failed:",
            type(error).__name__,
            "(private SQL/credential values were not logged)",
        )
        raise SystemExit(1)
