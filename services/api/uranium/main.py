import hmac
import secrets
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, select, text
from sqlalchemy.exc import SQLAlchemyError
from starlette.exceptions import HTTPException as StarletteHTTPException

from .audit import append_audit
from .auth import DemoIdentityAdapter, Principal, allowed_case_ids, digest, resolve_principal
from .config import Settings
from .contracts import (
    ApplicationView,
    Envelope,
    EvidenceView,
    HealthView,
    InstitutionView,
    JobView,
    LoginRequest,
    PreviewView,
    UserView,
)
from .db import make_engine, session_factory
from .models import (
    Application,
    ApplicationDraft,
    ApprovalSnapshot,
    AuditEvent,
    AuthSession,
    Clarification,
    Connector,
    Document,
    DocumentVersion,
    Institution,
    LoginThrottle,
    PreviewTicket,
    User,
)
from .supabase_storage import storage_for_settings


def create_app(settings=None):
    settings = settings or Settings()
    settings.validate()
    engine = make_engine(settings.database_url)
    factory = session_factory(engine)
    storage = storage_for_settings(settings)
    from .processing_config import ProcessingPolicy

    policy = ProcessingPolicy()
    policy.validate(settings.environment)

    @asynccontextmanager
    async def lifespan(_):
        # Explicit worker CLI owns processing; API never starts hidden parsing tasks.
        yield
        engine.dispose()

    app = FastAPI(
        title="URANIUM VERIFY",
        version="0.5.0",
        lifespan=lifespan,
        openapi_url="/api/v1/openapi.json",
        docs_url="/api/v1/docs",
    )
    app.state.engine, app.state.session_factory, app.state.storage = engine, factory, storage
    app.state.environment = settings.environment
    app.state.processing_policy = policy

    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_allowed_origins),
        allow_credentials=True,
        allow_methods=["GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Accept", "Content-Type", "X-CSRF-Token", "Authorization"],
    )

    @app.get("/health", include_in_schema=False)
    def wake_health():
        # Public liveness/wake-up check. The existing /api/v1/health remains
        # the strict readiness check for Render; a DB outage must not restart
        # an otherwise running process merely because a pinger contacted it.
        try:
            with engine.begin() as connection:
                if engine.dialect.name == "postgresql":
                    connection.execute(text("SET LOCAL statement_timeout = '3000ms'"))
                connection.execute(text("SELECT 1"))
            return {"ok": True, "db": True}
        except Exception:
            return {"ok": True, "db": False}

    def envelope(request, data=None, error=None, **meta):
        return {
            "data": data,
            "meta": {
                "request_id": request.state.request_id,
                "processed_at": int(time.time()),
                "source_version": "phase-5",
                **meta,
            },
            "error": error,
        }

    @app.middleware("http")
    async def secure_headers(request, call_next):
        request.state.request_id = str(uuid.uuid4())
        response = await call_next(request)
        response.headers.update(
            {
                "X-Request-ID": request.state.request_id,
                "X-Content-Type-Options": "nosniff",
                "Cache-Control": "no-store",
                "Referrer-Policy": "no-referrer",
                "X-Frame-Options": "SAMEORIGIN",
            }
        )
        return response

    @app.exception_handler(StarletteHTTPException)
    async def http_error(request, exc):
        if exc.status_code in {401, 403}:
            # Route templates exclude ticket values, credentials and raw user-supplied IDs.
            route = request.scope.get("route")
            with factory() as audit_db:
                append_audit(
                    audit_db,
                    getattr(request.state, "actor_id", None),
                    "AUTHORIZATION_DENIED",
                    getattr(route, "path", "protected-route"),
                    request.state.request_id,
                )
                audit_db.commit()
        codes = {
            401: "SESSION_REQUIRED",
            403: "FORBIDDEN",
            404: "NOT_FOUND",
            429: "RATE_LIMITED",
            503: "SERVICE_UNAVAILABLE",
            409: "CONFLICT",
        }
        return JSONResponse(
            status_code=exc.status_code,
            content=envelope(
                request,
                error={
                    "code": codes.get(exc.status_code, "REQUEST_FAILED"),
                    "message": str(exc.detail),
                    "field_errors": {},
                    "retryable": exc.status_code in {429, 503},
                },
            ),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, exc):
        fields = {".".join(str(x) for x in e["loc"]): e["msg"] for e in exc.errors()}
        return JSONResponse(
            status_code=422,
            content=envelope(
                request,
                error={
                    "code": "VALIDATION_ERROR",
                    "message": "Check the highlighted fields.",
                    "field_errors": fields,
                    "retryable": False,
                },
            ),
        )

    @app.exception_handler(SQLAlchemyError)
    async def database_error(request, _):
        return JSONResponse(
            status_code=503,
            content=envelope(
                request,
                error={
                    "code": "DATABASE_UNAVAILABLE",
                    "message": "Database unavailable. Check migrations and connection.",
                    "field_errors": {},
                    "retryable": True,
                },
            ),
        )

    def db_session():
        with factory() as db:
            yield db

    def principal(request: Request, db=Depends(db_session)):
        p = resolve_principal(db, request.cookies.get("uv_session"))
        request.state.actor_id = p.user.id
        db.info.update(actor_id=p.user.id, request_id=request.state.request_id)
        if request.method not in {"GET", "HEAD", "OPTIONS"}:
            if not hmac.compare_digest(digest(request.headers.get("X-CSRF-Token", "")), p.session.csrf_hash):
                raise HTTPException(403, "Invalid request verification token.")
        return p

    def require_roles(p, roles):
        if not p.roles.intersection(roles):
            raise HTTPException(403, "This workspace is outside your role scope.")

    def require_case(db, p, case_id, request, scope="read"):
        case = db.scalar(
            select(Application).where(
                Application.id == case_id, Application.id.in_(allowed_case_ids(db, p, scope))
            )
        )
        if not case:
            append_audit(db, p.user.id, "ACCESS_DENIED", case_id, request.state.request_id)
            db.commit()
            raise HTTPException(404, "Record unavailable in your authorized scope.")
        return case

    def user_view(p, csrf=None):
        return UserView(
            id=p.user.id,
            email=p.user.email,
            name=p.user.name,
            roles=sorted(p.roles),
            institution_ids=sorted(p.institution_ids),
            landing=p.landing,
            expires_at=p.session.expires_at,
            csrf_token=csrf,
        ).model_dump()

    def case_view(db, case):
        institution = db.get(Institution, case.institution_id)
        draft = db.get(ApplicationDraft, case.id)
        return ApplicationView(
            id=case.id,
            institution_id=case.institution_id,
            institution_name=institution.name,
            category=case.category,
            academic_year=case.academic_year,
            status=case.status,
            is_mock=case.is_mock,
            version=draft.lock_version if draft else 1,
            updated_at=draft.updated_at if draft else case.created_at,
            catalogue_id=draft.catalogue_id if draft else None,
            revision_id=draft.revision_id if draft else None,
        ).model_dump()

    @app.get("/api/v1/health", response_model=Envelope[HealthView])
    def health(request: Request):
        try:
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))
                connection.execute(text("SELECT version_num FROM alembic_version"))
        except SQLAlchemyError:
            raise HTTPException(503, "Database unavailable or migration missing.")
        return envelope(
            request,
            HealthView(
                status="ok", database="ready", storage=getattr(storage, "adapter_name", "private-local")
            ).model_dump(),
        )

    @app.post("/api/v1/auth/session", response_model=Envelope[UserView])
    def login(body: LoginRequest, request: Request, response: Response, db=Depends(db_session)):
        now = int(time.time())
        throttle_key = digest(
            (request.client.host if request.client else "local") + body.email.lower().strip()
        )
        throttle = db.get(LoginThrottle, throttle_key)
        if throttle and throttle.reset_at > now and throttle.attempts >= 10:
            raise HTTPException(429, "Too many attempts. Try again later.")
        user = DemoIdentityAdapter().authenticate(db, body.email, body.password)
        if not user:
            if not throttle:
                throttle = LoginThrottle(key=throttle_key, attempts=0, reset_at=now + 300)
                db.add(throttle)
            if throttle.reset_at <= now:
                throttle.attempts, throttle.reset_at = 0, now + 300
            throttle.attempts += 1
            db.commit()
            raise HTTPException(401, "Invalid credentials.")
        if throttle:
            db.delete(throttle)
        old = db.scalar(
            select(AuthSession).where(AuthSession.token_hash == digest(request.cookies.get("uv_session", "")))
        )
        if old:
            old.revoked_at = now
        token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
        session = AuthSession(
            user_id=user.id,
            token_hash=digest(token),
            csrf_hash=digest(csrf),
            expires_at=now + settings.session_ttl,
        )
        db.add(session)
        append_audit(db, user.id, "LOGIN", user.id, request.state.request_id)
        db.commit()
        response.set_cookie(
            "uv_session",
            token,
            httponly=True,
            samesite="strict",
            secure=settings.cookie_secure,
            max_age=settings.session_ttl,
            path="/api/v1",
        )
        response.set_cookie(
            "uv_csrf",
            csrf,
            httponly=False,
            samesite="strict",
            secure=settings.cookie_secure,
            max_age=settings.session_ttl,
            path="/",
        )
        return envelope(request, user_view(resolve_principal(db, token), csrf))

    @app.get("/api/v1/me", response_model=Envelope[UserView])
    def me(request: Request, p: Principal = Depends(principal)):
        return envelope(request, user_view(p))

    @app.delete("/api/v1/auth/session", response_model=Envelope[dict])
    def logout(request: Request, response: Response, p=Depends(principal), db=Depends(db_session)):
        p.session.revoked_at = int(time.time())
        append_audit(db, p.user.id, "LOGOUT", p.user.id, request.state.request_id)
        db.commit()
        response.delete_cookie("uv_session", path="/api/v1")
        response.delete_cookie("uv_csrf", path="/")
        return envelope(request, {"revoked": True})

    @app.get("/api/v1/applications", response_model=Envelope[list[ApplicationView]])
    def applications(
        request: Request,
        page: int = Query(1, ge=1),
        page_size: int = Query(20, ge=1, le=100),
        search: str = Query("", max_length=200),
        year: str = Query("", max_length=16),
        category: str = Query("", max_length=64),
        status: str = Query("", max_length=40),
        p=Depends(principal),
        db=Depends(db_session),
    ):
        query = (
            select(Application)
            .join(Institution)
            .outerjoin(ApplicationDraft, ApplicationDraft.id == Application.id)
            .where(Application.id.in_(allowed_case_ids(db, p)))
        )
        if search:
            term = "%" + search.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
            query = query.where(
                Institution.name.ilike(term, escape="\\")
                | Application.id.ilike(term, escape="\\")
                | Application.category.ilike(term, escape="\\")
            )
        if year:
            query = query.where(Application.academic_year == year)
        if category:
            query = query.where(Application.category == category)
        if status:
            query = query.where(Application.status == status)
        total = db.scalar(select(func.count()).select_from(query.subquery()))
        items = db.scalars(
            query.order_by(
                func.coalesce(ApplicationDraft.updated_at, Application.created_at).desc(), Application.id
            )
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
        return envelope(
            request, [case_view(db, a) for a in items], page=page, page_size=page_size, total=total
        )

    @app.get("/api/v1/applications/{case_id}", response_model=Envelope[ApplicationView])
    def application(case_id: str, request: Request, p=Depends(principal), db=Depends(db_session)):
        return envelope(request, case_view(db, require_case(db, p, case_id, request)))

    @app.get("/api/v1/institutions", response_model=Envelope[list[InstitutionView]])
    def institutions(request: Request, p=Depends(principal), db=Depends(db_session)):
        ids = select(Application.institution_id).where(Application.id.in_(allowed_case_ids(db, p)))
        rows = db.scalars(
            select(Institution)
            .where((Institution.id.in_(p.institution_ids)) | (Institution.id.in_(ids)))
            .order_by(Institution.id)
        ).all()
        return envelope(
            request, [InstitutionView.model_validate(r, from_attributes=True).model_dump() for r in rows]
        )

    @app.get("/api/v1/institutions/{institution_id}/history", response_model=Envelope[list[dict]])
    def history(institution_id: str, request: Request, p=Depends(principal), db=Depends(db_session)):
        accessible = db.scalar(
            select(Application).where(
                Application.institution_id == institution_id, Application.id.in_(allowed_case_ids(db, p))
            )
        )
        if institution_id not in p.institution_ids and not accessible:
            raise HTTPException(404, "Record unavailable in your authorized scope.")
        from .institution_service import historical_rows

        return envelope(request, historical_rows(db, institution_id))

    def evidence_view(db, version):
        from .processing import latest_job

        result = EvidenceView.model_validate(version, from_attributes=True).model_dump()
        job = latest_job(db, version.id)
        if job:
            result["status"] = job.state
        return result

    @app.get("/api/v1/applications/{case_id}/documents", response_model=Envelope[list[EvidenceView]])
    def documents(case_id: str, request: Request, p=Depends(principal), db=Depends(db_session)):
        require_case(db, p, case_id, request, "evidence")
        rows = db.scalars(
            select(DocumentVersion)
            .where(DocumentVersion.application_id == case_id)
            .order_by(DocumentVersion.document_id, DocumentVersion.number)
        ).all()
        return envelope(request, [evidence_view(db, v) for v in rows])

    def authorized_version(document_id, number, request, p, db):
        doc = db.get(Document, document_id)
        require_case(db, p, doc.application_id if doc else "missing", request, "evidence")
        version = db.scalar(
            select(DocumentVersion).where(
                DocumentVersion.document_id == document_id, DocumentVersion.number == number
            )
        )
        if not version:
            raise HTTPException(404, "Record unavailable in your authorized scope.")
        return version

    @app.get("/api/v1/documents/{document_id}/versions/{number}", response_model=Envelope[EvidenceView])
    def evidence(
        document_id: str, number: int, request: Request, p=Depends(principal), db=Depends(db_session)
    ):
        return envelope(request, evidence_view(db, authorized_version(document_id, number, request, p, db)))

    @app.post(
        "/api/v1/documents/{document_id}/versions/{number}/preview", response_model=Envelope[PreviewView]
    )
    def preview(
        document_id: str, number: int, request: Request, p=Depends(principal), db=Depends(db_session)
    ):
        version = authorized_version(document_id, number, request, p, db)
        from .processing import previewable

        if not previewable(db, version):
            raise HTTPException(
                409, "This file is quarantined pending safety validation. Preview is unavailable."
            )
        token = secrets.token_urlsafe(32)
        expires = min(int(time.time()) + settings.preview_ttl, p.session.expires_at)
        db.add(
            PreviewTicket(
                token_hash=digest(token), session_id=p.session.id, version_id=version.id, expires_at=expires
            )
        )
        append_audit(db, p.user.id, "PREVIEW_ISSUED", version.id, request.state.request_id)
        db.commit()
        return envelope(request, {"url": f"/api/v1/evidence/preview/{token}", "expires_at": expires})

    @app.get("/api/v1/evidence/preview/{ticket}", responses={200: {"content": {"application/pdf": {}}}})
    def preview_content(ticket: str, request: Request, p=Depends(principal), db=Depends(db_session)):
        saved = db.scalar(
            select(PreviewTicket).where(
                PreviewTicket.token_hash == digest(ticket),
                PreviewTicket.session_id == p.session.id,
                PreviewTicket.expires_at > int(time.time()),
            )
        )
        if not saved:
            raise HTTPException(404, "Preview expired or unavailable.")
        version = db.get(DocumentVersion, saved.version_id)
        from .processing import previewable

        if not previewable(db, version):
            raise HTTPException(409, "This file is quarantined pending safety validation.")
        require_case(db, p, version.application_id, request, "evidence")
        try:
            content = storage.read(version.storage_key)
        except (FileNotFoundError, ValueError):
            raise HTTPException(404, "Evidence file unavailable.")
        append_audit(db, p.user.id, "PREVIEW_OPENED", version.id, request.state.request_id)
        db.commit()
        return Response(
            content,
            media_type=version.media_type,
            headers={
                "Content-Disposition": 'inline; filename="evidence"',
                "Content-Security-Policy": "sandbox",
            },
        )

    @app.get("/api/v1/shell/access", response_model=Envelope[dict])
    def shell_access(
        request: Request,
        space: str,
        section: str = "",
        case_id: str | None = None,
        record_id: str | None = None,
        request_id: str | None = None,
        p=Depends(principal),
        db=Depends(db_session),
    ):
        if space == "institution":
            require_roles(p, {"institution_admin", "institution_submitter"})
        elif space == "officer":
            require_roles(p, {"officer", "specialist", "supervisor", "auditor"})
            if "specialist" in p.roles and not p.roles.intersection({"officer", "supervisor"}):
                if section not in {"verifications", "evidence", "authenticity", "inspection"}:
                    raise HTTPException(403, "This page is outside the specialist task scope.")
            if "auditor" in p.roles and not p.roles.intersection({"officer", "supervisor", "specialist"}):
                if section != "reports":
                    raise HTTPException(403, "This page is outside the auditor scope.")
        elif space == "admin":
            require_roles(p, {"admin", "auditor"} if section == "audit" else {"admin"})
        elif space != "shared":
            raise HTTPException(404, "Unknown workspace.")
        if case_id:
            require_case(db, p, case_id, request, section)
        if record_id:
            snapshot = db.get(ApprovalSnapshot, record_id)
            if not snapshot or snapshot.institution_id not in p.institution_ids:
                raise HTTPException(404, "Record unavailable in your authorized scope.")
        if request_id:
            clarification = db.get(Clarification, request_id)
            if not clarification or not clarification.published:
                raise HTTPException(404, "Record unavailable in your authorized scope.")
            require_case(db, p, clarification.application_id, request)
        return envelope(request, {"allowed": True, "phase": 1})

    @app.get("/api/v1/admin/audit", response_model=Envelope[list[dict]])
    def audits(request: Request, page: int = Query(1, ge=1), p=Depends(principal), db=Depends(db_session)):
        require_roles(p, {"admin", "auditor"})
        rows = db.scalars(
            select(AuditEvent)
            .order_by(AuditEvent.created_at.desc(), AuditEvent.id)
            .offset((page - 1) * 20)
            .limit(20)
        ).all()
        total = db.scalar(select(func.count()).select_from(AuditEvent))
        return envelope(
            request,
            [
                {
                    "id": r.id,
                    "actor_id": r.actor_id,
                    "operation": r.operation,
                    "target_id": r.target_id,
                    "created_at": r.created_at,
                }
                for r in rows
            ],
            page=page,
            page_size=20,
            total=total,
        )

    @app.get("/api/v1/admin/users", response_model=Envelope[list[dict]])
    def users(request: Request, p=Depends(principal), db=Depends(db_session)):
        require_roles(p, {"admin"})
        return envelope(
            request,
            [
                {"id": r.id, "name": r.name, "email": r.email, "active": r.active}
                for r in db.scalars(select(User).order_by(User.email)).all()
            ],
        )

    @app.get("/api/v1/admin/integrations", response_model=Envelope[list[dict]])
    def connectors(request: Request, p=Depends(principal), db=Depends(db_session)):
        require_roles(p, {"admin"})
        return envelope(
            request,
            [
                {"id": r.id, "name": r.name, "mode": r.mode, "status": r.status}
                for r in db.scalars(select(Connector).order_by(Connector.id)).all()
            ],
        )

    @app.get("/api/v1/contracts/job-example", response_model=Envelope[JobView], include_in_schema=True)
    def job_contract(request: Request, p=Depends(principal)):
        raise HTTPException(
            503, "This schema example does not start jobs. Use the authorized document processing endpoints."
        )

    from .institution_api import install_institution_api

    install_institution_api(
        app,
        db_session=db_session,
        principal=principal,
        require_case=require_case,
        require_roles=require_roles,
        envelope=envelope,
        case_view=case_view,
        storage=storage,
    )
    from .officer_api import install_officer_api

    install_officer_api(
        app,
        db_session=db_session,
        principal=principal,
        envelope=envelope,
        case_view=case_view,
        require_roles=require_roles,
        storage=storage,
    )
    from .release_api import install_release_api

    install_release_api(
        app,
        db_session=db_session,
        principal=principal,
        envelope=envelope,
        require_case=require_case,
        require_roles=require_roles,
        storage=storage,
        settings=settings,
    )
    from .portal_content import install_portal_content

    install_portal_content(
        app, db_session=db_session, principal=principal, require_roles=require_roles, envelope=envelope
    )
    from .restored_portal import install_restored_portal

    install_restored_portal(
        app,
        db_session=db_session,
        principal=principal,
        require_case=require_case,
        require_roles=require_roles,
        envelope=envelope,
    )
    return app


app = create_app()
