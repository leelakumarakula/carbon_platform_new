"""Phase 7 calculation schemas. Request bodies forbid unknown fields: no request can carry a calculated or final tCO2e value —
the server computes every value from the frozen inputs (decision A1, spec role 4.10)."""
import uuid
from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from app.schemas.common import Reason, UtcDatetime

CALCULATED_LABEL = "Calculated tCO2e — not verified, not issued"
DEMO_LABEL = "DEMO — not carbon accounting"


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RunIn(_Strict):
    project_id: uuid.UUID
    monitoring_period_id: uuid.UUID
    crediting_period_id: uuid.UUID | None = None
    notes: Reason | None = None


class ReasonBody(_Strict):
    reason: Reason


class QaCompleteIn(_Strict):
    result: Literal["PASS", "FAIL"]
    notes: Reason


# ---------------------------------------------------------------- outputs
class Blocker(BaseModel):
    code: str
    message: str
    reason: str | None = None
    details: dict[str, Any] = {}


class CalcCheck(BaseModel):
    key: str
    label: str
    result: Literal["PASS", "FAIL", "WARN"]
    details: list[str] = []


class StepStatus(BaseModel):
    step: str
    status: str                 # IMPLEMENTED / NOT_INCLUDED_DEMO / NOT_CONFIGURED
    rule_code: str | None = None
    label: str


class CalcPeriodRef(BaseModel):
    id: uuid.UUID
    name: str
    period_number: int
    status: str
    start_date: date
    end_date: date


class CalcProjectOut(BaseModel):
    id: uuid.UUID
    project_code: str
    name: str
    status: str
    environment: str
    periods: list[CalcPeriodRef]


class ModuleOut(BaseModel):
    code: str
    version: str
    methodology_code: str
    version_label: str
    calculation_rules_version: int
    readiness: str
    label: str
    rules: dict[str, str]
    variables: list[dict[str, Any]]
    constants: list[dict[str, Any]]
    steps: list[dict[str, Any]]


class ReadinessOut(BaseModel):
    project_id: uuid.UUID
    project_code: str
    project_status: str
    environment: str
    monitoring_period_id: uuid.UUID
    monitoring_period: str
    methodology_label: str | None
    is_demo_illustrative: bool
    module_code: str | None
    module_version: str | None
    module_readiness: str | None
    dataset_id: uuid.UUID | None
    dataset_code: str | None
    dataset_status: str | None
    ready: bool
    blockers: list[Blocker]
    warnings: list[str]
    steps: list[StepStatus]
    input_rows: int
    calculation_rules: list[dict[str, Any]]


class RunOut(BaseModel):
    id: uuid.UUID
    run_code: str
    project_id: uuid.UUID
    project_code: str
    monitoring_period_id: uuid.UUID
    monitoring_period: str
    period_start: date
    period_end: date
    crediting_period_id: uuid.UUID | None
    mrv_dataset_id: uuid.UUID | None
    dataset_code: str | None
    methodology_label: str
    methodology_version_id: uuid.UUID
    is_demo_illustrative: bool
    calculation_rules_version: int
    module_code: str | None
    module_version: str | None
    module_readiness: str | None
    engine_version: str
    input_sha256: str | None
    output_sha256: str | None
    net_result: str | None
    net_unit: str | None
    status: str
    status_reason: str | None
    blockers: list[Blocker]
    notes: str | None
    recalculation_of_run_id: uuid.UUID | None
    recalculation_of_code: str | None
    recalculation_reason: str | None
    superseded_by_run_id: uuid.UUID | None
    superseded_by_code: str | None
    superseded_at: UtcDatetime | None
    environment: str
    created_by_name: str | None
    created_at: UtcDatetime
    frozen_by_name: str | None
    frozen_at: UtcDatetime | None
    executed_by_name: str | None
    executed_at: UtcDatetime | None
    submitted_by_name: str | None
    submitted_at: UtcDatetime | None
    approved_by_name: str | None
    approved_at: UtcDatetime | None
    closed_by_name: str | None
    closed_at: UtcDatetime | None
    result_label: str = CALCULATED_LABEL
    demo_label: str | None
    steps: list[StepStatus]
    can_freeze: bool
    can_execute: bool
    can_submit: bool
    can_cancel: bool
    can_review: bool
    can_approve: bool
    can_recalculate: bool


class InputOut(BaseModel):
    seq: int
    variable_code: str
    source_type: str
    source_id: uuid.UUID | None
    source_version: int | None
    source_code: str | None
    value: str
    value_kind: str
    unit: str | None
    level: str
    stratum_id: uuid.UUID | None
    farm_id: uuid.UUID | None
    sampling_point_id: uuid.UUID | None
    field_collection_id: uuid.UUID | None
    sample_id: uuid.UUID | None
    root_sample_id: uuid.UUID | None
    requirement_source: str | None
    source_reference: str | None
    source_sha256: str | None


class InputsOut(BaseModel):
    run_id: uuid.UUID
    input_sha256: str | None
    snapshot: dict[str, Any] | None
    inputs: list[InputOut]


class OutputOut(BaseModel):
    seq: int
    step: str
    output_code: str
    rule_code: str
    calculation_rule_id: uuid.UUID
    equation_reference: str | None
    value: str
    unit: str
    level: str
    entity_id: uuid.UUID | None
    input_seqs: list[int]
    output_seqs: list[int]
    is_final: bool


class OutputsOut(BaseModel):
    run_id: uuid.UUID
    output_sha256: str | None
    net_result: str | None
    net_unit: str | None
    result_label: str = CALCULATED_LABEL
    demo_label: str | None
    steps: list[StepStatus]
    outputs: list[OutputOut]


class QaReviewOut(BaseModel):
    id: uuid.UUID
    started_by_name: str | None
    started_at: UtcDatetime
    completed_by_name: str | None
    completed_at: UtcDatetime | None
    result: str | None
    notes: str | None
    checks: list[CalcCheck]


class CalcQaView(BaseModel):
    run: RunOut
    checks: list[CalcCheck]
    reviews: list[QaReviewOut]
    can_start: bool
    can_complete: bool
    can_approve: bool
    blocked_reasons: list[str]


class LineageSource(BaseModel):
    seq: int
    variable_code: str
    source_type: str
    value: str
    unit: str | None
    chain: dict[str, Any]


class LineageOutput(BaseModel):
    seq: int
    step: str
    output_code: str
    value: str
    unit: str
    rule: dict[str, Any]
    input_seqs: list[int]
    output_seqs: list[int]
    is_final: bool


class LineageOut(BaseModel):
    run: RunOut
    methodology: dict[str, Any]
    dataset: dict[str, Any] | None
    final: LineageOutput | None
    outputs: list[LineageOutput]
    inputs: list[LineageSource]
    qa_reviews: list[QaReviewOut]
    history: list[dict[str, Any]]
    # Phase 8A: internal pre-verification records of the run (not verification)
    findings: list[dict[str, Any]] = []
    reports: list[dict[str, Any]] = []
    readiness: list[dict[str, Any]] = []


class CompareOut(BaseModel):
    run_a: RunOut
    run_b: RunOut
    same_inputs: bool
    same_outputs: bool
    changed_fields: dict[str, list[Any]]
    inputs_added: list[dict[str, Any]]
    inputs_removed: list[dict[str, Any]]
    inputs_changed: list[dict[str, Any]]
    outputs_changed: list[dict[str, Any]]


class HistoryRow(BaseModel):
    action: str
    from_status: str | None
    to_status: str | None
    user_name: str | None
    at: UtcDatetime
    reason: str | None
