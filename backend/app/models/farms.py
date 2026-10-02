"""Farm (spec section 7.3): boundary (geography, versioned), ownership, land/crop/practice history (versioned),
documents, evidence and overlap checks."""
import uuid
from datetime import date, datetime
from decimal import Decimal
from enum import Enum

from sqlalchemy import Boolean, CheckConstraint, Date, ForeignKey, Index, Integer, Numeric, Unicode, UnicodeText, UniqueConstraint, text
from sqlalchemy.orm import Mapped, declared_attr, mapped_column, relationship

from app.models.base import Base, Environment, Timestamped, UUIDPrimaryKey, in_check, utcnow
from app.models.gis import Geography


class FarmStatus(str, Enum):
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    GIS_REVIEW = "GIS_REVIEW"
    VERIFIED = "VERIFIED"
    REJECTED = "REJECTED"
    INACTIVE = "INACTIVE"


LAND_TENURES = ["OWNED", "LEASED", "SHARECROPPED", "COMMUNITY", "GOVERNMENT_ALLOTTED", "CUSTOMARY", "OTHER"]
EVIDENCE_SOURCES = ["FARMER_CLAIM", "FIELD_AGENT", "SATELLITE", "DOCUMENT", "INPUT_RECORD", "OTHER"]
VERIFICATION_STATES = ["UNVERIFIED", "VERIFIED", "NEEDS_REVIEW", "REJECTED"]


class Farm(UUIDPrimaryKey, Timestamped, Base):
    __tablename__ = "farms"
    __table_args__ = (
        CheckConstraint(in_check("status", FarmStatus), name="status"),
        CheckConstraint(in_check("land_tenure", LAND_TENURES), name="land_tenure"),
        CheckConstraint(in_check("environment", Environment), name="environment"),
        CheckConstraint("area_hectares IS NULL OR area_hectares > 0", name="area_positive"),
    )
    farm_code: Mapped[str] = mapped_column(Unicode(30), unique=True)
    farmer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("farmers.id"), index=True)  # operator; not necessarily owner
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), index=True)
    name: Mapped[str] = mapped_column(Unicode(200))
    village: Mapped[str | None] = mapped_column(Unicode(120))
    sub_district: Mapped[str | None] = mapped_column(Unicode(120))
    district: Mapped[str | None] = mapped_column(Unicode(120))
    state: Mapped[str | None] = mapped_column(Unicode(120))
    country: Mapped[str] = mapped_column(Unicode(2))
    land_tenure: Mapped[str] = mapped_column(Unicode(25))
    declared_area_hectares: Mapped[Decimal | None] = mapped_column(Numeric(14, 4))
    area_hectares: Mapped[Decimal | None] = mapped_column(Numeric(14, 4))  # measured by SQL Server from the current boundary
    current_boundary_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("farm_boundaries.id", use_alter=True))
    status: Mapped[str] = mapped_column(Unicode(15), default=FarmStatus.DRAFT.value)
    submitted_at: Mapped[datetime | None]
    submitted_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    verified_at: Mapped[datetime | None]
    verified_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    review_notes: Mapped[str | None] = mapped_column(Unicode(2000))
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    environment: Mapped[str] = mapped_column(Unicode(10), default=Environment.LIVE.value)

    boundaries: Mapped[list["FarmBoundary"]] = relationship(back_populates="farm", foreign_keys="FarmBoundary.farm_id",
                                                            order_by="FarmBoundary.version")


