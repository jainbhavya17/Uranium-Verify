import os
import re
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from uranium.config import load_local_environment


def make_engine(url: str):
    load_local_environment()
    is_sqlite = url.startswith("sqlite")

    if is_sqlite:
        Path("var").mkdir(exist_ok=True)

    engine = create_engine(
        url,
        connect_args={"check_same_thread": False} if is_sqlite else {"connect_timeout": 5},
        pool_pre_ping=True,
        **({} if is_sqlite else {"pool_timeout": 5}),
    )

    if is_sqlite:

        @event.listens_for(engine, "connect")
        def enable_foreign_keys(connection, _):
            connection.execute("PRAGMA foreign_keys=ON")

    elif engine.dialect.name == "postgresql":
        schema = os.getenv("DATABASE_SCHEMA", "").strip()

        if schema:
            if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", schema):
                raise ValueError("Invalid DATABASE_SCHEMA")

            @event.listens_for(engine, "connect")
            def select_schema(connection, _):
                previous_autocommit = connection.autocommit
                try:
                    connection.autocommit = True
                    with connection.cursor() as cursor:
                        cursor.execute(f'SET search_path TO "{schema}", public')
                finally:
                    connection.autocommit = previous_autocommit

    return engine


def session_factory(engine):
    return sessionmaker(bind=engine, expire_on_commit=False)
