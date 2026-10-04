"""Methodology catalog + versions (/methodologies) and project methodology selection (/projects/{id}/methodology)."""
import uuid
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Body, Depends, File, Form, UploadFile, status
from pydantic import BaseModel, StringConstraints

from app.api.deps import DB, Ctx, read_upload, require
from app.schemas.common import IdRef, validate_payload
from app.schemas.methodologies import (
    ApplicabilityRuleIn,
    CalculationModuleOption,
    CalculationRuleIn,
    ChangeOut,
    ConfirmIn,
    EvaluationIn,
    EvaluationOut,
    GeneralRuleIn,
    MethodologyIn,
    MethodologyOut,
    MethodologyUpdate,
    ModuleSelectionIn,
    MonitoringRuleIn,
    ProjectMethodologyView,
    ReviewIn,
    ReviewOut,
    RuleKind,
    RuleOut,
    UnlockIn,
    VersionDetail,
    VersionIn,
    VersionTransition,
    VersionUpdate,
)
from app.schemas.projects import ReasonBody
from app.security.permissions import P
from app.security.principal import Principal
from app.services import methodology_service as svc
from app.services import project_methodology_service as pms
from app.services import project_service as psvc
from app.services.methodology_mappers import (
    change_out,
    evaluation_out,
    methodology_out,
    project_view,
    rule_out,
    version_detail,
)

router = APIRouter(tags=["methodologies"])
Reader = Annotated[Principal, Depends(require(P.METHODOLOGIES_READ))]
Manager = Annotated[Principal, Depends(require(P.METHODOLOGIES_MANAGE))]
Approver = Annotated[Principal, Depends(require(P.METHODOLOGIES_APPROVE))]
ProjectReader = Annotated[Principal, Depends(require(P.PROJECTS_READ))]
RULE_SCHEMAS: dict[str, type[BaseModel]] = {"applicability": ApplicabilityRuleIn, "monitoring": MonitoringRuleIn,
                                            "calculation": CalculationRuleIn, "general": GeneralRuleIn}


# ---------------------------------------------------------------- catalog
@router.get("/methodologies", response_model=list[MethodologyOut])
def list_methodologies(principal: Reader, db: DB, environment: Literal["LIVE", "DEMO"] | None = None,
                       standard_id: uuid.UUID | None = None) -> list[MethodologyOut]:
    return [methodology_out(db, m) for m in svc.list_methodologies(db, principal, environment, standard_id)]


@router.post("/methodologies", response_model=MethodologyOut, status_code=status.HTTP_201_CREATED)
def create_methodology(body: MethodologyIn, principal: Manager, db: DB, ctx: Ctx) -> MethodologyOut:
    return methodology_out(db, svc.create_methodology(db, ctx, principal, body))


@router.get("/methodologies/versions/{version_id}", response_model=VersionDetail)
def get_version(version_id: uuid.UUID, principal: Reader, db: DB) -> VersionDetail:
    m, v = svc.get_version(db, principal, version_id)
    return version_detail(db, principal, m, v)


@router.patch("/methodologies/versions/{version_id}", response_model=VersionDetail)
def update_version(version_id: uuid.UUID, body: VersionUpdate, principal: Manager, db: DB, ctx: Ctx) -> VersionDetail:
    v = svc.update_version(db, ctx, principal, version_id, body)
    m, v = svc.get_version(db, principal, v.id)
    return version_detail(db, principal, m, v)


@router.post("/methodologies/versions/{version_id}/rules/{kind}", response_model=RuleOut, status_code=status.HTTP_201_CREATED)
def add_rule(version_id: uuid.UUID, kind: RuleKind, principal: Manager, db: DB, ctx: Ctx,
             body: Annotated[dict[str, Any], Body()]) -> RuleOut:
    data: BaseModel = validate_payload(RULE_SCHEMAS[kind], body)
    return rule_out(kind, svc.add_rule(db, ctx, principal, version_id, kind, data))  # type: ignore[arg-type]


@router.delete("/methodologies/versions/{version_id}/rules/{kind}/{rule_id}", status_code=status.HTTP_204_NO_CONTENT,
               summary="Remove a rule from a DRAFT version (recorded in the change history)")
def delete_rule(version_id: uuid.UUID, kind: RuleKind, rule_id: uuid.UUID, body: ReasonBody, principal: Manager, db: DB, ctx: Ctx) -> None:
    svc.delete_rule(db, ctx, principal, version_id, kind, rule_id, body.reason)


@router.get("/methodologies/versions/{version_id}/calculation-modules", response_model=list[CalculationModuleOption],
            summary="Calculation modules the platform has, with their compatibility for this version")