class FarmBoundary(UUIDPrimaryKey, Base):
    """Every boundary ever saved is kept; exactly one per farm is CURRENT."""
    __tablename__ = "farm_boundaries"
    __table_args__ = (
        UniqueConstraint("farm_id", "version"),
        CheckConstraint(in_check("status", ["CURRENT", "SUPERSEDED"]), name="status"),
        CheckConstraint(in_check("source", ["DRAWN", "GEOJSON_UPLOAD", "KML_UPLOAD", "GPS_WALK", "SURVEY", "IMPORT"]), name="source"),
        Index("uq_farm_boundaries_current", "farm_id", unique=True, mssql_where=text("status = 'CURRENT'")),
    )
    farm_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("farms.id"))
    version: Mapped[int] = mapped_column(Integer)
    boundary: Mapped[str] = mapped_column(Geography())  # WKT on the Python side; geography in SQL Server
    source: Mapped[str] = mapped_column(Unicode(20))
    source_document_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("documents.id"))
    area_m2: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    area_hectares: Mapped[Decimal] = mapped_column(Numeric(14, 4))
    perimeter_m: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    centroid_lat: Mapped[Decimal] = mapped_column(Numeric(10, 7))
    centroid_lon: Mapped[Decimal] = mapped_column(Numeric(10, 7))
    vertex_count: Mapped[int] = mapped_column(Integer)
    validation_notes: Mapped[str | None] = mapped_column(UnicodeText)
    status: Mapped[str] = mapped_column(Unicode(12), default="CURRENT")
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(default=utcnow, server_default=text("SYSUTCDATETIME()"))
    superseded_at: Mapped[datetime | None]

    farm: Mapped[Farm] = relationship(back_populates="boundaries", foreign_keys=[farm_id])


class FarmOwnership(UUIDPrimaryKey, Base):
    """Who owns / holds rights to the land. The farmer operating the farm need not be the owner."""
    __tablename__ = "farm_ownership"
    __table_args__ = (
        CheckConstraint(in_check("owner_type", ["FARMER", "INDIVIDUAL", "ORGANIZATION", "GOVERNMENT", "COMMUNITY"]), name="owner_type"),
        CheckConstraint(in_check("operator_relationship", ["OWNER", "CO_OWNER", "TENANT", "LESSEE", "SHARECROPPER",
                                                           "CUSTODIAN", "OTHER"]), name="operator_relationship"),
        CheckConstraint(in_check("verification_status", VERIFICATION_STATES), name="verification_status"),
        CheckConstraint("ownership_share_pct IS NULL OR (ownership_share_pct > 0 AND ownership_share_pct <= 100)", name="share"),
        CheckConstraint("valid_to IS NULL OR valid_from IS NULL OR valid_to >= valid_from", name="dates"),
    )
    farm_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("farms.id"), index=True)
    owner_type: Mapped[str] = mapped_column(Unicode(15))
    owner_farmer_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("farmers.id"))
    owner_name: Mapped[str] = mapped_column(Unicode(200))
    operator_relationship: Mapped[str] = mapped_column(Unicode(15))
    ownership_share_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    title_reference: Mapped[str | None] = mapped_column(Unicode(120))  # land record / survey number
    evidence_document_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("documents.id"))
    valid_from: Mapped[date | None] = mapped_column(Date)
    valid_to: Mapped[date | None] = mapped_column(Date)
    end_reason: Mapped[str | None] = mapped_column(Unicode(1000))
    verification_status: Mapped[str] = mapped_column(Unicode(15), default="UNVERIFIED")
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    reviewed_at: Mapped[datetime | None]
    review_notes: Mapped[str | None] = mapped_column(Unicode(1000))
    recorded_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    recorded_at: Mapped[datetime] = mapped_column(default=utcnow, server_default=text("SYSUTCDATETIME()"))


class VersionedHistory:
    """History-preserving records: an edit inserts a new version; previous versions are never changed
    (only `is_current` flips). A retraction is a new version with is_retracted = 1."""
    record_id: Mapped[uuid.UUID]
    version: Mapped[int] = mapped_column(Integer)
    is_current: Mapped[bool] = mapped_column(Boolean, default=True)
    is_retracted: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("0"))
    source: Mapped[str] = mapped_column(Unicode(15))
    evidence_document_id: Mapped[uuid.UUID | None]
    verification_status: Mapped[str] = mapped_column(Unicode(15), default="UNVERIFIED")
    reviewed_by: Mapped[uuid.UUID | None]
    reviewed_at: Mapped[datetime | None]
    review_notes: Mapped[str | None] = mapped_column(Unicode(1000))
    change_reason: Mapped[str | None] = mapped_column(Unicode(1000))
    notes: Mapped[str | None] = mapped_column(Unicode(2000))
    recorded_by: Mapped[uuid.UUID | None]
    recorded_at: Mapped[datetime] = mapped_column(default=utcnow, server_default=text("SYSUTCDATETIME()"))

    @declared_attr
    def farm_id(cls) -> Mapped[uuid.UUID]:
        return mapped_column(ForeignKey("farms.id"))

    @classmethod
    def history_args(cls, table: str) -> tuple:
        return (
            UniqueConstraint("record_id", "version", name=f"uq_{table}_record_version"),
            Index(f"uq_{table}_current", "record_id", unique=True, mssql_where=text("is_current = 1")),
            Index(f"ix_{table}_farm_current", "farm_id", "is_current"),
            CheckConstraint(in_check("source", EVIDENCE_SOURCES), name="source"),
            CheckConstraint(in_check("verification_status", VERIFICATION_STATES), name="verification_status"),
        )


