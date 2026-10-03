"""Phase 8B — VVB / ACVA verification workflow (decisions C1–C20). Verification only (no validation, no registry, no credits).

The platform records an external VVB's work and decision; it never acts as the VVB.
- a VVB is an organization with org_type = 'VVB' (no accreditation is modelled)
- an assignment links project + monitoring period + VVB organization; two-sided (the project proposes, the VVB accepts with a
  conflict-of-interest declaration or declines); never reactivated; a replacement links to the previous assignment
- a submission sends a currently valid Phase 8A READY package (readiness review + manifest hash); a newer package supersedes it and a
  stale one is invalidated — never mutated
- VVB findings (OPEN → RESPONDED → CLOSED, CLOSED → OPEN) and corrective actions (REQUESTED → RESPONDED → ACCEPTED,
  RESPONDED → REQUESTED, open → CANCELLED) keep the current row plus append-only events
- a decision (VERIFIED / NOT_VERIFIED) requires the VVB's report PDF; the VVB-stated verified quantity is kept separately from the
  calculated quantity and is never a credit. A decision is immutable except CURRENT → SUPERSEDED (e.g. after a recalculation)
"""
import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, CheckConstraint, Date, ForeignKey, Index, Integer, Numeric, Unicode, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, Environment, UUIDPrimaryKey, in_check, utcnow

ASSIGNMENT_STATUSES = ["PROPOSED", "ACCEPTED", "COMPLETED", "DECLINED", "WITHDRAWN", "TERMINATED"]
OPEN_ASSIGNMENT_STATUSES = ("PROPOSED", "ACCEPTED")
SUBMISSION_STATUSES = ["SUBMITTED", "SUPERSEDED", "INVALIDATED"]
VFINDING_STATUSES = ["OPEN", "RESPONDED", "CLOSED"]
CA_STATUSES = ["REQUESTED", "RESPONDED", "ACCEPTED", "CANCELLED"]
OPEN_CA_STATUSES = ("REQUESTED", "RESPONDED")
DECISION_OUTCOMES = ["VERIFIED", "NOT_VERIFIED"]
DECISION_STATUSES = ["CURRENT", "SUPERSEDED"]
VFINDING_CATEGORIES = ["OBSERVATION", "NON_CONFORMITY", "CLARIFICATION", "MISSING_EVIDENCE", "CALCULATION_ISSUE", "METHODOLOGY_ISSUE"]
TARGET_TYPES = ["SUBMISSION", "MONITORING_PERIOD", "CALCULATION_RUN", "INPUT", "OUTPUT", "LAB_RESULT", "MRV_EVIDENCE", "DATASET",
                "CALCULATION_REPORT", "METHODOLOGY", "DOCUMENT"]


class VerificationAssignment(UUIDPrimaryKey, Base):
    __tablename__ = "verification_assignments"
    __table_args__ = (
        CheckConstraint(in_check("status", ASSIGNMENT_STATUSES), name="status"),
        CheckConstraint(in_check("environment", Environment), name="environment"),
        CheckConstraint("status NOT IN ('ACCEPTED', 'COMPLETED', 'TERMINATED') OR (coi_declaration IS NOT NULL AND accepted_by IS NOT NULL)",
                        name="coi_on_accept"),
        CheckConstraint("status NOT IN ('DECLINED', 'WITHDRAWN', 'TERMINATED') OR closed_reason IS NOT NULL", name="closed_reason"),
        Index("uq_verification_assignments_open", "monitoring_period_id", unique=True, mssql_where=text("status IN ('PROPOSED', 'ACCEPTED')")),
        Index("ix_verification_assignments_vvb", "vvb_organization_id", "status"),
    )
    assignment_code: Mapped[str] = mapped_column(Unicode(20), unique=True)        # VAS-YYYY-NNNNNN
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    monitoring_period_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("monitoring_periods.id"))
    vvb_organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"))
    status: Mapped[str] = mapped_column(Unicode(12), default="PROPOSED")
    previous_assignment_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("verification_assignments.id"))
    notes: Mapped[str | None] = mapped_column(Unicode(2000))
    proposed_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    proposed_at: Mapped[datetime] = mapped_column(default=utcnow, server_default=text("SYSUTCDATETIME()"))
    accepted_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    accepted_at: Mapped[datetime | None]
    coi_declaration: Mapped[str | None] = mapped_column(Unicode(4000))           # C7: mandatory on acceptance
    coi_declared_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    coi_declared_at: Mapped[datetime | None]
    completed_at: Mapped[datetime | None]
    closed_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))   # declined / withdrawn / terminated by
    closed_at: Mapped[datetime | None]
    closed_side: Mapped[str | None] = mapped_column(Unicode(10))                  # PROJECT / VVB
    closed_reason: Mapped[str | None] = mapped_column(Unicode(1000))
    environment: Mapped[str] = mapped_column(Unicode(10), default=Environment.LIVE.value)


