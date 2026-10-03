"""Phase 6 schemas.

Two families on purpose (decision 16):
- project-side schemas (`/api/v1/lab`) may carry the full internal lineage (field collection, point, farm, project);
- laboratory-facing schemas (`*LabView`, `/api/v1/laboratory`) are explicit allow-lists. They never contain farmer, farm,
  boundary, GPS, sampling point, field collection, stratum, project name or project-side locations.
"""
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field, StringConstraints, model_validator

from app.schemas.common import UtcDatetime

Reason = Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=1000)]
Short = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
Mid = Annotated[str, StringConstraints(strip_whitespace=True, max_length=500)]
Depth = Annotated[Decimal, Field(ge=0, le=1000, max_digits=6, decimal_places=1)]


# ---------------------------------------------------------------- requests
class EngagementIn(BaseModel):
    project_id: uuid.UUID
    laboratory_org_id: uuid.UUID
    rule_ids: list[uuid.UUID] = Field(min_length=1, max_length=100)
    notes: Mid | None = None


class ReasonIn(BaseModel):
    reason: Reason


class SampleIn(BaseModel):
    field_collection_id: uuid.UUID
    laboratory_org_id: uuid.UUID | None = None      # required only when several laboratories are engaged
    parent_sample_id: uuid.UUID | None = None       # split / sub-sample
    description: Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=500)]
    depth_top_cm: Depth | None = None               # defaults to the field collection's actual depth
    depth_bottom_cm: Depth | None = None
    quantity: Annotated[Decimal, Field(ge=0, max_digits=10, decimal_places=3)] | None = None
    quantity_unit: Annotated[str, StringConstraints(strip_whitespace=True, max_length=20)] | None = None
    container_label: Annotated[str, StringConstraints(strip_whitespace=True, max_length=100)] | None = None


class SampleUpdate(BaseModel):
    description: Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=500)] | None = None
    quantity: Annotated[Decimal, Field(ge=0, max_digits=10, decimal_places=3)] | None = None
    quantity_unit: Annotated[str, StringConstraints(strip_whitespace=True, max_length=20)] | None = None
    container_label: Annotated[str, StringConstraints(strip_whitespace=True, max_length=100)] | None = None


class SealIn(BaseModel):
    seal_number: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
    occurred_at: datetime | None = None
    location_text: Annotated[str, StringConstraints(strip_whitespace=True, max_length=300)] | None = None


class CustodyEventIn(BaseModel):
    event_type: Literal["TRANSFERRED", "EXCEPTION_RECORDED", "EXCEPTION_RESOLVED"]
    exception_type: Literal["DAMAGED", "SEAL_BROKEN", "LOST", "OTHER"] | None = None
    resolve_to: Literal["VOIDED", "REJECTED_AT_RECEIPT"] | None = None   # otherwise resolves back to the interrupted state
    reason: Reason | None = None
    occurred_at: datetime | None = None
    location_text: Annotated[str, StringConstraints(strip_whitespace=True, max_length=300)] | None = None

    @model_validator(mode="after")
    def _rules(self) -> "CustodyEventIn":
        if self.event_type == "EXCEPTION_RECORDED" and not self.exception_type:
            raise ValueError("exception_type is required for EXCEPTION_RECORDED.")
        if self.event_type in ("EXCEPTION_RECORDED", "EXCEPTION_RESOLVED") and not self.reason:
            raise ValueError("A reason is required for custody exceptions.")
        return self


class ShipmentIn(BaseModel):
    project_id: uuid.UUID
    laboratory_org_id: uuid.UUID
    carrier: Annotated[str, StringConstraints(strip_whitespace=True, max_length=120)] | None = None
    tracking_number: Annotated[str, StringConstraints(strip_whitespace=True, max_length=120)] | None = None
    notes: Mid | None = None


class ShipmentItemsIn(BaseModel):
    sample_ids: list[uuid.UUID] = Field(min_length=1, max_length=500)


