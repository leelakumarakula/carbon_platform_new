"""MRV: plans, monitoring periods, strata, sampling designs/points/assignments, field collection, monitoring data,
evidence, datasets and QA (Phase 5). Every route checks the permission; services enforce organization scope."""
import uuid
from datetime import datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, File, Form, UploadFile, status
from sqlalchemy import select

from app.api.deps import DB, Ctx, read_upload, require, require_any
from app.models import FieldCollectionRecord, MrvDataset, MrvPlan, Project, SamplingDesign
from app.repositories import projects as project_repo
from app.schemas.audit import AuditLogOut
from app.schemas.mrv import (
    AssignIn,
    BulkAssignIn,
    CollectionOut,
    CollectionReview,
    CollectionStart,
    CollectionUpdate,
    ControlCandidate,
    DatasetIn,
    DatasetOut,
    DesignIn,
    DesignOut,
    DesignParams,
    DesignVersionOut,
    EvidenceOut,
    GenerateOut,
    MeasurementIn,
    MeasurementOut,
    MonitoringRecordAmend,
    MonitoringRecordIn,
    MonitoringRecordOut,
    PeriodIn,
    PeriodOut,
    PlanDecision,
    PlanIn,
    PlanOut,
    PlanUpdate,
    PointOut,
    ProjectMrvSummary,
    QaComplete,
    QaReviewOut,
    QaView,
    ReasonBody,
    RelocationDecision,
    RelocationIn,
    RelocationOut,
    StratumIn,
    StratumOut,
    StratumUpdate,
)
from app.security.permissions import P
from app.security.principal import Principal
from app.services import mrv_access
from app.services import mrv_mappers as mm
from app.services import mrv_service as msvc
from app.services import sampling_service as ssvc
from app.services.audit_query_service import audit_rows_out
from app.services.mrv_requirements import requirements

router = APIRouter(prefix="/mrv", tags=["mrv"])
Reader = Annotated[Principal, Depends(require(P.MRV_READ))]
Manager = Annotated[Principal, Depends(require(P.MRV_MANAGE))]
Approver = Annotated[Principal, Depends(require(P.MRV_APPROVE))]
QaReviewer = Annotated[Principal, Depends(require(P.MRV_REVIEW))]
Recorder = Annotated[Principal, Depends(require_any(P.MRV_COLLECT, P.MRV_MANAGE))]
EvidenceWriter = Annotated[Principal, Depends(require_any(P.MRV_COLLECT, P.MRV_MANAGE, P.SAMPLING_COLLECT))]
SamplingManager = Annotated[Principal, Depends(require(P.SAMPLING_MANAGE))]
SamplingReviewer = Annotated[Principal, Depends(require(P.SAMPLING_REVIEW))]
Assigner = Annotated[Principal, Depends(require(P.SAMPLING_ASSIGN))]
Collector = Annotated[Principal, Depends(require(P.SAMPLING_COLLECT))]
FieldOrReader = Annotated[Principal, Depends(require_any(P.MRV_READ, P.SAMPLING_COLLECT))]
Relocator = Annotated[Principal, Depends(require_any(P.SAMPLING_COLLECT, P.SAMPLING_MANAGE))]
Corrector = Annotated[Principal, Depends(require_any(P.SAMPLING_COLLECT, P.SAMPLING_REVIEW))]
MRV_AUDIT_PREFIXES = ("MRV_", "MONITORING_", "STRATUM_", "SAMPLING_", "FIELD_")


# ---------------------------------------------------------------- projects / requirements / history
@router.get("/projects", response_model=list[ProjectMrvSummary], summary="Projects with a locked methodology (MRV dashboard)")
def mrv_projects(principal: Reader, db: DB) -> list[ProjectMrvSummary]:
    scope = principal.scope_for(P.MRV_READ)
    stmt = select(Project).where(Project.methodology_status == "CONFIRMED")
    if scope is not None:
        stmt = stmt.where(Project.organization_id.in_(list(scope)))
    return [mm.project_summary(db, p) for p in db.scalars(stmt.order_by(Project.project_code)).all()]


