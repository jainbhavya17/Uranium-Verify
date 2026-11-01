from datetime import date
from typing import Literal
from urllib.parse import urlsplit

from fastapi import Depends, HTTPException, Request
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import update

from .audit import append_audit
from .models import PortalContent


class Notice(BaseModel):
    id: str = Field(min_length=1, max_length=64)
    title: str = Field(min_length=3, max_length=180)
    summary: str = Field(min_length=3, max_length=400)
    body: str = Field(min_length=3, max_length=12000)
    category: Literal["Guidance", "Updates", "Maintenance"]
    status: Literal["Draft", "Published", "Archived"]
    publishedOn: date
    pinned: bool = False
    link: str = Field(default="", max_length=2048)

    @field_validator("link")
    @classmethod
    def safe_link(cls, value):
        if not value:
            return value
        parsed = urlsplit(value)
        if "\\" in value or any(ord(c) < 32 for c in value):
            raise ValueError("Unsafe link")
        if value.startswith("/") and not value.startswith("//"):
            return value
        if parsed.scheme == "https" and parsed.hostname and not parsed.username:
            return value
        raise ValueError("Use a local portal path or HTTPS URL")


class Announcement(BaseModel):
    enabled: bool = False
    text: str = Field(default="", max_length=240)
    link: str = Field(default="/notices", max_length=2048)
    _safe_link = field_validator("link")(Notice.safe_link.__func__)


class ContentUpdate(BaseModel):
    version: int = Field(ge=0)
    notices: list[Notice] = Field(max_length=100)
    announcement: Announcement


def install_portal_content(app, *, db_session, principal, require_roles, envelope):
    def read(db):
        row = db.get(PortalContent, "public")
        return (
            {"version": row.version, **row.payload}
            if row
            else {
                "version": 0,
                "notices": [],
                "announcement": {"enabled": False, "text": "", "link": "/notices"},
            }
        )

    @app.get("/api/v1/portal/content")
    def public_content(request: Request, db=Depends(db_session)):
        content = read(db)
        today = date.today().isoformat()
        content["notices"] = sorted(
            [n for n in content["notices"] if n["status"] == "Published" and n["publishedOn"] <= today],
            key=lambda n: (n["pinned"], n["publishedOn"]),
            reverse=True,
        )
        return envelope(request, content)

    @app.get("/api/v1/admin/portal/content")
    def admin_content(request: Request, p=Depends(principal), db=Depends(db_session)):
        require_roles(p, {"admin"})
        return envelope(request, read(db))

    @app.put("/api/v1/admin/portal/content")
    def save_content(body: ContentUpdate, request: Request, p=Depends(principal), db=Depends(db_session)):
        require_roles(p, {"admin"})
        if len({n.id for n in body.notices}) != len(body.notices):
            raise HTTPException(422, "Notice IDs must be unique.")
        payload = body.model_dump(mode="json", exclude={"version"})
        if body.version == 0:
            if db.get(PortalContent, "public"):
                raise HTTPException(409, "Notices changed. Reload before saving.")
            db.add(PortalContent(id="public", version=1, payload=payload))
        else:
            result = db.execute(
                update(PortalContent)
                .where(PortalContent.id == "public", PortalContent.version == body.version)
                .values(version=body.version + 1, payload=payload)
            )
            if result.rowcount != 1:
                raise HTTPException(409, "Notices changed. Reload before saving.")
        append_audit(
            db,
            p.user.id,
            "PORTAL_CONTENT_UPDATED",
            "public",
            request.state.request_id,
            {"version": body.version + 1, "notice_count": len(body.notices)},
        )
        db.commit()
        return envelope(request, read(db))
