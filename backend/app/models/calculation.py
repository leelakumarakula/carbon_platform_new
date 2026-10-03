"""Phase 7 — carbon calculation (spec sections 7.10, 18, 19, 20).

Rules:
- a calculation run is executed by a registered, methodology-specific Python module (app/calculation) that matches the
  project's locked methodology version and its calculation rules exactly; nothing here stores an executable formula
- inputs are frozen into a canonical JSON snapshot (+ SHA-256) and normalized `calculation_inputs` rows; the engine reads
  only that snapshot, never live Phase 5 / 6 tables
- runs are never edited after their lifecycle points and never deleted (DB triggers); a correction is a new run
  (`recalculation_of_run_id`); approving it supersedes the previous APPROVED run of the same reporting period
- values are stored as exact decimal strings (Python Decimal, no float, no storage rounding)
- a calculated value is CALCULATED — not verified, not issued; nothing here is a credit
"""
import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, Unicode, UnicodeText, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, Environment, UUIDPrimaryKey, in_check, utcnow

RUN_STATUSES = ["DRAFT", "INPUTS_FROZEN", "CALCULATED", "QA_REVIEW", "APPROVED", "SUPERSEDED", "BLOCKED", "CANCELLED", "REJECTED"]
OPEN_RUN_STATUSES = ("DRAFT", "INPUTS_FROZEN", "CALCULATED", "QA_REVIEW")
MODULE_READINESS = ["NOT_PRODUCTION_READY", "PRODUCTION_READY"]
CALC_STEPS = ["BASELINE", "PROJECT", "EMISSIONS", "REMOVALS", "LEAKAGE", "UNCERTAINTY", "ADJUSTMENT", "NET"]
INPUT_SOURCES = ["LAB_RESULT", "MONITORING_RECORD", "STRATUM_AREA", "SAMPLING_DESIGN_PARAMETER", "MODULE_CONSTANT"]
VALUE_KINDS = ["NUMBER", "TEXT"]
LEVELS = ["PROJECT", "STRATUM", "FARM", "SAMPLING_POINT"]
QA_RESULTS = ["PASS", "FAIL"]


class CalculationRun(UUIDPrimaryKey, Base):
    __tablename__ = "calculation_runs"
    __table_args__ = (
        CheckConstraint(in_check("status", RUN_STATUSES), name="status"),
        CheckConstraint(in_check("environment", Environment), name="environment"),
        CheckConstraint("module_readiness IS NULL OR " + in_check("module_readiness", MODULE_READINESS), name="module_readiness"),
        CheckConstraint("input_snapshot IS NULL OR ISJSON(input_snapshot) = 1", name="input_snapshot_json"),
        CheckConstraint("blockers IS NULL OR ISJSON(blockers) = 1", name="blockers_json"),
        CheckConstraint("parameters IS NULL OR ISJSON(parameters) = 1", name="parameters_json"),
        CheckConstraint("recalculation_of_run_id IS NULL OR recalculation_reason IS NOT NULL", name="recalculation_reason"),
        CheckConstraint("status <> 'INPUTS_FROZEN' OR input_sha256 IS NOT NULL", name="frozen_hash"),
        CheckConstraint("status NOT IN ('CALCULATED', 'QA_REVIEW', 'APPROVED', 'SUPERSEDED') OR output_sha256 IS NOT NULL", name="output_hash"),
        # one open run and one APPROVED run per reporting period
        Index("uq_calculation_runs_open", "monitoring_period_id", unique=True,
              mssql_where=text("status IN ('DRAFT', 'INPUTS_FROZEN', 'CALCULATED', 'QA_REVIEW')")),
        Index("uq_calculation_runs_approved", "monitoring_period_id", unique=True, mssql_where=text("status = 'APPROVED'")),
        Index("ix_calculation_runs_project_status", "project_id", "status"),
    )
    run_code: Mapped[str] = mapped_column(Unicode(20), unique=True)        # CALC-YYYY-NNNNNN
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"))
    monitoring_period_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("monitoring_periods.id"), index=True)   # reporting period
    crediting_period_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("project_crediting_periods.id"))
    mrv_dataset_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("mrv_datasets.id"))                  # bound at freeze
    methodology_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("methodologies.id"))
    methodology_version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("methodology_versions.id"))
    project_methodology_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("project_methodologies.id"))
    calculation_rules_version: Mapped[int] = mapped_column(Integer)
    monitoring_rules_version: Mapped[int] = mapped_column(Integer)
    module_code: Mapped[str | None] = mapped_column(Unicode(80))
    module_version: Mapped[str | None] = mapped_column(Unicode(30))
    module_readiness: Mapped[str | None] = mapped_column(Unicode(25))
    engine_version: Mapped[str] = mapped_column(Unicode(30))
    parameters: Mapped[str | None] = mapped_column(UnicodeText)               # JSON run configuration (none in Phase 7)
    input_snapshot: Mapped[str | None] = mapped_column(UnicodeText)           # canonical JSON
    input_sha256: Mapped[str | None] = mapped_column(Unicode(64))
    output_sha256: Mapped[str | None] = mapped_column(Unicode(64))
    net_result: Mapped[str | None] = mapped_column(Unicode(80))               # exact decimal string of the final NET output
    net_unit: Mapped[str | None] = mapped_column(Unicode(40))
    blockers: Mapped[str | None] = mapped_column(UnicodeText)                 # JSON list when BLOCKED
    status: Mapped[str] = mapped_column(Unicode(15), default="DRAFT")
    status_reason: Mapped[str | None] = mapped_column(Unicode(1000))
    notes: Mapped[str | None] = mapped_column(Unicode(2000))
    recalculation_of_run_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("calculation_runs.id"))
    recalculation_reason: Mapped[str | None] = mapped_column(Unicode(1000))
    superseded_by_run_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("calculation_runs.id"))
    superseded_at: Mapped[datetime | None]
    environment: Mapped[str] = mapped_column(Unicode(10), default=Environment.LIVE.value)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(default=utcnow, server_default=text("SYSUTCDATETIME()"))
    frozen_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    frozen_at: Mapped[datetime | None]
    executed_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    executed_at: Mapped[datetime | None]
    submitted_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    submitted_at: Mapped[datetime | None]
    approved_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    approved_at: Mapped[datetime | None]
    closed_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))     # blocked / cancelled / rejected by
    closed_at: Mapped[datetime | None]