@router.get("/projects/{project_id}/requirements", summary="MRV requirements of the locked methodology version (or CONFIGURATION_REQUIRED)")
def project_requirements(project_id: uuid.UUID, principal: Reader, db: DB) -> dict[str, Any]:
    p = mrv_access.project(db, principal, project_id)
    _, v = mrv_access.locked_methodology(db, p)
    return requirements(db, v).as_dict()


@router.get("/projects/{project_id}/history", response_model=list[AuditLogOut], summary="MRV audit history of a project")
def mrv_history(project_id: uuid.UUID, principal: Reader, db: DB) -> list[AuditLogOut]:
    p = mrv_access.project(db, principal, project_id)
    return audit_rows_out(db, msvc.history_rows(db, p, MRV_AUDIT_PREFIXES))


@router.get("/projects/{project_id}/collectors", summary="Users who may be assigned sampling points (sampling.collect)")
def project_collectors(project_id: uuid.UUID, principal: Assigner, db: DB) -> list[dict[str, Any]]:
    return [{"id": i, "full_name": n, "email": e} for i, n, e in ssvc.collectors(db, principal, project_id)]


# ---------------------------------------------------------------- plans
@router.get("/plans", response_model=list[PlanOut])
def list_plans(principal: Reader, db: DB, project_id: uuid.UUID) -> list[PlanOut]:
    p = mrv_access.project(db, principal, project_id)
    return [mm.plan_out(db, principal, x, p) for x in msvc.plans(db, p.id)]


@router.post("/plans", response_model=PlanOut, status_code=status.HTTP_201_CREATED)
def create_plan(body: PlanIn, principal: Manager, db: DB, ctx: Ctx) -> PlanOut:
    plan = msvc.create_plan(db, ctx, principal, body)
    return mm.plan_out(db, principal, plan, mrv_access.project(db, principal, plan.project_id))


@router.get("/plans/{plan_id}", response_model=PlanOut)
def get_plan(plan_id: uuid.UUID, principal: Reader, db: DB) -> PlanOut:
    plan, p = msvc.get_plan(db, principal, plan_id)
    return mm.plan_out(db, principal, plan, p)


@router.patch("/plans/{plan_id}", response_model=PlanOut)
def update_plan(plan_id: uuid.UUID, body: PlanUpdate, principal: Manager, db: DB, ctx: Ctx) -> PlanOut:
    plan = msvc.update_plan(db, ctx, principal, plan_id, body)
    return mm.plan_out(db, principal, plan, mrv_access.project(db, principal, plan.project_id))


@router.post("/plans/{plan_id}/measurements", response_model=MeasurementOut, status_code=status.HTTP_201_CREATED)
def add_measurement(plan_id: uuid.UUID, body: MeasurementIn, principal: Manager, db: DB, ctx: Ctx) -> MeasurementOut:
    return mm.measurement_out(db, msvc.add_measurement(db, ctx, principal, plan_id, body))


def _plan_action(db: DB, principal: Principal, plan: MrvPlan) -> PlanOut:
    return mm.plan_out(db, principal, plan, mrv_access.project(db, principal, plan.project_id))


@router.post("/plans/{plan_id}/submit", response_model=PlanOut)
def submit_plan(plan_id: uuid.UUID, body: ReasonBody, principal: Manager, db: DB, ctx: Ctx) -> PlanOut:
    return _plan_action(db, principal, msvc.submit_plan(db, ctx, principal, plan_id, body.reason))


@router.post("/plans/{plan_id}/approve", response_model=PlanOut)
def approve_plan(plan_id: uuid.UUID, body: PlanDecision, principal: Approver, db: DB, ctx: Ctx) -> PlanOut:
    return _plan_action(db, principal, msvc.approve_plan(db, ctx, principal, plan_id, body.reason, body.acknowledge_configuration_gaps))


@router.post("/plans/{plan_id}/return", response_model=PlanOut)
def return_plan(plan_id: uuid.UUID, body: ReasonBody, principal: Approver, db: DB, ctx: Ctx) -> PlanOut:
    return _plan_action(db, principal, msvc.return_plan(db, ctx, principal, plan_id, body.reason))


@router.post("/plans/{plan_id}/withdraw", response_model=PlanOut)
def withdraw_plan(plan_id: uuid.UUID, body: ReasonBody, principal: Manager, db: DB, ctx: Ctx) -> PlanOut:
    return _plan_action(db, principal, msvc.withdraw_plan(db, ctx, principal, plan_id, body.reason))


