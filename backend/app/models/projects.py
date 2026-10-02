"""Projects (spec section 7.4): the project, its participating farms, team, standard/activity selection history,
crediting periods, baseline metadata, carbon-rights references, documents, derived boundary and status history.

Distinctions kept explicit (spec section 41):
  Farmer  → farmers         Farm → farms           Project → projects
  Participation (farm in project, period) → project_farms
  Carbon rights (who holds the rights, on what reference) → project_carbon_rights
Nothing is deleted: removals, supersessions and endings are status changes with who/when/why.
"""
import uuid
from datetime import date, datetime
from decimal import Decimal
from enum import Enum

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    ForeignKey,
    Identity,
    Index,
    Integer,
    Numeric,
    Unicode,
    UnicodeText,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, Environment, Timestamped, UUIDPrimaryKey, in_check, utcnow
from app.models.gis import Geography


class ProjectStatus(str, Enum):
    """Full lifecycle (spec section 8). Phase 3 only implements transitions up to ACTIVITY_SELECTED (plus CLOSED);
    later phases add the transitions into the remaining states."""
    DRAFT = "DRAFT"
    DATA_COLLECTION = "DATA_COLLECTION"
    ELIGIBILITY_REVIEW = "ELIGIBILITY_REVIEW"
    STANDARD_SELECTED = "STANDARD_SELECTED"
    ACTIVITY_SELECTED = "ACTIVITY_SELECTED"
    METHODOLOGY_REVIEW = "METHODOLOGY_REVIEW"
    METHODOLOGY_CONFIRMED = "METHODOLOGY_CONFIRMED"
    MRV_PLANNED = "MRV_PLANNED"
    MONITORING = "MONITORING"
    CALCULATION_READY = "CALCULATION_READY"
    CALCULATED = "CALCULATED"
    VALIDATION = "VALIDATION"
    VERIFICATION = "VERIFICATION"
    VERIFIED = "VERIFIED"
    REGISTRY_SUBMISSION = "REGISTRY_SUBMISSION"
    REGISTERED = "REGISTERED"
    ISSUANCE_PENDING = "ISSUANCE_PENDING"
    ISSUED = "ISSUED"
    ACTIVE = "ACTIVE"
    CLOSED = "CLOSED"


# Project categories (assumption, see docs/project-workflow.md). Classification only — never used as a rule.
PROJECT_TYPES = ["AGRICULTURAL_LAND_MANAGEMENT", "AGROFORESTRY", "RICE_CULTIVATION", "GRASSLAND_MANAGEMENT", "OTHER"]
# Project team roles: existing system role codes (the user must hold that role; no second permission system).
PROJECT_ROLES = ["PROJECT_MANAGER", "MRV_MANAGER", "METHODOLOGY_SPECIALIST", "FIELD_SUPERVISOR", "FIELD_AGENT", "GIS_SPECIALIST",
                 "PLATFORM_GIS_SPECIALIST", "QA_OFFICER", "FINANCE_MANAGER", "CALCULATION_ANALYST", "REGISTRY_MANAGER", "CREDIT_MANAGER",
                 "SUPPORT"]
CARBON_RIGHT_HOLDERS = ["FARMER", "LANDOWNER", "ORGANIZATION", "FARMER_GROUP", "OTHER"]
CREDITING_PERIOD_STATUSES = ["PROPOSED", "SUPERSEDED", "CANCELLED", "CONFIRMED", "ACTIVE", "ENDED"]  # later phases use the last three


