"""Farm schemas."""
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field, StringConstraints, model_validator

from app.schemas.common import Reason, UtcDatetime
from app.schemas.documents import DocumentOut
from app.schemas.farmers import ChecklistItem, Country, Text, TransitionReadiness

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=200)]
Note = Annotated[str, StringConstraints(strip_whitespace=True, max_length=2000)]
Tenure = Literal["OWNED", "LEASED", "SHARECROPPED", "COMMUNITY", "GOVERNMENT_ALLOTTED", "CUSTOMARY", "OTHER"]
Source = Literal["FARMER_CLAIM", "FIELD_AGENT", "SATELLITE", "DOCUMENT", "INPUT_RECORD", "OTHER"]
Year = Annotated[int, Field(ge=1950, le=2100)]
Qty = Annotated[Decimal, Field(ge=0, max_digits=14, decimal_places=4)]


class FarmCreate(BaseModel):
    farmer_id: uuid.UUID
    name: Name
    village: Text | None = None
    sub_district: Text | None = None
    district: Text | None = None
    state: Text | None = None
    country: Country
    land_tenure: Tenure
    declared_area_hectares: Annotated[Decimal, Field(gt=0, max_digits=14, decimal_places=4)] | None = None


class FarmUpdate(BaseModel):
    name: Name | None = None
    village: Text | None = None
    sub_district: Text | None = None
    district: Text | None = None
    state: Text | None = None
    land_tenure: Tenure | None = None
    declared_area_hectares: Annotated[Decimal, Field(gt=0, max_digits=14, decimal_places=4)] | None = None


class GeometryIn(BaseModel):
    geojson: dict[str, Any] | None = None
    kml: Annotated[str, StringConstraints(max_length=2_000_000)] | None = None

    @model_validator(mode="after")
    def _one(self) -> "GeometryIn":
        if (self.geojson is None) == (self.kml is None):
            raise ValueError("provide exactly one of geojson or kml")
        return self


class BoundaryIn(GeometryIn):
    source: Literal["DRAWN", "GEOJSON_UPLOAD", "KML_UPLOAD", "GPS_WALK", "SURVEY", "IMPORT"] = "DRAWN"


class GeometryReportOut(BaseModel):
    geojson: dict[str, Any]
    area_m2: float
    area_hectares: float
    perimeter_m: float
    centroid_lat: float
    centroid_lon: float
    vertex_count: int
    notes: list[str]
    warnings: list[str]


class BoundaryOut(BaseModel):
    id: uuid.UUID
    version: int
    status: str
    source: str
    source_document_id: uuid.UUID | None
    geojson: dict[str, Any]
    area_hectares: Decimal
    area_m2: Decimal
    perimeter_m: Decimal
    centroid_lat: Decimal
    centroid_lon: Decimal
    vertex_count: int
    validation_notes: str | None
    created_by: uuid.UUID | None
    created_at: UtcDatetime
    superseded_at: UtcDatetime | None


class OwnershipIn(BaseModel):
    owner_type: Literal["FARMER", "INDIVIDUAL", "ORGANIZATION", "GOVERNMENT", "COMMUNITY"]
    owner_farmer_id: uuid.UUID | None = None
    owner_name: Name | None = None
    operator_relationship: Literal["OWNER", "CO_OWNER", "TENANT", "LESSEE", "SHARECROPPER", "CUSTODIAN", "OTHER"]
    ownership_share_pct: Annotated[Decimal, Field(gt=0, le=100, max_digits=5, decimal_places=2)] | None = None
    title_reference: Annotated[str, StringConstraints(strip_whitespace=True, max_length=120)] | None = None
    evidence_document_id: uuid.UUID | None = None
    valid_from: date | None = None


class OwnershipEnd(BaseModel):
    valid_to: date
    reason: Reason


class ReviewDecision(BaseModel):
    status: Literal["VERIFIED", "NEEDS_REVIEW", "REJECTED"]
    notes: Reason