# ---------------------------------------------------------------- monitoring periods
@router.get("/monitoring-periods", response_model=list[PeriodOut])
def list_periods(principal: Reader, db: DB, project_id: uuid.UUID) -> list[PeriodOut]:
    p = mrv_access.project(db, principal, project_id)
    return [mm.period_out(db, x) for x in msvc.periods(db, p.id)]


@router.post("/monitoring-periods", response_model=PeriodOut, status_code=status.HTTP_201_CREATED)
def create_period(body: PeriodIn, principal: Manager, db: DB, ctx: Ctx) -> PeriodOut:
    return mm.period_out(db, msvc.create_period(db, ctx, principal, body))


@router.get("/monitoring-periods/{period_id}", response_model=PeriodOut)
def get_period(period_id: uuid.UUID, principal: Reader, db: DB) -> PeriodOut:
    return mm.period_out(db, msvc.get_period(db, principal, period_id)[0])


@router.post("/monitoring-periods/{period_id}/{action}", response_model=PeriodOut,
             summary="plan | start | open-collection | submit | close")
def period_action(period_id: uuid.UUID, action: Literal["plan", "start", "open-collection", "submit", "close"], body: ReasonBody,
                  principal: Manager, db: DB, ctx: Ctx) -> PeriodOut:
    if action == "submit":
        return mm.period_out(db, msvc.submit_period(db, ctx, principal, period_id, body.reason))
    return mm.period_out(db, msvc.period_action(db, ctx, principal, period_id, action, body.reason))


# ---------------------------------------------------------------- strata
@router.get("/projects/{project_id}/strata", response_model=list[StratumOut])
def list_strata(project_id: uuid.UUID, principal: FieldOrReader, db: DB, include_history: bool = False) -> list[StratumOut]:
    p = mrv_access.project(db, principal, project_id, P.MRV_READ)
    req = ssvc.required_characteristics(db, p) if p.methodology_status == "CONFIRMED" else []
    return [mm.stratum_out(db, s, req) for s in ssvc.strata(db, p.id, include_history)]


@router.get("/projects/{project_id}/control-site-candidates", response_model=list[ControlCandidate],
            summary="Farms that may serve as a baseline control site (eligible, not participating in this project)")
def control_site_candidates(project_id: uuid.UUID, principal: SamplingManager, db: DB) -> list[ControlCandidate]:
    return [ControlCandidate(**c) for c in ssvc.control_candidates(db, principal, project_id)]


@router.post("/projects/{project_id}/strata", response_model=StratumOut, status_code=status.HTTP_201_CREATED)
def create_stratum(project_id: uuid.UUID, body: StratumIn, principal: SamplingManager, db: DB, ctx: Ctx) -> StratumOut:
    s = ssvc.create_stratum(db, ctx, principal, project_id, body)
    p = mrv_access.project(db, principal, s.project_id, P.SAMPLING_MANAGE)
    return mm.stratum_out(db, s, ssvc.required_characteristics(db, p))


@router.patch("/strata/{stratum_id}", response_model=StratumOut, summary="Edit a DRAFT stratum, or revise an APPROVED one (new version)")
def update_stratum(stratum_id: uuid.UUID, body: StratumUpdate, principal: SamplingManager, db: DB, ctx: Ctx) -> StratumOut:
    s = ssvc.update_stratum(db, ctx, principal, stratum_id, body)
    p = mrv_access.project(db, principal, s.project_id, P.SAMPLING_MANAGE)
    return mm.stratum_out(db, s, ssvc.required_characteristics(db, p))


@router.post("/strata/{stratum_id}/approve", response_model=StratumOut)
def approve_stratum(stratum_id: uuid.UUID, body: ReasonBody, principal: SamplingReviewer, db: DB, ctx: Ctx) -> StratumOut:
    s = ssvc.approve_stratum(db, ctx, principal, stratum_id, body.reason)
    p = mrv_access.project(db, principal, s.project_id, P.SAMPLING_REVIEW)
    return mm.stratum_out(db, s, ssvc.required_characteristics(db, p))


