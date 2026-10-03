"""Phase 8B project-side verification API (`/api/v1/verification`): propose / withdraw / terminate VVB assignments, submit the Phase 8A
READY package, answer VVB findings and corrective actions, read decisions and their lineage. The project never closes a VVB finding and
never records a decision (the VVB does, through `/api/v1/vvb`). Verification only — no validation, registry or issuance endpoint exists."""
import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, Form, Response, UploadFile, status

from app.api.deps import DB, Ctx, read_upload, require_any
from app.core.errors import NotFound, PermissionDenied
from app.models import VerificationSubmission
from app.schemas.lab import DocumentRef
from app.schemas.verification import (
    AssignmentIn,
    AssignmentOut,
    CorrectiveActionOut,
    LineageOut,
    PeriodVerificationView,
    ReasonIn,
    SubmissionOut,
    VFindingOut,
    VRespondIn,
    VvbOrgOut,
)
from app.security.permissions import P
from app.security.principal import Principal
from app.services import calculation_mappers as cm
from app.services import calculation_service as cs
from app.services import document_service
from app.services import verification_access as va
from app.services import verification_findings as vf
from app.services import verification_mappers as vm
from app.services import verification_service as vs

router = APIRouter(prefix="/verification", tags=["verification — project side (VVB / ACVA)"])

Reader = Annotated[Principal, Depends(require_any(*va.PROJECT_VISIBLE))]
Manager = Annotated[Principal, Depends(require_any(P.VERIFICATION_MANAGE))]
Responder = Annotated[Principal, Depends(require_any(P.VERIFICATION_RESPOND))]


def _assignment(db: Any, principal: Principal, a: Any) -> AssignmentOut:
    return vm.assignment_out(db, principal, a)


@router.get("/projects/{project_id}/vvb-organizations", response_model=list[VvbOrgOut],
            summary="Active VVB organizations of the project's environment (no accreditation is modelled)")
def vvb_organizations(project_id: uuid.UUID, principal: Reader, db: DB) -> list[VvbOrgOut]:
    return [VvbOrgOut(id=o.id, name=o.name, code=o.code) for o in vs.vvb_organizations(db, principal, project_id)]


@router.get("/projects/{project_id}/assignments", response_model=list[AssignmentOut])
def list_assignments(project_id: uuid.UUID, principal: Reader, db: DB, period_id: uuid.UUID | None = None) -> list[AssignmentOut]:
    return [_assignment(db, principal, a) for a in vs.assignments(db, principal, project_id, period_id)]


@router.get("/projects/{project_id}/periods/{period_id}", response_model=PeriodVerificationView,
            summary="Verification panel of one monitoring period (period records are authoritative)")
def period_view(project_id: uuid.UUID, period_id: uuid.UUID, principal: Reader, db: DB, ctx: Ctx) -> PeriodVerificationView:
    v = vs.period_view(db, ctx, principal, project_id, period_id)
    run, ready, d = v["run"], v["ready"], v["decision"]
    return PeriodVerificationView(
        project_id=v["project"].id, project_status=v["project"].status, monitoring_period_id=v["period"].id,
        period_number=v["period"].period_number, ready_review_code=ready.readiness_code if ready else None,
        calculated_value=run.net_result if run else None, calculated_unit=run.net_unit if run else None,
        assignments=[_assignment(db, principal, a) for a in v["assignments"]], current_decision=vm.decision_out(db, d) if d else None,
        submit_blockers=v["submit_blockers"], can_manage=v["can_manage"], can_respond=v["can_respond"])


@router.post("/projects/{project_id}/assignments", response_model=AssignmentOut, status_code=status.HTTP_201_CREATED,
             summary="Propose a VVB assignment for a monitoring period (one open assignment per period)")
def propose(project_id: uuid.UUID, body: AssignmentIn, principal: Manager, db: DB, ctx: Ctx) -> AssignmentOut:
    a = vs.propose(db, ctx, principal, project_id, body.monitoring_period_id, body.vvb_organization_id, body.notes, body.previous_assignment_id)
    return _assignment(db, principal, a)


@router.get("/assignments/{assignment_id}", response_model=AssignmentOut)
def get_assignment(assignment_id: uuid.UUID, principal: Reader, db: DB, ctx: Ctx) -> AssignmentOut:
    a, _ = va.project_assignment(db, principal, assignment_id)
    vs.refresh(db, ctx, a)
    return _assignment(db, principal, a)


@router.post("/assignments/{assignment_id}/withdraw", response_model=AssignmentOut, summary="Withdraw a PROPOSED assignment")
def withdraw(assignment_id: uuid.UUID, body: ReasonIn, principal: Manager, db: DB, ctx: Ctx) -> AssignmentOut:
    return _assignment(db, principal, vs.withdraw(db, ctx, principal, assignment_id, body.reason))


