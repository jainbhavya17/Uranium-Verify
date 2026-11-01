"""Add the original portal sample pack without resetting any existing records."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "services/api"))
from uranium.config import Settings
from uranium.db import make_engine, session_factory
from uranium.storage import LocalPrivateStorage
from uranium.seed_restored_portal import seed_restored_portal

settings = Settings()
settings.validate()
with session_factory(make_engine(settings.database_url))() as db:
    print(seed_restored_portal(db, LocalPrivateStorage(settings.storage_root)))
