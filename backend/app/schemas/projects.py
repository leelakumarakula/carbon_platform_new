"""Project, catalog and participation schemas (Phase 3)."""
import uuid
from datetime import date
from decimal import Decimal
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field, StringConstraints, model_validator

from app.schemas.common import Reason, UtcDatetime, upper_code
from app.schemas.documents import DocumentOut
from app.schemas.farmers import ChecklistItem, TransitionReadiness

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=200)]
LongText = Annotated[str, StringConstraints(strip_whitespace=True, max_length=4000)]
MidText = Annotated[str, StringConstraints(strip_whitespace=True, max_length=2000)]
ShortText = Annotated[str, StringConstraints(strip_whitespace=True, max_length=200)]
Country = Annotated[str, StringConstraints(max_length=2), upper_code(r"[A-Z]{2}", "Country (ISO 3166-1 alpha-2)")]
CatalogCode = Annotated[str, StringConstraints(max_length=40), upper_code(r"[A-Z][A-Z0-9_-]{1,39}", "Code")]
Url = Annotated[str, StringConstraints(strip_whitespace=True, max_length=500, pattern=r"^https?://\S+$")]
ProjectType = Literal["AGRICULTURAL_LAND_MANAGEMENT", "AGROFORESTRY", "RICE_CULTIVATION", "GRASSLAND_MANAGEMENT", "OTHER"]
ProjectRole = Literal["PROJECT_MANAGER", "MRV_MANAGER", "METHODOLOGY_SPECIALIST", "FIELD_SUPERVISOR", "FIELD_AGENT", "GIS_SPECIALIST",
                      "PLATFORM_GIS_SPECIALIST", "QA_OFFICER", "FINANCE_MANAGER", "CALCULATION_ANALYST", "REGISTRY_MANAGER",
                      "CREDIT_MANAGER", "SUPPORT"]
HolderType = Literal["FARMER", "LANDOWNER", "ORGANIZATION", "FARMER_GROUP", "OTHER"]


# ---------------------------------------------------------------- catalog
class StandardIn(BaseModel):
    code: CatalogCode
    name: Name
    owner_name: ShortText | None = None
    program_type: Literal["VOLUNTARY", "COMPLIANCE", "OTHER"]
    description: MidText | None = None
    source_url: Url | None = None
    environment: Literal["LIVE", "DEMO"] = "LIVE"


class StandardUpdate(BaseModel):
    name: Name | None = None
    owner_name: ShortText | None = None
    description: MidText | None = None
    source_url: Url | None = None
    status: Literal["ACTIVE", "INACTIVE"] | None = None


class ActivityIn(BaseModel):
    code: CatalogCode
    name: Name
    category: Annotated[str, StringConstraints(strip_whitespace=True, max_length=60)] | None = None
    description: MidText | None = None
    environment: Literal["LIVE", "DEMO"] = "LIVE"
    standard_ids: list[uuid.UUID] = []


class ActivityUpdate(BaseModel):
    name: Name | None = None
    category: Annotated[str, StringConstraints(strip_whitespace=True, max_length=60)] | None = None
    description: MidText | None = None
    status: Literal["ACTIVE", "INACTIVE"] | None = None


class StandardLink(BaseModel):
    standard_id: uuid.UUID


class ActivityOut(BaseModel):
    id: uuid.UUID
    code: str
    name: str
    category: str | None
    description: str | None
    status: str
    environment: str
    standard_ids: list[uuid.UUID] = []


class StandardOut(BaseModel):
    id: uuid.UUID
    code: str
    name: str
    owner_name: str | None
    program_type: str
    description: str | None
    source_url: str | None
    status: str
    environment: str
    activity_ids: list[uuid.UUID] = []


# ---------------------------------------------------------------- project
class ProjectCreate(BaseModel):
    organization_id: uuid.UUID
    name: Name
    description: LongText | None = None
    project_type: ProjectType
    country: Country
    region: ShortText | None = None
    start_date: date | None = None


class ProjectUpdate(BaseModel):
    name: Name | None = None
    description: LongText | None = None
    project_type: ProjectType | None = None
    country: Country | None = None
    region: ShortText | None = None
    start_date: date | None = None


class ProjectTransition(BaseModel):
    reason: Reason


class ProjectSummary(BaseModel):
    id: uuid.UUID
    project_code: str
    name: str
    project_type: str
    organization_id: uuid.UUID
    organization_name: str | None
    country: str
    region: str | None
    status: str
    start_date: date | None
    standard_name: str | None
    activity_name: str | None
    methodology_status: str
    farm_count: int
    area_hectares: Decimal | None
    environment: str
    created_at: UtcDatetime


class SelectionOut(BaseModel):
    id: uuid.UUID
    ref_id: uuid.UUID
    code: str
    name: str
    is_current: bool
    reason: str | None
    selected_by: uuid.UUID | None
    selected_at: UtcDatetime
    superseded_at: UtcDatetime | None