@router.post("/assignments/{assignment_id}/terminate", response_model=AssignmentOut, summary="Terminate an ACCEPTED assignment")
def terminate(assignment_id: uuid.UUID, body: ReasonIn, principal: Manager, db: DB, ctx: Ctx) -> AssignmentOut:
    return _assignment(db, principal, vs.terminate(db, ctx, principal, assignment_id, body.reason, "PROJECT"))


@router.post("/assignments/{assignment_id}/submit", response_model=SubmissionOut, status_code=status.HTTP_201_CREATED,
             summary="Submit the period's currently valid Phase 8A READY package to the accepted VVB")
def submit(assignment_id: uuid.UUID, principal: Manager, db: DB, ctx: Ctx) -> SubmissionOut:
    return vm.submission_out(db, vs.submit(db, ctx, principal, assignment_id))


@router.get("/submissions/{submission_id}/findings", response_model=list[VFindingOut])
def findings(submission_id: uuid.UUID, principal: Reader, db: DB) -> list[VFindingOut]:
    s, _, _ = va.project_submission(db, principal, submission_id)
    return [vm.finding_out(db, f) for f in vf.findings_of(db, s.id)]


@router.post("/submissions/{submission_id}/evidence", response_model=DocumentRef, status_code=status.HTTP_201_CREATED,
             summary="Attach response evidence (PDF) to the current submission; the assigned VVB may read it")
def upload_evidence(submission_id: uuid.UUID, principal: Responder, db: DB, ctx: Ctx, file: Annotated[UploadFile, File()],
                    title: Annotated[str | None, Form(max_length=200)] = None) -> DocumentRef:
    d = vf.upload_evidence(db, ctx, principal, submission_id, file.filename, read_upload(file), title)
    return DocumentRef(document_id=d.id, category=d.category, title=d.title, file_name=None, sha256=None, uploaded_at=d.created_at)


@router.post("/findings/{finding_id}/respond", response_model=VFindingOut, summary="Answer an OPEN VVB finding (the VVB closes it)")
def respond(finding_id: uuid.UUID, body: VRespondIn, principal: Responder, db: DB, ctx: Ctx) -> VFindingOut:
    return vm.finding_out(db, vf.respond(db, ctx, principal, finding_id, body.response, body.document_id))


@router.post("/corrective-actions/{action_id}/respond", response_model=CorrectiveActionOut, summary="Answer a REQUESTED corrective action")
def respond_ca(action_id: uuid.UUID, body: VRespondIn, principal: Responder, db: DB, ctx: Ctx) -> CorrectiveActionOut:
    return vm.ca_out(db, vf.respond_ca(db, ctx, principal, action_id, body.response, body.document_id))


@router.get("/decisions/{decision_id}/lineage", response_model=LineageOut,
            summary="decision → assignment → submission → readiness → manifest → report → run → … → project")
def lineage(decision_id: uuid.UUID, principal: Reader, db: DB) -> LineageOut:
    out = LineageOut(**vs.lineage(db, principal, decision_id))
    d, _, _ = vs.get_decision(db, principal, decision_id)
    s = db.get(VerificationSubmission, d.submission_id)
    try:
        run, _ = cs.get_run(db, principal, s.calculation_run_id) if s else (None, None)
        if run is not None:
            out.calculation_lineage = cm.lineage(db, principal, run).model_dump(mode="json")
    except (NotFound, PermissionDenied):
        out.calculation_lineage = None
    return out


@router.get("/assignments/{assignment_id}/submissions", response_model=list[SubmissionOut])
def list_submissions(assignment_id: uuid.UUID, principal: Reader, db: DB, ctx: Ctx) -> list[SubmissionOut]:
    a, _ = va.project_assignment(db, principal, assignment_id)
    vs.refresh(db, ctx, a)
    return [vm.submission_out(db, s) for s in vs.submissions(db, a.id)]


@router.get("/submissions/{submission_id}", response_model=SubmissionOut)
def get_submission(submission_id: uuid.UUID, principal: Reader, db: DB, ctx: Ctx) -> SubmissionOut:
    s, a, _ = va.project_submission(db, principal, submission_id)
    vs.refresh(db, ctx, a)
    db.refresh(s)
    return vm.submission_out(db, s)


@router.get("/decisions/{decision_id}/report", summary="Download the VVB's verification report (PDF, integrity re-checked, audited)")
def decision_report(decision_id: uuid.UUID, principal: Reader, db: DB, ctx: Ctx) -> Response:
    d, _, _ = vs.get_decision(db, principal, decision_id)
    _, data = document_service.download(db, ctx, principal, d.report_document_id)
    return Response(content=data, media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="{d.decision_code}.pdf"'})
