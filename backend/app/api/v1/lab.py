"""Phase 6 project-side laboratory API (`/api/v1/lab`). Laboratory users are served only by `/api/v1/laboratory`."""
import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile, status
from pydantic import BaseModel

from app.api.deps import DB, Ctx, read_upload, require, require_any
from app.schemas.lab import (
    CustodyEventIn,
    CustodyEventOut,
    DocumentRef,
    EngagementIn,
    EngagementOut,
    LaboratoryOrgOut,
    LineageOut,
    ReasonIn,
    ResultOut,
    RuleRef,
    SampleDetailOut,
    SampleIn,
    SampleOut,
    SampleUpdate,
    SealIn,
    ShipmentIn,
    ShipmentItemsIn,
    ShipmentOut,
)
from app.security.permissions import P
from app.security.principal import Principal
from app.services import lab_mappers as lm
from app.services import lab_service as ls
from app.services import laboratory_service as lab

router = APIRouter(prefix="/lab", tags=["laboratory (project side)"])

Reader = Annotated[Principal, Depends(require(P.LAB_READ))]
EngageOrRead = Annotated[Principal, Depends(require_any(P.LAB_ENGAGE, P.LAB_READ))]
Engager = Annotated[Principal, Depends(require(P.LAB_ENGAGE))]
SampleReader = Annotated[Principal, Depends(require_any(P.LAB_READ, P.LAB_SAMPLE_REGISTER, P.LAB_SAMPLE_MANAGE))]
Registrar = Annotated[Principal, Depends(require_any(P.LAB_SAMPLE_REGISTER, P.LAB_SAMPLE_MANAGE))]
SampleManager = Annotated[Principal, Depends(require(P.LAB_SAMPLE_MANAGE))]
Shipper = Annotated[Principal, Depends(require(P.LAB_SHIPMENT_MANAGE))]
ShipmentReader = Annotated[Principal, Depends(require_any(P.LAB_READ, P.LAB_SHIPMENT_MANAGE))]


class DispatchIn(BaseModel):
    occurred_at: datetime | None = None


# ---------------------------------------------------------------- engagements
@router.get("/projects/{project_id}/laboratories", response_model=list[LaboratoryOrgOut], summary="Laboratory organizations that can be engaged")
def list_laboratories(project_id: uuid.UUID, principal: EngageOrRead, db: DB) -> list[LaboratoryOrgOut]:
    return [LaboratoryOrgOut(id=o.id, code=o.code, name=o.name, environment=o.environment) for o in ls.laboratories(db, principal, project_id)]


@router.get("/projects/{project_id}/laboratory-rules", response_model=list[RuleRef], summary="LABORATORY rules of the locked methodology version")
def list_rules(project_id: uuid.UUID, principal: EngageOrRead, db: DB) -> list[RuleRef]:
    return [lm.rule_ref(db, r.id) for r in ls.laboratory_rules(db, principal, project_id)]


@router.get("/engagements", response_model=list[EngagementOut])
def list_engagements(principal: EngageOrRead, db: DB, project_id: uuid.UUID) -> list[EngagementOut]:
    ls.project_for(db, principal, project_id, P.LAB_ENGAGE, P.LAB_READ)
    return [lm.engagement_out(db, principal, e) for e in ls.engagements(db, project_id)]


@router.post("/engagements", response_model=EngagementOut, status_code=status.HTTP_201_CREATED, summary="Propose an engagement (project side)")
def propose(body: EngagementIn, principal: Engager, db: DB, ctx: Ctx) -> EngagementOut:
    return lm.engagement_out(db, principal, ls.propose_engagement(db, ctx, principal, body))


@router.post("/engagements/{engagement_id}/end", response_model=EngagementOut, summary="End an engagement (project side)")
def end(engagement_id: uuid.UUID, body: ReasonIn, principal: Engager, db: DB, ctx: Ctx) -> EngagementOut:
    return lm.engagement_out(db, principal, ls.end_engagement(db, ctx, principal, engagement_id, body.reason, "PROJECT"))


# ---------------------------------------------------------------- samples
@router.get("/samples", response_model=list[SampleOut])
def list_samples(principal: SampleReader, db: DB, project_id: uuid.UUID | None = None, monitoring_period_id: uuid.UUID | None = None,
                 field_collection_id: uuid.UUID | None = None) -> list[SampleOut]:
    return [lm.sample_out(db, principal, s) for s in ls.samples(db, principal, project_id=project_id, monitoring_period_id=monitoring_period_id,
                                                                  field_collection_id=field_collection_id)]


@router.post("/samples", response_model=SampleOut, status_code=status.HTTP_201_CREATED,
             summary="Register a physical sample (SMP-…) from a SUBMITTED/ACCEPTED field collection; tests are created automatically")
def register(body: SampleIn, principal: Registrar, db: DB, ctx: Ctx) -> SampleOut:
    return lm.sample_out(db, principal, ls.register_sample(db, ctx, principal, body))


@router.get("/samples/{sample_id}", response_model=SampleDetailOut)
def get_sample(sample_id: uuid.UUID, principal: SampleReader, db: DB) -> SampleDetailOut:
    s, _ = ls.get_sample(db, principal, sample_id, P.LAB_READ, P.LAB_SAMPLE_REGISTER, P.LAB_SAMPLE_MANAGE)
    return lm.sample_detail(db, principal, s)


@router.patch("/samples/{sample_id}", response_model=SampleOut)
def update_sample(sample_id: uuid.UUID, body: SampleUpdate, principal: Registrar, db: DB, ctx: Ctx) -> SampleOut:
    return lm.sample_out(db, principal, ls.update_sample(db, ctx, principal, sample_id, body))


