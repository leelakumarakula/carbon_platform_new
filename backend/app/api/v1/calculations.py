"""Phase 7 calculation API (`/api/v1/calculations`). Only modules in the application registry are ever used here; no endpoint
accepts a calculated or final tCO2e value (request bodies forbid unknown fields)."""
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.api.deps import DB, Ctx, require
from app.calculation import registry
from app.core.errors import Conflict
from app.schemas.calculation import (
    CalcPeriodRef,
    CalcProjectOut,
    CalcQaView,
    CompareOut,
    InputsOut,
    LineageOut,
    ModuleOut,
    OutputsOut,
    QaCompleteIn,
    ReadinessOut,
    ReasonBody,
    RunIn,
    RunOut,
)
from app.security.permissions import P
from app.security.principal import Principal
from app.services import calculation_mappers as cm
from app.services import calculation_service as cs

router = APIRouter(prefix="/calculations", tags=["calculations"])

Reader = Annotated[Principal, Depends(require(P.CALCULATION_READ))]
Manager = Annotated[Principal, Depends(require(P.CALCULATION_MANAGE))]
Reviewer = Annotated[Principal, Depends(require(P.CALCULATION_REVIEW))]
Approver = Annotated[Principal, Depends(require(P.CALCULATION_APPROVE))]


@router.get("/modules", response_model=list[ModuleOut], summary="Registered methodology calculation modules (none in Phase 7)")
def list_modules(principal: Reader) -> list[ModuleOut]:
    return [cm.module_out(m) for m in registry.modules()]


@router.get("/projects", response_model=list[CalcProjectOut], summary="Projects in monitoring or later (calculation.read scope)")
def list_projects(principal: Reader, db: DB) -> list[CalcProjectOut]:
    return [CalcProjectOut(id=p.id, project_code=p.project_code, name=p.name, status=p.status, environment=p.environment,
                           periods=[CalcPeriodRef(id=m.id, name=m.name, period_number=m.period_number, status=m.status, start_date=m.start_date,
                                                  end_date=m.end_date) for m in periods]) for p, periods in cs.projects(db, principal)]


@router.get("/projects/{project_id}/readiness", response_model=ReadinessOut, summary="Deterministic calculation blockers for a period")
def readiness(project_id: uuid.UUID, principal: Reader, db: DB, monitoring_period_id: uuid.UUID,
              crediting_period_id: uuid.UUID | None = None) -> ReadinessOut:
    return cm.readiness_out(db, cs.readiness(db, principal, project_id, monitoring_period_id, crediting_period_id))


@router.get("/runs", response_model=list[RunOut])
def list_runs(principal: Reader, db: DB, project_id: uuid.UUID, monitoring_period_id: uuid.UUID | None = None) -> list[RunOut]:
    return [cm.run_out(db, principal, r) for r in cs.runs(db, principal, project_id, monitoring_period_id)]


@router.post("/runs", response_model=RunOut, status_code=status.HTTP_201_CREATED)
def create_run(body: RunIn, principal: Manager, db: DB, ctx: Ctx) -> RunOut:
    return cm.run_out(db, principal, cs.create_run(db, ctx, principal, body))


@router.get("/runs/{run_id}", response_model=RunOut)
def get_run(run_id: uuid.UUID, principal: Reader, db: DB) -> RunOut:
    return cm.run_out(db, principal, cs.get_run(db, principal, run_id)[0])


@router.post("/runs/{run_id}/freeze", response_model=RunOut, summary="Readiness check + frozen input snapshot (BLOCKED when not ready)")
def freeze(run_id: uuid.UUID, principal: Manager, db: DB, ctx: Ctx) -> RunOut:
    return cm.run_out(db, principal, cs.freeze(db, ctx, principal, run_id))


@router.get("/runs/{run_id}/inputs", response_model=InputsOut)
def run_inputs(run_id: uuid.UUID, principal: Reader, db: DB) -> InputsOut:
    return cm.inputs_out(db, cs.get_run(db, principal, run_id)[0])


