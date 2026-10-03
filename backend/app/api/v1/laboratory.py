"""Phase 6 laboratory-facing API (`/api/v1/laboratory`). Every response is an explicit allow-list (`*LabView`): no farmer,
farm, boundary, GPS, sampling point, field collection, stratum, project name or project-side location (decision 16)."""
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, UploadFile, status

from app.api.deps import DB, Ctx, read_upload, require, require_any
from app.schemas.lab import (
    AccessionIn,
    CorrectionIn,
    CustodyEventIn,
    CustodyEventLabView,
    DocumentRef,
    EngagementLabView,
    LabDashboardCounts,
    QaDecisionIn,
    QaLabView,
    ReasonIn,
    ReceiptIn,
    ResultIn,
    ResultLabView,
    ResultUpdate,
    RetestIn,
    SampleLabView,
    ShipmentLabView,
    TestLabView,
    TestStartIn,
)
from app.security.permissions import P
from app.security.principal import Principal
from app.services import lab_mappers as lm
from app.services import lab_service as ls
from app.services import laboratory_service as lab

router = APIRouter(prefix="/laboratory", tags=["laboratory (lab side)"])

LabReader = Annotated[Principal, Depends(require(P.LAB_LAB_READ))]
EngagementReader = Annotated[Principal, Depends(require_any(P.LAB_LAB_READ, P.LAB_ENGAGEMENT_ACCEPT))]
Accepter = Annotated[Principal, Depends(require(P.LAB_ENGAGEMENT_ACCEPT))]
Receiver = Annotated[Principal, Depends(require(P.LAB_RECEIVE))]
Tester = Annotated[Principal, Depends(require(P.LAB_TEST))]
Reviewer = Annotated[Principal, Depends(require(P.LAB_QA))]
Retester = Annotated[Principal, Depends(require(P.LAB_RETEST_REQUEST))]


@router.get("/dashboard", response_model=LabDashboardCounts)
def dashboard(principal: LabReader, db: DB) -> LabDashboardCounts:
    return LabDashboardCounts(**lab.counts(db, principal))


# ---------------------------------------------------------------- engagements
@router.get("/engagements", response_model=list[EngagementLabView])
def engagements(principal: EngagementReader, db: DB) -> list[EngagementLabView]:
    return [lm.engagement_lab_view(db, principal, e) for e in lab.engagements(db, principal)]


@router.post("/engagements/{engagement_id}/accept", response_model=EngagementLabView, summary="Accept a proposed engagement (laboratory side)")
def accept(engagement_id: uuid.UUID, principal: Accepter, db: DB, ctx: Ctx) -> EngagementLabView:
    return lm.engagement_lab_view(db, principal, ls.accept_engagement(db, ctx, principal, engagement_id))


@router.post("/engagements/{engagement_id}/end", response_model=EngagementLabView, summary="End an engagement (laboratory side)")
def end(engagement_id: uuid.UUID, body: ReasonIn, principal: Accepter, db: DB, ctx: Ctx) -> EngagementLabView:
    return lm.engagement_lab_view(db, principal, ls.end_engagement(db, ctx, principal, engagement_id, body.reason, "LABORATORY"))


# ---------------------------------------------------------------- inbox & receipt
@router.get("/shipments", response_model=list[ShipmentLabView], summary="Shipments addressed to your laboratory")
def inbox(principal: LabReader, db: DB) -> list[ShipmentLabView]:
    return [lm.shipment_lab_view(db, principal, sh) for sh in lab.inbox(db, principal)]


@router.get("/shipments/{shipment_id}", response_model=ShipmentLabView)
def shipment(shipment_id: uuid.UUID, principal: LabReader, db: DB) -> ShipmentLabView:
    return lm.shipment_lab_view(db, principal, lab.lab_shipment(db, principal, shipment_id))


@router.post("/shipments/{shipment_id}/receive", response_model=ShipmentLabView, summary="Item-level receipt (accept or reject with a reason)")
def receive(shipment_id: uuid.UUID, body: ReceiptIn, principal: Receiver, db: DB, ctx: Ctx) -> ShipmentLabView:
    return lm.shipment_lab_view(db, principal, lab.receive(db, ctx, principal, shipment_id, body))