LAND_USES = ["CROPLAND", "GRASSLAND", "FOREST", "FALLOW", "WETLAND", "SETTLEMENT", "AGROFORESTRY", "OTHER"]
PRACTICE_CATEGORIES = ["TILLAGE", "FERTILIZER", "MANURE", "IRRIGATION", "RESIDUE", "WATER_MANAGEMENT", "GRAZING",
                       "COVER_CROP", "CROP_ROTATION", "AGROFORESTRY", "OTHER"]


class FarmLandHistory(UUIDPrimaryKey, VersionedHistory, Base):
    __tablename__ = "farm_land_history"
    __table_args__ = (*VersionedHistory.history_args("farm_land_history"),
                      CheckConstraint(in_check("land_use", LAND_USES), name="land_use"),
                      CheckConstraint("year BETWEEN 1950 AND 2100", name="year"))
    year: Mapped[int] = mapped_column(Integer)
    land_use: Mapped[str] = mapped_column(Unicode(20))
    land_use_detail: Mapped[str | None] = mapped_column(Unicode(200))


class FarmCropHistory(UUIDPrimaryKey, VersionedHistory, Base):
    __tablename__ = "farm_crop_history"
    __table_args__ = (*VersionedHistory.history_args("farm_crop_history"),
                      CheckConstraint("year BETWEEN 1950 AND 2100", name="year"),
                      CheckConstraint("irrigation IS NULL OR " + in_check("irrigation", ["RAINFED", "IRRIGATED", "PARTIAL"]), name="irrigation"),
                      CheckConstraint("harvest_date IS NULL OR planting_date IS NULL OR harvest_date >= planting_date", name="dates"))
    year: Mapped[int] = mapped_column(Integer)
    season: Mapped[str | None] = mapped_column(Unicode(40))
    crop_name: Mapped[str] = mapped_column(Unicode(120))
    crop_variety: Mapped[str | None] = mapped_column(Unicode(120))
    area_hectares: Mapped[Decimal | None] = mapped_column(Numeric(14, 4))
    planting_date: Mapped[date | None] = mapped_column(Date)
    harvest_date: Mapped[date | None] = mapped_column(Date)
    yield_quantity: Mapped[Decimal | None] = mapped_column(Numeric(14, 3))
    yield_unit: Mapped[str | None] = mapped_column(Unicode(20))
    irrigation: Mapped[str | None] = mapped_column(Unicode(10))
    residue_management: Mapped[str | None] = mapped_column(Unicode(60))


class FarmPracticeHistory(UUIDPrimaryKey, VersionedHistory, Base):
    __tablename__ = "farm_practice_history"
    __table_args__ = (*VersionedHistory.history_args("farm_practice_history"),
                      CheckConstraint(in_check("practice_phase", ["HISTORICAL", "CURRENT", "PROPOSED"]), name="practice_phase"),
                      CheckConstraint(in_check("practice_category", PRACTICE_CATEGORIES), name="practice_category"),
                      CheckConstraint("implementation_status IS NULL OR " + in_check("implementation_status",
                                      ["PLANNED", "IN_PROGRESS", "IMPLEMENTED", "ABANDONED"]), name="implementation_status"),
                      CheckConstraint("year BETWEEN 1950 AND 2100", name="year"))
    year: Mapped[int] = mapped_column(Integer)
    season: Mapped[str | None] = mapped_column(Unicode(40))
    practice_phase: Mapped[str] = mapped_column(Unicode(12))
    practice_category: Mapped[str] = mapped_column(Unicode(20))
    practice_type: Mapped[str] = mapped_column(Unicode(120))
    quantity: Mapped[Decimal | None] = mapped_column(Numeric(14, 3))
    unit: Mapped[str | None] = mapped_column(Unicode(30))
    frequency: Mapped[str | None] = mapped_column(Unicode(60))
    start_date: Mapped[date | None] = mapped_column(Date)
    implementation_status: Mapped[str | None] = mapped_column(Unicode(15))
    expected_change: Mapped[str | None] = mapped_column(Unicode(1000))