# ---------------------------------------------------------------- sampling designs
@router.get("/sampling-designs", response_model=list[DesignOut])
def list_designs(principal: Reader, db: DB, project_id: uuid.UUID, monitoring_period_id: uuid.UUID | None = None) -> list[DesignOut]:
    p = mrv_access.project(db, principal, project_id)
    stmt = select(SamplingDesign).where(SamplingDesign.project_id == p.id)
    if monitoring_period_id:
        stmt = stmt.where(SamplingDesign.monitoring_period_id == monitoring_period_id)
    return [mm.design_out(db, d) for d in db.scalars(stmt.order_by(SamplingDesign.created_at)).all()]


@router.post("/sampling-designs", response_model=DesignOut, status_code=status.HTTP_201_CREATED)
def create_design(body: DesignIn, principal: SamplingManager, db: DB, ctx: Ctx) -> DesignOut:
    return mm.design_out(db, ssvc.create_design(db, ctx, principal, body))


@router.get("/sampling-designs/{design_id}", response_model=DesignOut)
def get_design(design_id: uuid.UUID, principal: Reader, db: DB) -> DesignOut:
    return mm.design_out(db, ssvc.get_design(db, principal, design_id)[0])


@router.post("/sampling-designs/{design_id}/versions", response_model=DesignVersionOut, status_code=status.HTTP_201_CREATED)
def add_design_version(design_id: uuid.UUID, body: DesignParams, principal: SamplingManager, db: DB, ctx: Ctx) -> DesignVersionOut:
    return mm.design_version_out(db, ssvc.add_design_version(db, ctx, principal, design_id, body))


@router.post("/sampling-designs/{design_id}/versions/{version_id}/approve", response_model=DesignVersionOut)
def approve_design_version(design_id: uuid.UUID, version_id: uuid.UUID, body: ReasonBody, principal: SamplingReviewer, db: DB,
                           ctx: Ctx) -> DesignVersionOut:
    return mm.design_version_out(db, ssvc.approve_design_version(db, ctx, principal, design_id, version_id, body.reason))


@router.post("/sampling-designs/{design_id}/generate-points", response_model=GenerateOut, status_code=status.HTTP_201_CREATED)
def generate_points(design_id: uuid.UUID, principal: SamplingManager, db: DB, ctx: Ctx) -> GenerateOut:
    pts = ssvc.generate_points(db, ctx, principal, design_id)
    out = mm.points_out(db, pts)
    per: dict[str, int] = {}
    for x in out:
        per[x.stratum_code or ""] = per.get(x.stratum_code or "", 0) + 1
    return GenerateOut(created=len(out), per_stratum=per, points=out)


# ---------------------------------------------------------------- sampling points / assignments / relocations
@router.get("/sampling-points", response_model=list[PointOut], summary="Points (collectors see only points assigned to them)")
def list_points(principal: FieldOrReader, db: DB, project_id: uuid.UUID | None = None, monitoring_period_id: uuid.UUID | None = None,
                mine: bool = False) -> list[PointOut]:
    if project_id and principal.has(P.MRV_READ) and not mine:
        mrv_access.project(db, principal, project_id)
    return mm.points_out(db, ssvc.list_points(db, principal, project_id, monitoring_period_id, mine))


@router.post("/sampling-points/assign", response_model=list[PointOut], summary="Assign several points to one collector")
def bulk_assign(body: BulkAssignIn, principal: Assigner, db: DB, ctx: Ctx) -> list[PointOut]:
    return mm.points_out(db, ssvc.bulk_assign(db, ctx, principal, body.point_ids, body.collector_id, body.planned_date, body.instructions))


@router.get("/sampling-points/{point_id}", response_model=PointOut)
def get_point(point_id: uuid.UUID, principal: FieldOrReader, db: DB) -> PointOut:
    return mm.points_out(db, [ssvc.get_point(db, principal, point_id, P.SAMPLING_COLLECT, P.MRV_READ)[0]])[0]


@router.post("/sampling-points/{point_id}/assign", response_model=PointOut)
def assign_point(point_id: uuid.UUID, body: AssignIn, principal: Assigner, db: DB, ctx: Ctx) -> PointOut:
    return mm.points_out(db, [ssvc.assign(db, ctx, principal, point_id, body.collector_id, body.planned_date, body.instructions)])[0]


