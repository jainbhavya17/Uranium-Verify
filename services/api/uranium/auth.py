import hashlib
import hmac
import secrets
import time
from dataclasses import dataclass
from typing import Protocol

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Assignment, AuthSession, ContentGrant, Membership, User

ROLES = {
    "institution_submitter": "Institution submitter",
    "institution_admin": "Institution administrator",
    "officer": "Scrutiny officer",
    "specialist": "Verification specialist",
    "supervisor": "Supervisor",
    "admin": "Platform / rule administrator",
    "auditor": "Read-only auditor",
}


def digest(value: str):
    return hashlib.sha256(value.encode()).hexdigest()


def password_hash(password: str, salt: str | None = None):
    salt = salt or secrets.token_hex(16)
    result = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 310_000).hex()
    return f"pbkdf2_sha256${salt}${result}"


def verify_password(password: str, encoded: str):
    try:
        _, salt, _ = encoded.split("$")
        return hmac.compare_digest(password_hash(password, salt), encoded)
    except ValueError:
        return False


class IdentityAdapter(Protocol):
    def authenticate(self, db: Session, email: str, password: str) -> User | None: ...


DUMMY_PASSWORD_HASH = password_hash("unusable", "dummy-fixed-salt")


class DemoIdentityAdapter:
    """Development only. Role/membership are resolved from DB on EVERY request."""

    def authenticate(self, db: Session, email: str, password: str):
        user = db.scalar(select(User).where(User.email == email.lower().strip(), User.active.is_(True)))
        encoded = user.password_hash if user else DUMMY_PASSWORD_HASH
        valid = verify_password(password, encoded)
        return user if valid else None


@dataclass
class Principal:
    user: User
    session: AuthSession
    roles: set[str]
    institution_ids: set[str]

    @property
    def landing(self):
        if self.roles & {"institution_submitter", "institution_admin"}:
            return "/institution/dashboard"
        if self.roles & {"officer", "supervisor"}:
            return "/officer/dashboard"
        if "specialist" in self.roles:
            return "/officer/verifications"
        if "admin" in self.roles:
            return "/admin/users-roles"
        return "/admin/audit"


def resolve_principal(db, token):
    session = db.scalar(select(AuthSession).where(AuthSession.token_hash == digest(token or "")))
    now = int(time.time())
    if not session or session.revoked_at or session.expires_at <= now:
        raise HTTPException(401, "Session missing or expired. Please sign in.")
    user = db.get(User, session.user_id)
    if not user or not user.active:
        raise HTTPException(401, "Session missing or expired. Please sign in.")
    memberships = db.scalars(
        select(Membership).where(
            Membership.user_id == user.id,
            (Membership.valid_until.is_(None)) | (Membership.valid_until > now),
        )
    ).all()
    return Principal(
        user,
        session,
        {m.role_id for m in memberships},
        {
            m.institution_id
            for m in memberships
            if m.institution_id and m.role_id in {"institution_admin", "institution_submitter"}
        },
    )


def allowed_case_ids(db, p: Principal, scope="read"):
    from .models import Application

    if p.roles & {"institution_submitter", "institution_admin"}:
        return select(Application.id).where(Application.institution_id.in_(p.institution_ids))
    allowed_scopes = []
    if "officer" in p.roles:
        allowed_scopes.append("REVIEW")
    if "supervisor" in p.roles:
        allowed_scopes.append("SUPERVISE")
    if "specialist" in p.roles and scope in {"read", "evidence", "authenticity", "inspection"}:
        allowed_scopes.append("VERIFY")
    assignments = select(Assignment.application_id).where(
        Assignment.user_id == p.user.id, Assignment.active.is_(True), Assignment.scope.in_(allowed_scopes)
    )
    grants = select(ContentGrant.application_id).where(
        ContentGrant.user_id == p.user.id, ContentGrant.expires_at > int(time.time())
    )
    if "supervisor" in p.roles:
        jurisdictions = select(Membership.institution_id).where(
            Membership.user_id == p.user.id,
            Membership.role_id == "supervisor",
            Membership.institution_id.is_not(None),
            (Membership.valid_until.is_(None)) | (Membership.valid_until > int(time.time())),
        )
        return assignments.union(
            grants, select(Application.id).where(Application.institution_id.in_(jurisdictions))
        )
    return assignments.union(grants)


def review_case_ids(db, p: Principal):
    """Officer report authority never derives from an institution membership."""
    from .models import Application

    scopes = []
    if "officer" in p.roles:
        scopes.append("REVIEW")
    if "supervisor" in p.roles:
        scopes.append("SUPERVISE")
    assigned = select(Assignment.application_id).where(
        Assignment.user_id == p.user.id, Assignment.active.is_(True), Assignment.scope.in_(scopes)
    )
    grants = select(ContentGrant.application_id).where(
        ContentGrant.user_id == p.user.id, ContentGrant.expires_at > int(time.time())
    )
    if "supervisor" in p.roles:
        jurisdictions = select(Membership.institution_id).where(
            Membership.user_id == p.user.id,
            Membership.role_id == "supervisor",
            Membership.institution_id.is_not(None),
            (Membership.valid_until.is_(None)) | (Membership.valid_until > int(time.time())),
        )
        return assigned.union(
            grants, select(Application.id).where(Application.institution_id.in_(jurisdictions))
        )
    return assigned.union(grants)
