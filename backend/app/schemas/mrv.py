"""MRV, stratification, sampling and field-collection schemas (Phase 5)."""
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field, StringConstraints, model_validator

from app.schemas.common import Reason, UtcDatetime, upper_code

Short = Annotated[str, StringConstraints(strip_whitespace=True, max_length=200)]
Mid = Annotated[str, StringConstraints(strip_whitespace=True, max_length=1000)]
Long = Annotated[str, StringConstraints(strip_whitespace=True, max_length=2000)]
Code = Annotated[str, StringConstraints(max_length=40), upper_code(r"[A-Z][A-Z0-9_.-]{0,39}", "Code")]
Lat = Annotated[float, Field(ge=-90, le=90)]
Lon = Annotated[float, Field(ge=-180, le=180)]
Depth = Annotated[Decimal, Field(ge=0, le=1000, max_digits=6, decimal_places=1)]
Quantification = Literal["MEASURE_AND_REMEASURE", "MEASURE_AND_MODEL", "OTHER", "CONFIGURATION_REQUIRED"]
Category = Literal["SOIL", "CROP", "PLANTING", "HARVEST", "TILLAGE", "FERTILIZER", "MANURE", "RESIDUE", "IRRIGATION", "WATER_MANAGEMENT",
                   "YIELD", "PRACTICE_CHANGE", "FUEL", "OTHER"]


class ReasonBody(BaseModel):
    reason: Reason


# ---------------------------------------------------------------- plans
class MeasurementIn(BaseModel):
    code: Code
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=200)]
    category: Category
    value_type: Literal["NUMBER", "TEXT", "DATE", "BOOLEAN", "CHOICE"]
    unit: Annotated[str, StringConstraints(strip_whitespace=True, max_length=40)] | None = None
    allowed_values: list[str] | None = None
    level: Literal["PROJECT", "FARM", "STRATUM", "SAMPLING_POINT"] = "FARM"
    frequency: Annotated[str, StringConstraints(strip_whitespace=True, max_length=120)] | None = None
    required: bool = True

    @model_validator(mode="after")
    def _choice(self) -> "MeasurementIn":
        if self.value_type == "CHOICE" and not self.allowed_values:
            raise ValueError("CHOICE measurements need allowed_values.")
        return self


class PlanIn(BaseModel):
    project_id: uuid.UUID
    monitoring_frequency: Short | None = None
    monitoring_start: date | None = None
    monitoring_end: date | None = None
    quantification_approach: Quantification | None = None   # only when the methodology does not configure it
    required_evidence: Long | None = None
    notes: Long | None = None
    measurements: list[MeasurementIn] = []                   # project-configured additions

    @model_validator(mode="after")
    def _dates(self) -> "PlanIn":
        if self.monitoring_start and self.monitoring_end and self.monitoring_end <= self.monitoring_start:
            raise ValueError("monitoring_end must be after monitoring_start.")
        return self


class PlanUpdate(BaseModel):
    monitoring_frequency: Short | None = None
    monitoring_start: date | None = None
    monitoring_end: date | None = None
    quantification_approach: Quantification | None = None
    required_evidence: Long | None = None
    notes: Long | None = None


class PlanDecision(BaseModel):
    reason: Reason
    acknowledge_configuration_gaps: bool = False


class MeasurementOut(BaseModel):
    id: uuid.UUID
    code: str
    name: str
    category: str
    value_type: str
    unit: str | None
    allowed_values: list[str] | None
    level: str
    frequency: str | None
    required: bool
    source: str
    monitoring_rule_id: uuid.UUID | None


