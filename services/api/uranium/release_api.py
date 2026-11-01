"""Clarification, account, in-app notification and immutable export contracts."""

import asyncio
import hashlib
import os
import secrets
import time
from pathlib import Path
from typing import Literal
from fastapi import Depends, Header, HTTPException, Query, Request
from fastapi.responses import Response
from pydantic import Field
from sqlalchemy import select, update, func
from .contracts import Envelope
from .institution_contracts import StrictModel
from .institution_service import idempotent
from .models import (
    Clarification,
    ClarificationScope,
    ClarificationResponse,
    ClarificationResolution,
    Application,
    Revision,
    Notification,
    AccountPreference,
    AuthSession,
    User,
    ReportRequest,
    ReportJob,
    ReportSnapshot,
    ReportPublication,
    RecoveryToken,
    LoginThrottle,
)
from .clarifications import (
    published,
    response_view,
    begin_response,
    save_response,
    submit_response,
    attach_response,
    touch_response,
)
from .auth import digest, password_hash, verify_password, review_case_ids
from .audit import append_audit
from .notifications import target_allowed, target_url
from .reports import report_view


class VersionBody(StrictModel):
    expected_version: int = Field(ge=1)


class ResponseSave(VersionBody):
    explanation: str = Field(max_length=2000)
    changes: dict[str, str] = Field(default_factory=dict, max_length=4)


class ResponseSubmit(VersionBody):
    declaration: Literal[True]


class ResolveRequest(VersionBody):
    rationale: str = Field(min_length=10, max_length=2000)


class PublishSummary(StrictModel):
    public_message: str = Field(min_length=10, max_length=2000)


class ProfileSave(VersionBody):
    name: str = Field(min_length=2, max_length=160)
    in_app: bool = True
    reduced_motion: bool = False
    high_contrast: bool = False


class PasswordChange(StrictModel):
    current_password: str = Field(min_length=1, max_length=200)
    password: str = Field(min_length=12, max_length=200)


class RecoveryRequest(StrictModel):
    email: str = Field(min_length=3, max_length=254)


class RecoveryConfirm(StrictModel):
    token: str = Field(min_length=30, max_length=200)
    password: str = Field(min_length=12, max_length=200)


