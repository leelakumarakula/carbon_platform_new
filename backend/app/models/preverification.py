"""Phase 8A — internal pre-verification (decisions B1–B12). Internal only: no VVB/ACVA, no validation or verification.

- calculation findings: an internal QA observation on a non-DRAFT calculation run (B2–B6). The current row carries the status;
  every change is an append-only event. Identity, target and original text never change (trigger)
- calculation reports: canonical JSON + SHA-256 and a deterministic text-only PDF (document) + SHA-256, only for APPROVED runs (B7, B8);
  immutable, CURRENT → SUPERSEDED only
- calculation readiness reviews: per monitoring period, "internally approved for submission to verification" — NOT verification
  (B9, B12). The project status is not changed
"""
import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Index, Integer, Unicode, UnicodeText, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, Environment, UUIDPrimaryKey, in_check, utcnow

FINDING_CATEGORIES = ["OBSERVATION", "NON_CONFORMITY", "CLARIFICATION", "MISSING_EVIDENCE", "CALCULATION_ISSUE", "METHODOLOGY_ISSUE"]
FINDING_STATUSES = ["OPEN", "RESPONDED", "RESOLVED", "WITHDRAWN"]
OPEN_FINDING_STATUSES = ("OPEN", "RESPONDED")
TARGET_SOURCES = ["LAB_RESULT", "MONITORING_RECORD", "STRATUM_AREA", "SAMPLING_DESIGN_PARAMETER", "MODULE_CONSTANT"]
REPORT_STATUSES = ["CURRENT", "SUPERSEDED"]
READINESS_STATUSES = ["DRAFT", "SUBMITTED", "READY", "REJECTED", "WITHDRAWN", "INVALIDATED"]
OPEN_READINESS_STATUSES = ("DRAFT", "SUBMITTED")


class CalculationFinding(UUIDPrimaryKey, Base):
    __tablename__ = "calculation_findings"
    __table_args__ = (
        CheckConstraint(in_check("category", FINDING_CATEGORIES), name="category"),
        CheckConstraint(in_check("status", FINDING_STATUSES), name="status"),
        CheckConstraint(in_check("environment", Environment), name="environment"),
        CheckConstraint("target_source_type IS NULL OR " + in_check("target_source_type", TARGET_SOURCES), name="target_source_type"),
        CheckConstraint("status <> 'WITHDRAWN' OR withdraw_reason IS NOT NULL", name="withdraw_reason"),
        Index("ix_calculation_findings_period_status", "monitoring_period_id", "status"),
        Index("ix_calculation_findings_project_status", "project_id", "status"),
    )
    finding_code: Mapped[str] = mapped_column(Unicode(20), unique=True)          # CFND-YYYY-NNNNNN
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"))
    monitoring_period_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("monitoring_periods.id"))
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("calculation_runs.id"), index=True)
    category: Mapped[str] = mapped_column(Unicode(20))
    blocking: Mapped[bool] = mapped_column(Boolean)
    title: Mapped[str] = mapped_column(Unicode(200))
    description: Mapped[str] = mapped_column(Unicode(4000))
    target_input_seq: Mapped[int | None] = mapped_column(Integer)
    target_output_seq: Mapped[int | None] = mapped_column(Integer)
    target_calculation_rule_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("methodology_calculation_rules.id"))
    target_source_type: Mapped[str | None] = mapped_column(Unicode(30))
    target_source_id: Mapped[uuid.UUID | None]
    evidence_document_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("documents.id"))
    status: Mapped[str] = mapped_column(Unicode(12), default="OPEN")
    raised_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    raised_at: Mapped[datetime] = mapped_column(default=utcnow, server_default=text("SYSUTCDATETIME()"))
    response_text: Mapped[str | None] = mapped_column(Unicode(4000))
    response_document_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("documents.id"))
    responded_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    responded_at: Mapped[datetime | None]
    resolution_note: Mapped[str | None] = mapped_column(Unicode(2000))
    resolved_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    resolved_at: Mapped[datetime | None]
    resolved_by_run_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("calculation_runs.id"))
    withdrawn_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    withdrawn_at: Mapped[datetime | None]
    withdraw_reason: Mapped[str | None] = mapped_column(Unicode(1000))
    environment: Mapped[str] = mapped_column(Unicode(10), default=Environment.LIVE.value)