class PlanOut(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    project_code: str
    plan_version: int
    status: str
    methodology_id: uuid.UUID
    methodology_version_id: uuid.UUID
    methodology_label: str
    monitoring_frequency: str | None
    monitoring_start: date | None
    monitoring_end: date | None
    quantification_approach: str
    sampling_requirements_ref: str | None
    required_evidence: str | None
    configuration_status: str
    configuration_gaps: list[str]
    notes: str | None
    supersedes_id: uuid.UUID | None
    created_by: uuid.UUID | None
    created_at: UtcDatetime
    submitted_by: uuid.UUID | None
    submitted_at: UtcDatetime | None
    approved_by: uuid.UUID | None
    approved_at: UtcDatetime | None
    status_reason: str | None
    measurements: list[MeasurementOut] = []
    can_edit: bool = False
    can_submit: bool = False
    can_approve: bool = False
    # decision V1 (platform governance): ACKNOWLEDGE_ALLOWED for DEMO projects / non-production, PRODUCTION_BLOCK otherwise
    gap_approval_policy: str = "ACKNOWLEDGE_ALLOWED"
    approval_blockers: list[str] = []
    gaps_acknowledged_by: uuid.UUID | None = None


# ---------------------------------------------------------------- periods
class PeriodIn(BaseModel):
    project_id: uuid.UUID
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=200)]
    purpose: Literal["BASELINE", "MONITORING", "VERIFICATION", "OTHER"] = "MONITORING"
    start_date: date
    end_date: date

    @model_validator(mode="after")
    def _dates(self) -> "PeriodIn":
        if self.end_date <= self.start_date:
            raise ValueError("end_date must be after start_date.")
        return self


class PeriodOut(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    project_code: str
    mrv_plan_id: uuid.UUID
    plan_version: int
    methodology_version_id: uuid.UUID
    period_number: int
    name: str
    purpose: str
    start_date: date
    end_date: date
    status: str
    status_reason: str | None
    created_at: UtcDatetime
    counts: dict[str, int] = {}
    allowed_transitions: list[str] = []


# ---------------------------------------------------------------- strata
class CharacteristicIn(BaseModel):
    characteristic: Literal["SOIL_TYPE", "CROP", "LAND_USE", "MANAGEMENT_PRACTICE", "IRRIGATION", "GEOGRAPHY", "CLIMATE", "OTHER"]
    value: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
    source: Literal["FARM_DATA", "FIELD_OBSERVATION", "DECLARED", "EXTERNAL_DATASET"] = "DECLARED"


class StratumIn(BaseModel):
    code: Code
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=200)]
    description: Long | None = None
    farm_ids: list[uuid.UUID] = Field(min_length=1)
    characteristics: list[CharacteristicIn] = []
    criteria: dict[str, Any] | None = None


class StratumUpdate(BaseModel):
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=200)] | None = None
    description: Long | None = None
    farm_ids: list[uuid.UUID] | None = None
    characteristics: list[CharacteristicIn] | None = None
    criteria: dict[str, Any] | None = None
    reason: Reason | None = None


class StratumOut(BaseModel):
    id: uuid.UUID
    record_id: uuid.UUID
    project_id: uuid.UUID
    version: int
    is_current: bool
    code: str
    name: str
    description: str | None
    criteria: dict[str, Any] | None
    geojson: dict[str, Any] | None
    area_hectares: Decimal | None
    farm_ids: list[uuid.UUID]
    farm_codes: list[str]
    characteristics: list[CharacteristicIn]
    missing_required_characteristics: list[str]
    source: str
    status: str
    change_reason: str | None
    created_by: uuid.UUID | None
    created_at: UtcDatetime
    approved_by: uuid.UUID | None
    approved_at: UtcDatetime | None


# ---------------------------------------------------------------- sampling designs
class AllocationIn(BaseModel):
    stratum_id: uuid.UUID
    sample_count: Annotated[int, Field(ge=1, le=10_000)]
    allocation_basis: Mid | None = None