class ReceiptItemIn(BaseModel):
    sample_id: uuid.UUID
    accepted: bool
    condition: Mid | None = None
    seal_number_observed: Annotated[str, StringConstraints(strip_whitespace=True, max_length=100)] | None = None
    reason: Reason | None = None

    @model_validator(mode="after")
    def _reason(self) -> "ReceiptItemIn":
        if not self.accepted and not self.reason:
            raise ValueError("A reason is required to reject a sample at receipt.")
        return self


class ReceiptIn(BaseModel):
    items: list[ReceiptItemIn] = Field(min_length=1, max_length=500)
    occurred_at: datetime | None = None
    location_text: Annotated[str, StringConstraints(strip_whitespace=True, max_length=300)] | None = None


class AccessionIn(BaseModel):
    accession_number: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]


class TestStartIn(BaseModel):
    method_reported: Mid | None = None


class ResultIn(BaseModel):
    """Exactly one of value_number / value_text. Text is stored verbatim (e.g. "ND", "<0.05", "<LOQ") — never parsed."""
    result_type: Literal["NUMERIC", "TEXT"]
    value_number: Annotated[Decimal, Field(max_digits=18, decimal_places=6)] | None = None
    value_text: Annotated[str, StringConstraints(min_length=1, max_length=200)] | None = None
    unit: Annotated[str, StringConstraints(max_length=40)] | None = None
    analysed_at: datetime
    method_reported: Mid | None = None

    @model_validator(mode="after")
    def _one_value(self) -> "ResultIn":
        if self.result_type == "NUMERIC" and (self.value_number is None or self.value_text is not None):
            raise ValueError("A NUMERIC result needs value_number and no value_text.")
        if self.result_type == "TEXT" and (self.value_text is None or self.value_number is not None):
            raise ValueError("A TEXT result needs value_text and no value_number.")
        return self


class CorrectionIn(ResultIn):
    reason: Reason


class ResultUpdate(BaseModel):
    result_type: Literal["NUMERIC", "TEXT"] | None = None
    value_number: Annotated[Decimal, Field(max_digits=18, decimal_places=6)] | None = None
    value_text: Annotated[str, StringConstraints(min_length=1, max_length=200)] | None = None
    unit: Annotated[str, StringConstraints(max_length=40)] | None = None
    analysed_at: datetime | None = None
    method_reported: Mid | None = None


class RetestIn(BaseModel):
    reason: Reason
    sample_id: uuid.UUID | None = None      # a split of the same root sample; defaults to the original sample


class QaDecisionIn(BaseModel):
    decision: Literal["APPROVED", "REJECTED", "RETEST_REQUIRED"]
    notes: Reason
    acknowledge_configuration: bool = False   # only where CONFIGURATION_REQUIRED may be acknowledged (DEMO / non-production)


# ---------------------------------------------------------------- shared small views
class LabQaCheck(BaseModel):
    key: str
    label: str
    result: Literal["PASS", "FAIL", "WARN", "CONFIGURATION_REQUIRED"]
    details: list[str] = []
    acknowledgeable: bool = False


class DocumentRef(BaseModel):
    document_id: uuid.UUID
    category: str
    title: str
    file_name: str | None
    sha256: str | None
    uploaded_at: UtcDatetime | None


class RuleRef(BaseModel):
    rule_id: uuid.UUID
    rule_code: str
    parameter: str
    unit: str | None
    method: str | None
    measurement_source: str


