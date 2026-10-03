"""Phase 8A internal pre-verification API (`/api/v1/calculations`): findings, calculation reports and internal verification readiness.
Internal only — no VVB/ACVA, validation or verification endpoint exists."""
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Response, UploadFile, status

from app.api.deps import DB, Ctx, read_upload, require, require_any
from app.schemas.lab import DocumentRef
from app.schemas.preverification import (
    FindingIn,
    FindingOut,
    ManifestOut,
    NotesIn,
    ReadinessCreateIn,
    ReadinessOut,
    ReadinessView,
    ReasonIn,
    ReportDetailOut,
    ReportOut,
    ReportVerifyOut,
    ResolveIn,
    RespondIn,
)
from app.security.permissions import P
from app.security.principal import Principal
from app.services import calculation_findings as cf
from app.services import calculation_readiness as cr
from app.services import calculation_report as crep
from app.services import calculation_service as cs
from app.services import document_service
from app.services import preverification_mappers as pvm

router = APIRouter(prefix="/calculations", tags=["calculations — internal pre-verification"])

Reader = Annotated[Principal, Depends(require(P.CALCULATION_READ))]
Manager = Annotated[Principal, Depends(require(P.CALCULATION_MANAGE))]
Reviewer = Annotated[Principal, Depends(require(P.CALCULATION_REVIEW))]
Approver = Annotated[Principal, Depends(require(P.CALCULATION_APPROVE))]
Contributor = Annotated[Principal, Depends(require_any(P.CALCULATION_MANAGE, P.CALCULATION_REVIEW))]


# ---------------------------------------------------------------- findings
@router.get("/findings", response_model=list[FindingOut])
def list_findings(principal: Reader, db: DB, project_id: uuid.UUID, monitoring_period_id: uuid.UUID | None = None,
                  run_id: uuid.UUID | None = None, finding_status: str | None = None) -> list[FindingOut]:
    return [pvm.finding_out(db, principal, f) for f in cf.findings(db, principal, project_id, monitoring_period_id, run_id, finding_status)]


@router.post("/runs/{run_id}/findings", response_model=FindingOut, status_code=status.HTTP_201_CREATED,
             summary="Raise an internal finding on a non-DRAFT run (QA)")
def raise_finding(run_id: uuid.UUID, body: FindingIn, principal: Reviewer, db: DB, ctx: Ctx) -> FindingOut:
    return pvm.finding_out(db, principal, cf.raise_finding(db, ctx, principal, run_id, body))


@router.get("/findings/{finding_id}", response_model=FindingOut)
def get_finding(finding_id: uuid.UUID, principal: Reader, db: DB) -> FindingOut:
    return pvm.finding_out(db, principal, cf.get_finding(db, principal, finding_id)[0])


@router.get("/findings/{finding_id}/history", response_model=FindingOut, summary="The finding with its append-only event history")
def finding_history(finding_id: uuid.UUID, principal: Reader, db: DB) -> FindingOut:
    return pvm.finding_out(db, principal, cf.get_finding(db, principal, finding_id)[0])


@router.post("/findings/{finding_id}/respond", response_model=FindingOut)
def respond(finding_id: uuid.UUID, body: RespondIn, principal: Manager, db: DB, ctx: Ctx) -> FindingOut:
    return pvm.finding_out(db, principal, cf.respond(db, ctx, principal, finding_id, body.response, body.document_id))


@router.post("/findings/{finding_id}/resolve", response_model=FindingOut)
def resolve(finding_id: uuid.UUID, body: ResolveIn, principal: Reviewer, db: DB, ctx: Ctx) -> FindingOut:
    return pvm.finding_out(db, principal, cf.resolve(db, ctx, principal, finding_id, body.note, body.resolved_by_run_id))


@router.post("/findings/{finding_id}/return", response_model=FindingOut, summary="Return a response (RESPONDED → OPEN)")
def return_response(finding_id: uuid.UUID, body: ReasonIn, principal: Reviewer, db: DB, ctx: Ctx) -> FindingOut:
    return pvm.finding_out(db, principal, cf.return_response(db, ctx, principal, finding_id, body.reason))


@router.post("/findings/{finding_id}/reopen", response_model=FindingOut)
def reopen(finding_id: uuid.UUID, body: ReasonIn, principal: Reviewer, db: DB, ctx: Ctx) -> FindingOut:
    return pvm.finding_out(db, principal, cf.reopen(db, ctx, principal, finding_id, body.reason))


@router.post("/findings/{finding_id}/withdraw", response_model=FindingOut)
def withdraw_finding(finding_id: uuid.UUID, body: ReasonIn, principal: Reviewer, db: DB, ctx: Ctx) -> FindingOut:
    return pvm.finding_out(db, principal, cf.withdraw(db, ctx, principal, finding_id, body.reason))


@router.post("/runs/{run_id}/evidence", response_model=DocumentRef, status_code=status.HTTP_201_CREATED,
             summary="Attach evidence (PDF / image) to a non-DRAFT run, for findings and responses")
