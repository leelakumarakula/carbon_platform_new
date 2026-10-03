"""Phase 8B VVB / ACVA workspace API (`/api/v1/vvb`) — a separate allow-list API (C8), like `/api/v1/laboratory` for laboratories.

A VVB user reaches only assignments of its own (active, same-environment) VVB organization; the package of an ACCEPTED / COMPLETED
assignment is an allow-list view (no generic project, farmer, KYC, bank, agreement or audit read). The VVB accepts with a conflict-of-
interest declaration, raises / closes findings, requests corrective actions and records its own external decision with its report PDF.
The platform records that decision; it does not verify, validate, register or issue anything.
"""
import uuid
from decimal import Decimal, InvalidOperation
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Response, UploadFile, status

from app.api.deps import DB, Ctx, read_upload, require_any
from app.core.errors import NotFound, ValidationFailed
from app.models import VerificationDecision
from app.schemas.verification import (
    AcceptIn,
    AssignmentOut,
    CorrectiveActionIn,
    CorrectiveActionOut,
    DecisionOut,
    NoteIn,
    PackageOut,
    ReasonIn,
    VDocumentRef,
    VFindingIn,
    VFindingOut,
)
from app.security.permissions import P
from app.security.principal import Principal
from app.services import document_service
from app.services import verification_access as va
from app.services import verification_findings as vf
from app.services import verification_mappers as vm
from app.services import verification_package as vp
from app.services import verification_service as vs

router = APIRouter(prefix="/vvb", tags=["vvb — VVB / ACVA workspace"])

VvbReader = Annotated[Principal, Depends(require_any(*va.VVB_CODES))]
VvbReviewer = Annotated[Principal, Depends(require_any(P.VERIFICATION_VVB_REVIEW))]
VvbDecider = Annotated[Principal, Depends(require_any(P.VERIFICATION_DECIDE))]


@router.get("/assignments", response_model=list[AssignmentOut], summary="Assignments of my VVB organization(s)")
def list_assignments(principal: VvbReader, db: DB) -> list[AssignmentOut]:
    return [vm.assignment_out(db, principal, a, vvb=True) for a in vs.vvb_assignments(db, principal)]


@router.get("/assignments/{assignment_id}", response_model=AssignmentOut)
def get_assignment(assignment_id: uuid.UUID, principal: VvbReader, db: DB, ctx: Ctx) -> AssignmentOut:
    a, _, _ = va.vvb_assignment(db, principal, assignment_id, P.VERIFICATION_VVB_READ)
    vs.refresh(db, ctx, a)
    return vm.assignment_out(db, principal, a, vvb=True)


@router.post("/assignments/{assignment_id}/accept", response_model=AssignmentOut,
             summary="Accept a PROPOSED assignment with a mandatory conflict-of-interest declaration")
def accept(assignment_id: uuid.UUID, body: AcceptIn, principal: VvbReviewer, db: DB, ctx: Ctx) -> AssignmentOut:
    return vm.assignment_out(db, principal, vs.accept(db, ctx, principal, assignment_id, body.coi_declaration), vvb=True)


@router.post("/assignments/{assignment_id}/decline", response_model=AssignmentOut)
def decline(assignment_id: uuid.UUID, body: ReasonIn, principal: VvbReviewer, db: DB, ctx: Ctx) -> AssignmentOut:
    return vm.assignment_out(db, principal, vs.decline(db, ctx, principal, assignment_id, body.reason), vvb=True)


@router.post("/assignments/{assignment_id}/terminate", response_model=AssignmentOut)
def terminate(assignment_id: uuid.UUID, body: ReasonIn, principal: VvbReviewer, db: DB, ctx: Ctx) -> AssignmentOut:
    return vm.assignment_out(db, principal, vs.terminate(db, ctx, principal, assignment_id, body.reason, "VVB"), vvb=True)


@router.get("/submissions/{submission_id}/package", response_model=PackageOut, summary="The submitted package (allow-list view)")
def package(submission_id: uuid.UUID, principal: VvbReader, db: DB) -> PackageOut:
    s, a, p, _ = va.vvb_submission(db, principal, submission_id, P.VERIFICATION_VVB_READ)
    return PackageOut(submission=vm.submission_out(db, s, vvb=True), **vp.package(db, s, a, p))


@router.get("/submissions/{submission_id}/documents", response_model=list[VDocumentRef])
def documents(submission_id: uuid.UUID, principal: VvbReader, db: DB) -> list[VDocumentRef]:
    s, _, _, _ = va.vvb_submission(db, principal, submission_id, P.VERIFICATION_VVB_READ)
    return [VDocumentRef(**d) for d in vp.document_refs(db, s)]


@router.get("/submissions/{submission_id}/documents/{document_id}",
            summary="Download a document referenced by the submitted package (integrity re-checked, audited in both organizations)")
def download(submission_id: uuid.UUID, document_id: uuid.UUID, principal: VvbReader, db: DB, ctx: Ctx) -> Response:
    s, a, p, _ = va.vvb_submission(db, principal, submission_id, P.VERIFICATION_VVB_READ)
    v, data = vp.download(db, ctx, s, a, p, principal, document_id)
    return Response(content=data, media_type=v.mime_type, headers={"Content-Disposition": f'attachment; filename="{v.file_name}"',
                                                                   "X-Content-SHA256": v.checksum_sha256})


@router.get("/submissions/{submission_id}/findings", response_model=list[VFindingOut])
def findings(submission_id: uuid.UUID, principal: VvbReader, db: DB) -> list[VFindingOut]:
    s, _, _, _ = va.vvb_submission(db, principal, submission_id, P.VERIFICATION_VVB_READ)
    return [vm.finding_out(db, f, vvb=True) for f in vf.findings_of(db, s.id)]