# ---------------------------------------------------------------- project side
class EngagementOut(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    project_code: str
    project_name: str
    project_org_name: str
    laboratory_org_id: uuid.UUID
    laboratory_org_name: str
    methodology_version_id: uuid.UUID
    methodology_label: str
    status: str
    replaces_engagement_id: uuid.UUID | None
    notes: str | None
    rules: list[RuleRef]
    proposed_by_name: str | None
    proposed_at: UtcDatetime
    accepted_by_name: str | None
    accepted_at: UtcDatetime | None
    ended_by_name: str | None
    ended_at: UtcDatetime | None
    ended_side: str | None
    end_reason: str | None
    environment: str
    can_end: bool = False


class LaboratoryOrgOut(BaseModel):
    id: uuid.UUID
    code: str
    name: str
    environment: str


class CustodyEventOut(BaseModel):
    sequence_no: int
    event_type: str
    from_state: str | None
    to_state: str
    actor_name: str | None
    actor_org_name: str | None
    actor_role: str | None
    actor_side: str
    occurred_at: UtcDatetime
    recorded_at: UtcDatetime
    location_text: str | None
    latitude: Decimal | None
    longitude: Decimal | None
    seal_number: str | None
    shipment_code: str | None
    exception_type: str | None
    reason: str | None


class ResultOut(BaseModel):
    id: uuid.UUID
    test_id: uuid.UUID
    test_code: str
    version: int
    status: str
    result_type: str
    value_number: Decimal | None
    value_text: str | None
    unit: str | None
    analysed_at: UtcDatetime | None
    analyst_name: str | None
    method_reported: str | None
    report: DocumentRef | None
    source: str
    supersedes_result_id: uuid.UUID | None
    superseded_by_result_id: uuid.UUID | None
    status_reason: str | None
    submitted_at: UtcDatetime | None
    approved_at: UtcDatetime | None
    approved_by_name: str | None
    rule_code: str
    parameter: str
    authoritative: bool = False


class TestOut(BaseModel):
    id: uuid.UUID
    test_code: str
    status: str
    sample_code: str
    rule: RuleRef
    plan_measurement_code: str
    plan_measurement_type: str
    retest_of_test_code: str | None
    retest_reason: str | None
    laboratory_org_name: str
    results: list[ResultOut] = []


class SampleOut(BaseModel):
    id: uuid.UUID
    sample_code: str
    root_sample_code: str
    parent_sample_code: str | None
    status: str
    description: str
    depth_top_cm: Decimal
    depth_bottom_cm: Decimal
    quantity: Decimal | None
    quantity_unit: str | None
    container_label: str | None
    seal_number: str | None
    accession_number: str | None
    # internal lineage — project side only
    field_collection_id: uuid.UUID
    field_collection_code: str
    field_collection_version: int
    field_collection_status: str
    sampling_point_code: str
    farm_code: str | None
    project_id: uuid.UUID
    project_code: str
    monitoring_period_id: uuid.UUID
    laboratory_org_id: uuid.UUID
    laboratory_org_name: str
    engagement_id: uuid.UUID
    registered_by_name: str | None
    registered_at: UtcDatetime
    sealed_at: UtcDatetime | None
    environment: str
    test_count: int = 0
    approved_count: int = 0
    can_seal: bool = False
    can_edit: bool = False


class SampleDetailOut(SampleOut):
    custody: list[CustodyEventOut]
    tests: list[TestOut]
    shipments: list[str]


class ShipmentItemOut(BaseModel):
    sample_id: uuid.UUID
    sample_code: str
    status: str
    receipt_condition: str | None
    receipt_reason: str | None
    received_at: UtcDatetime | None


class ShipmentOut(BaseModel):
    id: uuid.UUID
    shipment_code: str
    project_id: uuid.UUID
    project_code: str
    laboratory_org_id: uuid.UUID
    laboratory_org_name: str
    status: str
    carrier: str | None
    tracking_number: str | None
    notes: str | None
    created_at: UtcDatetime
    dispatched_at: UtcDatetime | None
    received_at: UtcDatetime | None
    cancel_reason: str | None
    items: list[ShipmentItemOut]
    documents: list[DocumentRef] = []


class QaReviewOut(BaseModel):
    id: uuid.UUID
    decision: str
    notes: str
    reviewer_name: str | None
    reviewed_at: UtcDatetime
    configuration_acknowledged: bool
    checks: list[LabQaCheck] = []


class LineageOut(BaseModel):
    """Approved (or any non-draft) result with its full lineage — project side only."""
    result: ResultOut
    versions: list[ResultOut]
    test: dict[str, Any]
    sample: dict[str, Any]
    root_sample: dict[str, Any]
    field_collection: dict[str, Any]
    sampling_point: dict[str, Any]
    stratum: dict[str, Any] | None
    farm: dict[str, Any]
    project: dict[str, Any]
    methodology: dict[str, Any]
    methodology_rule: RuleRef
    plan_measurement: dict[str, Any]
    custody: list[CustodyEventOut]
    shipments: list[dict[str, Any]]
    qa_reviews: list[QaReviewOut]


# ---------------------------------------------------------------- laboratory-facing (allow-lists)
class EngagementLabView(BaseModel):
    id: uuid.UUID
    project_code: str
    project_org_name: str
    laboratory_org_name: str
    methodology_label: str
    status: str
    rules: list[RuleRef]
    proposed_at: UtcDatetime
    accepted_at: UtcDatetime | None
    ended_at: UtcDatetime | None
    ended_side: str | None
    end_reason: str | None
    environment: str
    can_accept: bool = False
    can_end: bool = False


class CustodyEventLabView(BaseModel):
    sequence_no: int
    event_type: str
    from_state: str | None
    to_state: str
    occurred_at: UtcDatetime
    actor_org_name: str | None
    actor_role: str | None
    actor_side: str
    actor_name: str | None = None        # laboratory-side events only
    location_text: str | None = None     # laboratory-side events only
    reason: str | None = None            # laboratory-side events only
    seal_number: str | None
    exception_type: str | None


class ResultLabView(BaseModel):
    id: uuid.UUID
    version: int
    status: str
    result_type: str
    value_number: Decimal | None
    value_text: str | None
    unit: str | None
    analysed_at: UtcDatetime | None
    analyst_name: str | None
    method_reported: str | None
    report: DocumentRef | None
    source: str
    supersedes_result_id: uuid.UUID | None
    status_reason: str | None
    submitted_at: UtcDatetime | None
    approved_at: UtcDatetime | None
    can_edit: bool = False
    can_submit: bool = False


class TestLabView(BaseModel):
    id: uuid.UUID
    test_code: str
    status: str
    sample_id: uuid.UUID
    sample_code: str
    project_code: str
    rule: RuleRef
    required_unit: str | None
    value_type: str
    unit_configuration: Literal["CONFIGURED", "CONFIGURATION_REQUIRED"]
    method_reported: str | None
    retest_of_test_code: str | None
    retest_reason: str | None
    results: list[ResultLabView] = []
    can_start: bool = False
    can_enter_result: bool = False


class SampleLabView(BaseModel):
    id: uuid.UUID
    sample_code: str
    parent_sample_code: str | None
    status: str
    description: str
    depth_top_cm: Decimal
    depth_bottom_cm: Decimal
    quantity: Decimal | None
    quantity_unit: str | None
    container_label: str | None
    seal_number: str | None
    accession_number: str | None
    project_code: str
    project_org_name: str
    laboratory_org_name: str
    methodology_label: str
    tests: list[TestLabView] = []
    custody: list[CustodyEventLabView] = []


class ShipmentItemLabView(BaseModel):
    sample_id: uuid.UUID
    sample_code: str
    status: str
    seal_number: str | None
    receipt_condition: str | None
    receipt_reason: str | None
    received_at: UtcDatetime | None


class ShipmentLabView(BaseModel):
    id: uuid.UUID
    shipment_code: str
    project_code: str
    project_org_name: str
    laboratory_org_name: str
    status: str
    carrier: str | None
    tracking_number: str | None
    dispatched_at: UtcDatetime | None
    received_at: UtcDatetime | None
    items: list[ShipmentItemLabView]
    documents: list[DocumentRef] = []
    can_receive: bool = False


class QaLabView(BaseModel):
    result: ResultLabView
    test: TestLabView
    sample_code: str
    checks: list[LabQaCheck]
    reviews: list[QaReviewOut]
    can_start: bool
    can_decide: bool
    can_approve: bool
    blocked_reasons: list[str] = []


class LabDashboardCounts(BaseModel):
    engagements_pending: int
    shipments_incoming: int
    samples_to_register: int
    tests_open: int
    results_awaiting_qa: int