class Project(UUIDPrimaryKey, Timestamped, Base):
    __tablename__ = "projects"
    __table_args__ = (
        CheckConstraint(in_check("status", ProjectStatus), name="status"),
        CheckConstraint(in_check("project_type", PROJECT_TYPES), name="project_type"),
        CheckConstraint(in_check("environment", Environment), name="environment"),
        # NOT_SELECTED → UNDER_REVIEW (candidates being evaluated) → CONFIRMED (methodology + version locked).
        CheckConstraint(in_check("methodology_status", ["NOT_SELECTED", "UNDER_REVIEW", "CONFIRMED"]), name="methodology_status"),
    )
    project_code: Mapped[str] = mapped_column(Unicode(30), unique=True)
    name: Mapped[str] = mapped_column(Unicode(200))
    description: Mapped[str | None] = mapped_column(Unicode(4000))
    project_type: Mapped[str] = mapped_column(Unicode(40))
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), index=True)
    country: Mapped[str] = mapped_column(Unicode(2))
    region: Mapped[str | None] = mapped_column(Unicode(200))
    start_date: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(Unicode(25), default=ProjectStatus.DRAFT.value, index=True)
    standard_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("standards.id"))     # current selection (history in project_standards)
    activity_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("activities.id"))    # current selection (history in project_activities)
    methodology_status: Mapped[str] = mapped_column(Unicode(20), default="NOT_SELECTED")
    methodology_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("methodologies.id"))           # locked (Phase 4)
    methodology_version_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("methodology_versions.id"))
    current_boundary_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("project_boundaries.id", use_alter=True))
    submitted_at: Mapped[datetime | None]
    submitted_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    eligibility_reviewed_at: Mapped[datetime | None]
    eligibility_reviewed_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    review_notes: Mapped[str | None] = mapped_column(Unicode(2000))
    environment: Mapped[str] = mapped_column(Unicode(10), default=Environment.LIVE.value)
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))


class ProjectFarm(UUIDPrimaryKey, Base):
    """A farm's participation in a project. Removing a farm ends the participation; the row stays."""
    __tablename__ = "project_farms"
    __table_args__ = (
        CheckConstraint(in_check("status", ["ACTIVE", "REMOVED"]), name="status"),
        CheckConstraint("participation_end IS NULL OR participation_end >= participation_start", name="dates"),
        Index("uq_project_farms_active", "project_id", "farm_id", unique=True, mssql_where=text("status = 'ACTIVE'")),
    )
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    farm_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("farms.id"), index=True)
    farmer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("farmers.id"), index=True)
    status: Mapped[str] = mapped_column(Unicode(10), default="ACTIVE")
    participation_start: Mapped[date] = mapped_column(Date)
    participation_end: Mapped[date | None] = mapped_column(Date)
    farm_boundary_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("farm_boundaries.id"))   # boundary version when added (lineage)
    farm_area_hectares: Mapped[Decimal] = mapped_column(Numeric(14, 4))
    conflicts_acknowledged: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("0"))
    conflict_notes: Mapped[str | None] = mapped_column(Unicode(2000))
    conflicts_snapshot: Mapped[str | None] = mapped_column(UnicodeText)  # JSON: overlaps / other participations visible at add time
    added_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    added_at: Mapped[datetime] = mapped_column(default=utcnow, server_default=text("SYSUTCDATETIME()"))
    removed_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    removed_at: Mapped[datetime | None]
    removal_reason: Mapped[str | None] = mapped_column(Unicode(1000))


class ProjectParticipant(UUIDPrimaryKey, Base):
    """Project team membership. The project role must be a role the user already holds (RBAC stays the authority)."""
    __tablename__ = "project_participants"
    __table_args__ = (
        CheckConstraint(in_check("status", ["ACTIVE", "REMOVED"]), name="status"),
        CheckConstraint(in_check("project_role", PROJECT_ROLES), name="project_role"),
        CheckConstraint("end_date IS NULL OR start_date IS NULL OR end_date >= start_date", name="dates"),
        Index("uq_project_participants_active", "project_id", "user_id", "project_role", unique=True,
              mssql_where=text("status = 'ACTIVE'")),
    )
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    project_role: Mapped[str] = mapped_column(Unicode(40))
    status: Mapped[str] = mapped_column(Unicode(10), default="ACTIVE")
    start_date: Mapped[date | None] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)
    notes: Mapped[str | None] = mapped_column(Unicode(1000))
    added_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    added_at: Mapped[datetime] = mapped_column(default=utcnow, server_default=text("SYSUTCDATETIME()"))
    updated_at: Mapped[datetime | None]
    removed_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    removed_at: Mapped[datetime | None]
    removal_reason: Mapped[str | None] = mapped_column(Unicode(1000))