class CalculationFindingEvent(UUIDPrimaryKey, Base):
    """Append-only history of a finding (trigger)."""
    __tablename__ = "calculation_finding_events"
    __table_args__ = (UniqueConstraint("finding_id", "seq"),)
    finding_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("calculation_findings.id"), index=True)
    seq: Mapped[int] = mapped_column(Integer)
    action: Mapped[str] = mapped_column(Unicode(20))                 # RAISED / RESPONDED / RESOLVED / REOPENED / RESPONSE_RETURNED / WITHDRAWN
    from_status: Mapped[str | None] = mapped_column(Unicode(12))
    to_status: Mapped[str] = mapped_column(Unicode(12))
    actor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    occurred_at: Mapped[datetime] = mapped_column(default=utcnow, server_default=text("SYSUTCDATETIME()"))
    note: Mapped[str | None] = mapped_column(Unicode(4000))
    document_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("documents.id"))
    run_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("calculation_runs.id"))   # e.g. the run that resolves it


class CalculationReport(UUIDPrimaryKey, Base):
    """Official calculation report of an APPROVED run (immutable; CURRENT → SUPERSEDED only, trigger)."""
    __tablename__ = "calculation_reports"
    __table_args__ = (
        UniqueConstraint("run_id", "version"),
        CheckConstraint(in_check("status", REPORT_STATUSES), name="status"),
        CheckConstraint(in_check("environment", Environment), name="environment"),
        CheckConstraint("ISJSON(content) = 1", name="content_json"),
        Index("uq_calculation_reports_current", "run_id", unique=True, mssql_where=text("status = 'CURRENT'")),
    )
    report_code: Mapped[str] = mapped_column(Unicode(20), unique=True)            # CRPT-YYYY-NNNNNN
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("calculation_runs.id"))
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"))
    monitoring_period_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("monitoring_periods.id"))
    version: Mapped[int] = mapped_column(Integer)
    generator_version: Mapped[str] = mapped_column(Unicode(40))
    content: Mapped[str] = mapped_column(UnicodeText)                              # canonical JSON
    content_sha256: Mapped[str] = mapped_column(Unicode(64))
    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("documents.id"))     # the PDF (category CALCULATION_REPORT)
    pdf_sha256: Mapped[str] = mapped_column(Unicode(64))
    status: Mapped[str] = mapped_column(Unicode(12), default="CURRENT")
    superseded_by_report_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("calculation_reports.id"))
    superseded_at: Mapped[datetime | None]
    generated_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    generated_at: Mapped[datetime] = mapped_column(default=utcnow, server_default=text("SYSUTCDATETIME()"))
    environment: Mapped[str] = mapped_column(Unicode(10), default=Environment.LIVE.value)


class CalculationReadinessReview(UUIDPrimaryKey, Base):
    """Internal verification readiness of one monitoring period — NOT verification (B9)."""
    __tablename__ = "calculation_readiness_reviews"
    __table_args__ = (
        CheckConstraint(in_check("status", READINESS_STATUSES), name="status"),
        CheckConstraint(in_check("environment", Environment), name="environment"),
        CheckConstraint("checks IS NULL OR ISJSON(checks) = 1", name="checks_json"),
        CheckConstraint("manifest IS NULL OR ISJSON(manifest) = 1", name="manifest_json"),
        CheckConstraint("status <> 'READY' OR (manifest IS NOT NULL AND manifest_sha256 IS NOT NULL)", name="ready_manifest"),
        CheckConstraint("status <> 'INVALIDATED' OR invalidation_reason IS NOT NULL", name="invalidation_reason"),
        CheckConstraint("status <> 'WITHDRAWN' OR withdraw_reason IS NOT NULL", name="withdraw_reason"),
        Index("uq_calculation_readiness_open", "monitoring_period_id", unique=True, mssql_where=text("status IN ('DRAFT', 'SUBMITTED')")),
        Index("uq_calculation_readiness_ready", "monitoring_period_id", unique=True, mssql_where=text("status = 'READY'")),
    )
    readiness_code: Mapped[str] = mapped_column(Unicode(20), unique=True)         # RDY-YYYY-NNNNNN
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    monitoring_period_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("monitoring_periods.id"))
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("calculation_runs.id"), index=True)
    report_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("calculation_reports.id"))
    status: Mapped[str] = mapped_column(Unicode(12), default="DRAFT")
    checks: Mapped[str | None] = mapped_column(UnicodeText)
    manifest: Mapped[str | None] = mapped_column(UnicodeText)
    manifest_sha256: Mapped[str | None] = mapped_column(Unicode(64))
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(default=utcnow, server_default=text("SYSUTCDATETIME()"))
    submitted_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    submitted_at: Mapped[datetime | None]
    decided_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    decided_at: Mapped[datetime | None]
    decision_notes: Mapped[str | None] = mapped_column(Unicode(2000))
    withdrawn_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    withdrawn_at: Mapped[datetime | None]
    withdraw_reason: Mapped[str | None] = mapped_column(Unicode(1000))
    invalidated_at: Mapped[datetime | None]
    invalidation_reason: Mapped[str | None] = mapped_column(Unicode(2000))
    environment: Mapped[str] = mapped_column(Unicode(10), default=Environment.LIVE.value)
