"""Methodologies (spec section 7.5, 9, 48): methodology → versions → rules, documents, change history, and the
project-side candidate evaluations and the locked project methodology.

Rules:
- a methodology belongs to one standard / crediting route and is offered for one or more activities
- versions are never edited once out of DRAFT; changing rules means a new version (DRAFT → IN_REVIEW → APPROVED)
- several versions may be APPROVED at the same time (e.g. two active versions of one methodology); drafts are never
  candidates
- calculation rules only *document* equations and their source; no equation is implemented in Phase 4 and every
  version starts NOT_PRODUCTION_READY for calculation
- evaluations (candidate results) and change history are append-only
"""
import uuid
from datetime import date, datetime
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
    Unicode,
    UnicodeText,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, Environment, Timestamped, UUIDPrimaryKey, in_check, utcnow


class VersionStatus(str, Enum):
    DRAFT = "DRAFT"
    IN_REVIEW = "IN_REVIEW"
    APPROVED = "APPROVED"
    SUPERSEDED = "SUPERSEDED"
    RETIRED = "RETIRED"
    WITHDRAWN = "WITHDRAWN"


RULE_CATEGORIES = ["STANDARD", "ACTIVITY", "COUNTRY", "GEOGRAPHY", "LAND_USE", "HISTORICAL_PRACTICE", "CURRENT_PRACTICE",
                   "PROPOSED_PRACTICE", "START_DATE", "DATA_AVAILABILITY", "BASELINE", "ADDITIONALITY", "MONITORING",
                   "QUANTIFICATION", "SAMPLING", "EVIDENCE", "OTHER"]
OPERATORS = ["EQUALS", "NOT_EQUALS", "IN", "NOT_IN", "ANY_IN", "ALL_IN", "NONE_IN", "GTE", "LTE", "BETWEEN", "DATE_ON_OR_AFTER",
             "DATE_ON_OR_BEFORE", "IS_TRUE", "IS_FALSE", "EXISTS"]
ON_FAIL = ["NOT_APPLICABLE", "EVIDENCE_REQUIRED", "NEEDS_INFORMATION"]
OUTCOMES = ["APPLICABLE", "NOT_APPLICABLE", "NEEDS_INFORMATION", "EVIDENCE_REQUIRED"]
GENERAL_RULE_TYPES = ["CREDITING_PERIOD", "BASELINE", "ADDITIONALITY", "LEAKAGE", "UNCERTAINTY", "SAMPLING", "PERMANENCE", "GENERAL"]
CALC_READINESS = ["NOT_PRODUCTION_READY", "PRODUCTION_READY"]


class Methodology(UUIDPrimaryKey, Timestamped, Base):
    __tablename__ = "methodologies"
    __table_args__ = (
        CheckConstraint(in_check("status", ["ACTIVE", "INACTIVE"]), name="status"),
        CheckConstraint(in_check("environment", Environment), name="environment"),
    )
    code: Mapped[str] = mapped_column(Unicode(40), unique=True)
    name: Mapped[str] = mapped_column(Unicode(300))
    standard_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("standards.id"), index=True)
    owner_name: Mapped[str | None] = mapped_column(Unicode(200))
    description: Mapped[str | None] = mapped_column(Unicode(4000))
    source_url: Mapped[str | None] = mapped_column(Unicode(500))
    status: Mapped[str] = mapped_column(Unicode(10), default="ACTIVE")
    environment: Mapped[str] = mapped_column(Unicode(10), default=Environment.LIVE.value)
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))


class MethodologyActivity(Base):
    """The activities a methodology covers (catalog link used to find candidates; not an applicability rule)."""
    __tablename__ = "methodology_activities"
    methodology_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("methodologies.id"), primary_key=True)
    activity_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("activities.id"), primary_key=True, index=True)
    created_at: Mapped[datetime] = mapped_column(default=utcnow, server_default=text("SYSUTCDATETIME()"))


