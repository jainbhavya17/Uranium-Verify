import hashlib
import json
import time
from typing import Callable

from fastapi import Depends, Header, HTTPException, Query, Request, Response
from sqlalchemy import func, select

from .auth import allowed_case_ids
from .contracts import Envelope
from .institution_contracts import (
    AttachmentView,
    CatalogueView,
    ChecklistView,
    CreateDraft,
    DraftView,
    FixtureAttachment,
    ReadinessView,
    ReceiptView,
    SaveDraft,
    SnapshotView,
    SubmitDraft,
)
from .institution_service import (
    QUARANTINE,
    TRUSTED_FIXTURE,
    attach_workflow,
    catalogue_view,
    changes_for,
    checklist_view,
    create_workflow,
    historical_rows,
    idempotent,
    save_workflow,
    snapshot_view,
    state_view,
    submit_workflow,
    synthetic_pdf,
    workflow_draft,
)
from .models import (
    Application,
    ApplicationCatalogue,
    ApplicationDraft,
    ApplicationTimeline,
    ApprovalSnapshot,
    SubmissionReceipt,
)


def install_institution_api(
    app,
    *,
    db_session: Callable,
    principal: Callable,
    require_case: Callable,
    require_roles: Callable,
    envelope: Callable,
    case_view: Callable,
    storage,
):
    def institution_read(db, p, identifier):
        accessible = db.scalar(
            select(Application.id)
            .where(Application.institution_id == identifier, Application.id.in_(allowed_case_ids(db, p)))
            .limit(1)
        )
        if identifier not in p.institution_ids and not accessible:
            raise HTTPException(404, "Record unavailable in your authorized scope.")

    def institution_write(db, p, identifier, final=False):
        require_roles(p, {"institution_admin"} if final else {"institution_admin", "institution_submitter"})
        if identifier not in p.institution_ids:
            raise HTTPException(404, "Record unavailable in your authorized scope.")
        from .models import Membership

        allowed = {"institution_admin"} if final else {"institution_admin", "institution_submitter"}
        if not db.scalar(
            select(Membership.id)
            .where(
                Membership.user_id == p.user.id,
                Membership.institution_id == identifier,
                Membership.role_id.in_(allowed),
                ((Membership.valid_until.is_(None)) | (Membership.valid_until > int(time.time()))),
            )
            .limit(1)
        ):
            raise HTTPException(403, "This action requires the appropriate role in this institution.")

    @app.get("/api/v1/catalog/applications", response_model=Envelope[list[CatalogueView]])
    def catalogue(
        request: Request,
        year: str | None = Query(None, max_length=16),
        p=Depends(principal),
        db=Depends(db_session),
    ):
        require_roles(p, {"institution_admin", "institution_submitter"})
        query = select(ApplicationCatalogue)
        if year:
            query = query.where(ApplicationCatalogue.academic_year == year)
        rows = db.scalars(
            query.order_by(ApplicationCatalogue.academic_year.desc(), ApplicationCatalogue.code)
        ).all()
        return envelope(request, [catalogue_view(db, item) for item in rows])

    @app.post("/api/v1/applications", response_model=Envelope[DraftView])
    def create(
        body: CreateDraft,
        request: Request,
        idempotency_key: str | None = Header(None),
        p=Depends(principal),
        db=Depends(db_session),
    ):
        institution_write(db, p, body.institution_id)
        result = idempotent(
            db,
            p,
            "CREATE_DRAFT",
            idempotency_key,
            body.model_dump(),
            lambda _: create_workflow(db, p, body, request.state.request_id),
        )
        return envelope(request, result)

    @app.get("/api/v1/applications/{case_id}/state", response_model=Envelope[DraftView])
    def state(case_id: str, request: Request, p=Depends(principal), db=Depends(db_session)):
        return envelope(request, state_view(db, require_case(db, p, case_id, request), p))

    @app.patch("/api/v1/applications/{case_id}/draft", response_model=Envelope[DraftView])
    def save(
        case_id: str,
        body: SaveDraft,
        request: Request,
        idempotency_key: str | None = Header(None),
        p=Depends(principal),
        db=Depends(db_session),
    ):
        case = require_case(db, p, case_id, request)
        institution_write(db, p, case.institution_id)
        result = idempotent(
            db,
            p,
            f"SAVE:{case_id}",
            idempotency_key,
            body.model_dump(mode="json"),
            lambda _: save_workflow(db, p, case, body, request.state.request_id),
        )
        return envelope(request, result)

    @app.get("/api/v1/applications/{case_id}/requirements", response_model=Envelope[ChecklistView])
    def requirements(case_id: str, request: Request, p=Depends(principal), db=Depends(db_session)):
        case = require_case(db, p, case_id, request)
        return envelope(request, checklist_view(db, case, workflow_draft(db, case)))

    @app.get("/api/v1/applications/{case_id}/precheck", response_model=Envelope[ReadinessView])
    @app.post("/api/v1/applications/{case_id}/precheck", response_model=Envelope[ReadinessView])
    def precheck(case_id: str, request: Request, p=Depends(principal), db=Depends(db_session)):
        case = require_case(db, p, case_id, request)
        from .precheck import view_precheck

        if request.method == "POST":
            institution_write(db, p, case.institution_id)
        result = view_precheck(db, case, workflow_draft(db, case), save=request.method == "POST")
        db.commit()
        return envelope(request, result)

    @app.post("/api/v1/applications/{case_id}/documents/fixtures", response_model=Envelope[AttachmentView])
    def attach_fixture(
        case_id: str,
        body: FixtureAttachment,
        request: Request,
        idempotency_key: str | None = Header(None),
        p=Depends(principal),
        db=Depends(db_session),
    ):
        if app.state.environment != "test":
            raise HTTPException(404, "Use the original-document upload workflow.")
        case = require_case(db, p, case_id, request, "evidence")
        institution_write(db, p, case.institution_id)
        # A fixture key is validated against the saved slot before generating any bytes.
        from .models import ApplicationRequirement, RequirementSnapshot

        slot = db.get(RequirementSnapshot, body.requirement_id)
        requirement = db.get(ApplicationRequirement, body.requirement_id)
        draft = workflow_draft(db, case)
        if not slot or not slot.active or not requirement or requirement.revision_id != draft.revision_id:
            raise HTTPException(404, "Document slot unavailable in this draft revision.")
        if body.document_type not in slot.payload["acceptable_alternatives"]:
            raise HTTPException(422, "Choose an allowed controlled fixture for this document slot.")
        result = idempotent(
            db,
            p,
            f"ATTACH:{case_id}",
            idempotency_key,
            body.model_dump(),
            lambda _: attach_workflow(
                db,
                p,
                case,
                body.expected_version,
                body.requirement_id,
                body.document_type,
                synthetic_pdf(body.document_type),
                f"mock-{body.document_type.lower()}.pdf",
                True,
                storage,
                request.state.request_id,
            ),
        )
        return envelope(request, result)

    @app.post("/api/v1/applications/{case_id}/documents/quarantine", response_model=Envelope[AttachmentView])
    async def quarantine(
        case_id: str,
        request: Request,
        requirement_id: str = Query(max_length=64),
        document_type: str = Query(max_length=64),
        expected_version: int = Query(ge=1),
        filename: str = Query(max_length=200),
        idempotency_key: str | None = Header(None),
        p=Depends(principal),
        db=Depends(db_session),
    ):
        if app.state.environment != "test":
            raise HTTPException(404, "Use the original-document upload workflow.")
        case = require_case(db, p, case_id, request, "evidence")
        institution_write(db, p, case.institution_id)
        limit = 1024 * 1024
        content = bytearray()
        async for chunk in request.stream():
            content.extend(chunk)
            if len(content) > limit:
                raise HTTPException(
                    413, "Phase 2 quarantine transport limit is 1 MiB. No file parsing was performed."
                )
        if not content:
            raise HTTPException(422, "Choose a non-empty file to quarantine.")
        payload = {
            "expected_version": expected_version,
            "requirement_id": requirement_id,
            "document_type": document_type,
            "filename": filename,
            "sha256": hashlib.sha256(content).hexdigest(),
        }
        result = idempotent(
            db,
            p,
            f"QUARANTINE:{case_id}",
            idempotency_key,
            payload,
            lambda _: attach_workflow(
                db,
                p,
                case,
                expected_version,
                requirement_id,
                document_type,
                bytes(content),
                filename,
                False,
                storage,
                request.state.request_id,
            ),
        )
        assert result["status"] == QUARANTINE
        return envelope(request, result)

    @app.post("/api/v1/applications/{case_id}/submit", response_model=Envelope[ReceiptView])
    def submit(
        case_id: str,
        body: SubmitDraft,
        request: Request,
        idempotency_key: str | None = Header(None),
        p=Depends(principal),
        db=Depends(db_session),
    ):
        case = require_case(db, p, case_id, request)
        institution_write(db, p, case.institution_id, final=True)
        result = idempotent(
            db,
            p,
            f"SUBMIT:{case_id}",
            idempotency_key,
            body.model_dump(),
            lambda checksum: submit_workflow(db, p, case, body, checksum, request.state.request_id),
        )
        return envelope(request, result)

    @app.get("/api/v1/applications/{case_id}/receipt", response_model=Envelope[ReceiptView])
    def receipt(case_id: str, request: Request, p=Depends(principal), db=Depends(db_session)):
        require_case(db, p, case_id, request)
        row = db.scalar(select(SubmissionReceipt).where(SubmissionReceipt.application_id == case_id))
        if not row:
            raise HTTPException(404, "No Phase 2 submission acknowledgment exists for this case.")
        return envelope(request, row.payload)

    @app.get("/api/v1/applications/{case_id}/acknowledgment")
    def acknowledgment(case_id: str, request: Request, p=Depends(principal), db=Depends(db_session)):
        result = receipt(case_id, request, p, db)["data"]
        return Response(
            json.dumps(result, indent=2),
            media_type="application/json",
            headers={"Content-Disposition": f'attachment; filename="{result["acknowledgment"]}.json"'},
        )

    @app.get("/api/v1/applications/{case_id}/timeline", response_model=Envelope[list[dict]])
    def timeline(case_id: str, request: Request, p=Depends(principal), db=Depends(db_session)):
        case = require_case(db, p, case_id, request)
        rows = db.scalars(
            select(ApplicationTimeline)
            .where(ApplicationTimeline.application_id == case_id)
            .order_by(ApplicationTimeline.created_at, ApplicationTimeline.id)
        ).all()
        values = [
            {
                "id": row.id,
                "event_type": row.event_type,
                "summary": row.summary,
                "created_at": row.created_at,
                "payload": row.payload,
            }
            for row in rows
        ]
        if not rows:
            values = [
                {
                    "id": case.id,
                    "event_type": case.status,
                    "summary": "Legacy synthetic Phase 1 fixture; no Phase 2 acknowledgment was generated.",
                    "created_at": case.created_at,
                    "payload": {"is_mock": True},
                }
            ]
        return envelope(request, values)

    @app.get("/api/v1/institutions/{institution_id}/history/compare", response_model=Envelope[dict])
    def compare(
        institution_id: str,
        request: Request,
        left_id: str,
        right_id: str | None = None,
        application_id: str | None = None,
        p=Depends(principal),
        db=Depends(db_session),
    ):
        institution_read(db, p, institution_id)
        left = db.get(ApprovalSnapshot, left_id)
        if (
            not left
            or left.institution_id != institution_id
            or not snapshot_view(db, left)["baseline_eligible"]
        ):
            raise HTTPException(404, "Approved comparison record unavailable in this scope.")
        if bool(right_id) == bool(application_id):
            raise HTTPException(422, "Select exactly one other approved snapshot or application.")
        baseline = snapshot_view(db, left)
        if right_id:
            right = db.get(ApprovalSnapshot, right_id)
            if (
                not right
                or right.institution_id != institution_id
                or not snapshot_view(db, right)["baseline_eligible"]
            ):
                raise HTTPException(404, "Approved comparison record unavailable in this scope.")
            target = snapshot_view(db, right)
            profile = target["profile"]
            details = {
                "proposed_name": profile["name"],
                "proposed_address": profile.get("address"),
                "affiliation": profile.get("affiliation"),
                "courses": [
                    {"course": c["course"], "requested_intake": c["approved_intake"]}
                    for c in profile["courses"]
                ],
            }
            differences = changes_for(baseline["profile"], details)
            for item in differences:
                item["interpretation"] = "APPROVED_HISTORY_CHANGE"
            return envelope(request, {"left": baseline, "right": target, "changes": differences})
        case = require_case(db, p, application_id, request)
        if case.institution_id != institution_id:
            raise HTTPException(404, "Record unavailable in your authorized scope.")
        draft = workflow_draft(db, case)
        return envelope(
            request,
            {
                "left": baseline,
                "application_id": case.id,
                "changes": changes_for(baseline["profile"], draft.details),
            },
        )

    @app.get(
        "/api/v1/institutions/{institution_id}/history/{record_id}", response_model=Envelope[SnapshotView]
    )
    def history_detail(
        institution_id: str, record_id: str, request: Request, p=Depends(principal), db=Depends(db_session)
    ):
        institution_read(db, p, institution_id)
        row = next((r for r in historical_rows(db, institution_id) if r["id"] == record_id), None)
        if not row:
            raise HTTPException(404, "Record unavailable in your authorized scope.")
        return envelope(request, row)

    @app.get("/api/v1/institutions/{institution_id}/dashboard", response_model=Envelope[dict])
    def dashboard(institution_id: str, request: Request, p=Depends(principal), db=Depends(db_session)):
        institution_write(db, p, institution_id)
        counts = db.execute(
            select(Application.status, func.count())
            .where(Application.institution_id == institution_id)
            .group_by(Application.status)
        ).all()
        rows = db.scalars(
            select(Application)
            .outerjoin(ApplicationDraft, ApplicationDraft.id == Application.id)
            .where(Application.institution_id == institution_id)
            .order_by(
                func.coalesce(ApplicationDraft.updated_at, Application.created_at).desc(), Application.id
            )
            .limit(5)
        ).all()
        history = historical_rows(db, institution_id)
        return envelope(
            request,
            {
                "counts": dict(counts),
                "recent": [case_view(db, row) for row in rows],
                "latest_baseline": next((s for s in history if s["baseline_eligible"]), None),
                "is_mock": True,
            },
        )

    from .processing_api import install_processing_api

    install_processing_api(
        app,
        db_session=db_session,
        principal=principal,
        require_case=require_case,
        institution_write=institution_write,
        envelope=envelope,
        storage=storage,
    )
    return TRUSTED_FIXTURE
