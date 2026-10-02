"""MRV (spec section 7.6, 7.7, 13, 14, 17): MRV plans, monitoring periods, strata, sampling designs and points,
assignments, field collection records, monitoring (activity) records, evidence, MRV datasets and QA reviews.

Rules:
- everything hangs off a project whose methodology + version is LOCKED (Phase 4); requirements come from that
  version's monitoring and SAMPLING rules. Anything the version does not configure is CONFIGURATION_REQUIRED and
  any project-configured value is labelled PROJECT_CONFIGURED — nothing methodology-specific is invented
- approved plans, strata, design versions and datasets are never edited: corrections are new versions
- sampling points are validated by SQL Server geography (inside a participating farm's current boundary);
  moving a point needs a relocation request with old/new location, reason, user, time and approval
- field collection records and monitoring records are versioned (corrections create new versions)
- no laboratory, calculation or carbon quantity exists in Phase 5
"""
import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    Unicode,
    UnicodeText,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, Environment, UUIDPrimaryKey, in_check, utcnow
from app.models.gis import Geography

PLAN_STATUSES = ["DRAFT", "SUBMITTED", "APPROVED", "SUPERSEDED", "WITHDRAWN"]
PERIOD_STATUSES = ["DRAFT", "PLANNED", "ACTIVE", "DATA_COLLECTION", "SUBMITTED", "QA_REVIEW", "APPROVED", "REJECTED", "CLOSED"]
DATASET_STATUSES = ["DRAFT", "COLLECTING", "SUBMITTED", "QA_REVIEW", "APPROVED", "REJECTED", "SUPERSEDED"]
QUANTIFICATION = ["MEASURE_AND_REMEASURE", "MEASURE_AND_MODEL", "OTHER", "CONFIGURATION_REQUIRED"]
MEASUREMENT_CATEGORIES = ["SOIL", "CROP", "PLANTING", "HARVEST", "TILLAGE", "FERTILIZER", "MANURE", "RESIDUE", "IRRIGATION",
                          "WATER_MANAGEMENT", "YIELD", "PRACTICE_CHANGE", "FUEL", "OTHER"]
VALUE_TYPES = ["NUMBER", "TEXT", "DATE", "BOOLEAN", "CHOICE"]
MEASUREMENT_LEVELS = ["PROJECT", "FARM", "STRATUM", "SAMPLING_POINT"]
STRATUM_CHARACTERISTICS = ["SOIL_TYPE", "CROP", "LAND_USE", "MANAGEMENT_PRACTICE", "IRRIGATION", "GEOGRAPHY", "CLIMATE", "OTHER"]
EVIDENCE_TYPES = ["FIELD_PHOTO", "FIELD_NOTE", "PRACTICE_RECORD", "DOCUMENT", "GPS", "OBSERVATION"]
EVIDENCE_ENTITIES = ["PROJECT", "FARM", "MONITORING_PERIOD", "SAMPLING_POINT", "FIELD_COLLECTION", "MONITORING_RECORD"]


class MrvPlan(UUIDPrimaryKey, Base):
    """One version of a project's MRV plan, bound to the locked methodology version."""
    __tablename__ = "mrv_plans"
    __table_args__ = (
        UniqueConstraint("project_id", "plan_version"),
        CheckConstraint(in_check("status", PLAN_STATUSES), name="status"),
        CheckConstraint(in_check("quantification_approach", QUANTIFICATION), name="quantification_approach"),
        CheckConstraint(in_check("configuration_status", ["CONFIGURED", "CONFIGURATION_REQUIRED"]), name="configuration_status"),
        CheckConstraint("monitoring_end IS NULL OR monitoring_start IS NULL OR monitoring_end > monitoring_start", name="dates"),
        CheckConstraint("configuration_gaps IS NULL OR ISJSON(configuration_gaps) = 1", name="gaps_json"),
        Index("uq_mrv_plans_approved", "project_id", unique=True, mssql_where=text("status = 'APPROVED'")),
    )
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    plan_version: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(Unicode(12), default="DRAFT")
    project_methodology_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("project_methodologies.id"))
    methodology_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("methodologies.id"))
    methodology_version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("methodology_versions.id"))
    monitoring_frequency: Mapped[str | None] = mapped_column(Unicode(200))
    monitoring_start: Mapped[date | None] = mapped_column(Date)
    monitoring_end: Mapped[date | None] = mapped_column(Date)
    quantification_approach: Mapped[str] = mapped_column(Unicode(25), default="CONFIGURATION_REQUIRED")
    sampling_requirements_ref: Mapped[str | None] = mapped_column(Unicode(1000))   # methodology rule codes used
    required_evidence: Mapped[str | None] = mapped_column(Unicode(2000))
    configuration_status: Mapped[str] = mapped_column(Unicode(25), default="CONFIGURATION_REQUIRED")
    configuration_gaps: Mapped[str | None] = mapped_column(UnicodeText)                # JSON list of unconfigured requirements
    gaps_acknowledged_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    notes: Mapped[str | None] = mapped_column(Unicode(2000))
    supersedes_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("mrv_plans.id"))
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(default=utcnow, server_default=text("SYSUTCDATETIME()"))
    submitted_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    submitted_at: Mapped[datetime | None]
    approved_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    approved_at: Mapped[datetime | None]
    status_reason: Mapped[str | None] = mapped_column(Unicode(1000))