class ProjectOut(ProjectSummary):
    description: str | None
    standard_id: uuid.UUID | None
    activity_id: uuid.UUID | None
    current_boundary_id: uuid.UUID | None
    submitted_at: UtcDatetime | None
    submitted_by: uuid.UUID | None
    eligibility_reviewed_at: UtcDatetime | None
    eligibility_reviewed_by: uuid.UUID | None
    review_notes: str | None
    updated_at: UtcDatetime
    allowed_transitions: list[str]
    readiness: list[TransitionReadiness]
    can_manage: bool
    can_review: bool
    can_review_boundary: bool
    is_editable: bool
    counts: dict[str, int]


# ---------------------------------------------------------------- farms & carbon rights
class CarbonRightIn(BaseModel):
    holder_type: HolderType
    holder_farmer_id: uuid.UUID | None = None
    holder_organization_id: uuid.UUID | None = None
    holder_name: ShortText | None = None
    share_pct: Annotated[Decimal, Field(gt=0, le=100, max_digits=6, decimal_places=3)] | None = None
    agreement_id: uuid.UUID | None = None
    document_id: uuid.UUID | None = None
    reference: ShortText | None = None
    effective_from: date
    effective_to: date | None = None

    @model_validator(mode="after")
    def _check(self) -> "CarbonRightIn":
        if not (self.agreement_id or self.document_id or (self.reference and self.reference.strip())):
            raise ValueError("Record the agreement, a document or a reference that evidences the carbon rights.")
        if self.effective_to and self.effective_to < self.effective_from:
            raise ValueError("effective_to is before effective_from.")
        return self


class ProjectCarbonRightIn(CarbonRightIn):
    project_farm_id: uuid.UUID


class ProjectFarmIn(BaseModel):
    farm_id: uuid.UUID
    participation_start: date
    participation_end: date | None = None
    carbon_rights: CarbonRightIn
    acknowledge_conflicts: bool = False
    conflict_notes: MidText | None = None

    @model_validator(mode="after")
    def _dates(self) -> "ProjectFarmIn":
        if self.participation_end and self.participation_end < self.participation_start:
            raise ValueError("participation_end is before participation_start.")
        return self


class ConflictOut(BaseModel):
    kind: Literal["FARM_OVERLAP", "OTHER_PROJECT_PARTICIPATION"]
    status: str | None = None
    detail: str
    other_farm_code: str | None = None
    other_project_code: str | None = None
    overlap_area_m2: Decimal | None = None


class CarbonRightOut(BaseModel):
    id: uuid.UUID
    project_farm_id: uuid.UUID
    farm_id: uuid.UUID
    farm_code: str | None = None
    farmer_id: uuid.UUID
    holder_type: str
    holder_farmer_id: uuid.UUID | None
    holder_organization_id: uuid.UUID | None
    holder_name: str
    share_pct: Decimal | None
    agreement_id: uuid.UUID | None
    agreement_number: str | None = None
    document_id: uuid.UUID | None
    reference: str | None
    effective_from: date
    effective_to: date | None
    status: str
    verification_status: str
    reviewed_by: uuid.UUID | None
    reviewed_at: UtcDatetime | None
    review_notes: str | None
    end_reason: str | None
    created_by: uuid.UUID | None
    created_at: UtcDatetime


class ProjectFarmOut(BaseModel):
    id: uuid.UUID
    farm_id: uuid.UUID
    farm_code: str
    farm_name: str
    farm_status: str
    farmer_id: uuid.UUID
    farmer_code: str
    farmer_name: str
    status: str
    participation_start: date
    participation_end: date | None
    farm_boundary_id: uuid.UUID
    farm_area_hectares: Decimal
    boundary_changed: bool        # the farm's current boundary is no longer the version recorded when it was added
    conflicts_acknowledged: bool
    conflict_notes: str | None
    conflicts: list[ConflictOut]
    carbon_rights: list[CarbonRightOut]
    added_by: uuid.UUID | None
    added_at: UtcDatetime
    removed_at: UtcDatetime | None
    removal_reason: str | None
    geojson: dict[str, Any] | None = None


class ReasonBody(BaseModel):
    reason: Reason


class CarbonRightReview(BaseModel):
    status: Literal["VERIFIED", "REJECTED"]
    notes: Reason


class CarbonRightEnd(BaseModel):
    status: Literal["ENDED", "VOID"] = "ENDED"
    effective_to: date | None = None
    reason: Reason


class EligibleFarmOut(BaseModel):
    farm_id: uuid.UUID
    farm_code: str
    farm_name: str
    farmer_id: uuid.UUID
    farmer_name: str
    farmer_status: str
    farm_status: str
    area_hectares: Decimal | None
    eligible: bool
    reasons: list[str]
    conflicts: list[ConflictOut]
    in_other_projects: list[str]


# ---------------------------------------------------------------- participants
class ParticipantIn(BaseModel):
    user_id: uuid.UUID
    project_role: ProjectRole
    start_date: date | None = None
    end_date: date | None = None
    notes: Annotated[str, StringConstraints(strip_whitespace=True, max_length=1000)] | None = None


class ParticipantUpdate(BaseModel):
    start_date: date | None = None
    end_date: date | None = None
    notes: Annotated[str, StringConstraints(strip_whitespace=True, max_length=1000)] | None = None
    status: Literal["REMOVED"] | None = None
    reason: Reason | None = None