@router.post("/sampling-points/{point_id}/skip", response_model=PointOut)
def skip_point(point_id: uuid.UUID, body: ReasonBody, principal: SamplingReviewer, db: DB, ctx: Ctx) -> PointOut:
    return mm.points_out(db, [ssvc.skip_point(db, ctx, principal, point_id, body.reason)])[0]


@router.get("/sampling-points/{point_id}/relocations", response_model=list[RelocationOut])
def list_relocations(point_id: uuid.UUID, principal: FieldOrReader, db: DB) -> list[RelocationOut]:
    sp, _ = ssvc.get_point(db, principal, point_id, P.SAMPLING_COLLECT, P.MRV_READ)
    return [mm.relocation_out(r) for r in ssvc.relocations(db, sp.id)]


@router.post("/sampling-points/{point_id}/relocations", response_model=RelocationOut, status_code=status.HTTP_201_CREATED,
             summary="Request a point move (old/new location, reason; needs approval)")
def request_relocation(point_id: uuid.UUID, body: RelocationIn, principal: Relocator, db: DB, ctx: Ctx) -> RelocationOut:
    return mm.relocation_out(ssvc.request_relocation(db, ctx, principal, point_id, body.latitude, body.longitude, body.reason))


@router.post("/relocations/{relocation_id}/decision", response_model=RelocationOut)
def decide_relocation(relocation_id: uuid.UUID, body: RelocationDecision, principal: SamplingReviewer, db: DB, ctx: Ctx) -> RelocationOut:
    return mm.relocation_out(ssvc.decide_relocation(db, ctx, principal, relocation_id, body.decision, body.notes))


# ---------------------------------------------------------------- field collections
@router.get("/field-collections", response_model=list[CollectionOut])
def list_collections(principal: FieldOrReader, db: DB, project_id: uuid.UUID | None = None, monitoring_period_id: uuid.UUID | None = None,
                     mine: bool = False) -> list[CollectionOut]:
    if project_id and principal.has(P.MRV_READ) and not mine:
        mrv_access.project(db, principal, project_id)
    return [mm.collection_out(db, principal, c) for c in ssvc.list_collections(db, principal, project_id, monitoring_period_id, mine)]


@router.post("/field-collections", response_model=CollectionOut, status_code=status.HTTP_201_CREATED)
def start_collection(body: CollectionStart, principal: Collector, db: DB, ctx: Ctx) -> CollectionOut:
    return mm.collection_out(db, principal, ssvc.start_collection(db, ctx, principal, body.sampling_point_id))


@router.get("/field-collections/{collection_id}", response_model=CollectionOut)
def get_collection(collection_id: uuid.UUID, principal: FieldOrReader, db: DB) -> CollectionOut:
    return mm.collection_out(db, principal, ssvc.get_collection(db, principal, collection_id, P.SAMPLING_COLLECT, P.MRV_READ)[0])


@router.patch("/field-collections/{collection_id}", response_model=CollectionOut)
def update_collection(collection_id: uuid.UUID, body: CollectionUpdate, principal: Collector, db: DB, ctx: Ctx) -> CollectionOut:
    return mm.collection_out(db, principal, ssvc.update_collection(db, ctx, principal, collection_id, body))


@router.post("/field-collections/{collection_id}/submit", response_model=CollectionOut)
def submit_collection(collection_id: uuid.UUID, principal: Collector, db: DB, ctx: Ctx) -> CollectionOut:
    return mm.collection_out(db, principal, ssvc.submit_collection(db, ctx, principal, collection_id))


@router.post("/field-collections/{collection_id}/review", response_model=CollectionOut)
def review_collection(collection_id: uuid.UUID, body: CollectionReview, principal: SamplingReviewer, db: DB, ctx: Ctx) -> CollectionOut:
    return mm.collection_out(db, principal, ssvc.review_collection(db, ctx, principal, collection_id, body.decision, body.notes))


@router.post("/field-collections/{collection_id}/correct", response_model=CollectionOut, status_code=status.HTTP_201_CREATED,
             summary="Correct an accepted record: creates a new version that supersedes it once accepted")
def correct_collection(collection_id: uuid.UUID, body: ReasonBody, principal: Corrector, db: DB, ctx: Ctx) -> CollectionOut:
    return mm.collection_out(db, principal, ssvc.correct_collection(db, ctx, principal, collection_id, body.reason))