class DesignParams(BaseModel):
    statistical_design: Literal["STRATIFIED_RANDOM", "SIMPLE_RANDOM", "SYSTEMATIC_GRID", "OTHER"]
    target_precision_pct: Annotated[Decimal, Field(gt=0, le=100, max_digits=6, decimal_places=2)] | None = None
    confidence_level_pct: Annotated[Decimal, Field(gt=0, lt=100, max_digits=6, decimal_places=2)] | None = None
    variability_cv_pct: Annotated[Decimal, Field(ge=0, le=1000, max_digits=7, decimal_places=2)] | None = None
    min_detectable_difference: Annotated[str, StringConstraints(strip_whitespace=True, max_length=100)] | None = None
    sampling_method: Mid | None = None
    depth_top_cm: Depth
    depth_bottom_cm: Depth
    min_distance_m: Annotated[Decimal, Field(ge=0, le=10_000, max_digits=8, decimal_places=1)] | None = None
    repeat_sampling: Annotated[str, StringConstraints(strip_whitespace=True, max_length=500)] | None = None
    random_seed: Annotated[int, Field(ge=0, le=2_147_483_647)] | None = None
    notes: Long | None = None
    allocations: list[AllocationIn] = Field(min_length=1)

    @model_validator(mode="after")
    def _depth(self) -> "DesignParams":
        if self.depth_bottom_cm <= self.depth_top_cm:
            raise ValueError("depth_bottom_cm must be greater than depth_top_cm.")
        return self


class DesignIn(DesignParams):
    monitoring_period_id: uuid.UUID
    code: Code
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=200)]


class AllocationOut(BaseModel):
    stratum_id: uuid.UUID
    stratum_code: str
    stratum_area_hectares: Decimal | None
    sample_count: int
    allocation_basis: str | None


class DesignVersionOut(BaseModel):
    id: uuid.UUID
    version: int
    status: str
    statistical_design: str
    target_precision_pct: Decimal | None
    confidence_level_pct: Decimal | None
    variability_cv_pct: Decimal | None
    min_detectable_difference: str | None
    sampling_method: str | None
    depth_top_cm: Decimal
    depth_bottom_cm: Decimal
    min_distance_m: Decimal | None
    repeat_sampling: str | None
    random_seed: int
    requirement_source: str
    configuration_status: str
    configuration_gaps: list[str]
    notes: str | None
    allocations: list[AllocationOut]
    created_by: uuid.UUID | None
    created_at: UtcDatetime
    approved_by: uuid.UUID | None
    approved_at: UtcDatetime | None
    points_generated_at: UtcDatetime | None
    field_rules: dict[str, Any] | None = None   # frozen GPS tolerance / duplicate threshold / checklist / photos, with sources