class VerificationSubmission(UUIDPrimaryKey, Base):
    __tablename__ = "verification_submissions"
    __table_args__ = (
        UniqueConstraint("assignment_id", "seq"),
        CheckConstraint(in_check("status", SUBMISSION_STATUSES), name="status"),
        CheckConstraint(in_check("environment", Environment), name="environment"),
        Index("uq_verification_submissions_current", "assignment_id", unique=True, mssql_where=text("status = 'SUBMITTED'")),
    )
    submission_code: Mapped[str] = mapped_column(Unicode(20), unique=True)       # VSUB-YYYY-NNNNNN
    assignment_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("verification_assignments.id"), index=True)
    seq: Mapped[int] = mapped_column(Integer)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"))
    monitoring_period_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("monitoring_periods.id"))
    readiness_review_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("calculation_readiness_reviews.id"))
    calculation_run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("calculation_runs.id"))
    calculation_report_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("calculation_reports.id"))
    manifest_sha256: Mapped[str] = mapped_column(Unicode(64))
    status: Mapped[str] = mapped_column(Unicode(12), default="SUBMITTED")
    submitted_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    submitted_at: Mapped[datetime] = mapped_column(default=utcnow, server_default=text("SYSUTCDATETIME()"))
    closed_at: Mapped[datetime | None]
    closed_reason: Mapped[str | None] = mapped_column(Unicode(2000))              # why superseded / invalidated
    superseded_by_submission_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("verification_submissions.id"))
    environment: Mapped[str] = mapped_column(Unicode(10), default=Environment.LIVE.value)


class VerificationFinding(UUIDPrimaryKey, Base):
    __tablename__ = "verification_findings"
    __table_args__ = (
        CheckConstraint(in_check("category", VFINDING_CATEGORIES), name="category"),
        CheckConstraint(in_check("status", VFINDING_STATUSES), name="status"),
        CheckConstraint(in_check("target_type", TARGET_TYPES), name="target_type"),
        CheckConstraint(in_check("environment", Environment), name="environment"),
        Index("ix_verification_findings_submission_status", "submission_id", "status"),
    )
    finding_code: Mapped[str] = mapped_column(Unicode(20), unique=True)          # VFND-YYYY-NNNNNN
    assignment_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("verification_assignments.id"), index=True)
    submission_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("verification_submissions.id"))
    category: Mapped[str] = mapped_column(Unicode(20))
    blocking: Mapped[bool] = mapped_column(Boolean)                                # C13: no severity scale
    title: Mapped[str] = mapped_column(Unicode(200))
    description: Mapped[str] = mapped_column(Unicode(4000))
    target_type: Mapped[str] = mapped_column(Unicode(20))
    target_ref: Mapped[str | None] = mapped_column(Unicode(80))                   # id / seq inside the submitted package
    status: Mapped[str] = mapped_column(Unicode(12), default="OPEN")
    raised_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    raised_at: Mapped[datetime] = mapped_column(default=utcnow, server_default=text("SYSUTCDATETIME()"))
    response_text: Mapped[str | None] = mapped_column(Unicode(4000))
    response_document_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("documents.id"))
    responded_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    responded_at: Mapped[datetime | None]
    closure_note: Mapped[str | None] = mapped_column(Unicode(2000))
    closed_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    closed_at: Mapped[datetime | None]
    environment: Mapped[str] = mapped_column(Unicode(10), default=Environment.LIVE.value)


class VerificationFindingEvent(UUIDPrimaryKey, Base):
    """Append-only history (trigger)."""
    __tablename__ = "verification_finding_events"
    __table_args__ = (UniqueConstraint("finding_id", "seq"),)
    finding_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("verification_findings.id"), index=True)
    seq: Mapped[int] = mapped_column(Integer)
    action: Mapped[str] = mapped_column(Unicode(20))
    from_status: Mapped[str | None] = mapped_column(Unicode(12))
    to_status: Mapped[str] = mapped_column(Unicode(12))
    actor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    actor_org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"))
    actor_side: Mapped[str] = mapped_column(Unicode(10))                           # PROJECT / VVB
    occurred_at: Mapped[datetime] = mapped_column(default=utcnow, server_default=text("SYSUTCDATETIME()"))
    note: Mapped[str | None] = mapped_column(Unicode(4000))
    document_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("documents.id"))