# ---------------------------------------------------------------- monitoring records & evidence
@router.get("/monitoring-records", response_model=list[MonitoringRecordOut])
def list_records(principal: Reader, db: DB, monitoring_period_id: uuid.UUID, include_history: bool = False) -> list[MonitoringRecordOut]:
    mp, _ = msvc.get_period(db, principal, monitoring_period_id)
    return [mm.record_out(db, r) for r in msvc.monitoring_records(db, mp.id, include_history)]


@router.post("/monitoring-records", response_model=MonitoringRecordOut, status_code=status.HTTP_201_CREATED)
def add_record(body: MonitoringRecordIn, principal: Recorder, db: DB, ctx: Ctx) -> MonitoringRecordOut:
    return mm.record_out(db, msvc.add_monitoring_record(db, ctx, principal, body))


@router.post("/monitoring-records/{record_id}/amend", response_model=MonitoringRecordOut, summary="Correct a record (new version)")
def amend_record(record_id: uuid.UUID, body: MonitoringRecordAmend, principal: Recorder, db: DB, ctx: Ctx) -> MonitoringRecordOut:
    return mm.record_out(db, msvc.amend_monitoring_record(db, ctx, principal, record_id, body))


@router.get("/evidence", response_model=list[EvidenceOut])
def list_evidence(principal: FieldOrReader, db: DB, project_id: uuid.UUID, monitoring_period_id: uuid.UUID | None = None,
                  entity_id: uuid.UUID | None = None) -> list[EvidenceOut]:
    p = project_repo.get(db, project_id)
    if p is None:
        raise mrv_access.not_found()
    if not principal.can_in_org(P.MRV_READ, p.organization_id):  # collectors: evidence of their own collection / point only
        if entity_id is None:
            mrv_access.project(db, principal, project_id)
        elif db.get(FieldCollectionRecord, entity_id) is not None:
            ssvc.get_collection(db, principal, entity_id, P.SAMPLING_COLLECT)
        else:
            ssvc.get_point(db, principal, entity_id, P.SAMPLING_COLLECT)
    return [mm.evidence_out(e) for e in msvc.evidence_for(db, project_id, monitoring_period_id, entity_id)]


@router.post("/evidence", response_model=EvidenceOut, status_code=status.HTTP_201_CREATED, summary="MRV evidence (file optional for GPS / notes)")
def add_evidence(principal: EvidenceWriter, db: DB, ctx: Ctx, project_id: Annotated[uuid.UUID, Form()],
                 entity_type: Annotated[Literal["PROJECT", "FARM", "MONITORING_PERIOD", "SAMPLING_POINT", "FIELD_COLLECTION", "MONITORING_RECORD"],
                                        Form()],
                 entity_id: Annotated[uuid.UUID, Form()],
                 evidence_type: Annotated[Literal["FIELD_PHOTO", "FIELD_NOTE", "PRACTICE_RECORD", "DOCUMENT", "GPS", "OBSERVATION"], Form()],
                 description: Annotated[str | None, Form(max_length=2000)] = None, latitude: Annotated[float | None, Form(ge=-90, le=90)] = None,
                 longitude: Annotated[float | None, Form(ge=-180, le=180)] = None, captured_at: Annotated[datetime | None, Form()] = None,
                 file: Annotated[UploadFile | None, File()] = None) -> EvidenceOut:
    data = read_upload(file) if file is not None else None
    return mm.evidence_out(msvc.add_evidence(db, ctx, principal, project_id=project_id, entity_type=entity_type, entity_id=entity_id,
                                             evidence_type=evidence_type, description=description, latitude=latitude, longitude=longitude,
                                             captured_at=captured_at, filename=file.filename if file else None, data=data))


# ---------------------------------------------------------------- datasets & QA
@router.get("/datasets", response_model=list[DatasetOut])
def list_datasets(principal: Reader, db: DB, project_id: uuid.UUID, monitoring_period_id: uuid.UUID | None = None) -> list[DatasetOut]:
    p = mrv_access.project(db, principal, project_id)
    stmt = select(MrvDataset).where(MrvDataset.project_id == p.id)
    if monitoring_period_id:
        stmt = stmt.where(MrvDataset.monitoring_period_id == monitoring_period_id)
    return [mm.dataset_out(db, principal, d) for d in db.scalars(stmt.order_by(MrvDataset.created_at.desc())).all()]