class MrvPlanMeasurement(UUIDPrimaryKey, Base):
    """Configurable measurement definition of a plan version: copied from the methodology's monitoring rules
    (source METHODOLOGY) or added by the project (source PROJECT_CONFIGURED)."""
    __tablename__ = "mrv_plan_measurements"
    __table_args__ = (
        UniqueConstraint("mrv_plan_id", "code"),
        CheckConstraint(in_check("category", MEASUREMENT_CATEGORIES), name="category"),
        CheckConstraint(in_check("value_type", VALUE_TYPES), name="value_type"),
        CheckConstraint(in_check("level", MEASUREMENT_LEVELS), name="level"),
        CheckConstraint(in_check("source", ["METHODOLOGY", "PROJECT_CONFIGURED"]), name="source"),
        CheckConstraint("allowed_values IS NULL OR ISJSON(allowed_values) = 1", name="allowed_values_json"),
    )
    mrv_plan_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("mrv_plans.id"), index=True)
    code: Mapped[str] = mapped_column(Unicode(40))
    name: Mapped[str] = mapped_column(Unicode(200))
    category: Mapped[str] = mapped_column(Unicode(20))
    value_type: Mapped[str] = mapped_column(Unicode(10))
    unit: Mapped[str | None] = mapped_column(Unicode(40))
    allowed_values: Mapped[str | None] = mapped_column(UnicodeText)
    level: Mapped[str] = mapped_column(Unicode(20), default="FARM")
    frequency: Mapped[str | None] = mapped_column(Unicode(120))
    required: Mapped[bool] = mapped_column(Boolean, default=True)
    source: Mapped[str] = mapped_column(Unicode(20))
    monitoring_rule_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("methodology_monitoring_rules.id"))


class MonitoringPeriod(UUIDPrimaryKey, Base):
    __tablename__ = "monitoring_periods"
    __table_args__ = (
        UniqueConstraint("project_id", "period_number"),
        CheckConstraint(in_check("status", PERIOD_STATUSES), name="status"),
        CheckConstraint(in_check("purpose", ["BASELINE", "MONITORING", "VERIFICATION", "OTHER"]), name="purpose"),
        CheckConstraint("end_date > start_date", name="dates"),
    )
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    mrv_plan_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("mrv_plans.id"), index=True)
    methodology_version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("methodology_versions.id"))
    period_number: Mapped[int] = mapped_column(Integer)
    name: Mapped[str] = mapped_column(Unicode(200))
    purpose: Mapped[str] = mapped_column(Unicode(15), default="MONITORING")   # BASELINE = baseline measurement (measure & remeasure)
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(Unicode(16), default="DRAFT")
    status_reason: Mapped[str | None] = mapped_column(Unicode(1000))
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(default=utcnow, server_default=text("SYSUTCDATETIME()"))
    updated_at: Mapped[datetime] = mapped_column(default=utcnow, onupdate=utcnow, server_default=text("SYSUTCDATETIME()"))


