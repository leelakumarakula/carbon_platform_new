"""Phase 9A schemas — registry submission & credit issuance. Request bodies forbid unknown fields. No body carries a calculated or a
VVB-verified quantity: the only quantity ever entered is the registry-stated issuance quantity (whole units), with registry evidence."""
import uuid
from datetime import date
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.schemas.common import Reason, UtcDatetime

CALCULATED_LABEL = "Calculated tCO2e — not verified, not issued"
VERIFIED_LABEL = "VVB-stated verified quantity"
ISSUED_LABEL = "Registry-issued credits"
ISSUED_NOTE = "As stated by the registry (issuance statement / registry response). Not available inventory; no transfer or retirement here."
DEMO_NOTE = "DEMO — no registry issuance"

Ref = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
Unit = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=40)]
Serial = Annotated[str, StringConstraints(min_length=1, max_length=200)]        # kept exactly as supplied (no stripping, no parsing)
Whole = Annotated[int, Field(gt=0, le=10**15)]                                     # D7: whole units


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ChecklistItem(_Strict):
    code: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=60)]
    title: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
    source: Literal["REGISTRY_SUBMISSION", "VERIFICATION_REPORT", "CALCULATION_REPORT"]


class AccountIn(_Strict):
    organization_id: uuid.UUID
    registry_organization_id: uuid.UUID
    external_account_id: Ref
    label: Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=200)]
    adapter_code: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=30)] = "MANUAL"
    credit_unit: Unit | None = None
    verified_unit_equivalent: Unit | None = None
    document_checklist: list[ChecklistItem] | None = Field(default=None, max_length=50)


class AccountConfigIn(_Strict):
    credit_unit: Unit | None = None
    verified_unit_equivalent: Unit | None = None
    document_checklist: list[ChecklistItem] | None = Field(default=None, max_length=50)
    reason: Reason


class ReasonIn(_Strict):
    reason: Reason


class RegistrationIn(_Strict):
    registry_account_id: uuid.UUID
    notes: Annotated[str, StringConstraints(strip_whitespace=True, max_length=2000)] | None = None


class RegisteredIn(_Strict):
    external_project_id: Ref
    registered_on: date | None = None
    document_id: uuid.UUID
    note: Annotated[str, StringConstraints(strip_whitespace=True, max_length=2000)] | None = None


class RegistrationRejectedIn(_Strict):
    reason: Reason
    document_id: uuid.UUID


class SubmissionIn(_Strict):
    monitoring_period_id: uuid.UUID
    registry_account_id: uuid.UUID
    previous_submission_id: uuid.UUID | None = None


class RecordSubmittedIn(_Strict):
    external_submission_id: Ref
    document_id: uuid.UUID
    note: Annotated[str, StringConstraints(strip_whitespace=True, max_length=2000)] | None = None


class QueryIn(_Strict):
    note: Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=2000)]
    document_id: uuid.UUID | None = None


class ResponseIn(_Strict):
    outcome: Literal["ACCEPTED", "REJECTED"]
    document_id: uuid.UUID
    reason: Annotated[str, StringConstraints(strip_whitespace=True, max_length=2000)] | None = None
    external_response_ref: Ref | None = None


class WithdrawIn(_Strict):
    reason: Reason
    document_id: uuid.UUID


class ReconcileIn(_Strict):
    """Manual reconciliation (registry evidence required); API adapters query the registry instead."""
    outcome: Literal["FOUND", "NOT_FOUND", "MATCH", "MISMATCH"]
    document_id: uuid.UUID | None = None
    external_submission_id: Ref | None = None
    note: Annotated[str, StringConstraints(strip_whitespace=True, max_length=2000)] | None = None


class SerialRangeIn(_Strict):
    serial_start: Serial | None = None
    serial_end: Serial | None = None
    quantity: Whole


class BatchIn(_Strict):
    vintage: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=60)]    # registry-stated (D8)
    quantity: Whole
    serial_ranges: list[SerialRangeIn] = Field(min_length=1, max_length=200)


class IssuanceIn(_Strict):
    external_issuance_id: Ref
    issuance_date: date
    quantity: Whole                                   # registry-stated issued quantity — never a calculated or verified value
    unit: Unit
    source: Literal["MANUAL", "API"] = "MANUAL"
    document_id: uuid.UUID | None = None              # ISSUANCE_STATEMENT (required for MANUAL)
    batches: list[BatchIn] = Field(min_length=1, max_length=100)


class CorrectionIn(IssuanceIn):
    reason: Reason


class NoteIn(_Strict):
    note: Annotated[str, StringConstraints(strip_whitespace=True, max_length=2000)] | None = None


class CancelIn(_Strict):
    reason: Reason
    document_id: uuid.UUID


# ---------------------------------------------------------------- responses
class OrgRef(BaseModel):
    id: uuid.UUID
    code: str
    name: str


