"""Add isolated browser-check identities; never alter existing accounts."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "services/api"))
from sqlalchemy import select
from uranium.config import Settings
from uranium.db import make_engine, session_factory
from uranium.auth import password_hash
from uranium.models import User, Membership, Assignment
from uranium.seed import fixture_id

with session_factory(make_engine(Settings().database_url))() as db:
    for name, source in [("institution", "admin.a"), ("officer", "officer.a"), ("platform", "platform")]:
        email = f"qa.{name}@demo.uranium.test"
        if db.scalar(select(User).where(User.email == email)):
            continue
        original = db.scalar(select(User).where(User.email == source + "@demo.uranium.test"))
        user = User(
            id=fixture_id(email),
            email=email,
            name=f"Synthetic QA {name}",
            password_hash=password_hash("Test-fixtures-only-472!"),
        )
        db.add(user)
        db.flush()
        for m in db.scalars(select(Membership).where(Membership.user_id == original.id)):
            db.add(Membership(user_id=user.id, role_id=m.role_id, institution_id=m.institution_id))
        for a in db.scalars(select(Assignment).where(Assignment.user_id == original.id)):
            db.add(Assignment(user_id=user.id, application_id=a.application_id, scope=a.scope))
    db.commit()
print("Additive synthetic browser QA accounts ready. No existing credentials modified.")