class MethodologyVersion(UUIDPrimaryKey, Base):
    __tablename__ = "methodology_versions"
    __table_args__ = (
        UniqueConstraint("methodology_id", "version_number"),
        UniqueConstraint("methodology_id", "version_label"),
        CheckConstraint(in_check("status", VersionStatus), name="status"),
        CheckConstraint(in_check("calculation_readiness", CALC_READINESS), name="calculation_readiness"),
        CheckConstraint("effective_to IS NULL OR effective_from IS NULL OR effective_to >= effective_from", name="dates"),
    )
    methodology_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("methodologies.id"), index=True)
    version_number: Mapped[int] = mapped_column(Integer)          # internal sequence 1, 2, 3 …
    version_label: Mapped[str] = mapped_column(Unicode(30))        # as published, e.g. "2.2"
    status: Mapped[str] = mapped_column(Unicode(12), default=VersionStatus.DRAFT.value)
    effective_from: Mapped[date | None] = mapped_column(Date)
    effective_to: Mapped[date | None] = mapped_column(Date)
    source_name: Mapped[str | None] = mapped_column(Unicode(300))  # e.g. publisher + document title
    source_url: Mapped[str | None] = mapped_column(Unicode(500))
    source_document_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("documents.id"))
    rules_version: Mapped[int] = mapped_column(Integer, default=1)               # revision counters of each rule set
    monitoring_rules_version: Mapped[int] = mapped_column(Integer, default=1)
    calculation_rules_version: Mapped[int] = mapped_column(Integer, default=1)
    calculation_readiness: Mapped[str] = mapped_column(Unicode(25), default="NOT_PRODUCTION_READY")
    is_demo_illustrative: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("0"))
    notes: Mapped[str | None] = mapped_column(Unicode(2000))
    based_on_version_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("methodology_versions.id"))
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(default=utcnow, server_default=text("SYSUTCDATETIME()"))
    submitted_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    submitted_at: Mapped[datetime | None]
    approved_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    approved_at: Mapped[datetime | None]
    superseded_at: Mapped[datetime | None]
    superseded_by_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("methodology_versions.id"))
    status_reason: Mapped[str | None] = mapped_column(Unicode(1000))


class _VersionRule:
    """Columns shared by all rule tables: rules belong to one methodology version."""
    methodology_version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("methodology_versions.id"), index=True)
    rule_code: Mapped[str] = mapped_column(Unicode(40))
    title: Mapped[str] = mapped_column(Unicode(300))
    description: Mapped[str | None] = mapped_column(Unicode(4000))
    source_reference: Mapped[str | None] = mapped_column(Unicode(300))   # section / clause / equation number in the source
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(default=utcnow, server_default=text("SYSUTCDATETIME()"))


class MethodologyApplicabilityRule(UUIDPrimaryKey, _VersionRule, Base):
    """A deterministic applicability condition: `fact_key OPERATOR expected_value`. Missing facts give
    NEEDS_INFORMATION; a failed check gives `on_fail`. The engine proposes; people decide."""
    __tablename__ = "methodology_applicability_rules"
    __table_args__ = (
        UniqueConstraint("methodology_version_id", "rule_code"),
        CheckConstraint(in_check("category", RULE_CATEGORIES), name="category"),
        CheckConstraint(in_check("operator", OPERATORS), name="operator"),
        CheckConstraint(in_check("on_fail", ON_FAIL), name="on_fail"),
        CheckConstraint("expected_value IS NULL OR ISJSON(expected_value) = 1", name="expected_value_json"),
    )
    category: Mapped[str] = mapped_column(Unicode(25))
    fact_key: Mapped[str] = mapped_column(Unicode(60))
    operator: Mapped[str] = mapped_column(Unicode(20))
    expected_value: Mapped[str | None] = mapped_column(UnicodeText)        # JSON
    on_fail: Mapped[str] = mapped_column(Unicode(20), default="NOT_APPLICABLE")
    evidence_requirement: Mapped[str | None] = mapped_column(Unicode(1000))
    mandatory: Mapped[bool] = mapped_column(Boolean, default=True)