class ParticipantOut(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    user_name: str
    user_email: str
    project_role: str
    status: str
    start_date: date | None
    end_date: date | None
    notes: str | None
    added_by: uuid.UUID | None
    added_at: UtcDatetime
    updated_at: UtcDatetime | None
    removed_at: UtcDatetime | None
    removal_reason: str | None


class CandidateUserOut(BaseModel):
    user_id: uuid.UUID
    full_name: str
    email: str
    roles: list[str]


# ---------------------------------------------------------------- standard / activity selection
class StandardSelect(BaseModel):
    standard_id: uuid.UUID
    reason: Reason | None = None


class ActivitySelect(BaseModel):
    activity_id: uuid.UUID
    reason: Reason | None = None


class ProjectStandardsOut(BaseModel):
    current: StandardOut | None
    history: list[SelectionOut]
    available: list[StandardOut]


class ProjectActivitiesOut(BaseModel):
    current: ActivityOut | None
    history: list[SelectionOut]
    available: list[ActivityOut]
    methodology_status: str


# ---------------------------------------------------------------- crediting period / baseline
class CreditingPeriodIn(BaseModel):
    start_date: date
    end_date: date
    notes: MidText | None = None
    replaces_id: uuid.UUID | None = None
    reason: Reason | None = None

    @model_validator(mode="after")
    def _dates(self) -> "CreditingPeriodIn":
        if self.end_date <= self.start_date:
            raise ValueError("end_date must be after start_date.")
        return self


class CreditingPeriodOut(BaseModel):
    id: uuid.UUID
    period_number: int
    start_date: date
    end_date: date
    status: str
    notes: str | None
    replaces_id: uuid.UUID | None
    created_by: uuid.UUID | None
    created_at: UtcDatetime
    status_changed_at: UtcDatetime | None
    status_reason: str | None
    length_days: int


class BaselineIn(BaseModel):
    period_start: date
    period_end: date
    description: LongText | None = None
    data_sources: MidText | None = None
    notes: MidText | None = None
    reason: Reason | None = None

    @model_validator(mode="after")
    def _dates(self) -> "BaselineIn":
        if self.period_end < self.period_start:
            raise ValueError("period_end is before period_start.")
        return self


class BaselineOut(BaseModel):
    id: uuid.UUID
    version: int
    is_current: bool
    period_start: date
    period_end: date
    description: str | None
    data_sources: str | None
    notes: str | None
    change_reason: str | None
    created_by: uuid.UUID | None
    created_at: UtcDatetime


class BaselinesOut(BaseModel):
    current: BaselineOut | None
    versions: list[BaselineOut]
    note: str = "Baseline metadata only. No baseline emissions or removals are calculated in this phase."


# ---------------------------------------------------------------- boundary
class ProjectOverlapOut(BaseModel):
    other_project_id: uuid.UUID | None
    other_project_code: str | None
    other_project_visible: bool
    same_organization: bool
    overlap_area_m2: Decimal


class BoundaryReview(BaseModel):
    decision: Literal["ACCEPTED", "ISSUES"]
    notes: Reason


class ProjectBoundaryOut(BaseModel):
    id: uuid.UUID
    version: int
    status: str
    geojson: dict[str, Any]
    area_m2: Decimal
    area_hectares: Decimal
    sum_farm_area_hectares: Decimal
    internal_overlap_hectares: Decimal
    farm_count: int
    is_valid: bool
    validation_notes: str | None
    computed_by: uuid.UUID | None
    computed_at: UtcDatetime
    review_status: str
    reviewed_by: uuid.UUID | None
    reviewed_at: UtcDatetime | None
    review_notes: str | None


class BoundaryFarmOut(BaseModel):
    farm_id: uuid.UUID
    farm_code: str
    farm_name: str
    area_hectares: Decimal
    geojson: dict[str, Any]
    open_overlaps: int


class ProjectBoundaryView(BaseModel):
    current: ProjectBoundaryOut | None
    stale: bool                   # farms or their boundaries changed since the current version was computed
    farms: list[BoundaryFarmOut]
    project_overlaps: list[ProjectOverlapOut]
    versions: list[ProjectBoundaryOut]
    can_recompute: bool
    can_review: bool


# ---------------------------------------------------------------- history / participation
class StatusHistoryOut(BaseModel):
    id: int
    from_status: str | None
    to_status: str
    action: str
    reason: str | None
    changed_by: uuid.UUID | None
    changed_by_name: str | None
    changed_at: UtcDatetime
    request_id: str | None


class MyParticipationOut(BaseModel):
    project_id: uuid.UUID
    project_code: str
    project_name: str
    project_status: str
    farm_id: uuid.UUID
    farm_code: str
    farm_name: str
    participation_status: str
    participation_start: date
    participation_end: date | None
    carbon_rights: list[CarbonRightOut]


class ProjectDocumentsOut(BaseModel):
    documents: list[DocumentOut]
    categories: list[str]


__all__ = ["ChecklistItem", "TransitionReadiness"]