@router.post("/submissions/{submission_id}/findings", response_model=VFindingOut, status_code=status.HTTP_201_CREATED)
def raise_finding(submission_id: uuid.UUID, body: VFindingIn, principal: VvbReviewer, db: DB, ctx: Ctx) -> VFindingOut:
    return vm.finding_out(db, vf.raise_finding(db, ctx, principal, submission_id, body), vvb=True)


@router.post("/findings/{finding_id}/close", response_model=VFindingOut)
def close(finding_id: uuid.UUID, body: NoteIn, principal: VvbReviewer, db: DB, ctx: Ctx) -> VFindingOut:
    return vm.finding_out(db, vf.close(db, ctx, principal, finding_id, body.note), vvb=True)


@router.post("/findings/{finding_id}/return", response_model=VFindingOut, summary="Return an insufficient response (RESPONDED → OPEN)")
def return_response(finding_id: uuid.UUID, body: ReasonIn, principal: VvbReviewer, db: DB, ctx: Ctx) -> VFindingOut:
    return vm.finding_out(db, vf.return_response(db, ctx, principal, finding_id, body.reason), vvb=True)


@router.post("/findings/{finding_id}/reopen", response_model=VFindingOut, summary="Reopen a CLOSED finding (reason required)")
def reopen(finding_id: uuid.UUID, body: ReasonIn, principal: VvbReviewer, db: DB, ctx: Ctx) -> VFindingOut:
    return vm.finding_out(db, vf.reopen(db, ctx, principal, finding_id, body.reason), vvb=True)


@router.post("/findings/{finding_id}/corrective-actions", response_model=CorrectiveActionOut, status_code=status.HTTP_201_CREATED)
def request_ca(finding_id: uuid.UUID, body: CorrectiveActionIn, principal: VvbReviewer, db: DB, ctx: Ctx) -> CorrectiveActionOut:
    return vm.ca_out(db, vf.request_ca(db, ctx, principal, finding_id, body.description, body.due_date), vvb=True)


@router.post("/corrective-actions/{action_id}/accept", response_model=CorrectiveActionOut)
def accept_ca(action_id: uuid.UUID, body: NoteIn, principal: VvbReviewer, db: DB, ctx: Ctx) -> CorrectiveActionOut:
    return vm.ca_out(db, vf.review_ca(db, ctx, principal, action_id, True, body.note), vvb=True)


@router.post("/corrective-actions/{action_id}/reject", response_model=CorrectiveActionOut, summary="Reject the response (back to REQUESTED)")
def reject_ca(action_id: uuid.UUID, body: NoteIn, principal: VvbReviewer, db: DB, ctx: Ctx) -> CorrectiveActionOut:
    return vm.ca_out(db, vf.review_ca(db, ctx, principal, action_id, False, body.note), vvb=True)


@router.post("/corrective-actions/{action_id}/cancel", response_model=CorrectiveActionOut)
def cancel_ca(action_id: uuid.UUID, body: ReasonIn, principal: VvbReviewer, db: DB, ctx: Ctx) -> CorrectiveActionOut:
    return vm.ca_out(db, vf.cancel_ca(db, ctx, principal, action_id, body.reason), vvb=True)


@router.post("/submissions/{submission_id}/decision", response_model=DecisionOut, status_code=status.HTTP_201_CREATED,
             summary="Record the VVB's external decision (VERIFIED / NOT_VERIFIED) with its verification report PDF")
def decide(submission_id: uuid.UUID, principal: VvbDecider, db: DB, ctx: Ctx, file: Annotated[UploadFile, File()],
           outcome: Annotated[str, Form(max_length=15)], rationale: Annotated[str, Form(min_length=3, max_length=4000)],
           verified_quantity: Annotated[str | None, Form(max_length=40)] = None,
           verified_quantity_unit: Annotated[str | None, Form(max_length=40)] = None) -> DecisionOut:
    qty: Decimal | None = None
    if verified_quantity is not None and verified_quantity.strip():
        try:
            qty = Decimal(verified_quantity.strip())
        except InvalidOperation:
            raise ValidationFailed("The VVB-stated verified quantity must be a decimal number.", error_code="INVALID_QUANTITY") from None
        if not qty.is_finite() or qty < 0:
            raise ValidationFailed("The VVB-stated verified quantity must be a non-negative number.", error_code="INVALID_QUANTITY")
    unit = verified_quantity_unit.strip() if verified_quantity_unit and verified_quantity_unit.strip() else None
    d = vs.decide(db, ctx, principal, submission_id, outcome.strip(), rationale.strip(), qty, unit, file.filename, read_upload(file))
    return vm.decision_out(db, d)


@router.get("/decisions/{decision_id}/report", summary="Download the decision's report PDF (own VVB organization only)")
def decision_report(decision_id: uuid.UUID, principal: VvbReader, db: DB, ctx: Ctx) -> Response:
    d = db.get(VerificationDecision, decision_id)
    if d is None:
        raise NotFound("Verification decision not found.", error_code="DECISION_NOT_FOUND")
    try:
        va.vvb_submission(db, principal, d.submission_id, P.VERIFICATION_VVB_READ)
    except NotFound:
        raise NotFound("Verification decision not found.", error_code="DECISION_NOT_FOUND") from None
    _, data = document_service.download(db, ctx, principal, d.report_document_id)
    return Response(content=data, media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="{d.decision_code}.pdf"'})