def calculation_modules(version_id: uuid.UUID, principal: Reader, db: DB) -> list[CalculationModuleOption]:
    m, v, mods = svc.compatible_modules(db, principal, version_id)
    return [CalculationModuleOption(code=mod.code, version=mod.version, label=mod.label, methodology_code=mod.methodology_code,
                                    version_label=mod.version_label, readiness=mod.readiness, compatible=ok,
                                    selected=v.calculation_module_code == mod.code,
                                    calculation_rules=list(mod.calculation_rule_definitions),
                                    monitoring_rules=list(mod.monitoring_rule_definitions),
                                    sampling_parameters=dict(mod.sampling_parameters), assumptions=list(mod.assumptions),
                                    variables=mod.declaration()["variables"]) for mod, ok in mods]


@router.post("/methodologies/versions/{version_id}/calculation-module", response_model=VersionDetail,
             summary="Choose (or clear) the calculation module of a DRAFT version; copies the module's rule set")
def select_calculation_module(version_id: uuid.UUID, body: ModuleSelectionIn, principal: Manager, db: DB, ctx: Ctx) -> VersionDetail:
    svc.select_calculation_module(db, ctx, principal, version_id, body.module_code, body.reason)
    return _detail(db, principal, version_id)


class ReadinessDecision(BaseModel):
    approve: bool
    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=1000)]


@router.post("/methodologies/versions/{version_id}/calculation-readiness/request", response_model=VersionDetail,
             summary="Request production readiness of the selected calculation module (evidence summary required)")
def request_readiness(version_id: uuid.UUID, body: ReasonBody, principal: Manager, db: DB, ctx: Ctx) -> VersionDetail:
    svc.request_calculation_readiness(db, ctx, principal, version_id, body.reason)
    return _detail(db, principal, version_id)


@router.post("/methodologies/versions/{version_id}/calculation-readiness/decide", response_model=VersionDetail,
             summary="Approve or reject the open readiness request (not the requester)")
def decide_readiness(version_id: uuid.UUID, body: ReadinessDecision, principal: Approver, db: DB, ctx: Ctx) -> VersionDetail:
    svc.decide_calculation_readiness(db, ctx, principal, version_id, body.approve, body.reason)
    return _detail(db, principal, version_id)


@router.post("/methodologies/versions/{version_id}/calculation-readiness/revoke", response_model=VersionDetail)
def revoke_readiness(version_id: uuid.UUID, body: ReasonBody, principal: Approver, db: DB, ctx: Ctx) -> VersionDetail:
    svc.revoke_calculation_readiness(db, ctx, principal, version_id, body.reason)
    return _detail(db, principal, version_id)


def _detail(db: DB, principal: Principal, version_id: uuid.UUID) -> VersionDetail:
    m, v = svc.get_version(db, principal, version_id)
    return version_detail(db, principal, m, v)


@router.post("/methodologies/versions/{version_id}/submit", response_model=VersionDetail)
def submit_version(version_id: uuid.UUID, body: VersionTransition, principal: Manager, db: DB, ctx: Ctx) -> VersionDetail:
    svc.submit_version(db, ctx, principal, version_id, body.reason)
    return _detail(db, principal, version_id)


@router.post("/methodologies/versions/{version_id}/approve", response_model=VersionDetail)
def approve_version(version_id: uuid.UUID, body: VersionTransition, principal: Approver, db: DB, ctx: Ctx) -> VersionDetail:
    svc.approve_version(db, ctx, principal, version_id, body.reason, body.supersedes_version_id)
    return _detail(db, principal, version_id)


@router.post("/methodologies/versions/{version_id}/return", response_model=VersionDetail)
def return_version(version_id: uuid.UUID, body: VersionTransition, principal: Approver, db: DB, ctx: Ctx) -> VersionDetail:
    svc.return_version(db, ctx, principal, version_id, body.reason)
    return _detail(db, principal, version_id)


@router.post("/methodologies/versions/{version_id}/retire", response_model=VersionDetail)
def retire_version(version_id: uuid.UUID, body: VersionTransition, principal: Manager, db: DB, ctx: Ctx) -> VersionDetail:
    svc.retire_version(db, ctx, principal, version_id, body.reason)
    return _detail(db, principal, version_id)


@router.post("/methodologies/versions/{version_id}/withdraw", response_model=VersionDetail)
def withdraw_version(version_id: uuid.UUID, body: VersionTransition, principal: Manager, db: DB, ctx: Ctx) -> VersionDetail:
    svc.withdraw_version(db, ctx, principal, version_id, body.reason)
    return _detail(db, principal, version_id)


@router.get("/methodologies/{methodology_id}", response_model=MethodologyOut)
def get_methodology(methodology_id: uuid.UUID, principal: Reader, db: DB) -> MethodologyOut:
    return methodology_out(db, svc.get_methodology(db, principal, methodology_id))