class ProjectStratum(UUIDPrimaryKey, Base):
    """A versioned stratum: a group of participating farms with shared characteristics. Geometry and area are the
    SQL Server union of the member farms' current boundaries."""
    __tablename__ = "project_strata"
    __table_args__ = (
        UniqueConstraint("record_id", "version"),
        CheckConstraint(in_check("status", ["DRAFT", "APPROVED", "SUPERSEDED", "RETIRED"]), name="status"),
        CheckConstraint(in_check("source", ["FARM_GROUPING", "IMPORTED"]), name="source"),
        CheckConstraint("criteria IS NULL OR ISJSON(criteria) = 1", name="criteria_json"),
        Index("uq_project_strata_current", "record_id", unique=True, mssql_where=text("is_current = 1")),
    )
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    record_id: Mapped[uuid.UUID] = mapped_column(index=True)        # stable identity across versions
    version: Mapped[int] = mapped_column(Integer, default=1)
    is_current: Mapped[bool] = mapped_column(Boolean, default=True)
    code: Mapped[str] = mapped_column(Unicode(40))
    name: Mapped[str] = mapped_column(Unicode(200))
    description: Mapped[str | None] = mapped_column(Unicode(2000))
    criteria: Mapped[str | None] = mapped_column(UnicodeText)       # JSON: the stratification rule used
    geometry: Mapped[str | None] = mapped_column(Geography())
    area_hectares: Mapped[Decimal | None] = mapped_column(Numeric(14, 4))
    farm_boundary_ids: Mapped[str | None] = mapped_column(UnicodeText)  # JSON: exact farm boundary versions in the union
    source: Mapped[str] = mapped_column(Unicode(15), default="FARM_GROUPING")
    status: Mapped[str] = mapped_column(Unicode(12), default="DRAFT")
    change_reason: Mapped[str | None] = mapped_column(Unicode(1000))
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(default=utcnow, server_default=text("SYSUTCDATETIME()"))
    approved_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    approved_at: Mapped[datetime | None]


class StratumFarm(Base):
    __tablename__ = "stratum_farms"
    stratum_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("project_strata.id"), primary_key=True)
    farm_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("farms.id"), primary_key=True, index=True)
    farm_boundary_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("farm_boundaries.id"))


class StratumCharacteristic(UUIDPrimaryKey, Base):
    __tablename__ = "stratum_characteristics"
    __table_args__ = (
        UniqueConstraint("stratum_id", "characteristic"),
        CheckConstraint(in_check("characteristic", STRATUM_CHARACTERISTICS), name="characteristic"),
        CheckConstraint(in_check("source", ["FARM_DATA", "FIELD_OBSERVATION", "DECLARED", "EXTERNAL_DATASET"]), name="source"),
    )
    stratum_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("project_strata.id"), index=True)
    characteristic: Mapped[str] = mapped_column(Unicode(25))
    value: Mapped[str] = mapped_column(Unicode(200))
    source: Mapped[str] = mapped_column(Unicode(20), default="DECLARED")
    required_by_methodology: Mapped[bool] = mapped_column(Boolean, default=False)


class SamplingDesign(UUIDPrimaryKey, Base):
    __tablename__ = "sampling_designs"
    __table_args__ = (UniqueConstraint("monitoring_period_id", "code"),)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    mrv_plan_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("mrv_plans.id"))
    monitoring_period_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("monitoring_periods.id"), index=True)
    methodology_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("methodologies.id"))
    methodology_version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("methodology_versions.id"))
    code: Mapped[str] = mapped_column(Unicode(40))
    name: Mapped[str] = mapped_column(Unicode(200))
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(default=utcnow, server_default=text("SYSUTCDATETIME()"))