class OwnershipOut(BaseModel):
    id: uuid.UUID
    owner_type: str
    owner_farmer_id: uuid.UUID | None
    owner_name: str
    operator_relationship: str
    ownership_share_pct: Decimal | None
    title_reference: str | None
    evidence_document_id: uuid.UUID | None
    valid_from: date | None
    valid_to: date | None
    end_reason: str | None
    is_current: bool
    verification_status: str
    reviewed_by: uuid.UUID | None
    reviewed_at: UtcDatetime | None
    review_notes: str | None
    recorded_by: uuid.UUID | None
    recorded_at: UtcDatetime


# ---------- history (land / crop / practice)
class HistoryBase(BaseModel):
    source: Source = "FARMER_CLAIM"
    evidence_document_id: uuid.UUID | None = None
    notes: Note | None = None


class LandHistoryIn(HistoryBase):
    year: Year
    land_use: Literal["CROPLAND", "GRASSLAND", "FOREST", "FALLOW", "WETLAND", "SETTLEMENT", "AGROFORESTRY", "OTHER"]
    land_use_detail: Annotated[str, StringConstraints(strip_whitespace=True, max_length=200)] | None = None


class CropHistoryIn(HistoryBase):
    year: Year
    season: Annotated[str, StringConstraints(strip_whitespace=True, max_length=40)] | None = None
    crop_name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=120)]
    crop_variety: Annotated[str, StringConstraints(strip_whitespace=True, max_length=120)] | None = None
    area_hectares: Qty | None = None
    planting_date: date | None = None
    harvest_date: date | None = None
    yield_quantity: Annotated[Decimal, Field(ge=0, max_digits=14, decimal_places=3)] | None = None
    yield_unit: Annotated[str, StringConstraints(strip_whitespace=True, max_length=20)] | None = None
    irrigation: Literal["RAINFED", "IRRIGATED", "PARTIAL"] | None = None
    residue_management: Annotated[str, StringConstraints(strip_whitespace=True, max_length=60)] | None = None

    @model_validator(mode="after")
    def _dates(self) -> "CropHistoryIn":
        if self.planting_date and self.harvest_date and self.harvest_date < self.planting_date:
            raise ValueError("harvest date is before planting date")
        if (self.yield_quantity is None) != (self.yield_unit is None):
            raise ValueError("yield quantity and unit go together")
        return self


class PracticeHistoryIn(HistoryBase):
    year: Year
    season: Annotated[str, StringConstraints(strip_whitespace=True, max_length=40)] | None = None
    practice_phase: Literal["HISTORICAL", "CURRENT", "PROPOSED"]
    practice_category: Literal["TILLAGE", "FERTILIZER", "MANURE", "IRRIGATION", "RESIDUE", "WATER_MANAGEMENT", "GRAZING",
                               "COVER_CROP", "CROP_ROTATION", "AGROFORESTRY", "OTHER"]
    practice_type: Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=120)]
    quantity: Annotated[Decimal, Field(ge=0, max_digits=14, decimal_places=3)] | None = None
    unit: Annotated[str, StringConstraints(strip_whitespace=True, max_length=30)] | None = None
    frequency: Annotated[str, StringConstraints(strip_whitespace=True, max_length=60)] | None = None
    start_date: date | None = None
    implementation_status: Literal["PLANNED", "IN_PROGRESS", "IMPLEMENTED", "ABANDONED"] | None = None
    expected_change: Annotated[str, StringConstraints(strip_whitespace=True, max_length=1000)] | None = None

    @model_validator(mode="after")
    def _proposed(self) -> "PracticeHistoryIn":
        if self.practice_phase == "PROPOSED" and self.implementation_status is None:
            raise ValueError("proposed practices need an implementation status")
        if (self.quantity is None) != (self.unit is None):
            raise ValueError("quantity and unit go together")
        return self


class AmendIn(BaseModel):
    reason: Reason
    data: dict[str, Any]


class HistoryOut(BaseModel):
    id: uuid.UUID
    record_id: uuid.UUID
    version: int
    is_current: bool
    is_retracted: bool
    source: str
    evidence_document_id: uuid.UUID | None
    verification_status: str
    reviewed_by: uuid.UUID | None
    reviewed_at: UtcDatetime | None
    review_notes: str | None
    change_reason: str | None
    notes: str | None
    recorded_by: uuid.UUID | None
    recorded_at: UtcDatetime
    fields: dict[str, Any]