# Measurement provenance (decision V2-A) — declared explicitly by the methodology monitoring rule, never inferred from units,
# names, numeric types or sampling frequency. LABORATORY values are authoritative only as approved Phase 6 lab results;
# FIELD / FIELD_ACTIVITY values are captured through the Phase 5 MRV workflow. UNCLASSIFIED exists only for rules created
# before the field existed that could not be classified safely; new rules must declare one of the three real values.
MEASUREMENT_SOURCES = ["FIELD", "FIELD_ACTIVITY", "LABORATORY", "UNCLASSIFIED"]


class MethodologyMonitoringRule(UUIDPrimaryKey, _VersionRule, Base):
    """Monitoring requirement (parameter, frequency, method, measurement provenance). Used to configure MRV in Phase 5."""
    __tablename__ = "methodology_monitoring_rules"
    __table_args__ = (
        UniqueConstraint("methodology_version_id", "rule_code"),
        CheckConstraint(in_check("measurement_source", MEASUREMENT_SOURCES), name="measurement_source"),
    )
    parameter: Mapped[str] = mapped_column(Unicode(120))
    measurement_source: Mapped[str] = mapped_column(Unicode(20))
    unit: Mapped[str | None] = mapped_column(Unicode(40))
    frequency: Mapped[str | None] = mapped_column(Unicode(120))
    method: Mapped[str | None] = mapped_column(Unicode(1000))
    evidence_requirement: Mapped[str | None] = mapped_column(Unicode(1000))


class MethodologyCalculationRule(UUIDPrimaryKey, _VersionRule, Base):
    """Documents a calculation step and the equation reference in the authoritative source. It never contains an
    executable formula; Phase 7 implements verified equations in code with reference tests."""
    __tablename__ = "methodology_calculation_rules"
    __table_args__ = (
        UniqueConstraint("methodology_version_id", "rule_code"),
        CheckConstraint(in_check("step", ["BASELINE", "PROJECT", "EMISSIONS", "REMOVALS", "LEAKAGE", "UNCERTAINTY", "ADJUSTMENT", "NET"]),
                        name="step"),
        CheckConstraint(in_check("implementation_status", ["NOT_IMPLEMENTED", "NOT_PRODUCTION_READY", "VERIFIED"]),
                        name="implementation_status"),
    )
    step: Mapped[str] = mapped_column(Unicode(15))
    equation_reference: Mapped[str | None] = mapped_column(Unicode(120))
    parameters: Mapped[str | None] = mapped_column(Unicode(2000))        # names of inputs/parameters, documentation only
    implementation_status: Mapped[str] = mapped_column(Unicode(25), default="NOT_IMPLEMENTED")


class MethodologyRule(UUIDPrimaryKey, _VersionRule, Base):
    """Other version requirements (crediting period, baseline, additionality, leakage, uncertainty, sampling, …).
    `parameters` (JSON) holds configured values, e.g. {"min_years": 5}; the platform only applies a parameter when
    the specialist has configured it from the source."""
    __tablename__ = "methodology_rules"
    __table_args__ = (
        UniqueConstraint("methodology_version_id", "rule_code"),
        CheckConstraint(in_check("rule_type", GENERAL_RULE_TYPES), name="rule_type"),
        CheckConstraint("parameters IS NULL OR ISJSON(parameters) = 1", name="parameters_json"),
    )
    rule_type: Mapped[str] = mapped_column(Unicode(20))
    parameters: Mapped[str | None] = mapped_column(UnicodeText)


class MethodologyDocument(Base):
    __tablename__ = "methodology_documents"
    methodology_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("methodologies.id"), primary_key=True)
    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("documents.id"), primary_key=True)
    methodology_version_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("methodology_versions.id"))
    linked_at: Mapped[datetime] = mapped_column(default=utcnow, server_default=text("SYSUTCDATETIME()"))


class MethodologyChangeHistory(Base):
    """Append-only (trigger): every change to a methodology, version or rule set."""
    __tablename__ = "methodology_change_history"
    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    methodology_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("methodologies.id"), index=True)
    methodology_version_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("methodology_versions.id"))
    change_type: Mapped[str] = mapped_column(Unicode(40))
    summary: Mapped[str] = mapped_column(Unicode(1000))
    old_value: Mapped[str | None] = mapped_column(UnicodeText)
    new_value: Mapped[str | None] = mapped_column(UnicodeText)
    reason: Mapped[str | None] = mapped_column(Unicode(1000))
    changed_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    changed_at: Mapped[datetime] = mapped_column(default=utcnow, server_default=text("SYSUTCDATETIME()"))
    request_id: Mapped[str | None] = mapped_column(Unicode(64))


