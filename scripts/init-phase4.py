"""Add a separate governed-publication demo credential without changing existing users."""

import os
import secrets
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "services/api"))
from uranium.config import Settings
from uranium.db import make_engine, session_factory
from uranium.storage import LocalPrivateStorage
from uranium.seed_officer import seed_officer

settings = Settings()
password = os.getenv("PHASE4_DEMO_PASSWORD") or os.getenv("DEMO_PASSWORD", "")
if len(password) < 12:
    password = secrets.token_urlsafe(24)
    source = Path(".env")
    lines = [
        line
        for line in source.read_text(encoding="utf-8-sig").splitlines()
        if not line.startswith("PHASE4_DEMO_PASSWORD=")
    ]
    source.write_text("\n".join(lines) + f"\nPHASE4_DEMO_PASSWORD={password}\n", encoding="utf-8")
    os.environ["PHASE4_DEMO_PASSWORD"] = password
with session_factory(make_engine(settings.database_url))() as db:
    result = seed_officer(db, LocalPrivateStorage(settings.storage_root), password)
    db.commit()
print("Phase 4 synthetic fixture IDs:", result)
print(
    "New approver credential is configured through PHASE4_DEMO_PASSWORD (or DEMO_PASSWORD when sufficiently long). Existing identity hashes were preserved. No password was printed."
)