@router.post("/shipments/{shipment_id}/documents", response_model=DocumentRef, status_code=status.HTTP_201_CREATED,
             summary="Attach a chain-of-custody document (PDF only)")
def shipment_document(shipment_id: uuid.UUID, principal: Receiver, db: DB, ctx: Ctx, file: Annotated[UploadFile, File()],
                      title: Annotated[str | None, Form(max_length=200)] = None) -> DocumentRef:
    doc = lab.upload_custody_document(db, ctx, principal, shipment_id, file.filename, read_upload(file), title, "LABORATORY")
    return DocumentRef(**lab.doc_ref(db, doc.id))  # type: ignore[arg-type]


# ---------------------------------------------------------------- samples
@router.get("/samples", response_model=list[SampleLabView])
def samples(principal: LabReader, db: DB) -> list[SampleLabView]:
    return [lm.sample_lab_view(db, principal, s, with_detail=False) for s in lab.lab_samples(db, principal)]


@router.get("/samples/{sample_id}", response_model=SampleLabView)
def sample(sample_id: uuid.UUID, principal: LabReader, db: DB) -> SampleLabView:
    return lm.sample_lab_view(db, principal, lab.lab_sample(db, principal, sample_id))


@router.post("/samples/{sample_id}/accession", response_model=SampleLabView, summary="Register the received sample at the laboratory")
def accession(sample_id: uuid.UUID, body: AccessionIn, principal: Receiver, db: DB, ctx: Ctx) -> SampleLabView:
    return lm.sample_lab_view(db, principal, lab.accession(db, ctx, principal, sample_id, body.accession_number))


@router.post("/samples/{sample_id}/custody", response_model=list[CustodyEventLabView], status_code=status.HTTP_201_CREATED,
             summary="Laboratory-side custody exception / resolution")
def custody(sample_id: uuid.UUID, body: CustodyEventIn, principal: Receiver, db: DB, ctx: Ctx) -> list[CustodyEventLabView]:
    lab.lab_custody(db, ctx, principal, sample_id, body)
    return lm.custody_lab_view(db, ls.custody_events(db, sample_id))


# ---------------------------------------------------------------- tests & results
@router.get("/tests", response_model=list[TestLabView], summary="Worklist: tests on samples received by your laboratory")
def tests(principal: LabReader, db: DB, test_status: str | None = None) -> list[TestLabView]:
    return [lm.test_lab_view(db, principal, t) for t in lab.worklist(db, principal, test_status)]


@router.get("/tests/{test_id}", response_model=TestLabView)
def test(test_id: uuid.UUID, principal: LabReader, db: DB) -> TestLabView:
    return lm.test_lab_view(db, principal, lab.lab_test(db, principal, test_id))


@router.post("/tests/{test_id}/start", response_model=TestLabView)
def start(test_id: uuid.UUID, body: TestStartIn, principal: Tester, db: DB, ctx: Ctx) -> TestLabView:
    return lm.test_lab_view(db, principal, lab.start_test(db, ctx, principal, test_id, body.method_reported))


@router.post("/tests/{test_id}/results", response_model=ResultLabView, status_code=status.HTTP_201_CREATED,
             summary="Enter a result (numeric value or verbatim text; never converted)")
def create_result(test_id: uuid.UUID, body: ResultIn, principal: Tester, db: DB, ctx: Ctx) -> ResultLabView:
    return lm.result_lab_view(db, principal, lab.create_result(db, ctx, principal, test_id, body))


@router.patch("/results/{result_id}", response_model=ResultLabView)
def update_result(result_id: uuid.UUID, body: ResultUpdate, principal: Tester, db: DB, ctx: Ctx) -> ResultLabView:
    return lm.result_lab_view(db, principal, lab.update_result(db, ctx, principal, result_id, body))


@router.post("/results/{result_id}/report", response_model=ResultLabView, summary="Attach the laboratory report (PDF only)")
def report(result_id: uuid.UUID, principal: Tester, db: DB, ctx: Ctx, file: Annotated[UploadFile, File()],
           title: Annotated[str | None, Form(max_length=200)] = None) -> ResultLabView:
    return lm.result_lab_view(db, principal, lab.attach_report(db, ctx, principal, result_id, file.filename, read_upload(file), title))