class MethodologyEvaluation(UUIDPrimaryKey, Base):
    """One run of the candidate rules engine for a project. Inputs (facts) are snapshotted; append-only."""
    __tablename__ = "methodology_evaluations"
    __table_args__ = (CheckConstraint("ISJSON(facts) = 1", name="facts_json"),)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    standard_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("standards.id"))
    activity_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("activities.id"))
    engine_version: Mapped[str] = mapped_column(Unicode(20))
    facts: Mapped[str] = mapped_column(UnicodeText)          # JSON: every input fact with its source
    candidate_count: Mapped[int] = mapped_column(Integer)
    evaluated_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    evaluated_at: Mapped[datetime] = mapped_column(default=utcnow, server_default=text("SYSUTCDATETIME()"))
    request_id: Mapped[str | None] = mapped_column(Unicode(64))


class MethodologyEvaluationResult(UUIDPrimaryKey, Base):
    """One candidate (methodology version) in an evaluation, with the per-rule explanation. Append-only."""
    __tablename__ = "methodology_evaluation_results"
    __table_args__ = (
        UniqueConstraint("evaluation_id", "methodology_version_id"),
        CheckConstraint(in_check("outcome", OUTCOMES), name="outcome"),
        CheckConstraint("ISJSON(rule_results) = 1", name="rule_results_json"),
    )
    evaluation_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("methodology_evaluations.id"), index=True)
    methodology_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("methodologies.id"))
    methodology_version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("methodology_versions.id"))
    outcome: Mapped[str] = mapped_column(Unicode(20))
    rules_version: Mapped[int] = mapped_column(Integer)
    rule_results: Mapped[str] = mapped_column(UnicodeText)   # JSON list: rule, category, result, reason, evidence requirement


class ProjectMethodologyReview(UUIDPrimaryKey, Base):
    """Methodology specialist's review of one candidate result (the engine never decides)."""
    __tablename__ = "project_methodology_reviews"
    __table_args__ = (CheckConstraint(in_check("recommendation", ["RECOMMENDED", "NOT_RECOMMENDED"]), name="recommendation"),)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    evaluation_result_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("methodology_evaluation_results.id"), index=True)
    recommendation: Mapped[str] = mapped_column(Unicode(20))
    notes: Mapped[str] = mapped_column(Unicode(2000))
    evidence_acknowledged: Mapped[bool] = mapped_column(Boolean, default=False)
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    reviewed_at: Mapped[datetime] = mapped_column(default=utcnow, server_default=text("SYSUTCDATETIME()"))


class ProjectMethodology(UUIDPrimaryKey, Base):
    """The confirmed (locked) methodology + version of a project. Unlocking supersedes the row; history is kept."""
    __tablename__ = "project_methodologies"
    __table_args__ = (
        CheckConstraint(in_check("status", ["LOCKED", "UNLOCKED"]), name="status"),
        Index("uq_project_methodologies_locked", "project_id", unique=True, mssql_where=text("status = 'LOCKED'")),
    )
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    methodology_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("methodologies.id"))
    methodology_version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("methodology_versions.id"))
    evaluation_result_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("methodology_evaluation_results.id"))
    review_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("project_methodology_reviews.id"))
    rules_version: Mapped[int] = mapped_column(Integer)
    monitoring_rules_version: Mapped[int] = mapped_column(Integer)
    calculation_rules_version: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(Unicode(10), default="LOCKED")
    confirmation_notes: Mapped[str] = mapped_column(Unicode(2000))
    confirmed_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    locked_at: Mapped[datetime] = mapped_column(default=utcnow, server_default=text("SYSUTCDATETIME()"))
    unlocked_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    unlocked_at: Mapped[datetime | None]
    unlock_reason: Mapped[str | None] = mapped_column(Unicode(1000))