class SamplingDesignVersion(UUIDPrimaryKey, Base):
    """Configured sampling parameters. Sample counts are entered per stratum (never derived from an area rule)."""
    __tablename__ = "sampling_design_versions"
    __table_args__ = (
        UniqueConstraint("design_id", "version"),
        CheckConstraint(in_check("status", ["DRAFT", "APPROVED", "SUPERSEDED"]), name="status"),
        CheckConstraint(in_check("statistical_design", ["STRATIFIED_RANDOM", "SIMPLE_RANDOM", "SYSTEMATIC_GRID", "OTHER"]),
                        name="statistical_design"),
        CheckConstraint(in_check("requirement_source", ["METHODOLOGY", "PROJECT_CONFIGURED"]), name="requirement_source"),
        CheckConstraint(in_check("configuration_status", ["CONFIGURED", "CONFIGURATION_REQUIRED"]), name="configuration_status"),
        CheckConstraint("depth_bottom_cm > depth_top_cm", name="depth"),
        CheckConstraint("configuration_gaps IS NULL OR ISJSON(configuration_gaps) = 1", name="gaps_json"),
        CheckConstraint("field_rules IS NULL OR ISJSON(field_rules) = 1", name="field_rules_json"),
        Index("uq_sampling_design_versions_approved", "design_id", unique=True, mssql_where=text("status = 'APPROVED'")),
    )
    design_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sampling_designs.id"), index=True)
    version: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(Unicode(12), default="DRAFT")
    statistical_design: Mapped[str] = mapped_column(Unicode(20))
    target_precision_pct: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    confidence_level_pct: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    variability_cv_pct: Mapped[Decimal | None] = mapped_column(Numeric(7, 2))
    min_detectable_difference: Mapped[str | None] = mapped_column(Unicode(100))
    sampling_method: Mapped[str | None] = mapped_column(Unicode(1000))
    depth_top_cm: Mapped[Decimal] = mapped_column(Numeric(6, 1))
    depth_bottom_cm: Mapped[Decimal] = mapped_column(Numeric(6, 1))
    min_distance_m: Mapped[Decimal | None] = mapped_column(Numeric(8, 1))
    repeat_sampling: Mapped[str | None] = mapped_column(Unicode(500))
    random_seed: Mapped[int] = mapped_column(Integer)          # recorded so generation is reproducible
    requirement_source: Mapped[str] = mapped_column(Unicode(20))
    configuration_status: Mapped[str] = mapped_column(Unicode(25))
    configuration_gaps: Mapped[str | None] = mapped_column(UnicodeText)
    # field-collection rules frozen when the version is created (GPS tolerance, duplicate threshold, checklist version
    # and items, minimum photos, each with its source PLATFORM_DEFAULT / METHODOLOGY) — decisions S1, S2
    field_rules: Mapped[str | None] = mapped_column(UnicodeText)
    notes: Mapped[str | None] = mapped_column(Unicode(2000))
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(default=utcnow, server_default=text("SYSUTCDATETIME()"))
    approved_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    approved_at: Mapped[datetime | None]
    points_generated_at: Mapped[datetime | None]


class SamplingDesignStratum(Base):
    """Per-stratum allocation of a design version (configured sample count + recorded basis)."""
    __tablename__ = "sampling_design_strata"
    __table_args__ = (CheckConstraint("sample_count > 0", name="sample_count"),)
    design_version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sampling_design_versions.id"), primary_key=True)
    stratum_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("project_strata.id"), primary_key=True)
    sample_count: Mapped[int] = mapped_column(Integer)
    allocation_basis: Mapped[str | None] = mapped_column(Unicode(500))


class SamplingPoint(UUIDPrimaryKey, Base):
    __tablename__ = "sampling_points"
    __table_args__ = (
        CheckConstraint(in_check("status", ["PLANNED", "ASSIGNED", "COLLECTED", "SKIPPED", "CANCELLED"]), name="status"),
        CheckConstraint("latitude BETWEEN -90 AND 90 AND longitude BETWEEN -180 AND 180", name="coordinates"),
        UniqueConstraint("design_version_id", "stratum_id", "sequence"),
    )
    point_code: Mapped[str] = mapped_column(Unicode(30), unique=True)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    monitoring_period_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("monitoring_periods.id"), index=True)
    design_version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sampling_design_versions.id"), index=True)
    stratum_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("project_strata.id"), index=True)
    farm_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("farms.id"), index=True)
    farm_boundary_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("farm_boundaries.id"))
    sequence: Mapped[int] = mapped_column(Integer)
    location: Mapped[str] = mapped_column(Geography())
    latitude: Mapped[Decimal] = mapped_column(Numeric(10, 7))
    longitude: Mapped[Decimal] = mapped_column(Numeric(10, 7))
    planned_depth_top_cm: Mapped[Decimal] = mapped_column(Numeric(6, 1))
    planned_depth_bottom_cm: Mapped[Decimal] = mapped_column(Numeric(6, 1))
    status: Mapped[str] = mapped_column(Unicode(12), default="PLANNED")
    assigned_collector_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), index=True)
    planned_date: Mapped[date | None] = mapped_column(Date)
    status_reason: Mapped[str | None] = mapped_column(Unicode(1000))
    created_at: Mapped[datetime] = mapped_column(default=utcnow, server_default=text("SYSUTCDATETIME()"))