class CorrectiveAction(UUIDPrimaryKey, Base):
    __tablename__ = "corrective_actions"
    __table_args__ = (
        CheckConstraint(in_check("status", CA_STATUSES), name="status"),
        CheckConstraint(in_check("environment", Environment), name="environment"),
        Index("ix_corrective_actions_submission_status", "submission_id", "status"),
    )
    action_code: Mapped[str] = mapped_column(Unicode(20), unique=True)           # CAR-YYYY-NNNNNN
    finding_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("verification_findings.id"), index=True)
    submission_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("verification_submissions.id"))
    assignment_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("verification_assignments.id"))
    description: Mapped[str] = mapped_column(Unicode(4000))
    due_date: Mapped[date | None] = mapped_column(Date)                            # overdue is derived, never stored
    status: Mapped[str] = mapped_column(Unicode(12), default="REQUESTED")
    requested_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    requested_at: Mapped[datetime] = mapped_column(default=utcnow, server_default=text("SYSUTCDATETIME()"))
    response_text: Mapped[str | None] = mapped_column(Unicode(4000))
    response_document_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("documents.id"))
    responded_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    responded_at: Mapped[datetime | None]
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    reviewed_at: Mapped[datetime | None]
    review_note: Mapped[str | None] = mapped_column(Unicode(2000))
    environment: Mapped[str] = mapped_column(Unicode(10), default=Environment.LIVE.value)


class CorrectiveActionEvent(UUIDPrimaryKey, Base):
    """Append-only history (trigger)."""
    __tablename__ = "corrective_action_events"
    __table_args__ = (UniqueConstraint("corrective_action_id", "seq"),)
    corrective_action_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("corrective_actions.id"), index=True)
    seq: Mapped[int] = mapped_column(Integer)
    action: Mapped[str] = mapped_column(Unicode(20))
    from_status: Mapped[str | None] = mapped_column(Unicode(12))
    to_status: Mapped[str] = mapped_column(Unicode(12))
    actor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    actor_org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"))
    actor_side: Mapped[str] = mapped_column(Unicode(10))
    occurred_at: Mapped[datetime] = mapped_column(default=utcnow, server_default=text("SYSUTCDATETIME()"))
    note: Mapped[str | None] = mapped_column(Unicode(4000))
    document_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("documents.id"))


class VerificationDecision(UUIDPrimaryKey, Base):
    """The external VVB's recorded decision (C15, C16). Immutable except CURRENT → SUPERSEDED (trigger)."""
    __tablename__ = "verification_decisions"
    __table_args__ = (
        CheckConstraint(in_check("outcome", DECISION_OUTCOMES), name="outcome"),
        CheckConstraint(in_check("status", DECISION_STATUSES), name="status"),
        CheckConstraint(in_check("environment", Environment), name="environment"),
        CheckConstraint("(verified_quantity IS NULL AND verified_quantity_unit IS NULL) OR "
                        "(verified_quantity IS NOT NULL AND verified_quantity_unit IS NOT NULL)", name="quantity_unit"),
        UniqueConstraint("submission_id"),
        Index("uq_verification_decisions_current", "monitoring_period_id", unique=True, mssql_where=text("status = 'CURRENT'")),
    )
    decision_code: Mapped[str] = mapped_column(Unicode(20), unique=True)         # VDEC-YYYY-NNNNNN
    assignment_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("verification_assignments.id"), index=True)
    submission_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("verification_submissions.id"))
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"))
    monitoring_period_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("monitoring_periods.id"))
    vvb_organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"))
    outcome: Mapped[str] = mapped_column(Unicode(15))
    verified_quantity: Mapped[Decimal | None] = mapped_column(Numeric(28, 10))   # "VVB-stated verified quantity" — never a credit
    verified_quantity_unit: Mapped[str | None] = mapped_column(Unicode(40))
    rationale: Mapped[str] = mapped_column(Unicode(4000))
    report_document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("documents.id"))
    report_sha256: Mapped[str] = mapped_column(Unicode(64))
    manifest_sha256: Mapped[str] = mapped_column(Unicode(64))
    decided_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    decided_at: Mapped[datetime] = mapped_column(default=utcnow, server_default=text("SYSUTCDATETIME()"))
    status: Mapped[str] = mapped_column(Unicode(12), default="CURRENT")
    superseded_at: Mapped[datetime | None]
    superseded_reason: Mapped[str | None] = mapped_column(Unicode(2000))
    environment: Mapped[str] = mapped_column(Unicode(10), default=Environment.LIVE.value)