def install_release_api(
    app, *, db_session, principal, envelope, require_case, require_roles, storage, settings
):
    def finish(db, request, data):
        db.commit()
        return envelope(request, data)

    def preference(db, p):
        row = db.get(AccountPreference, p.user.id)
        return {
            "version": row.version if row else 1,
            "in_app": row.in_app if row else True,
            "reduced_motion": row.reduced_motion if row else False,
            "high_contrast": row.high_contrast if row else False,
        }

    def response_write(p):
        require_roles(p, {"institution_admin", "institution_submitter"})

    def report_access(db, p, identifier, request):
        require_roles(p, {"officer", "supervisor", "admin", "auditor"})
        row = db.get(ReportRequest, identifier)
        revision = db.get(Revision, row.revision_id) if row else None
        if not row or not revision:
            raise HTTPException(404, "Report unavailable.")
        if not db.scalar(
            select(Application.id).where(
                Application.id == revision.application_id, Application.id.in_(review_case_ids(db, p))
            )
        ):
            append_audit(db, p.user.id, "REPORT_ACCESS_DENIED", identifier, request.state.request_id)
            db.commit()
            raise HTTPException(404, "Report unavailable in your review scope.")
        return row

    @app.get("/api/v1/clarifications", response_model=Envelope[list[dict]])
    def inbox(
        request: Request,
        page: int = Query(1, ge=1),
        state: Literal["all", "open", "submitted", "closed", "overdue"] = "all",
        p=Depends(principal),
        db=Depends(db_session),
    ):
        response_write(p)
        query = (
            select(Clarification)
            .join(Application)
            .where(Clarification.published.is_(True), Application.institution_id.in_(p.institution_ids))
        )
        closed = Clarification.id.in_(select(ClarificationResolution.request_id))
        responded = Clarification.id.in_(select(ClarificationResponse.request_id))
        if state == "closed":
            query = query.where(closed)
        elif state == "submitted":
            query = query.where(responded, ~closed)
        elif state == "overdue":
            query = query.where(~responded, ~closed, Clarification.allowed_until <= int(time.time()))
        elif state == "open":
            query = query.where(
                ~responded,
                ~closed,
                Clarification.allowed_until > int(time.time()),
                Application.status == "CLARIFICATION_REQUESTED",
                Clarification.id.in_(select(ClarificationScope.id)),
            )
        total = db.scalar(select(func.count()).select_from(query.subquery()))
        items = db.scalars(
            query.order_by(Clarification.created_at.desc(), Clarification.id)
            .offset((page - 1) * 20)
            .limit(20)
        ).all()
        return envelope(
            request,
            [response_view(db, c, db.get(Application, c.application_id)) for c in items],
            page=page,
            total=total,
        )

    @app.get("/api/v1/clarifications/{identifier}", response_model=Envelope[dict])
    def detail(identifier: str, request: Request, p=Depends(principal), db=Depends(db_session)):
        row, case = published(db, p, identifier)
        return envelope(request, response_view(db, row, case))

    @app.post("/api/v1/clarifications/{identifier}/draft", response_model=Envelope[dict])
    def begin(identifier: str, request: Request, p=Depends(principal), db=Depends(db_session)):
        response_write(p)
        row, case = published(db, p, identifier)
        return finish(db, request, begin_response(db, p, row, case, request.state.request_id))

    @app.patch("/api/v1/clarifications/{identifier}/draft", response_model=Envelope[dict])
    def save(
        identifier: str,
        body: ResponseSave,
        request: Request,
        idempotency_key: str | None = Header(None),
        p=Depends(principal),
        db=Depends(db_session),
    ):
        response_write(p)
        row, case = published(db, p, identifier)
        result = idempotent(
            db,
            p,
            "RESPONSE_SAVE:" + identifier,
            idempotency_key,
            body.model_dump(),
            lambda _: save_response(db, p, row, case, body, request.state.request_id),
        )
        return envelope(request, result)

    @app.post("/api/v1/clarifications/{identifier}/responses", response_model=Envelope[dict])
    def submit(
        identifier: str,
        body: ResponseSubmit,
        request: Request,
        idempotency_key: str | None = Header(None),
        p=Depends(principal),
        db=Depends(db_session),
    ):
        require_roles(p, {"institution_admin"})
        row, case = published(db, p, identifier)
        return envelope(
            request,
            idempotent(
                db,
                p,
                "RESPONSE_SUBMIT:" + identifier,
                idempotency_key,
                body.model_dump(),
                lambda _: submit_response(db, p, row, case, body, request.state.request_id),
            ),
        )

    @app.post("/api/v1/clarifications/{identifier}/documents/upload", response_model=Envelope[dict])
    async def upload(
        identifier: str,
        request: Request,
        expected_version: int = Query(ge=1),
        document_type: str = Query(max_length=64),
        filename: str = Query(max_length=200),
        idempotency_key: str | None = Header(None),
        p=Depends(principal),
        db=Depends(db_session),
    ):
        response_write(p)
        row, case = published(db, p, identifier)
        from .clarifications import open_window

        scope = open_window(db, row, case)
        if document_type not in scope.document_types:
            raise HTTPException(422, "Document type is outside the correction scope.")
        policy = app.state.processing_policy
        limit = policy.pdf_bytes if filename.lower().endswith(".pdf") else policy.image_bytes
        content = bytearray()
        try:
            async with asyncio.timeout(60):
                async for chunk in request.stream():
                    if len(content) + len(chunk) > limit:
                        raise HTTPException(413, "File exceeds the engineering byte limit.")
                    content.extend(chunk)
        except TimeoutError:
            raise HTTPException(408, "Upload timed out. Retry with a stable connection.")
        from .processing import inspect_transport

        clean, mime = inspect_transport(content, filename, request.headers.get("content-type", ""), policy)
        payload = {
            "expected_version": expected_version,
            "document_type": document_type,
            "sha256": hashlib.sha256(content).hexdigest(),
            "filename": clean,
        }
        result = idempotent(
            db,
            p,
            "RESPONSE_UPLOAD:" + identifier,
            idempotency_key,
            payload,
            lambda _: attach_response(
                db,
                p,
                row,
                case,
                expected_version,
                document_type,
                bytes(content),
                clean,
                mime,
                storage,
                request.state.request_id,
            ),
        )
        return envelope(request, result)

    @app.post(
        "/api/v1/clarifications/{identifier}/documents/{version_id}/retry", response_model=Envelope[dict]
    )
    def retry_upload(
        identifier: str,
        version_id: str,
        body: VersionBody,
        request: Request,
        idempotency_key: str | None = Header(None),
        p=Depends(principal),
        db=Depends(db_session),
    ):
        response_write(p)
        row, case = published(db, p, identifier)

        def execute(_):
            _, draft = touch_response(db, row, case, body.expected_version)
            from .models import DocumentVersion
            from .processing import enqueue

            version = db.get(DocumentVersion, version_id)
            if not version or version.revision_id != draft.revision_id:
                raise HTTPException(404, "Response evidence unavailable.")
            job = enqueue(db, version, True)
            append_audit(db, p.user.id, "RESPONSE_EVIDENCE_RETRY", version.id, request.state.request_id)
            return {"job_id": job.id, "response_version": draft.version, "state": job.state}

        return envelope(
            request,
            idempotent(
                db,
                p,
                "RESPONSE_RETRY:" + identifier,
                idempotency_key,
                {"version_id": version_id, **body.model_dump()},
                execute,
            ),
        )

    @app.get("/api/v1/officer/cases/{case_id}/clarifications", response_model=Envelope[list[dict]])
    def officer_requests(case_id: str, request: Request, p=Depends(principal), db=Depends(db_session)):
        from .officer_service import officer_case

        case = officer_case(db, p, case_id, "review")
        return envelope(
            request,
            [
                response_view(db, r, case)
                for r in db.scalars(
                    select(Clarification)
                    .where(Clarification.application_id == case.id, Clarification.published.is_(True))
                    .order_by(Clarification.created_at, Clarification.id)
                )
            ],
        )

    @app.post("/api/v1/officer/clarifications/{identifier}/resolve", response_model=Envelope[dict])
    def resolve(
        identifier: str,
        body: ResolveRequest,
        request: Request,
        idempotency_key: str | None = Header(None),
        p=Depends(principal),
        db=Depends(db_session),
    ):
        from .officer_service import officer_case, touch_review, action

        row = db.get(Clarification, identifier)
        if not row:
            raise HTTPException(404, "Clarification unavailable.")
        case = officer_case(db, p, row.application_id, "review", True)

        def execute(_):
            response = db.scalar(
                select(ClarificationResponse).where(ClarificationResponse.request_id == row.id)
            )
            if not response:
                raise HTTPException(409, "An institution response is required before closure.")
            if db.scalar(
                select(ClarificationResolution.id).where(ClarificationResolution.request_id == row.id)
            ):
                raise HTTPException(409, "Clarification is already closed.")
            touch_review(db, case, body.expected_version)
            db.add(
                ClarificationResolution(
                    request_id=row.id, response_id=response.id, actor_id=p.user.id, rationale=body.rationale
                )
            )
            action(
                db,
                p,
                case,
                "CLARIFICATION_RESOLVED",
                body.rationale,
                request.state.request_id,
                {"request_id": row.id, "response_id": response.id},
            )
            return {"request_id": row.id, "closed": True}

        return envelope(
            request, idempotent(db, p, "RESOLVE:" + identifier, idempotency_key, body.model_dump(), execute)
        )

    @app.post("/api/v1/officer/clarifications/{identifier}/withdraw", response_model=Envelope[dict])
    def withdraw(
        identifier: str,
        body: ResolveRequest,
        request: Request,
        idempotency_key: str | None = Header(None),
        p=Depends(principal),
        db=Depends(db_session),
    ):
        from .officer_service import officer_case, touch_review, action

        row = db.get(Clarification, identifier)
        if not row:
            raise HTTPException(404, "Clarification unavailable.")
        case = officer_case(db, p, row.application_id, "review", True)

        def execute(_):
            if db.scalar(select(ClarificationResponse.id).where(ClarificationResponse.request_id == row.id)):
                raise HTTPException(409, "Review the submitted response instead of withdrawing it.")
            if db.scalar(
                select(ClarificationResolution.id).where(ClarificationResolution.request_id == row.id)
            ):
                raise HTTPException(409, "Request is already closed.")
            touch_review(db, case, body.expected_version)
            db.add(
                ClarificationResolution(
                    request_id=row.id, response_id=None, actor_id=p.user.id, rationale=body.rationale
                )
            )
            if case.status == "CLARIFICATION_REQUESTED":
                case.status = "UNDER_REVIEW"
            action(
                db,
                p,
                case,
                "CLARIFICATION_WITHDRAWN",
                body.rationale,
                request.state.request_id,
                {"request_id": row.id},
            )
            return {"request_id": row.id, "withdrawn": True}

        return envelope(
            request, idempotent(db, p, "WITHDRAW:" + identifier, idempotency_key, body.model_dump(), execute)
        )

    @app.get("/api/v1/notifications", response_model=Envelope[list[dict]])
    def notifications(
        request: Request,
        page: int = Query(1, ge=1),
        state: Literal["all", "unread", "read"] = "all",
        event_type: str = Query("", max_length=100),
        application_id: str = Query("", max_length=64),
        p=Depends(principal),
        db=Depends(db_session),
    ):
        query = select(Notification).where(Notification.user_id == p.user.id)
        if state == "unread":
            query = query.where(Notification.read_at.is_(None))
        if state == "read":
            query = query.where(Notification.read_at.is_not(None))
        # Query and current object authorization precede pagination of visible records.
        visible = [
            n
            for n in db.scalars(query.order_by(Notification.created_at.desc(), Notification.id))
            if target_allowed(db, p, n.target)
            and (not event_type or n.target.get("event_type") == event_type)
            and (not application_id or n.target.get("application_id") == application_id)
        ]
        return envelope(
            request,
            [
                {
                    "id": n.id,
                    "summary": n.summary,
                    "read_at": n.read_at,
                    "at": n.created_at,
                    "type": n.target.get("event_type"),
                    "application_id": n.target.get("application_id"),
                    "link": target_url(p, n.target),
                    "delivery": "IN_APP_DELIVERED",
                }
                for n in visible[(page - 1) * 20 : page * 20]
            ],
            page=page,
            total=len(visible),
        )

    @app.patch("/api/v1/notifications/read-all", response_model=Envelope[dict])
    def read_all(request: Request, p=Depends(principal), db=Depends(db_session)):
        db.execute(
            update(Notification)
            .where(Notification.user_id == p.user.id, Notification.read_at.is_(None))
            .values(read_at=int(time.time()))
        )
        return finish(db, request, {"read": True})

    @app.patch("/api/v1/notifications/{identifier}/read", response_model=Envelope[dict])
    def read_one(identifier: str, request: Request, p=Depends(principal), db=Depends(db_session)):
        n = db.get(Notification, identifier)
        if not n or n.user_id != p.user.id or not target_allowed(db, p, n.target):
            raise HTTPException(404, "Notification unavailable.")
        n.read_at = n.read_at or int(time.time())
        return finish(db, request, {"read": True})

    @app.get("/api/v1/me/preferences", response_model=Envelope[dict])
    def preferences(request: Request, p=Depends(principal), db=Depends(db_session)):
        return envelope(request, preference(db, p))

    @app.patch("/api/v1/me/profile", response_model=Envelope[dict])
    def profile(body: ProfileSave, request: Request, p=Depends(principal), db=Depends(db_session)):
        pref = db.get(AccountPreference, p.user.id)
        if not pref:
            pref = AccountPreference(id=p.user.id)
            db.add(pref)
            db.flush()
        changed = db.execute(
            update(AccountPreference)
            .where(AccountPreference.id == p.user.id, AccountPreference.version == body.expected_version)
            .values(
                version=body.expected_version + 1,
                in_app=body.in_app,
                reduced_motion=body.reduced_motion,
                high_contrast=body.high_contrast,
            )
        )
        if changed.rowcount != 1:
            raise HTTPException(409, "Account preferences changed. Reload before saving.")
        p.user.name = body.name
        append_audit(db, p.user.id, "PROFILE_PREFERENCES_CHANGED", p.user.id, request.state.request_id)
        return finish(db, request, preference(db, p))

    @app.get("/api/v1/me/sessions", response_model=Envelope[list[dict]])
    def sessions(request: Request, p=Depends(principal), db=Depends(db_session)):
        return envelope(
            request,
            [
                {
                    "id": s.id,
                    "created_at": s.created_at,
                    "expires_at": s.expires_at,
                    "current": s.id == p.session.id,
                }
                for s in db.scalars(
                    select(AuthSession)
                    .where(
                        AuthSession.user_id == p.user.id,
                        AuthSession.revoked_at.is_(None),
                        AuthSession.expires_at > int(time.time()),
                    )
                    .order_by(AuthSession.created_at.desc(), AuthSession.id)
                )
            ],
        )

    @app.delete("/api/v1/me/sessions/{identifier}", response_model=Envelope[dict])
    def revoke(identifier: str, request: Request, p=Depends(principal), db=Depends(db_session)):
        row = db.get(AuthSession, identifier)
        if not row or row.user_id != p.user.id:
            raise HTTPException(404, "Session unavailable.")
        row.revoked_at = int(time.time())
        append_audit(db, p.user.id, "OWN_SESSION_REVOKED", row.id, request.state.request_id)
        return finish(db, request, {"revoked": True, "current": row.id == p.session.id})

    @app.post("/api/v1/me/password", response_model=Envelope[dict])
    def password(body: PasswordChange, request: Request, p=Depends(principal), db=Depends(db_session)):
        if not verify_password(body.current_password, p.user.password_hash):
            raise HTTPException(403, "Current password is incorrect.")
        p.user.password_hash = password_hash(body.password)
        db.execute(
            update(AuthSession)
            .where(AuthSession.user_id == p.user.id, AuthSession.id != p.session.id)
            .values(revoked_at=int(time.time()))
        )
        append_audit(db, p.user.id, "PASSWORD_CHANGED", p.user.id, request.state.request_id)
        return finish(db, request, {"changed": True, "other_sessions_revoked": True})

    @app.post("/api/v1/auth/recovery", response_model=Envelope[dict])
    def recovery(body: RecoveryRequest, request: Request, db=Depends(db_session)):
        now = int(time.time())
        reference = secrets.token_hex(16)
        key = digest(
            "recovery:"
            + str(request.client.host if request.client else "")
            + ":"
            + body.email.strip().lower()
        )
        throttle = db.get(LoginThrottle, key)
        if not throttle or throttle.reset_at <= now:
            if throttle:
                throttle.attempts = 0
                throttle.reset_at = now + 900
            else:
                throttle = LoginThrottle(key=key, attempts=0, reset_at=now + 900)
                db.add(throttle)
        throttle.attempts += 1
        user = db.scalar(select(User).where(User.email == body.email.strip().lower(), User.active.is_(True)))
        if user and throttle.attempts <= 3:
            token = secrets.token_urlsafe(48)
            db.add(RecoveryToken(token_hash=digest(token), user_id=user.id, expires_at=now + 900))
            if (
                settings.environment == "development"
                and os.getenv("LOCAL_RECOVERY_PREVIEW", "false") == "true"
            ):
                root = Path("var/recovery-preview")
                root.mkdir(parents=True, exist_ok=True)
                file = root / (reference + ".txt")
                file.write_text(
                    "LOCAL DEMO ONLY - no email was sent. Expires in 15 minutes.\nhttp://127.0.0.1:5173/reset-password#token="
                    + token,
                    encoding="utf-8",
                )
                try:
                    file.chmod(0o600)
                except OSError:
                    pass
        append_audit(db, None, "RECOVERY_REQUESTED", "recovery", request.state.request_id)
        db.commit()
        return envelope(
            request,
            {
                "message": "If the account is eligible, recovery instructions are available through the configured recovery channel.",
                "reference": reference,
                "delivery": "EMAIL_SMS_UNCONFIGURED",
                "local_preview_enabled": settings.environment == "development"
                and os.getenv("LOCAL_RECOVERY_PREVIEW", "false") == "true",
            },
        )

    @app.post("/api/v1/auth/recovery/confirm", response_model=Envelope[dict])
    def confirm(body: RecoveryConfirm, request: Request, db=Depends(db_session)):
        row = db.scalar(select(RecoveryToken).where(RecoveryToken.token_hash == digest(body.token)))
        now = int(time.time())
        if not row or row.used_at or row.expires_at <= now:
            raise HTTPException(400, "Reset token is invalid or expired.")
        consumed = db.execute(
            update(RecoveryToken)
            .where(
                RecoveryToken.id == row.id, RecoveryToken.used_at.is_(None), RecoveryToken.expires_at > now
            )
            .values(used_at=now)
        )
        if consumed.rowcount != 1:
            raise HTTPException(400, "Reset token is invalid or expired.")
        user = db.get(User, row.user_id)
        if not user or not user.active:
            raise HTTPException(400, "Reset token is invalid or expired.")
        user.password_hash = password_hash(body.password)
        db.execute(update(AuthSession).where(AuthSession.user_id == user.id).values(revoked_at=now))
        db.execute(
            update(RecoveryToken)
            .where(RecoveryToken.user_id == user.id, RecoveryToken.used_at.is_(None))
            .values(used_at=now)
        )
        append_audit(db, user.id, "PASSWORD_RECOVERED", user.id, request.state.request_id)
        return finish(db, request, {"reset": True, "all_sessions_revoked": True})

    @app.get("/api/v1/reports", response_model=Envelope[list[dict]])
    def reports(request: Request, p=Depends(principal), db=Depends(db_session)):
        require_roles(p, {"officer", "supervisor", "admin", "auditor"})
        revisions = select(Revision.id).where(Revision.application_id.in_(review_case_ids(db, p)))
        return envelope(
            request,
            [
                report_view(db, r)
                for r in db.scalars(
                    select(ReportRequest)
                    .where(ReportRequest.revision_id.in_(revisions))
                    .order_by(ReportRequest.created_at.desc(), ReportRequest.id)
                )
            ],
        )

    @app.post("/api/v1/reports/{identifier}/publish-summary", response_model=Envelope[dict])
    def publish_summary(
        identifier: str,
        body: PublishSummary,
        request: Request,
        idempotency_key: str | None = Header(None),
        p=Depends(principal),
        db=Depends(db_session),
    ):
        from .models import ReviewState, OutboxEvent
        from .reports import render_report
        from .officer_service import officer_case

        require_roles(p, {"officer", "supervisor"})
        row = report_access(db, p, identifier, request)
        officer_case(db, p, db.get(Revision, row.revision_id).application_id, "review", True)

        def execute(_):
            job = db.get(ReportJob, row.id)
            snapshot = db.get(ReportSnapshot, job.snapshot_id) if job and job.snapshot_id else None
            if not snapshot or report_view(db, row)["stale"]:
                raise HTTPException(
                    409, "Publish only a ready current snapshot; generate a new report when inputs changed."
                )
            if db.scalar(select(ReportPublication.id).where(ReportPublication.snapshot_id == snapshot.id)):
                raise HTTPException(409, "This snapshot already has an immutable published summary.")
            revision = db.get(Revision, snapshot.revision_id)
            locked = db.execute(
                update(ReviewState)
                .where(ReviewState.id == revision.application_id, ReviewState.version == job.input_version)
                .values(version=job.input_version)
            )
            if locked.rowcount != 1:
                raise HTTPException(409, "Review changed. Generate and inspect a current report.")
            keep = [
                "schema",
                "application_id",
                "revision_id",
                "revision_number",
                "captured_at",
                "review_version",
                "institution",
                "academic_year",
                "category",
                "status",
                "is_mock",
                "official_decision",
                "requested",
                "approved_history",
                "reviewer",
                "clarifications",
                "limitations",
            ]
            safe = {key: snapshot.manifest[key] for key in keep}
            safe.update(
                {
                    "rationale": body.public_message,
                    "machine_findings": [],
                    "rule_results": [],
                    "human_actions": [],
                    "evidence": [],
                    "visibility": "INSTITUTION_PUBLISHED_SUMMARY",
                }
            )
            safe["limitations"] = [
                *safe["limitations"],
                "Institution-published summary. Private forensic results, internal prioritization and private officer actions are excluded. An absent result here does not mean a check passed.",
            ]
            content = render_report(safe, snapshot.version)
            key = secrets.token_hex(32)
            storage.write_once(key, content)
            publication = ReportPublication(
                snapshot_id=snapshot.id,
                actor_id=p.user.id,
                storage_key=key,
                manifest={**safe, "pdf_sha256": hashlib.sha256(content).hexdigest()},
            )
            db.add(publication)
            db.flush()
            db.add(
                OutboxEvent(
                    deduplication_key="summary:" + publication.id,
                    event_type="REPORT_SUMMARY_PUBLISHED",
                    payload={"application_id": revision.application_id, "report_id": publication.id},
                )
            )
            append_audit(
                db,
                p.user.id,
                "REPORT_SUMMARY_PUBLISHED",
                publication.id,
                request.state.request_id,
                {"source_snapshot_id": snapshot.id},
            )
            return {"id": publication.id, "published": True}

        return envelope(
            request,
            idempotent(db, p, "PUBLISH_SUMMARY:" + identifier, idempotency_key, body.model_dump(), execute),
        )

    @app.get("/api/v1/applications/{case_id}/published-reports", response_model=Envelope[list[dict]])
    def public_reports(case_id: str, request: Request, p=Depends(principal), db=Depends(db_session)):
        require_roles(p, {"institution_admin", "institution_submitter"})
        case = require_case(db, p, case_id, request)
        if case.institution_id not in p.institution_ids:
            raise HTTPException(404, "Report unavailable.")
        revisions = select(Revision.id).where(Revision.application_id == case.id)
        snapshots = select(ReportSnapshot.id).where(ReportSnapshot.revision_id.in_(revisions))
        return envelope(
            request,
            [
                {
                    "id": pub.id,
                    "at": pub.created_at,
                    "is_mock": pub.manifest["is_mock"],
                    "revision_id": pub.manifest["revision_id"],
                    "sha256": pub.manifest["pdf_sha256"],
                    "message": pub.manifest["rationale"],
                    "download_url": f"/api/v1/applications/{case.id}/published-reports/{pub.id}/download",
                }
                for pub in db.scalars(
                    select(ReportPublication)
                    .where(ReportPublication.snapshot_id.in_(snapshots))
                    .order_by(ReportPublication.created_at.desc(), ReportPublication.id)
                )
            ],
        )

    @app.get("/api/v1/applications/{case_id}/published-reports/{identifier}/download")
    def public_download(
        case_id: str, identifier: str, request: Request, p=Depends(principal), db=Depends(db_session)
    ):
        require_roles(p, {"institution_admin", "institution_submitter"})
        case = require_case(db, p, case_id, request)
        row = db.get(ReportPublication, identifier)
        if (
            case.institution_id not in p.institution_ids
            or not row
            or row.manifest["application_id"] != case.id
        ):
            raise HTTPException(404, "Report unavailable.")
        content = storage.read(row.storage_key)
        if hashlib.sha256(content).hexdigest() != row.manifest["pdf_sha256"]:
            raise HTTPException(409, "Published report integrity check failed.")
        append_audit(db, p.user.id, "PUBLISHED_REPORT_EXPORTED", row.id, request.state.request_id)
        db.commit()
        return Response(
            content,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="URANIUM-published-summary-{row.id}.pdf"'},
        )

    @app.get("/api/v1/reports/{identifier}/download")
    def download(identifier: str, request: Request, p=Depends(principal), db=Depends(db_session)):
        row = report_access(db, p, identifier, request)
        job = db.get(ReportJob, row.id)
        snapshot = db.get(ReportSnapshot, job.snapshot_id) if job and job.snapshot_id else None
        if not snapshot:
            raise HTTPException(409, "Report is not ready. Check the worker state.")
        content = storage.read(snapshot.storage_key)
        if hashlib.sha256(content).hexdigest() != snapshot.manifest.get("pdf_sha256"):
            raise HTTPException(409, "Report integrity check failed.")
        append_audit(
            db,
            p.user.id,
            "REPORT_EXPORTED",
            snapshot.id,
            request.state.request_id,
            {
                "sha256": snapshot.manifest["pdf_sha256"],
                "version": snapshot.version,
                "stale": report_view(db, row)["stale"],
            },
        )
        db.commit()
        return Response(
            content,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="URANIUM-review-{row.id}-v{snapshot.version}.pdf"'
            },
        )

    @app.post("/api/v1/reports/{identifier}/retry", response_model=Envelope[dict])
    def retry_report(identifier: str, request: Request, p=Depends(principal), db=Depends(db_session)):
        require_roles(p, {"officer", "supervisor"})
        row = report_access(db, p, identifier, request)
        from .officer_service import officer_case

        officer_case(db, p, db.get(Revision, row.revision_id).application_id, "review", True)
        job = db.get(ReportJob, row.id)
        if not job or job.snapshot_id or row.state != "FAILED" or job.attempt >= 3:
            raise HTTPException(
                409, "Report is not eligible for a bounded retry. Request a new snapshot if inputs changed."
            )
        row.state = "PENDING_GENERATION"
        job.lease_until = 0
        append_audit(db, p.user.id, "REPORT_RETRY", row.id, request.state.request_id)
        return finish(db, request, report_view(db, row))
