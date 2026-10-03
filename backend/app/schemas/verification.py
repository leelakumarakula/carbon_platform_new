"""Phase 8B schemas — VVB / ACVA verification. Request bodies forbid unknown fields; no body accepts a calculated value or credits."""
import uuid
from datetime import date
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, StringConstraints

from app.schemas.common import Reason, UtcDatetime
from app.schemas.preverification import CATEGORY_LABELS, FindingCategory

CALCULATED_LABEL = "Calculated tCO2e — not verified, not issued"
VERIFIED_QUANTITY_LABEL = "VVB-stated verified quantity"
VERIFIED_QUANTITY_NOTE = "Recorded as stated in the VVB's report. Not issued; not a credit."
DECISION_NOTE = "The platform records the external VVB's decision; it does not verify."
TargetType = Literal["SUBMISSION", "MONITORING_PERIOD", "CALCULATION_RUN", "INPUT", "OUTPUT", "LAB_RESULT", "MRV_EVIDENCE", "DATASET",
                     "CALCULATION_REPORT", "METHODOLOGY", "DOCUMENT"]
Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=4000)]
__all__ = ["CATEGORY_LABELS"]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


# ---------------------------------------------------------------- requests
class AssignmentIn(_Strict):
    monitoring_period_id: uuid.UUID
    vvb_organization_id: uuid.UUID
    notes: Annotated[str, StringConstraints(strip_whitespace=True, max_length=2000)] | None = None
    previous_assignment_id: uuid.UUID | None = None


class AcceptIn(_Strict):
    coi_declaration: Annotated[str, StringConstraints(strip_whitespace=True, min_length=10, max_length=4000)]


class ReasonIn(_Strict):
    reason: Reason


class NoteIn(_Strict):
    note: Reason


class VFindingIn(_Strict):
    category: FindingCategory
    blocking: bool
    title: Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=200)]
    description: Text
    target_type: TargetType = "SUBMISSION"
    target_ref: Annotated[str, StringConstraints(strip_whitespace=True, max_length=80)] | None = None


class VRespondIn(_Strict):
    response: Text
    document_id: uuid.UUID | None = None


class CorrectiveActionIn(_Strict):
    description: Text
    due_date: date | None = None


# ---------------------------------------------------------------- responses
class VvbOrgOut(BaseModel):
    id: uuid.UUID
    name: str
    code: str | None


class SubmissionOut(BaseModel):
    id: uuid.UUID
    submission_code: str
    seq: int
    status: str
    readiness_review_id: uuid.UUID
    readiness_code: str | None
    calculation_run_id: uuid.UUID
    run_code: str | None
    calculation_report_id: uuid.UUID
    report_code: str | None
    report_version: int | None
    manifest_sha256: str
    calculated_value: str | None
    calculated_unit: str | None
    calculated_label: str = CALCULATED_LABEL
    submitted_by_name: str | None
    submitted_at: UtcDatetime
    closed_at: UtcDatetime | None
    closed_reason: str | None
    superseded_by_submission_id: uuid.UUID | None


class DecisionOut(BaseModel):
    id: uuid.UUID
    decision_code: str
    assignment_id: uuid.UUID
    submission_id: uuid.UUID
    submission_code: str | None
    monitoring_period_id: uuid.UUID
    vvb_organization_id: uuid.UUID
    vvb_organization_name: str | None
    outcome: str
    verified_quantity: str | None
    verified_quantity_unit: str | None
    verified_quantity_label: str = VERIFIED_QUANTITY_LABEL
    verified_quantity_note: str = VERIFIED_QUANTITY_NOTE
    rationale: str
    report_document_id: uuid.UUID
    report_sha256: str
    manifest_sha256: str
    decided_by_name: str | None
    decided_at: UtcDatetime
    status: str
    superseded_at: UtcDatetime | None
    superseded_reason: str | None
    note: str = DECISION_NOTE