class AccountOut(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    registry_organization_id: uuid.UUID
    registry_name: str | None
    external_account_id: str
    label: str
    adapter_code: str
    adapter_mode: str | None
    credit_unit: str | None
    verified_unit_equivalent: str | None
    document_checklist: list[dict[str, Any]] | None
    status: str
    created_at: UtcDatetime
    closed_reason: str | None
    environment: str


class RegistrationOut(BaseModel):
    id: uuid.UUID
    registration_code: str
    project_id: uuid.UUID
    registry_account_id: uuid.UUID
    registry_organization_id: uuid.UUID
    registry_name: str | None
    status: str
    external_project_id: str | None
    registered_on: date | None
    evidence_document_id: uuid.UUID | None
    response_reason: str | None
    notes: str | None
    recorded_by_name: str | None
    recorded_at: UtcDatetime | None
    created_at: UtcDatetime
    label: str = "Recorded external fact — the platform does not register projects"


class EventOut(BaseModel):
    id: uuid.UUID
    event_type: str
    occurred_at: UtcDatetime
    actor_name: str | None
    adapter_code: str
    idempotency_key: str | None
    external_ref: str | None
    payload_sha256: str | None
    outcome: str | None
    checklist_item: str | None
    note: str | None
    document_id: uuid.UUID | None


class SerialRangeOut(BaseModel):
    seq: int
    serial_start: str | None
    serial_end: str | None
    quantity: int
    parsed: bool
    is_current: bool


class BatchOut(BaseModel):
    id: uuid.UUID
    batch_code: str
    issuance_id: uuid.UUID
    issuance_code: str | None
    external_issuance_id: str | None
    project_id: uuid.UUID
    project_code: str | None
    monitoring_period_id: uuid.UUID
    period_number: int | None
    registry_name: str | None
    vintage: str
    quantity: int
    unit: str
    status: str
    issuance_date: date | None
    serial_ranges: list[SerialRangeOut]
    source_superseded: bool
    environment: str
    label: str = ISSUED_LABEL
    note: str = ISSUED_NOTE


class IssuanceOut(BaseModel):
    id: uuid.UUID
    issuance_code: str
    registry_submission_id: uuid.UUID
    external_issuance_id: str
    issuance_date: date
    quantity: int
    unit: str
    source: str
    evidence_document_id: uuid.UUID | None
    api_response_sha256: str | None
    status: str
    corrects_issuance_id: uuid.UUID | None
    corrected_by_issuance_id: uuid.UUID | None
    correction_reason: str | None
    recorded_by_name: str | None
    recorded_at: UtcDatetime
    confirmed_by_name: str | None
    confirmed_at: UtcDatetime | None
    void_reason: str | None
    cancel_reason: str | None
    batches: list[BatchOut]
    can_confirm: bool
    label: str = ISSUED_LABEL


class SubmissionOut(BaseModel):
    id: uuid.UUID
    submission_code: str
    project_id: uuid.UUID
    monitoring_period_id: uuid.UUID
    registration_id: uuid.UUID
    registration_code: str | None
    external_project_id: str | None
    registry_account_id: uuid.UUID
    registry_name: str | None
    verification_decision_id: uuid.UUID
    decision_code: str | None
    decision_status: str | None
    previous_submission_id: uuid.UUID | None
    status: str
    snapshot_sha256: str | None
    idempotency_key: str | None
    external_submission_id: str | None
    submission_evidence_document_id: uuid.UUID | None
    response_document_id: uuid.UUID | None
    response_payload_sha256: str | None
    external_response_ref: str | None
    response_reason: str | None
    created_at: UtcDatetime
    frozen_at: UtcDatetime | None
    submitted_at: UtcDatetime | None
    response_at: UtcDatetime | None
    closed_reason: str | None
    source_superseded: bool
    environment: str


class SubmissionDetail(SubmissionOut):
    snapshot: dict[str, Any] | None
    events: list[EventOut]
    issuances: list[IssuanceOut]
    checklist: list[dict[str, Any]] | None
    documents: list[dict[str, Any]]


class Quantity(BaseModel):
    label: str
    value: str | None
    unit: str | None
    note: str | None = None


class EligibilityOut(BaseModel):
    registry_account_id: uuid.UUID | None
    account_label: str | None
    blockers: list[dict[str, str]]
    warnings: list[dict[str, str]]


class PeriodRegistryView(BaseModel):
    project_id: uuid.UUID
    organization_id: uuid.UUID
    project_status: str
    environment: str
    demo_note: str | None
    monitoring_period_id: uuid.UUID
    period_number: int
    registry_status: str
    calculated: Quantity
    verified: Quantity
    issued: list[Quantity]
    remaining: Quantity | None
    decision_code: str | None
    eligibility: list[EligibilityOut]
    registrations: list[RegistrationOut]
    submissions: list[SubmissionOut]
    issuances: list[IssuanceOut]
    can_manage: bool
    can_confirm: bool


class RegistryProjectOut(BaseModel):
    id: uuid.UUID
    project_code: str
    name: str
    status: str
    environment: str
    periods: list[dict[str, Any]]


class LineageOut(BaseModel):
    batch: dict[str, Any]
    chain: list[dict[str, Any]]
    sources: dict[str, Any] | None
    verification_lineage: dict[str, Any] | None
    calculation_lineage: dict[str, Any] | None