class FarmDocument(UUIDPrimaryKey, Base):
    __tablename__ = "farm_documents"
    farm_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("farms.id"), index=True)
    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("documents.id"), unique=True)
    created_at: Mapped[datetime] = mapped_column(default=utcnow, server_default=text("SYSUTCDATETIME()"))


class FarmEvidence(UUIDPrimaryKey, Base):
    """Evidence supporting (or contradicting) a farm claim — spec section 11 evidence engine inputs."""
    __tablename__ = "farm_evidence"
    __table_args__ = (
        CheckConstraint(in_check("claim_type", ["BOUNDARY", "OWNERSHIP", "LAND_USE", "CROP", "PRACTICE", "OTHER"]), name="claim_type"),
        CheckConstraint(in_check("source_type", EVIDENCE_SOURCES), name="source_type"),
        CheckConstraint(in_check("verification_status", VERIFICATION_STATES), name="verification_status"),
        CheckConstraint("(latitude IS NULL AND longitude IS NULL) OR (latitude BETWEEN -90 AND 90 AND longitude BETWEEN -180 AND 180)",
                        name="location"),
    )
    farm_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("farms.id"), index=True)
    claim_type: Mapped[str] = mapped_column(Unicode(15))
    claim_record_id: Mapped[uuid.UUID | None]  # history record_id / ownership id the evidence relates to
    source_type: Mapped[str] = mapped_column(Unicode(15))
    description: Mapped[str] = mapped_column(Unicode(2000))
    document_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("documents.id"))
    external_reference: Mapped[str | None] = mapped_column(Unicode(300))  # e.g. satellite scene id, record number
    observed_at: Mapped[datetime | None]
    latitude: Mapped[Decimal | None] = mapped_column(Numeric(10, 7))
    longitude: Mapped[Decimal | None] = mapped_column(Numeric(10, 7))
    verification_status: Mapped[str] = mapped_column(Unicode(15), default="UNVERIFIED")
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    reviewed_at: Mapped[datetime | None]
    review_notes: Mapped[str | None] = mapped_column(Unicode(1000))
    captured_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(default=utcnow, server_default=text("SYSUTCDATETIME()"))


class FarmOverlapCheck(UUIDPrimaryKey, Base):
    """A detected intersection between two current farm boundaries. Flagged for review, never auto-rejected."""
    __tablename__ = "farm_overlap_checks"
    __table_args__ = (
        CheckConstraint(in_check("status", ["OPEN", "CLEARED", "CONFIRMED_CONFLICT", "OBSOLETE"]), name="status"),
        CheckConstraint(in_check("relation", ["PARTIAL", "CONTAINS", "WITHIN", "EQUAL"]), name="relation"),
        Index("ix_farm_overlap_checks_farm_status", "farm_id", "status"),
    )
    farm_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("farms.id"))
    boundary_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("farm_boundaries.id"))
    other_farm_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("farms.id"), index=True)
    other_boundary_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("farm_boundaries.id"))
    relation: Mapped[str] = mapped_column(Unicode(10))
    overlap_area_m2: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    overlap_pct_of_farm: Mapped[Decimal] = mapped_column(Numeric(7, 3))
    overlap_pct_of_other: Mapped[Decimal] = mapped_column(Numeric(7, 3))
    same_farmer: Mapped[bool] = mapped_column(Boolean)
    same_organization: Mapped[bool] = mapped_column(Boolean)
    status: Mapped[str] = mapped_column(Unicode(20), default="OPEN")
    detected_at: Mapped[datetime] = mapped_column(default=utcnow, server_default=text("SYSUTCDATETIME()"))
    resolved_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    resolved_at: Mapped[datetime | None]
    resolution_notes: Mapped[str | None] = mapped_column(Unicode(2000))


Farm.current_boundary = relationship(FarmBoundary, foreign_keys=[Farm.current_boundary_id], viewonly=True)  # type: ignore[attr-defined]