@router.post("/results/{result_id}/submit", response_model=ResultLabView)
def submit(result_id: uuid.UUID, principal: Tester, db: DB, ctx: Ctx) -> ResultLabView:
    return lm.result_lab_view(db, principal, lab.submit_result(db, ctx, principal, result_id))


@router.post("/results/{result_id}/withdraw", response_model=ResultLabView)
def withdraw(result_id: uuid.UUID, body: ReasonIn, principal: Tester, db: DB, ctx: Ctx) -> ResultLabView:
    return lm.result_lab_view(db, principal, lab.withdraw_result(db, ctx, principal, result_id, body.reason))


@router.post("/results/{result_id}/correct", response_model=ResultLabView, status_code=status.HTTP_201_CREATED,
             summary="Correct an APPROVED result: a new version that supersedes it once approved")
def correct(result_id: uuid.UUID, body: CorrectionIn, principal: Tester, db: DB, ctx: Ctx) -> ResultLabView:
    data = ResultIn(**body.model_dump(exclude={"reason"}))
    return lm.result_lab_view(db, principal, lab.correct_result(db, ctx, principal, result_id, body.reason, data))


@router.post("/results/{result_id}/retest", response_model=TestLabView, status_code=status.HTTP_201_CREATED,
             summary="Request a retest (LAB_MANAGER, with a reason); the original result is kept")
def retest(result_id: uuid.UUID, body: RetestIn, principal: Retester, db: DB, ctx: Ctx) -> TestLabView:
    return lm.test_lab_view(db, principal, lab.request_retest(db, ctx, principal, result_id, body))


# ---------------------------------------------------------------- QA
@router.get("/qa", response_model=list[ResultLabView], summary="Results waiting for laboratory QA")
def qa_queue(principal: LabReader, db: DB) -> list[ResultLabView]:
    return [lm.result_lab_view(db, principal, r) for r in lab.results_awaiting_qa(db, principal)]


def _qa_view(db: DB, principal: Principal, result_id: uuid.UUID) -> QaLabView:
    r, checks, reviews = lab.qa_view_data(db, principal, result_id)
    t = lab.lab_test(db, principal, r.test_id)
    s = lab.lab_sample(db, principal, r.sample_id)
    is_reviewer = principal.can_in_org(P.LAB_QA, r.laboratory_org_id)
    blocked = lab.sod_violations(db, r, principal.user_id, approving=True)
    return QaLabView(result=lm.result_lab_view(db, principal, r), test=lm.test_lab_view(db, principal, t), sample_code=s.sample_code,
                     checks=checks, reviews=[lm.qa_review_out(db, x) for x in reviews],
                     can_start=is_reviewer and r.status == "SUBMITTED" and r.analyst_id != principal.user_id and r.submitted_by != principal.user_id,
                     can_decide=is_reviewer and r.status == "QA_REVIEW" and r.analyst_id != principal.user_id,
                     can_approve=is_reviewer and r.status == "QA_REVIEW" and not blocked and not any(c.result == "FAIL" for c in checks),
                     blocked_reasons=blocked)


@router.get("/qa/{result_id}", response_model=QaLabView)
def qa_view(result_id: uuid.UUID, principal: LabReader, db: DB) -> QaLabView:
    return _qa_view(db, principal, result_id)


@router.post("/qa/{result_id}/start", response_model=QaLabView)
def qa_start(result_id: uuid.UUID, principal: Reviewer, db: DB, ctx: Ctx) -> QaLabView:
    lab.start_qa(db, ctx, principal, result_id)
    return _qa_view(db, principal, result_id)


@router.post("/qa/{result_id}/decision", response_model=QaLabView, summary="APPROVED / REJECTED / RETEST_REQUIRED (never on your own work)")
def qa_decision(result_id: uuid.UUID, body: QaDecisionIn, principal: Reviewer, db: DB, ctx: Ctx) -> QaLabView:
    lab.decide(db, ctx, principal, result_id, body)
    return _qa_view(db, principal, result_id)