@router.post("/runs/{run_id}/execute", response_model=RunOut, summary="Run the registered module on the frozen snapshot (synchronous)")
def execute(run_id: uuid.UUID, principal: Manager, db: DB, ctx: Ctx) -> RunOut:
    return cm.run_out(db, principal, cs.execute(db, ctx, principal, run_id))


@router.get("/runs/{run_id}/outputs", response_model=OutputsOut)
def run_outputs(run_id: uuid.UUID, principal: Reader, db: DB) -> OutputsOut:
    return cm.outputs_out(db, cs.get_run(db, principal, run_id)[0])


@router.post("/runs/{run_id}/submit", response_model=RunOut)
def submit(run_id: uuid.UUID, principal: Manager, db: DB, ctx: Ctx) -> RunOut:
    return cm.run_out(db, principal, cs.submit(db, ctx, principal, run_id))


@router.post("/runs/{run_id}/cancel", response_model=RunOut)
def cancel(run_id: uuid.UUID, body: ReasonBody, principal: Manager, db: DB, ctx: Ctx) -> RunOut:
    return cm.run_out(db, principal, cs.cancel(db, ctx, principal, run_id, body.reason))


@router.post("/runs/{run_id}/approve", response_model=RunOut)
def approve(run_id: uuid.UUID, body: ReasonBody, principal: Approver, db: DB, ctx: Ctx) -> RunOut:
    return cm.run_out(db, principal, cs.approve(db, ctx, principal, run_id, body.reason))


@router.post("/runs/{run_id}/reject", response_model=RunOut)
def reject(run_id: uuid.UUID, body: ReasonBody, principal: Approver, db: DB, ctx: Ctx) -> RunOut:
    return cm.run_out(db, principal, cs.reject(db, ctx, principal, run_id, body.reason))


@router.post("/runs/{run_id}/recalculate", response_model=RunOut, status_code=status.HTTP_201_CREATED,
             summary="New run linked to this one (the old run is never changed)")
def recalculate(run_id: uuid.UUID, body: ReasonBody, principal: Manager, db: DB, ctx: Ctx) -> RunOut:
    return cm.run_out(db, principal, cs.recalculate(db, ctx, principal, run_id, body.reason))


@router.get("/runs/{run_id}/compare/{other_id}", response_model=CompareOut)
def compare(run_id: uuid.UUID, other_id: uuid.UUID, principal: Reader, db: DB) -> CompareOut:
    a, b = cs.get_run(db, principal, run_id)[0], cs.get_run(db, principal, other_id)[0]
    if a.project_id != b.project_id:
        raise Conflict("Only runs of the same project can be compared.", error_code="RUNS_NOT_COMPARABLE")
    return cm.compare(db, principal, a, b)


@router.get("/runs/{run_id}/lineage", response_model=LineageOut)
def run_lineage(run_id: uuid.UUID, principal: Reader, db: DB) -> LineageOut:
    return cm.lineage(db, principal, cs.get_run(db, principal, run_id)[0])


@router.get("/qa/{run_id}", response_model=CalcQaView)
def qa_view(run_id: uuid.UUID, principal: Reader, db: DB) -> CalcQaView:
    return cm.qa_view(db, principal, cs.get_run(db, principal, run_id)[0])


@router.post("/qa/{run_id}/start", response_model=CalcQaView)
def start_qa(run_id: uuid.UUID, principal: Reviewer, db: DB, ctx: Ctx) -> CalcQaView:
    cs.start_qa(db, ctx, principal, run_id)
    return cm.qa_view(db, principal, cs.get_run(db, principal, run_id)[0])


@router.post("/qa/{run_id}/complete", response_model=CalcQaView)
def complete_qa(run_id: uuid.UUID, body: QaCompleteIn, principal: Reviewer, db: DB, ctx: Ctx) -> CalcQaView:
    cs.complete_qa(db, ctx, principal, run_id, body.result, body.notes)
    return cm.qa_view(db, principal, cs.get_run(db, principal, run_id)[0])