class SamplingPointRelocation(UUIDPrimaryKey, Base):
    """A requested move of a sampling point. The point only moves when the request is approved."""
    __tablename__ = "sampling_point_relocations"
    __table_args__ = (CheckConstraint(in_check("status", ["PENDING", "APPROVED", "REJECTED"]), name="status"),)
    sampling_point_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sampling_points.id"), index=True)
    old_latitude: Mapped[Decimal] = mapped_column(Numeric(10, 7))
    old_longitude: Mapped[Decimal] = mapped_column(Numeric(10, 7))
    new_latitude: Mapped[Decimal] = mapped_column(Numeric(10, 7))
    new_longitude: Mapped[Decimal] = mapped_column(Numeric(10, 7))
    distance_m: Mapped[Decimal] = mapped_column(Numeric(10, 1))
    reason: Mapped[str] = mapped_column(Unicode(1000))
    status: Mapped[str] = mapped_column(Unicode(10), default="PENDING")
    requested_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    requested_at: Mapped[datetime] = mapped_column(default=utcnow, server_default=text("SYSUTCDATETIME()"))
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    reviewed_at: Mapped[datetime | None]
    review_notes: Mapped[str | None] = mapped_column(Unicode(1000))


class SamplingAssignment(UUIDPrimaryKey, Base):
    __tablename__ = "sampling_assignments"
    __table_args__ = (
        CheckConstraint(in_check("status", ["ACTIVE", "REASSIGNED", "COMPLETED", "CANCELLED"]), name="status"),
        Index("uq_sampling_assignments_active", "sampling_point_id", unique=True, mssql_where=text("status = 'ACTIVE'")),
    )
    sampling_point_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sampling_points.id"), index=True)
    collector_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    planned_date: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(Unicode(12), default="ACTIVE")
    instructions: Mapped[str | None] = mapped_column(Unicode(1000))
    assigned_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    assigned_at: Mapped[datetime] = mapped_column(default=utcnow, server_default=text("SYSUTCDATETIME()"))
    ended_at: Mapped[datetime | None]


class FieldCollectionRecord(UUIDPrimaryKey, Base):
    """What the collector did at a sampling point. Versioned: a correction is a new record superseding the old.
    Phase 6 links samples/shipments/labs to this record."""
    __tablename__ = "field_collection_records"
    __table_args__ = (
        CheckConstraint(in_check("status", ["IN_PROGRESS", "SUBMITTED", "ACCEPTED", "RETURNED", "SUPERSEDED"]), name="status"),
        CheckConstraint("gps_latitude IS NULL OR gps_latitude BETWEEN -90 AND 90", name="gps_lat"),
        CheckConstraint("gps_longitude IS NULL OR gps_longitude BETWEEN -180 AND 180", name="gps_lon"),
        CheckConstraint("actual_depth_bottom_cm IS NULL OR actual_depth_top_cm IS NULL OR actual_depth_bottom_cm > actual_depth_top_cm",
                        name="depth"),
        CheckConstraint("checklist IS NULL OR ISJSON(checklist) = 1", name="checklist_json"),
        CheckConstraint("field_rules IS NULL OR ISJSON(field_rules) = 1", name="field_rules_json"),
    )
    collection_code: Mapped[str] = mapped_column(Unicode(30), unique=True)
    sampling_point_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sampling_points.id"), index=True)
    assignment_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("sampling_assignments.id"))
    monitoring_period_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("monitoring_periods.id"), index=True)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    farm_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("farms.id"))
    collector_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    supersedes_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("field_collection_records.id"))
    status: Mapped[str] = mapped_column(Unicode(12), default="IN_PROGRESS")
    collected_at: Mapped[datetime | None]
    gps_location: Mapped[str | None] = mapped_column(Geography())
    gps_latitude: Mapped[Decimal | None] = mapped_column(Numeric(10, 7))
    gps_longitude: Mapped[Decimal | None] = mapped_column(Numeric(10, 7))
    gps_accuracy_m: Mapped[Decimal | None] = mapped_column(Numeric(8, 1))
    distance_from_point_m: Mapped[Decimal | None] = mapped_column(Numeric(10, 1))   # SQL Server STDistance
    gps_inside_farm: Mapped[bool | None] = mapped_column(Boolean)
    deviation_note: Mapped[str | None] = mapped_column(Unicode(1000))
    actual_depth_top_cm: Mapped[Decimal | None] = mapped_column(Numeric(6, 1))
    actual_depth_bottom_cm: Mapped[Decimal | None] = mapped_column(Numeric(6, 1))
    sample_quantity: Mapped[Decimal | None] = mapped_column(Numeric(10, 3))
    sample_unit: Mapped[str | None] = mapped_column(Unicode(20))
    observations: Mapped[str | None] = mapped_column(Unicode(2000))
    notes: Mapped[str | None] = mapped_column(Unicode(2000))
    checklist: Mapped[str | None] = mapped_column(UnicodeText)
    # rules this record is collected under, copied from its design version at start and never changed afterwards
    field_rules: Mapped[str | None] = mapped_column(UnicodeText)
    checklist_version: Mapped[str | None] = mapped_column(Unicode(120))
    gps_tolerance_m: Mapped[Decimal | None] = mapped_column(Numeric(8, 1))
    correction_reason: Mapped[str | None] = mapped_column(Unicode(1000))
    created_at: Mapped[datetime] = mapped_column(default=utcnow, server_default=text("SYSUTCDATETIME()"))
    submitted_at: Mapped[datetime | None]
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    reviewed_at: Mapped[datetime | None]
    review_notes: Mapped[str | None] = mapped_column(Unicode(1000))


