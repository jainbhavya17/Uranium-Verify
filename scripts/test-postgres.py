"""Run migrations and the API suite against a NEW isolated PostgreSQL database. No existing DB is reset."""

import os
import subprocess
import sys
import uuid
from pathlib import Path
from urllib.parse import quote

import psycopg
from psycopg import sql

password = os.environ.get("POSTGRES_PASSWORD", "")
if not password:
    raise SystemExit("Set POSTGRES_PASSWORD for your local development PostgreSQL server.")
port = int(os.environ.get("POSTGRES_PORT", "5433"))
name = "uranium_test_" + uuid.uuid4().hex[:12]
with psycopg.connect(
    host="127.0.0.1", port=port, user="uranium", password=password, dbname="postgres", autocommit=True
) as connection:
    connection.execute(
        sql.SQL("CREATE DATABASE {} ENCODING 'UTF8' TEMPLATE template0 LC_COLLATE 'C' LC_CTYPE 'C'").format(
            sql.Identifier(name)
        )
    )
url = f"postgresql+psycopg://uranium:{quote(password, safe='')}@127.0.0.1:{port}/{name}"
env = {**os.environ, "DATABASE_URL": url, "TEST_DATABASE_URL": url, "APP_ENV": "test"}
python = sys.executable
for args in [
    ["-m", "alembic", "upgrade", "head"],
    ["-m", "alembic", "check"],
    ["-m", "alembic", "downgrade", "base"],
    ["-m", "alembic", "upgrade", "head"],
    ["-m", "pytest", "-q", "tests/api", "--basetemp=var/pytest-postgres", "--junitxml=var/api-postgres.xml"],
]:
    result = subprocess.run([python, *args], env=env, check=False)
    if result.returncode:
        raise SystemExit(result.returncode)
Path("var/postgres-test-database.txt").write_text(name + "\n", encoding="utf-8")
print("PostgreSQL migration round-trip and API suite passed. Isolated test database retained:", name)