@router.post("/samples/{sample_id}/seal", response_model=SampleOut)
def seal(sample_id: uuid.UUID, body: SealIn, principal: Registrar, db: DB, ctx: Ctx) -> SampleOut:
    return lm.sample_out(db, principal, ls.seal_sample(db, ctx, principal, sample_id, body))


@router.post("/samples/{sample_id}/void", response_model=SampleOut)
def void(sample_id: uuid.UUID, body: ReasonIn, principal: SampleManager, db: DB, ctx: Ctx) -> SampleOut:
    return lm.sample_out(db, principal, ls.void_sample(db, ctx, principal, sample_id, body.reason))


@router.get("/samples/{sample_id}/custody", response_model=list[CustodyEventOut])
def custody(sample_id: uuid.UUID, principal: SampleReader, db: DB) -> list[CustodyEventOut]:
    s, _ = ls.get_sample(db, principal, sample_id, P.LAB_READ, P.LAB_SAMPLE_REGISTER, P.LAB_SAMPLE_MANAGE)
    return lm.custody_out(db, ls.custody_events(db, s.id))


@router.post("/samples/{sample_id}/custody", response_model=list[CustodyEventOut], status_code=status.HTTP_201_CREATED,
             summary="Project-side custody: transfer in transit, exception, resolution")
def add_custody(sample_id: uuid.UUID, body: CustodyEventIn, principal: SampleManager, db: DB, ctx: Ctx) -> list[CustodyEventOut]:
    ls.project_custody(db, ctx, principal, sample_id, body)
    return lm.custody_out(db, ls.custody_events(db, sample_id))


# ---------------------------------------------------------------- shipments
@router.get("/shipments", response_model=list[ShipmentOut])
def list_shipments(principal: ShipmentReader, db: DB, project_id: uuid.UUID) -> list[ShipmentOut]:
    ls.project_for(db, principal, project_id, P.LAB_READ, P.LAB_SHIPMENT_MANAGE)
    return [lm.shipment_out(db, sh) for sh in ls.shipments(db, project_id)]


@router.post("/shipments", response_model=ShipmentOut, status_code=status.HTTP_201_CREATED)
def create_shipment(body: ShipmentIn, principal: Shipper, db: DB, ctx: Ctx) -> ShipmentOut:
    return lm.shipment_out(db, ls.create_shipment(db, ctx, principal, body))


@router.get("/shipments/{shipment_id}", response_model=ShipmentOut)
def get_shipment(shipment_id: uuid.UUID, principal: ShipmentReader, db: DB) -> ShipmentOut:
    sh, _ = ls.get_shipment(db, principal, shipment_id, P.LAB_READ, P.LAB_SHIPMENT_MANAGE)
    return lm.shipment_out(db, sh)


@router.post("/shipments/{shipment_id}/items", response_model=ShipmentOut)
def add_items(shipment_id: uuid.UUID, body: ShipmentItemsIn, principal: Shipper, db: DB, ctx: Ctx) -> ShipmentOut:
    return lm.shipment_out(db, ls.add_items(db, ctx, principal, shipment_id, body.sample_ids))


@router.post("/shipments/{shipment_id}/items/{sample_id}/remove", response_model=ShipmentOut)
def remove_item(shipment_id: uuid.UUID, sample_id: uuid.UUID, principal: Shipper, db: DB, ctx: Ctx) -> ShipmentOut:
    return lm.shipment_out(db, ls.remove_item(db, ctx, principal, shipment_id, sample_id))


@router.post("/shipments/{shipment_id}/dispatch", response_model=ShipmentOut)
def dispatch(shipment_id: uuid.UUID, body: DispatchIn, principal: Shipper, db: DB, ctx: Ctx) -> ShipmentOut:
    return lm.shipment_out(db, ls.dispatch_shipment(db, ctx, principal, shipment_id, body.occurred_at))


@router.post("/shipments/{shipment_id}/cancel", response_model=ShipmentOut)
def cancel(shipment_id: uuid.UUID, body: ReasonIn, principal: Shipper, db: DB, ctx: Ctx) -> ShipmentOut:
    return lm.shipment_out(db, ls.cancel_shipment(db, ctx, principal, shipment_id, body.reason))


@router.post("/shipments/{shipment_id}/documents", response_model=DocumentRef, status_code=status.HTTP_201_CREATED,
             summary="Attach a chain-of-custody document (PDF only)")
def shipment_document(shipment_id: uuid.UUID, principal: Shipper, db: DB, ctx: Ctx, file: Annotated[UploadFile, File()],
                      title: Annotated[str | None, Form(max_length=200)] = None) -> DocumentRef:
    doc = lab.upload_custody_document(db, ctx, principal, shipment_id, file.filename, read_upload(file), title, "PROJECT")
    return DocumentRef(**lab.doc_ref(db, doc.id))  # type: ignore[arg-type]


# ---------------------------------------------------------------- results (non-draft) and lineage
@router.get("/results", response_model=list[ResultOut], summary="Laboratory results of a project (default: APPROVED); drafts are never shown")
def list_results(principal: Reader, db: DB, project_id: uuid.UUID,
                 result_status: Annotated[str, Query(alias="status", max_length=20)] = "APPROVED") -> list[ResultOut]:
    """`status=ALL` lists every non-draft version."""
    return [lm.result_out(db, r) for r in ls.project_results(db, principal, project_id, None if result_status == "ALL" else result_status)]


@router.get("/results/{result_id}/lineage", response_model=LineageOut, summary="Full lineage of a laboratory result")
def result_lineage(result_id: uuid.UUID, principal: Reader, db: DB) -> LineageOut:
    return lm.lineage(db, ls.get_project_result(db, principal, result_id))