@router.post("/datasets", response_model=DatasetOut, status_code=status.HTTP_201_CREATED)
def create_dataset(body: DatasetIn, principal: Manager, db: DB, ctx: Ctx) -> DatasetOut:
    return mm.dataset_out(db, principal, msvc.create_dataset(db, ctx, principal, body))


@router.get("/datasets/{dataset_id}", response_model=DatasetOut)
def get_dataset(dataset_id: uuid.UUID, principal: Reader, db: DB) -> DatasetOut:
    return mm.dataset_out(db, principal, msvc.get_dataset(db, principal, dataset_id)[0])


@router.get("/datasets/{dataset_id}/snapshot", summary="The frozen record list (lineage) of a submitted dataset")
def dataset_snapshot(dataset_id: uuid.UUID, principal: Reader, db: DB) -> dict[str, Any]:
    import json
    ds, _ = msvc.get_dataset(db, principal, dataset_id)
    return {"snapshot_sha256": ds.snapshot_sha256, "snapshot": json.loads(ds.snapshot) if ds.snapshot else None}


@router.post("/datasets/{dataset_id}/submit", response_model=DatasetOut)
def submit_dataset(dataset_id: uuid.UUID, body: ReasonBody, principal: Manager, db: DB, ctx: Ctx) -> DatasetOut:
    return mm.dataset_out(db, principal, msvc.submit_dataset(db, ctx, principal, dataset_id, body.reason))


@router.post("/datasets/{dataset_id}/approve", response_model=DatasetOut)
def approve_dataset(dataset_id: uuid.UUID, body: ReasonBody, principal: Approver, db: DB, ctx: Ctx) -> DatasetOut:
    return mm.dataset_out(db, principal, msvc.approve_dataset(db, ctx, principal, dataset_id, body.reason))


@router.post("/datasets/{dataset_id}/reject", response_model=DatasetOut)
def reject_dataset(dataset_id: uuid.UUID, body: ReasonBody, principal: Approver, db: DB, ctx: Ctx) -> DatasetOut:
    return mm.dataset_out(db, principal, msvc.reject_dataset(db, ctx, principal, dataset_id, body.reason))


def _qa_view(db: DB, principal: Principal, ds: MrvDataset) -> QaView:
    p = mrv_access.project(db, principal, ds.project_id)
    org = p.organization_id
    reviews = msvc.qa_reviews(db, ds.id)
    passed = bool(reviews) and reviews[-1].result == "PASS"
    return QaView(dataset=mm.dataset_out(db, principal, ds), checks=msvc.qa_checks(db, ds),
                  reviews=[mm.qa_review_out(r) for r in reviews],
                  can_start=ds.status == "SUBMITTED" and principal.can_in_org(P.MRV_REVIEW, org),
                  can_complete=ds.status == "QA_REVIEW" and principal.can_in_org(P.MRV_REVIEW, org) and ds.submitted_by != principal.user_id,
                  can_approve=ds.status == "QA_REVIEW" and passed and principal.can_in_org(P.MRV_APPROVE, org)
                  and ds.submitted_by != principal.user_id)


@router.get("/qa/{dataset_id}", response_model=QaView, summary="Automated QA checks + review history")
def qa_view(dataset_id: uuid.UUID, principal: Reader, db: DB) -> QaView:
    return _qa_view(db, principal, msvc.get_dataset(db, principal, dataset_id)[0])


@router.post("/qa/{dataset_id}/start", response_model=QaReviewOut)
def qa_start(dataset_id: uuid.UUID, principal: QaReviewer, db: DB, ctx: Ctx) -> QaReviewOut:
    return mm.qa_review_out(msvc.start_qa(db, ctx, principal, dataset_id))


@router.post("/qa/{dataset_id}/complete", response_model=QaReviewOut)
def qa_complete(dataset_id: uuid.UUID, body: QaComplete, principal: QaReviewer, db: DB, ctx: Ctx) -> QaReviewOut:
    return mm.qa_review_out(msvc.complete_qa(db, ctx, principal, dataset_id, body.result, body.notes))


