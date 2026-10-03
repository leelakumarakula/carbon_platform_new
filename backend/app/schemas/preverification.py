"""Phase 8A schemas — internal pre-verification (findings, reports, readiness). Request bodies forbid unknown fields."""
import uuid
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, StringConstraints

from app.schemas.calculation import Blocker
from app.schemas.common import Reason, UtcDatetime

READINESS_LABEL = "Internal readiness — not verification"
READY_MEANING = "Internally approved for submission to verification."
# B3: exactly the six finding categories of the specification (section 22); stored as codes
FindingCategory = Literal["OBSERVATION", "NON_CONFORMITY", "CLARIFICATION", "MISSING_EVIDENCE", "CALCULATION_ISSUE", "METHODOLOGY_ISSUE"]
CATEGORY_LABELS = {"OBSERVATION": "Observation", "NON_CONFORMITY": "Non-conformity", "CLARIFICATION": "Clarification",
                   "MISSING_EVIDENCE": "Missing Evidence", "CALCULATION_ISSUE": "Calculation Issue", "METHODOLOGY_ISSUE": "Methodology Issue"}
Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=4000)]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class FindingIn(_Strict):
    category: FindingCategory
    blocking: bool                       # B4: no severity scale
    title: Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=200)]
    description: Text
    target_input_seq: int | None = None
    target_output_seq: int | None = None
    target_calculation_rule_id: uuid.UUID | None = None
    target_source_type: Literal["LAB_RESULT", "MONITORING_RECORD", "STRATUM_AREA", "SAMPLING_DESIGN_PARAMETER", "MODULE_CONSTANT"] | None = None
    target_source_id: uuid.UUID | None = None
    evidence_document_id: uuid.UUID | None = None


class RespondIn(_Strict):
    response: Text
    document_id: uuid.UUID | None = None


class ResolveIn(_Strict):
    note: Reason
    resolved_by_run_id: uuid.UUID | None = None


class ReasonIn(_Strict):
    reason: Reason


class NotesIn(_Strict):
    notes: Reason


class ReadinessCreateIn(_Strict):
    monitoring_period_id: uuid.UUID


class FindingEventOut(BaseModel):
    seq: int
    action: str
    from_status: str | None
    to_status: str
    actor_name: str | None
    occurred_at: UtcDatetime
    note: str | None
    document_id: uuid.UUID | None
    run_id: uuid.UUID | None


class FindingOut(BaseModel):
    id: uuid.UUID
    finding_code: str
    project_id: uuid.UUID
    monitoring_period_id: uuid.UUID
    run_id: uuid.UUID
    run_code: str
    category: str
    category_label: str
    blocking: bool
    title: str
    description: str
    target_input_seq: int | None
    target_output_seq: int | None
    target_calculation_rule_id: uuid.UUID | None
    target_rule_code: str | None
    target_source_type: str | None
    target_source_id: uuid.UUID | None
    evidence_document_id: uuid.UUID | None
    status: str
    raised_by_name: str | None
    raised_at: UtcDatetime
    response_text: str | None
    response_document_id: uuid.UUID | None
    responded_by_name: str | None
    responded_at: UtcDatetime | None
    resolution_note: str | None
    resolved_by_name: str | None
    resolved_at: UtcDatetime | None
    resolved_by_run_id: uuid.UUID | None
    withdraw_reason: str | None
    environment: str
    events: list[FindingEventOut]
    can_respond: bool
    can_resolve: bool
    can_return: bool
    can_reopen: bool
    can_withdraw: bool


class ReportOut(BaseModel):
    id: uuid.UUID
    report_code: str
    run_id: uuid.UUID
    run_code: str
    version: int
    generator_version: str
    content_sha256: str
    pdf_sha256: str
    document_id: uuid.UUID
    status: str
    superseded_by_report_id: uuid.UUID | None
    superseded_at: UtcDatetime | None
    generated_by_name: str | None
    generated_at: UtcDatetime
    environment: str
    label: str


class ReportDetailOut(ReportOut):
    content: dict[str, Any]


class ReportVerifyOut(BaseModel):
    report_id: uuid.UUID
    report_code: str
    valid: bool
    problems: list[str]
    stale: bool
    content_sha256: str
    pdf_sha256: str
    stored_pdf_sha256: str | None
    generator_version: str
    current_generator_version: str


class ReadinessCheckOut(BaseModel):
    key: str
    label: str
    result: Literal["PASS", "FAIL", "WARN"]
    details: list[str] = []


class ReadinessOut(BaseModel):
    id: uuid.UUID
    readiness_code: str
    project_id: uuid.UUID
    monitoring_period_id: uuid.UUID
    run_id: uuid.UUID
    run_code: str
    report_id: uuid.UUID | None
    report_code: str | None
    status: str
    checks: list[ReadinessCheckOut]
    manifest_sha256: str | None
    created_by_name: str | None
    created_at: UtcDatetime
    submitted_by_name: str | None
    submitted_at: UtcDatetime | None
    decided_by_name: str | None
    decided_at: UtcDatetime | None
    decision_notes: str | None
    withdraw_reason: str | None
    invalidated_at: UtcDatetime | None
    invalidation_reason: str | None
    environment: str
    label: str = READINESS_LABEL
    meaning: str = READY_MEANING
    can_submit: bool
    can_approve: bool
    can_reject: bool
    can_withdraw: bool


class ReadinessView(BaseModel):
    project_id: uuid.UUID
    project_code: str
    project_status: str
    monitoring_period_id: uuid.UUID
    environment: str
    label: str = READINESS_LABEL
    meaning: str = READY_MEANING
    current_run_id: uuid.UUID | None
    current_run_code: str | None
    current_report_id: uuid.UUID | None
    ready_to_submit: bool
    blockers: list[Blocker]
    checks: list[ReadinessCheckOut]
    calculation_blockers: list[Blocker]          # Phase 7 readiness of the period (e.g. NO_CALCULATION_MODULE)
    open_blocking_findings: list[str]
    reviews: list[ReadinessOut]
    can_create: bool


class ManifestOut(BaseModel):
    readiness_id: uuid.UUID
    readiness_code: str
    status: str
    manifest_sha256: str | None
    manifest: dict[str, Any] | None
    label: str = READINESS_LABEL