class MonitoringRecord(UUIDPrimaryKey, Base):
    """A value of a configured measurement (activity data, practice records, measurements). Versioned per record_id."""
    __tablename__ = "monitoring_records"
    __table_args__ = (
        UniqueConstraint("record_id", "version"),
        CheckConstraint(in_check("measurement_phase", ["BASELINE", "PROJECT", "MONITORING"]), name="measurement_phase"),
        CheckConstraint(in_check("source", ["FIELD_OBSERVATION", "FARMER_CLAIM", "DOCUMENT", "INSTRUMENT", "OTHER"]), name="source"),
        CheckConstraint(in_check("status", ["RECORDED", "SUPERSEDED", "RETRACTED"]), name="status"),
        Index("uq_monitoring_records_current", "record_id", unique=True, mssql_where=text("is_current = 1")),
    )
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    monitoring_period_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("monitoring_periods.id"), index=True)
    measurement_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("mrv_plan_measurements.id"))
    record_id: Mapped[uuid.UUID] = mapped_column(index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    is_current: Mapped[bool] = mapped_column(Boolean, default=True)
    farm_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("farms.id"))
    stratum_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("project_strata.id"))
    sampling_point_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("sampling_points.id"))
    field_collection_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("field_collection_records.id"))
    measurement_phase: Mapped[str] = mapped_column(Unicode(12), default="MONITORING")
    value_number: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    value_text: Mapped[str | None] = mapped_column(Unicode(1000))
    value_date: Mapped[date | None] = mapped_column(Date)
    value_bool: Mapped[bool | None] = mapped_column(Boolean)
    unit: Mapped[str | None] = mapped_column(Unicode(40))
    observed_on: Mapped[date] = mapped_column(Date)
    source: Mapped[str] = mapped_column(Unicode(20), default="FIELD_OBSERVATION")
    status: Mapped[str] = mapped_column(Unicode(12), default="RECORDED")
    notes: Mapped[str | None] = mapped_column(Unicode(1000))
    change_reason: Mapped[str | None] = mapped_column(Unicode(1000))
    recorded_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    recorded_at: Mapped[datetime] = mapped_column(default=utcnow, server_default=text("SYSUTCDATETIME()"))


