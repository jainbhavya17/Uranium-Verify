"""Configure the three publicly advertised accounts in this isolated demo only."""

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "services/api"))

from sqlalchemy import select

from uranium.audit import append_audit
from uranium.auth import password_hash, verify_password
from uranium.config import Settings
from uranium.db import make_engine, session_factory
from uranium.models import AuthSession, User

root = Path(__file__).resolve().parents[1]
settings = Settings()
settings.validate()
config = json.loads((root / "config/demo-accounts.json").read_text(encoding="utf-8"))
allowed = {"admin.a@demo.uranium.test", "officer.a@demo.uranium.test", "platform@demo.uranium.test"}
if {a["email"] for a in config["accounts"]} != allowed:
    raise RuntimeError("Only the three advertised demonstration accounts may be configured.")

with session_factory(make_engine(settings.database_url))() as db:
    for account in config["accounts"]:
        user = db.scalar(select(User).where(User.email == account["email"]))
        if not user:
            raise RuntimeError("Run the normal sample-data setup before configuring sample sign-in.")
        if not verify_password(config["password"], user.password_hash):
            user.password_hash = password_hash(config["password"])
            for session in db.scalars(select(AuthSession).where(AuthSession.user_id == user.id)):
                session.revoked_at = int(time.time())
            append_audit(db, None, "PUBLIC_DEMO_CREDENTIAL_CONFIGURED", user.id, "demo-account-setup")
    db.commit()
print(
    "The three advertised sample accounts are ready. Existing roles, assignments and records are preserved."
)