class ProjectStandard(UUIDPrimaryKey, Base):
    """Standard / route selection history; exactly one current row per project."""
    __tablename__ = "project_standards"
    __table_args__ = (Index("uq_project_standards_current", "project_id", unique=True, mssql_where=text("is_current = 1")),)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    standard_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("standards.id"))
    is_current: Mapped[bool] = mapped_column(Boolean, default=True)
    reason: Mapped[str | None] = mapped_column(Unicode(1000))
    selected_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    selected_at: Mapped[datetime] = mapped_column(default=utcnow, server_default=text("SYSUTCDATETIME()"))
    superseded_at: Mapped[datetime | None]


class ProjectActivity(UUIDPrimaryKey, Base):
    """Activity selection history; exactly one current row per project."""
    __tablename__ = "project_activities"
    __table_args__ = (Index("uq_project_activities_current", "project_id", unique=True, mssql_where=text("is_current = 1")),)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    activity_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("activities.id"))
    standard_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("standards.id"))   # the standard it was selected under
    is_current: Mapped[bool] = mapped_column(Boolean, default=True)
    reason: Mapped[str | None] = mapped_column(Unicode(1000))
    selected_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    selected_at: Mapped[datetime] = mapped_column(default=utcnow, server_default=text("SYSUTCDATETIME()"))
    superseded_at: Mapped[datetime | None]
    superseded_reason: Mapped[str | None] = mapped_column(Unicode(1000))


class ProjectCreditingPeriod(UUIDPrimaryKey, Base):
    """Proposed crediting period(s). Methodology-specific length rules are validated in Phase 4, not here."""
    __tablename__ = "project_crediting_periods"
    __table_args__ = (
        UniqueConstraint("project_id", "period_number"),
        CheckConstraint(in_check("status", CREDITING_PERIOD_STATUSES), name="status"),
        CheckConstraint("end_date > start_date", name="dates"),
    )
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    period_number: Mapped[int] = mapped_column(Integer)
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(Unicode(12), default="PROPOSED")
    notes: Mapped[str | None] = mapped_column(Unicode(2000))
    replaces_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("project_crediting_periods.id"))
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(default=utcnow, server_default=text("SYSUTCDATETIME()"))
    status_changed_at: Mapped[datetime | None]
    status_changed_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    status_reason: Mapped[str | None] = mapped_column(Unicode(1000))


class ProjectBaseline(UUIDPrimaryKey, Base):
    """Baseline period metadata only — no baseline emissions/removals are calculated in Phase 3. Versioned."""
    __tablename__ = "project_baselines"
    __table_args__ = (
        UniqueConstraint("project_id", "version"),
        CheckConstraint("period_end >= period_start", name="dates"),
        Index("uq_project_baselines_current", "project_id", unique=True, mssql_where=text("is_current = 1")),
    )
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    version: Mapped[int] = mapped_column(Integer)
    is_current: Mapped[bool] = mapped_column(Boolean, default=True)
    period_start: Mapped[date] = mapped_column(Date)
    period_end: Mapped[date] = mapped_column(Date)
    description: Mapped[str | None] = mapped_column(Unicode(4000))
    data_sources: Mapped[str | None] = mapped_column(Unicode(2000))
    notes: Mapped[str | None] = mapped_column(Unicode(2000))
    change_reason: Mapped[str | None] = mapped_column(Unicode(1000))
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(default=utcnow, server_default=text("SYSUTCDATETIME()"))