# ---------- evidence
class EvidenceIn(BaseModel):
    claim_type: Literal["BOUNDARY", "OWNERSHIP", "LAND_USE", "CROP", "PRACTICE", "OTHER"]
    claim_record_id: uuid.UUID | None = None
    source_type: Source
    description: Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=2000)]
    document_id: uuid.UUID | None = None
    external_reference: Annotated[str, StringConstraints(strip_whitespace=True, max_length=300)] | None = None
    observed_at: datetime | None = None
    latitude: Annotated[Decimal, Field(ge=-90, le=90, max_digits=10, decimal_places=7)] | None = None
    longitude: Annotated[Decimal, Field(ge=-180, le=180, max_digits=10, decimal_places=7)] | None = None

    @model_validator(mode="after")
    def _loc(self) -> "EvidenceIn":
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("latitude and longitude go together")
        return self


class EvidenceOut(BaseModel):
    id: uuid.UUID
    claim_type: str
    claim_record_id: uuid.UUID | None
    source_type: str
    description: str
    document_id: uuid.UUID | None
    external_reference: str | None
    observed_at: UtcDatetime | None
    latitude: Decimal | None
    longitude: Decimal | None
    distance_to_boundary_m: float | None
    verification_status: str
    reviewed_by: uuid.UUID | None
    reviewed_at: UtcDatetime | None
    review_notes: str | None
    captured_by: uuid.UUID | None
    created_at: UtcDatetime


# ---------- overlaps
class OverlapResolve(BaseModel):
    resolution: Literal["CLEARED", "CONFIRMED_CONFLICT"]
    notes: Reason


class OverlapOut(BaseModel):
    id: uuid.UUID
    farm_id: uuid.UUID
    boundary_id: uuid.UUID
    other_farm_id: uuid.UUID | None          # hidden when the caller cannot see the other farm
    other_farm_code: str | None
    other_farm_visible: bool
    relation: str
    overlap_area_m2: Decimal
    overlap_pct_of_farm: Decimal
    overlap_pct_of_other: Decimal
    same_farmer: bool
    same_organization: bool
    status: str
    detected_at: UtcDatetime
    resolved_by: uuid.UUID | None
    resolved_at: UtcDatetime | None
    resolution_notes: str | None
    other_geojson: dict[str, Any] | None
    can_confirm: bool = False                # caller may mark this OPEN flag CONFIRMED_CONFLICT
    can_clear: bool = False                  # caller may CLEAR it (cross-org: Platform GIS Specialist only, decision D5)


# ---------- farm
class FarmSummary(BaseModel):
    id: uuid.UUID
    farm_code: str
    name: str
    farmer_id: uuid.UUID
    farmer_code: str
    farmer_name: str
    organization_id: uuid.UUID
    village: str | None
    district: str | None
    state: str | None
    country: str
    land_tenure: str
    declared_area_hectares: Decimal | None
    area_hectares: Decimal | None
    status: str
    open_overlaps: int
    environment: str
    centroid_lat: Decimal | None
    centroid_lon: Decimal | None
    created_at: UtcDatetime


class FarmOut(FarmSummary):
    sub_district: str | None
    current_boundary: BoundaryOut | None
    submitted_at: UtcDatetime | None
    submitted_by: uuid.UUID | None
    reviewed_by: uuid.UUID | None
    verified_at: UtcDatetime | None
    verified_by: uuid.UUID | None
    review_notes: str | None
    updated_at: UtcDatetime
    allowed_transitions: list[str]
    readiness: list[TransitionReadiness]
    history_counts: dict[str, int]
    evidence_count: int
    ownership_count: int
    can_manage: bool
    can_review: bool
    is_self: bool
    documents: list[DocumentOut]


class FarmTransition(BaseModel):
    reason: Reason


class NearQuery(BaseModel):
    lat: float
    lon: float
    radius_m: float


class NearbyFarm(BaseModel):
    farm_id: uuid.UUID
    farm_code: str
    name: str
    status: str
    distance_m: Decimal


__all__ = ["ChecklistItem", "TransitionReadiness"]