@router.patch("/methodologies/{methodology_id}", response_model=MethodologyOut)
def update_methodology(methodology_id: uuid.UUID, body: MethodologyUpdate, principal: Manager, db: DB, ctx: Ctx) -> MethodologyOut:
    return methodology_out(db, svc.update_methodology(db, ctx, principal, methodology_id, body))


@router.post("/methodologies/{methodology_id}/versions", response_model=VersionDetail, status_code=status.HTTP_201_CREATED,
             summary="New DRAFT version (optionally copying the rules of an existing version)")
def create_version(methodology_id: uuid.UUID, body: VersionIn, principal: Manager, db: DB, ctx: Ctx) -> VersionDetail:
    v = svc.create_version(db, ctx, principal, methodology_id, body)
    return _detail(db, principal, v.id)


@router.get("/methodologies/{methodology_id}/history", response_model=list[ChangeOut])
def methodology_history(methodology_id: uuid.UUID, principal: Reader, db: DB) -> list[ChangeOut]:
    return [change_out(c) for c in svc.history(db, principal, methodology_id)]


@router.post("/methodologies/{methodology_id}/documents", response_model=IdRef, status_code=status.HTTP_201_CREATED)
def upload_document(methodology_id: uuid.UUID, principal: Manager, db: DB, ctx: Ctx, file: Annotated[UploadFile, File()],
                    category: Annotated[str, Form(max_length=30)] = "METHODOLOGY_DOCUMENT", title: Annotated[str, Form(max_length=200)] = "",
                    version_id: Annotated[uuid.UUID | None, Form()] = None, as_source: Annotated[bool, Form()] = False) -> IdRef:
    return IdRef(id=svc.upload_document(db, ctx, principal, methodology_id, version_id, category, title, file.filename, read_upload(file),
                                        as_source))


# ---------------------------------------------------------------- project methodology selection
@router.get("/projects/{project_id}/methodology", response_model=ProjectMethodologyView)
def project_methodology(project_id: uuid.UUID, principal: ProjectReader, db: DB) -> ProjectMethodologyView:
    return project_view(db, principal, psvc.get_project(db, principal, project_id))


@router.post("/projects/{project_id}/methodology/candidates", response_model=EvaluationOut, status_code=status.HTTP_201_CREATED,
             summary="Run the deterministic candidate rules (proposals only; nothing is selected)")
def evaluate_candidates(project_id: uuid.UUID, body: EvaluationIn, principal: ProjectReader, db: DB, ctx: Ctx) -> EvaluationOut:
    return evaluation_out(db, pms.run_evaluation(db, ctx, principal, project_id, body.declared_facts))


@router.get("/projects/{project_id}/methodology/evaluations", response_model=list[EvaluationOut])
def list_evaluations(project_id: uuid.UUID, principal: ProjectReader, db: DB) -> list[EvaluationOut]:
    return [evaluation_out(db, e) for e in pms.evaluations(db, principal, project_id)]


@router.post("/projects/{project_id}/methodology/reviews", response_model=ReviewOut, status_code=status.HTTP_201_CREATED,
             summary="Methodology specialist recommendation for one candidate")
def review_candidate(project_id: uuid.UUID, body: ReviewIn, principal: ProjectReader, db: DB, ctx: Ctx) -> ReviewOut:
    rv = pms.review_candidate(db, ctx, principal, project_id, body)
    return ReviewOut(id=rv.id, evaluation_result_id=rv.evaluation_result_id, recommendation=rv.recommendation, notes=rv.notes,
                     evidence_acknowledged=rv.evidence_acknowledged, reviewed_by=rv.reviewed_by, reviewed_at=rv.reviewed_at)


@router.post("/projects/{project_id}/methodology/confirm", response_model=ProjectMethodologyView,
             summary="Confirm a recommended candidate: locks methodology + version")
def confirm_methodology(project_id: uuid.UUID, body: ConfirmIn, principal: ProjectReader, db: DB, ctx: Ctx) -> ProjectMethodologyView:
    pms.confirm(db, ctx, principal, project_id, body)
    return project_view(db, principal, psvc.get_project(db, principal, project_id))


@router.post("/projects/{project_id}/methodology/unlock", response_model=ProjectMethodologyView,
             summary="Explicitly unlock (audited, reason required); the project returns to methodology review")
def unlock_methodology(project_id: uuid.UUID, body: UnlockIn, principal: ProjectReader, db: DB, ctx: Ctx) -> ProjectMethodologyView:
    pms.unlock(db, ctx, principal, project_id, body.reason)
    return project_view(db, principal, psvc.get_project(db, principal, project_id))