class ProjectCarbonRight(UUIDPrimaryKey, Base):
    """Internal tracking of who holds the carbon rights for a farm's participation, and on what reference.
    Not legal wording; the agreement/document referenced is the source."""
    __tablename__ = "project_carbon_rights"
    __table_args__ = (
        CheckConstraint(in_check("holder_type", CARBON_RIGHT_HOLDERS), name="holder_type"),
        CheckConstraint(in_check("status", ["ACTIVE", "ENDED", "VOID"]), name="status"),
        CheckConstraint(in_check("verification_status", ["UNVERIFIED", "VERIFIED", "REJECTED"]), name="verification_status"),
        CheckConstraint("share_pct IS NULL OR (share_pct > 0 AND share_pct <= 100)", name="share"),
        CheckConstraint("effective_to IS NULL OR effective_to >= effective_from", name="dates"),
        CheckConstraint("agreement_id IS NOT NULL OR document_id IS NOT NULL OR reference IS NOT NULL", name="has_reference"),
    )
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    project_farm_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("project_farms.id"), index=True)
    farm_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("farms.id"), index=True)
    farmer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("farmers.id"))
    holder_type: Mapped[str] = mapped_column(Unicode(15))
    holder_farmer_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("farmers.id"))
    holder_organization_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("organizations.id"))
    holder_name: Mapped[str] = mapped_column(Unicode(200))
    share_pct: Mapped[Decimal | None] = mapped_column(Numeric(6, 3))
    agreement_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("farmer_agreements.id"))
    document_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("documents.id"))
    reference: Mapped[str | None] = mapped_column(Unicode(200))
    effective_from: Mapped[date] = mapped_column(Date)
    effective_to: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(Unicode(10), default="ACTIVE")
    verification_status: Mapped[str] = mapped_column(Unicode(12), default="UNVERIFIED")
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    reviewed_at: Mapped[datetime | None]
    review_notes: Mapped[str | None] = mapped_column(Unicode(2000))
    end_reason: Mapped[str | None] = mapped_column(Unicode(1000))
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(default=utcnow, server_default=text("SYSUTCDATETIME()"))
    updated_at: Mapped[datetime | None]


class ProjectDocument(Base):
    __tablename__ = "project_documents"
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), primary_key=True)
    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("documents.id"), primary_key=True)
    linked_at: Mapped[datetime] = mapped_column(default=utcnow, server_default=text("SYSUTCDATETIME()"))


class ProjectBoundary(UUIDPrimaryKey, Base):
    """Project boundary derived by SQL Server (UnionAggregate) from the current boundaries of the participating
    farms. Every recomputation is a new version; GIS review is recorded on the version it applies to."""
    __tablename__ = "project_boundaries"
    __table_args__ = (
        UniqueConstraint("project_id", "version"),
        CheckConstraint(in_check("status", ["CURRENT", "SUPERSEDED"]), name="status"),
        CheckConstraint(in_check("review_status", ["PENDING", "ACCEPTED", "ISSUES"]), name="review_status"),
        Index("uq_project_boundaries_current", "project_id", unique=True, mssql_where=text("status = 'CURRENT'")),
    )
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"))
    version: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(Unicode(12), default="CURRENT")
    boundary: Mapped[str] = mapped_column(Geography())
    area_m2: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    area_hectares: Mapped[Decimal] = mapped_column(Numeric(14, 4))               # union area (overlaps counted once)
    sum_farm_area_hectares: Mapped[Decimal] = mapped_column(Numeric(14, 4))      # plain sum of farm areas
    internal_overlap_hectares: Mapped[Decimal] = mapped_column(Numeric(14, 4))   # sum − union
    farm_count: Mapped[int] = mapped_column(Integer)
    farm_boundary_ids: Mapped[str] = mapped_column(UnicodeText)                  # JSON list: exact farm boundary versions used
    is_valid: Mapped[bool] = mapped_column(Boolean)
    validation_notes: Mapped[str | None] = mapped_column(Unicode(2000))
    project_overlaps: Mapped[str | None] = mapped_column(UnicodeText)            # JSON: other projects intersecting at compute time
    computed_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    computed_at: Mapped[datetime] = mapped_column(default=utcnow, server_default=text("SYSUTCDATETIME()"))
    superseded_at: Mapped[datetime | None]
    review_status: Mapped[str] = mapped_column(Unicode(10), default="PENDING")
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    reviewed_at: Mapped[datetime | None]
    review_notes: Mapped[str | None] = mapped_column(Unicode(2000))


class ProjectStatusHistory(Base):
    """Append-only (trigger) record of every project status change."""
    __tablename__ = "project_status_history"
    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    from_status: Mapped[str | None] = mapped_column(Unicode(25))
    to_status: Mapped[str] = mapped_column(Unicode(25))
    action: Mapped[str] = mapped_column(Unicode(40))
    reason: Mapped[str | None] = mapped_column(Unicode(1000))
    changed_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    changed_at: Mapped[datetime] = mapped_column(default=utcnow, server_default=text("SYSUTCDATETIME()"))
    request_id: Mapped[str | None] = mapped_column(Unicode(64))