def upload_evidence(run_id: uuid.UUID, principal: Contributor, db: DB, ctx: Ctx, file: Annotated[UploadFile, File()],
                    title: Annotated[str | None, Form(max_length=200)] = None) -> DocumentRef:
    d = cf.upload_evidence(db, ctx, principal, run_id, file.filename, read_upload(file), title)
    return DocumentRef(document_id=d.id, category=d.category, title=d.title, file_name=None, sha256=None, uploaded_at=d.created_at)


# ---------------------------------------------------------------- reports
@router.get("/runs/{run_id}/reports", response_model=list[ReportOut])
def list_reports(run_id: uuid.UUID, principal: Reader, db: DB) -> list[ReportOut]:
    run, _ = cs.get_run(db, principal, run_id)
    return [pvm.report_out(db, r) for r in crep.reports_of(db, run.id)]


@router.post("/runs/{run_id}/reports", response_model=ReportOut, status_code=status.HTTP_201_CREATED,
             summary="Generate the official report of an APPROVED run (synchronous, size-guarded)")
def generate_report(run_id: uuid.UUID, principal: Manager, db: DB, ctx: Ctx) -> ReportOut:
    return pvm.report_out(db, crep.generate(db, ctx, principal, run_id))


@router.get("/reports/{report_id}", response_model=ReportDetailOut)
def get_report(report_id: uuid.UUID, principal: Reader, db: DB) -> ReportOut:
    return pvm.report_out(db, crep.get_report(db, principal, report_id)[0], detail=True)


@router.get("/reports/{report_id}/pdf", summary="Download the report PDF (integrity-checked, audited)")
def report_pdf(report_id: uuid.UUID, principal: Reader, db: DB, ctx: Ctx) -> Response:
    rep, _ = crep.get_report(db, principal, report_id)
    _, data = document_service.download(db, ctx, principal, rep.document_id)
    return Response(content=data, media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="{rep.report_code}.pdf"'})


@router.get("/reports/{report_id}/verify", response_model=ReportVerifyOut, summary="Re-hash content and PDF; re-render; freshness")
def verify_report(report_id: uuid.UUID, principal: Reader, db: DB) -> ReportVerifyOut:
    return ReportVerifyOut(**crep.verify(db, crep.get_report(db, principal, report_id)[0]))


# ---------------------------------------------------------------- internal verification readiness (not verification)
@router.get("/projects/{project_id}/verification-readiness", response_model=ReadinessView,
            summary="Internal readiness of a monitoring period — not verification")
def readiness_view(project_id: uuid.UUID, principal: Reader, db: DB, ctx: Ctx, monitoring_period_id: uuid.UUID) -> ReadinessView:
    return pvm.view_out(db, principal, cr.view(db, ctx, principal, project_id, monitoring_period_id))


@router.post("/projects/{project_id}/verification-readiness", response_model=ReadinessOut, status_code=status.HTTP_201_CREATED)
def create_readiness(project_id: uuid.UUID, body: ReadinessCreateIn, principal: Manager, db: DB, ctx: Ctx) -> ReadinessOut:
    return pvm.readiness_out(db, principal, cr.create(db, ctx, principal, project_id, body.monitoring_period_id))


@router.get("/readiness/{review_id}", response_model=ReadinessOut)
def get_readiness(review_id: uuid.UUID, principal: Reader, db: DB, ctx: Ctx) -> ReadinessOut:
    r, _ = cr.get_review(db, principal, review_id)
    cr.refresh(db, ctx, r.monitoring_period_id)
    return pvm.readiness_out(db, principal, cr.get_review(db, principal, review_id)[0])


@router.get("/readiness/{review_id}/package", response_model=ManifestOut, summary="The frozen package manifest (references and hashes)")
def readiness_package(review_id: uuid.UUID, principal: Reader, db: DB, ctx: Ctx) -> ManifestOut:
    r, _ = cr.get_review(db, principal, review_id)
    cr.refresh(db, ctx, r.monitoring_period_id)
    return pvm.manifest_out(cr.get_review(db, principal, review_id)[0])


@router.post("/readiness/{review_id}/submit", response_model=ReadinessOut)
def submit_readiness(review_id: uuid.UUID, principal: Manager, db: DB, ctx: Ctx) -> ReadinessOut:
    return pvm.readiness_out(db, principal, cr.submit(db, ctx, principal, review_id))


@router.post("/readiness/{review_id}/approve", response_model=ReadinessOut)
def approve_readiness(review_id: uuid.UUID, body: NotesIn, principal: Approver, db: DB, ctx: Ctx) -> ReadinessOut:
    return pvm.readiness_out(db, principal, cr.approve(db, ctx, principal, review_id, body.notes))


@router.post("/readiness/{review_id}/reject", response_model=ReadinessOut)
def reject_readiness(review_id: uuid.UUID, body: NotesIn, principal: Approver, db: DB, ctx: Ctx) -> ReadinessOut:
    return pvm.readiness_out(db, principal, cr.reject(db, ctx, principal, review_id, body.notes))


@router.post("/readiness/{review_id}/withdraw", response_model=ReadinessOut)
def withdraw_readiness(review_id: uuid.UUID, body: ReasonIn, principal: Manager, db: DB, ctx: Ctx) -> ReadinessOut:
    return pvm.readiness_out(db, principal, cr.withdraw(db, ctx, principal, review_id, body.reason))