class CalculationInput(UUIDPrimaryKey, Base):
    """One frozen input value with its source (append-only; written at freeze)."""
    __tablename__ = "calculation_inputs"
    __table_args__ = (
        UniqueConstraint("run_id", "seq"),
        CheckConstraint(in_check("source_type", INPUT_SOURCES), name="source_type"),
        CheckConstraint(in_check("value_kind", VALUE_KINDS), name="value_kind"),
        CheckConstraint(in_check("level", LEVELS), name="level"),
        CheckConstraint("requirement_source IS NULL OR " + in_check("requirement_source", ["METHODOLOGY", "PROJECT_CONFIGURED", "MODULE"]),
                        name="requirement_source"),
        Index("ix_calculation_inputs_source", "source_id"),
    )
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("calculation_runs.id"), index=True)
    seq: Mapped[int] = mapped_column(Integer)
    variable_code: Mapped[str] = mapped_column(Unicode(60))
    source_type: Mapped[str] = mapped_column(Unicode(30))
    source_id: Mapped[uuid.UUID | None]
    source_version: Mapped[int | None] = mapped_column(Integer)
    source_code: Mapped[str | None] = mapped_column(Unicode(80))              # e.g. sample code, measurement code, constant code
    value: Mapped[str] = mapped_column(Unicode(1000))                         # exact decimal string or verbatim text
    value_kind: Mapped[str] = mapped_column(Unicode(10))
    unit: Mapped[str | None] = mapped_column(Unicode(40))
    level: Mapped[str] = mapped_column(Unicode(20))
    stratum_id: Mapped[uuid.UUID | None]
    farm_id: Mapped[uuid.UUID | None]
    sampling_point_id: Mapped[uuid.UUID | None]
    field_collection_id: Mapped[uuid.UUID | None]
    sample_id: Mapped[uuid.UUID | None]
    root_sample_id: Mapped[uuid.UUID | None]
    monitoring_rule_id: Mapped[uuid.UUID | None]
    plan_measurement_id: Mapped[uuid.UUID | None]
    requirement_source: Mapped[str | None] = mapped_column(Unicode(20))
    source_reference: Mapped[str | None] = mapped_column(Unicode(300))        # constants: methodology / module reference
    source_sha256: Mapped[str | None] = mapped_column(Unicode(64))            # e.g. the laboratory report checksum


class CalculationOutput(UUIDPrimaryKey, Base):
    """One intermediate or final value produced by the module (append-only; written at execution)."""
    __tablename__ = "calculation_outputs"
    __table_args__ = (
        UniqueConstraint("run_id", "seq"),
        CheckConstraint(in_check("step", CALC_STEPS), name="step"),
        CheckConstraint(in_check("level", LEVELS), name="level"),
        CheckConstraint("ISJSON(input_refs) = 1", name="input_refs_json"),
        Index("uq_calculation_outputs_final", "run_id", unique=True, mssql_where=text("is_final = 1")),
    )
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("calculation_runs.id"), index=True)
    seq: Mapped[int] = mapped_column(Integer)
    step: Mapped[str] = mapped_column(Unicode(15))
    output_code: Mapped[str] = mapped_column(Unicode(80))
    calculation_rule_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("methodology_calculation_rules.id"))
    rule_code: Mapped[str] = mapped_column(Unicode(40))
    equation_reference: Mapped[str | None] = mapped_column(Unicode(120))
    value: Mapped[str] = mapped_column(Unicode(80))                           # exact decimal string
    unit: Mapped[str] = mapped_column(Unicode(40))
    level: Mapped[str] = mapped_column(Unicode(20))
    entity_id: Mapped[uuid.UUID | None]                                       # stratum / farm / point when not PROJECT level
    input_refs: Mapped[str] = mapped_column(UnicodeText)                      # JSON {"inputs": [seq…], "outputs": [seq…]}
    is_final: Mapped[bool] = mapped_column(default=False)


class CalculationQaReview(UUIDPrimaryKey, Base):
    """Calculation QA (same pattern as MRV dataset QA). A completed review is immutable (trigger)."""
    __tablename__ = "calculation_qa_reviews"
    __table_args__ = (
        CheckConstraint("result IS NULL OR " + in_check("result", QA_RESULTS), name="result"),
        CheckConstraint("checks IS NULL OR ISJSON(checks) = 1", name="checks_json"),
    )
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("calculation_runs.id"), index=True)
    started_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    started_at: Mapped[datetime] = mapped_column(default=utcnow, server_default=text("SYSUTCDATETIME()"))
    completed_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    completed_at: Mapped[datetime | None]
    checks: Mapped[str | None] = mapped_column(UnicodeText)
    result: Mapped[str | None] = mapped_column(Unicode(10))
    notes: Mapped[str | None] = mapped_column(Unicode(2000))