class AssignmentOut(BaseModel):
    id: uuid.UUID
    assignment_code: str
    project_id: uuid.UUID
    project_code: str | None
    project_name: str | None
    monitoring_period_id: uuid.UUID
    period_number: int | None
    period_start: date | None
    period_end: date | None
    vvb_organization_id: uuid.UUID
    vvb_organization_name: str | None
    status: str
    previous_assignment_id: uuid.UUID | None
    notes: str | None
    proposed_by_name: str | None
    proposed_at: UtcDatetime
    accepted_by_name: str | None
    accepted_at: UtcDatetime | None
    coi_declaration: str | None
    coi_declared_by_name: str | None
    coi_declared_at: UtcDatetime | None
    completed_at: UtcDatetime | None
    closed_side: str | None
    closed_reason: str | None
    closed_at: UtcDatetime | None
    environment: str
    current_submission: SubmissionOut | None
    submissions: list[SubmissionOut]
    decisions: list[DecisionOut]
    actions: list[str]                       # what the caller may do now (UI hints; the API re-checks everything)
    decision_blockers: list[str]


class EventOut(BaseModel):
    seq: int
    action: str
    from_status: str | None
    to_status: str
    actor_name: str | None
    actor_side: str
    occurred_at: UtcDatetime
    note: str | None
    document_id: uuid.UUID | None


class CorrectiveActionOut(BaseModel):
    id: uuid.UUID
    action_code: str
    finding_id: uuid.UUID
    description: str
    due_date: date | None
    overdue: bool
    status: str
    requested_by_name: str | None
    requested_at: UtcDatetime
    response_text: str | None
    response_document_id: uuid.UUID | None
    responded_by_name: str | None
    responded_at: UtcDatetime | None
    reviewed_by_name: str | None
    reviewed_at: UtcDatetime | None
    review_note: str | None
    events: list[EventOut]


class VFindingOut(BaseModel):
    id: uuid.UUID
    finding_code: str
    assignment_id: uuid.UUID
    submission_id: uuid.UUID
    category: str
    category_label: str
    blocking: bool
    title: str
    description: str
    target_type: str
    target_ref: str | None
    status: str
    raised_by_name: str | None
    raised_at: UtcDatetime
    response_text: str | None
    response_document_id: uuid.UUID | None
    responded_by_name: str | None
    responded_at: UtcDatetime | None
    closure_note: str | None
    closed_by_name: str | None
    closed_at: UtcDatetime | None
    events: list[EventOut]
    corrective_actions: list[CorrectiveActionOut]


class VDocumentRef(BaseModel):
    document_id: uuid.UUID
    source: str
    category: str
    title: str
    status: str
    file_name: str | None
    mime_type: str | None
    size_bytes: int | None
    sha256: str | None
    uploaded_at: UtcDatetime | None


class PackageOut(BaseModel):
    """The VVB's allow-listed view of a submitted package (C9–C11)."""
    submission: SubmissionOut
    label: str
    project: dict[str, Any]
    period: dict[str, Any] | None
    manifest: dict[str, Any]
    manifest_sha256: str
    methodology: dict[str, Any]
    calculation: dict[str, Any]
    report: dict[str, Any] | None
    dataset: dict[str, Any]
    farms: list[dict[str, Any]]
    laboratory_results: list[dict[str, Any]]
    documents: list[VDocumentRef]


class PeriodVerificationView(BaseModel):
    """Project-side verification panel of one monitoring period."""
    project_id: uuid.UUID
    project_status: str
    monitoring_period_id: uuid.UUID
    period_number: int
    ready_review_code: str | None
    calculated_value: str | None
    calculated_unit: str | None
    calculated_label: str = CALCULATED_LABEL
    assignments: list[AssignmentOut]
    current_decision: DecisionOut | None
    submit_blockers: list[str]
    can_manage: bool
    can_respond: bool


class LineageOut(BaseModel):
    decision: dict[str, Any]
    chain: list[dict[str, Any]]
    # run → frozen inputs → approved dataset / laboratory results → samples → field collections → points → strata → farms → project
    # (the Phase 7 lineage, included when the caller also holds calculation.read)
    calculation_lineage: dict[str, Any] | None = None