class DesignOut(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    project_code: str
    mrv_plan_id: uuid.UUID
    monitoring_period_id: uuid.UUID
    monitoring_period_name: str
    methodology_version_id: uuid.UUID
    code: str
    name: str
    current: DesignVersionOut | None
    versions: list[DesignVersionOut]
    point_count: int


# ---------------------------------------------------------------- points / assignments / relocations
class PointOut(BaseModel):
    id: uuid.UUID
    point_code: str
    project_id: uuid.UUID
    monitoring_period_id: uuid.UUID
    design_version_id: uuid.UUID
    stratum_id: uuid.UUID
    stratum_code: str | None = None
    farm_id: uuid.UUID
    farm_code: str | None = None
    farm_name: str | None = None
    sequence: int
    latitude: Decimal
    longitude: Decimal
    planned_depth_top_cm: Decimal
    planned_depth_bottom_cm: Decimal
    status: str
    assigned_collector_id: uuid.UUID | None
    assigned_collector_name: str | None = None
    planned_date: date | None
    status_reason: str | None
    pending_relocation: bool = False
    collection_id: uuid.UUID | None = None
    collection_status: str | None = None


class AssignIn(BaseModel):
    collector_id: uuid.UUID
    planned_date: date | None = None
    instructions: Mid | None = None


class BulkAssignIn(AssignIn):
    point_ids: list[uuid.UUID] = Field(min_length=1, max_length=500)


class RelocationIn(BaseModel):
    latitude: Lat
    longitude: Lon
    reason: Reason


class RelocationDecision(BaseModel):
    decision: Literal["APPROVED", "REJECTED"]
    notes: Reason


class RelocationOut(BaseModel):
    id: uuid.UUID
    sampling_point_id: uuid.UUID
    old_latitude: Decimal
    old_longitude: Decimal
    new_latitude: Decimal
    new_longitude: Decimal
    distance_m: Decimal
    reason: str
    status: str
    requested_by: uuid.UUID | None
    requested_at: UtcDatetime
    reviewed_by: uuid.UUID | None
    reviewed_at: UtcDatetime | None
    review_notes: str | None


class GenerateOut(BaseModel):
    created: int
    per_stratum: dict[str, int]
    points: list[PointOut]


# ---------------------------------------------------------------- field collection
class CollectionStart(BaseModel):
    sampling_point_id: uuid.UUID


class CollectionUpdate(BaseModel):
    collected_at: datetime | None = None
    gps_latitude: Lat | None = None
    gps_longitude: Lon | None = None
    gps_accuracy_m: Annotated[Decimal, Field(ge=0, le=10_000, max_digits=8, decimal_places=1)] | None = None
    actual_depth_top_cm: Depth | None = None
    actual_depth_bottom_cm: Depth | None = None
    sample_quantity: Annotated[Decimal, Field(ge=0, max_digits=10, decimal_places=3)] | None = None
    sample_unit: Annotated[str, StringConstraints(strip_whitespace=True, max_length=20)] | None = None
    observations: Long | None = None
    notes: Long | None = None
    checklist: dict[str, bool] | None = None
    deviation_note: Mid | None = None


class CollectionReview(BaseModel):
    decision: Literal["ACCEPTED", "RETURNED"]
    notes: Reason


class CollectionOut(BaseModel):
    id: uuid.UUID
    collection_code: str
    sampling_point_id: uuid.UUID
    point_code: str | None = None
    monitoring_period_id: uuid.UUID
    project_id: uuid.UUID
    farm_id: uuid.UUID
    collector_id: uuid.UUID
    collector_name: str | None = None
    version: int
    supersedes_id: uuid.UUID | None
    status: str
    collected_at: UtcDatetime | None
    gps_latitude: Decimal | None
    gps_longitude: Decimal | None
    gps_accuracy_m: Decimal | None
    distance_from_point_m: Decimal | None
    gps_inside_farm: bool | None
    deviation_note: str | None
    actual_depth_top_cm: Decimal | None
    actual_depth_bottom_cm: Decimal | None
    planned_depth_top_cm: Decimal | None = None
    planned_depth_bottom_cm: Decimal | None = None
    sample_quantity: Decimal | None
    sample_unit: str | None
    observations: str | None
    notes: str | None
    checklist: dict[str, bool] | None
    required_checklist: list[str] = []
    correction_reason: str | None
    created_at: UtcDatetime
    submitted_at: UtcDatetime | None
    reviewed_by: uuid.UUID | None
    reviewed_at: UtcDatetime | None
    review_notes: str | None
    evidence_count: int = 0
    can_edit: bool = False
    can_review: bool = False
    # rules this record is collected under (frozen at start; PLATFORM_DEFAULT vs METHODOLOGY source per value)
    checklist_version: str | None = None
    checklist_items: list[dict[str, str]] = []
    gps_tolerance_m: Decimal | None = None
    min_photos: int = 1
    field_rules: dict[str, Any] | None = None
    # sample-based methodology parameters (e.g. SOC) come from Phase 6 analysis; never entered here
    analysis_status: str | None = None


# ---------------------------------------------------------------- monitoring records / evidence
class MonitoringRecordIn(BaseModel):
    monitoring_period_id: uuid.UUID
    measurement_id: uuid.UUID
    farm_id: uuid.UUID | None = None
    stratum_id: uuid.UUID | None = None
    sampling_point_id: uuid.UUID | None = None
    field_collection_id: uuid.UUID | None = None
    measurement_phase: Literal["BASELINE", "PROJECT", "MONITORING"] = "MONITORING"
    value: str | float | int | bool | None = None
    unit: Annotated[str, StringConstraints(strip_whitespace=True, max_length=40)] | None = None
    observed_on: date
    source: Literal["FIELD_OBSERVATION", "FARMER_CLAIM", "DOCUMENT", "INSTRUMENT", "OTHER"] = "FIELD_OBSERVATION"
    notes: Mid | None = None


class MonitoringRecordAmend(BaseModel):
    value: str | float | int | bool | None = None
    unit: Annotated[str, StringConstraints(strip_whitespace=True, max_length=40)] | None = None
    observed_on: date | None = None
    notes: Mid | None = None
    reason: Reason


class MonitoringRecordOut(BaseModel):
    id: uuid.UUID
    record_id: uuid.UUID
    version: int
    is_current: bool
    monitoring_period_id: uuid.UUID
    measurement_id: uuid.UUID
    measurement_code: str
    measurement_name: str
    farm_id: uuid.UUID | None
    stratum_id: uuid.UUID | None
    sampling_point_id: uuid.UUID | None
    field_collection_id: uuid.UUID | None
    measurement_phase: str
    value: Any
    unit: str | None
    observed_on: date
    source: str
    status: str
    notes: str | None
    change_reason: str | None
    recorded_by: uuid.UUID | None
    recorded_at: UtcDatetime


class EvidenceOut(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    monitoring_period_id: uuid.UUID | None
    entity_type: str
    entity_id: uuid.UUID
    evidence_type: str
    document_id: uuid.UUID | None
    checksum_sha256: str | None
    latitude: Decimal | None
    longitude: Decimal | None
    captured_at: UtcDatetime | None
    description: str | None
    source: str
    status: str
    uploaded_by: uuid.UUID | None
    uploaded_at: UtcDatetime


# ---------------------------------------------------------------- datasets / QA
class DatasetIn(BaseModel):
    monitoring_period_id: uuid.UUID
    notes: Long | None = None


class QaCheck(BaseModel):
    key: str
    label: str
    result: Literal["PASS", "FAIL", "WARN"]
    details: list[str] = []


class QaComplete(BaseModel):
    result: Literal["PASS", "FAIL", "REQUIRES_CORRECTION"]
    notes: Reason


class QaReviewOut(BaseModel):
    id: uuid.UUID
    dataset_id: uuid.UUID
    started_by: uuid.UUID | None
    started_at: UtcDatetime
    checks: list[QaCheck] | None
    result: str | None
    notes: str | None
    completed_by: uuid.UUID | None
    completed_at: UtcDatetime | None


class DatasetOut(BaseModel):
    id: uuid.UUID
    dataset_code: str
    project_id: uuid.UUID
    project_code: str
    monitoring_period_id: uuid.UUID
    monitoring_period_name: str
    mrv_plan_id: uuid.UUID
    plan_version: int
    methodology_version_id: uuid.UUID
    methodology_label: str
    version: int
    supersedes_id: uuid.UUID | None
    status: str
    snapshot_summary: dict[str, int] | None
    snapshot_sha256: str | None
    configuration_gaps: list[str]
    notes: str | None
    status_reason: str | None
    environment: str
    created_at: UtcDatetime
    submitted_by: uuid.UUID | None
    submitted_at: UtcDatetime | None
    approved_by: uuid.UUID | None
    approved_at: UtcDatetime | None
    allowed_actions: list[str] = []


class QaView(BaseModel):
    dataset: DatasetOut
    checks: list[QaCheck]
    reviews: list[QaReviewOut]
    can_start: bool
    can_complete: bool
    can_approve: bool


class ProjectMrvSummary(BaseModel):
    project_id: uuid.UUID
    project_code: str
    project_name: str
    project_status: str
    organization_name: str | None
    methodology_label: str | None
    environment: str
    approved_plan_version: int | None
    plan_count: int
    period_count: int
    open_period: str | None
    point_count: int
    collected_count: int
    dataset_status: str | None