class MrvEvidence(UUIDPrimaryKey, Base):
    __tablename__ = "mrv_evidence"
    __table_args__ = (
        CheckConstraint(in_check("evidence_type", EVIDENCE_TYPES), name="evidence_type"),
        CheckConstraint(in_check("entity_type", EVIDENCE_ENTITIES), name="entity_type"),
        CheckConstraint(in_check("status", ["SUBMITTED", "ACCEPTED", "REJECTED"]), name="status"),
        CheckConstraint(in_check("source", ["FIELD_COLLECTOR", "STAFF", "FARMER", "DOCUMENT"]), name="source"),
        CheckConstraint("(latitude IS NULL AND longitude IS NULL) OR (latitude BETWEEN -90 AND 90 AND longitude BETWEEN -180 AND 180)",
                        name="coordinates"),
    )
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    monitoring_period_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("monitoring_periods.id"))
    entity_type: Mapped[str] = mapped_column(Unicode(20))
    entity_id: Mapped[uuid.UUID] = mapped_column(index=True)
    evidence_type: Mapped[str] = mapped_column(Unicode(20))
    document_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("documents.id"))
    checksum_sha256: Mapped[str | None] = mapped_column(Unicode(64))
    latitude: Mapped[Decimal | None] = mapped_column(Numeric(10, 7))
    longitude: Mapped[Decimal | None] = mapped_column(Numeric(10, 7))
    captured_at: Mapped[datetime | None]
    description: Mapped[str | None] = mapped_column(Unicode(2000))
    source: Mapped[str] = mapped_column(Unicode(20), default="STAFF")
    status: Mapped[str] = mapped_column(Unicode(10), default="SUBMITTED")
    uploaded_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    uploaded_at: Mapped[datetime] = mapped_column(default=utcnow, server_default=text("SYSUTCDATETIME()"))
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    reviewed_at: Mapped[datetime | None]


class MrvDataset(UUIDPrimaryKey, Base):
    """Versioned monitoring dataset. On submission it freezes an exact snapshot of the record versions it contains
    (JSON + SHA-256) so an approved dataset is reproducible and can never change silently."""
    __tablename__ = "mrv_datasets"
    __table_args__ = (
        UniqueConstraint("monitoring_period_id", "version"),
        CheckConstraint(in_check("status", DATASET_STATUSES), name="status"),
        CheckConstraint("snapshot IS NULL OR ISJSON(snapshot) = 1", name="snapshot_json"),
        Index("uq_mrv_datasets_open", "monitoring_period_id", unique=True,
              mssql_where=text("status IN ('DRAFT', 'COLLECTING', 'SUBMITTED', 'QA_REVIEW')")),
    )
    dataset_code: Mapped[str] = mapped_column(Unicode(40), unique=True)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    monitoring_period_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("monitoring_periods.id"), index=True)
    mrv_plan_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("mrv_plans.id"))
    methodology_version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("methodology_versions.id"))
    version: Mapped[int] = mapped_column(Integer)
    supersedes_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("mrv_datasets.id"))
    status: Mapped[str] = mapped_column(Unicode(12), default="DRAFT")
    snapshot: Mapped[str | None] = mapped_column(UnicodeText)
    snapshot_sha256: Mapped[str | None] = mapped_column(Unicode(64))
    configuration_gaps: Mapped[str | None] = mapped_column(UnicodeText)
    notes: Mapped[str | None] = mapped_column(Unicode(2000))
    status_reason: Mapped[str | None] = mapped_column(Unicode(1000))
    environment: Mapped[str] = mapped_column(Unicode(10), default=Environment.LIVE.value)
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(default=utcnow, server_default=text("SYSUTCDATETIME()"))
    submitted_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    submitted_at: Mapped[datetime | None]
    approved_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    approved_at: Mapped[datetime | None]


class MrvQaReview(UUIDPrimaryKey, Base):
    __tablename__ = "mrv_qa_reviews"
    __table_args__ = (
        CheckConstraint("result IS NULL OR " + in_check("result", ["PASS", "FAIL", "REQUIRES_CORRECTION"]), name="result"),
        CheckConstraint("checks IS NULL OR ISJSON(checks) = 1", name="checks_json"),
    )
    dataset_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("mrv_datasets.id"), index=True)
    started_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    started_at: Mapped[datetime] = mapped_column(default=utcnow, server_default=text("SYSUTCDATETIME()"))
    checks: Mapped[str | None] = mapped_column(UnicodeText)       # JSON: automated checks at completion time
    result: Mapped[str | None] = mapped_column(Unicode(25))
    notes: Mapped[str | None] = mapped_column(Unicode(2000))
    completed_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    completed_at: Mapped[datetime | None]
