"""Laboratory & sample analysis (Phase 6). Starts at a Phase 5 field collection and ends at an APPROVED laboratory result.

Locked decisions (docs/laboratory-workflow.md):
- the project ↔ laboratory engagement is the only cross-organization relationship; laboratories are organizations
- a sample (SMP-…) keeps the field-collection version it was registered from, forever
- every test answers an in-scope methodology LABORATORY rule; tests are created automatically at registration
- results are versioned; exactly one APPROVED result per root sample + methodology rule; approved values never change
- custody events and lab QA reviews are append-only; custody ends at ANALYSED (retention / return / disposal are out of scope)
- nothing here is a calculation, a credit or a verification
"""
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, Numeric, Unicode, UnicodeText, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, Environment, UUIDPrimaryKey, in_check, utcnow

ENGAGEMENT_STATUSES = ["PROPOSED", "ACTIVE", "ENDED"]
SAMPLE_STATUSES = ["REGISTERED", "SEALED", "IN_SHIPMENT", "DISPATCHED", "IN_TRANSIT", "LAB_RECEIVED", "REJECTED_AT_RECEIPT",
                   "LAB_REGISTERED", "IN_ANALYSIS", "ANALYSED", "EXCEPTION", "VOIDED"]
CUSTODY_EVENTS = ["REGISTERED", "SEALED", "ADDED_TO_SHIPMENT", "REMOVED_FROM_SHIPMENT", "DISPATCHED", "TRANSFERRED", "RECEIVED", "REJECTED",
                  "LAB_REGISTERED", "ANALYSIS_STARTED", "ANALYSIS_COMPLETED", "EXCEPTION_RECORDED", "EXCEPTION_RESOLVED", "VOIDED"]
REASON_REQUIRED_EVENTS = ["REJECTED", "EXCEPTION_RECORDED", "EXCEPTION_RESOLVED", "VOIDED"]
EXCEPTION_TYPES = ["DAMAGED", "SEAL_BROKEN", "LOST", "OTHER"]
SHIPMENT_STATUSES = ["DRAFT", "DISPATCHED", "RECEIVED", "CANCELLED"]
ITEM_STATUSES = ["IN_SHIPMENT", "REMOVED", "RECEIVED", "REJECTED"]
TEST_STATUSES = ["REQUESTED", "IN_PROGRESS", "RESULT_SUBMITTED", "CLOSED", "CANCELLED"]
RESULT_STATUSES = ["DRAFT", "SUBMITTED", "QA_REVIEW", "APPROVED", "REJECTED", "RETEST_REQUIRED", "WITHDRAWN", "SUPERSEDED"]
RESULT_SOURCES = ["MANUAL", "LIMS_IMPORT"]          # no DEMO_MOCK (decision 20)
QA_DECISIONS = ["APPROVED", "REJECTED", "RETEST_REQUIRED"]


class ProjectLaboratoryEngagement(UUIDPrimaryKey, Base):
    """Project side proposes, laboratory side accepts (PROPOSED → ACTIVE → ENDED). Never reactivated: a scope change or a
    resumed collaboration is a new engagement."""
    __tablename__ = "project_laboratory_engagements"
    __table_args__ = (
        CheckConstraint(in_check("status", ENGAGEMENT_STATUSES), name="status"),
        CheckConstraint(in_check("environment", Environment), name="environment"),
        CheckConstraint("status <> 'ENDED' OR (end_reason IS NOT NULL AND ended_by IS NOT NULL)", name="end_reason"),
        CheckConstraint("status = 'PROPOSED' OR accepted_by IS NOT NULL OR status = 'ENDED'", name="accepted"),
        CheckConstraint("accepted_by IS NULL OR accepted_by <> proposed_by", name="proposer_not_accepter"),
        CheckConstraint("ended_side IS NULL OR ended_side IN ('PROJECT', 'LABORATORY')", name="ended_side"),
        Index("uq_lab_engagements_active", "project_id", "laboratory_org_id", unique=True, mssql_where=text("status = 'ACTIVE'")),
        Index("uq_lab_engagements_proposed", "project_id", "laboratory_org_id", unique=True, mssql_where=text("status = 'PROPOSED'")),
    )
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    laboratory_org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), index=True)
    methodology_version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("methodology_versions.id"))
    status: Mapped[str] = mapped_column(Unicode(10), default="PROPOSED")
    replaces_engagement_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("project_laboratory_engagements.id"))
    notes: Mapped[str | None] = mapped_column(Unicode(1000))
    proposed_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    proposed_at: Mapped[datetime] = mapped_column(default=utcnow, server_default=text("SYSUTCDATETIME()"))
    accepted_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    accepted_at: Mapped[datetime | None]
    ended_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    ended_at: Mapped[datetime | None]
    ended_side: Mapped[str | None] = mapped_column(Unicode(10))
    end_reason: Mapped[str | None] = mapped_column(Unicode(1000))
    environment: Mapped[str] = mapped_column(Unicode(10), default=Environment.LIVE.value)


class ProjectLaboratoryEngagementRule(Base):
    """Scope: the methodology LABORATORY rules the engagement covers (real foreign keys, decision 1)."""
    __tablename__ = "project_laboratory_engagement_rules"
    engagement_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("project_laboratory_engagements.id"), primary_key=True)
    methodology_monitoring_rule_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("methodology_monitoring_rules.id"), primary_key=True)


class LabSample(UUIDPrimaryKey, Base):
    """Physical sample identity (SMP-YYYY-NNNNNN). The field collection, point, farm and project links are internal lineage and
    are never part of a laboratory-facing response."""
    __tablename__ = "lab_samples"
    __table_args__ = (
        CheckConstraint(in_check("status", SAMPLE_STATUSES), name="status"),
        CheckConstraint(in_check("environment", Environment), name="environment"),
        CheckConstraint("depth_bottom_cm > depth_top_cm", name="depth"),
        CheckConstraint("quantity IS NULL OR quantity >= 0", name="quantity"),
    )
    sample_code: Mapped[str] = mapped_column(Unicode(30), unique=True)
    root_sample_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("lab_samples.id"), index=True)
    parent_sample_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("lab_samples.id"))
    field_collection_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("field_collection_records.id"), index=True)
    sampling_point_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sampling_points.id"))
    monitoring_period_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("monitoring_periods.id"))
    farm_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("farms.id"))
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"))
    methodology_version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("methodology_versions.id"))
    engagement_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("project_laboratory_engagements.id"))
    laboratory_org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), index=True)
    status: Mapped[str] = mapped_column(Unicode(20), default="REGISTERED")
    description: Mapped[str] = mapped_column(Unicode(500))
    depth_top_cm: Mapped[Decimal] = mapped_column(Numeric(6, 1))
    depth_bottom_cm: Mapped[Decimal] = mapped_column(Numeric(6, 1))
    quantity: Mapped[Decimal | None] = mapped_column(Numeric(10, 3))
    quantity_unit: Mapped[str | None] = mapped_column(Unicode(20))
    container_label: Mapped[str | None] = mapped_column(Unicode(100))
    seal_number: Mapped[str | None] = mapped_column(Unicode(100))
    accession_number: Mapped[str | None] = mapped_column(Unicode(100))
    registered_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    registered_at: Mapped[datetime] = mapped_column(default=utcnow, server_default=text("SYSUTCDATETIME()"))
    sealed_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    sealed_at: Mapped[datetime | None]
    environment: Mapped[str] = mapped_column(Unicode(10), default=Environment.LIVE.value)


class SampleCustodyEvent(UUIDPrimaryKey, Base):
    """Append-only chain of custody (trigger). Each event names the state it leaves and enters."""
    __tablename__ = "sample_custody_events"
    __table_args__ = (
        UniqueConstraint("sample_id", "sequence_no"),
        CheckConstraint(in_check("event_type", CUSTODY_EVENTS), name="event_type"),
        CheckConstraint(in_check("to_state", SAMPLE_STATUSES), name="to_state"),
        CheckConstraint("actor_side IN ('PROJECT', 'LABORATORY')", name="actor_side"),
        CheckConstraint("event_type NOT IN ('REJECTED', 'EXCEPTION_RECORDED', 'EXCEPTION_RESOLVED', 'VOIDED') OR reason IS NOT NULL",
                        name="reason_required"),
        CheckConstraint("exception_type IS NULL OR exception_type IN ('DAMAGED', 'SEAL_BROKEN', 'LOST', 'OTHER')", name="exception_type"),
        CheckConstraint("event_type <> 'EXCEPTION_RECORDED' OR exception_type IS NOT NULL", name="exception_type_required"),
    )
    sample_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("lab_samples.id"), index=True)
    sequence_no: Mapped[int] = mapped_column(Integer)
    event_type: Mapped[str] = mapped_column(Unicode(25))
    from_state: Mapped[str | None] = mapped_column(Unicode(20))
    to_state: Mapped[str] = mapped_column(Unicode(20))
    actor_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    actor_org_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("organizations.id"))
    actor_role: Mapped[str | None] = mapped_column(Unicode(40))
    actor_side: Mapped[str] = mapped_column(Unicode(10))
    occurred_at: Mapped[datetime]
    recorded_at: Mapped[datetime] = mapped_column(default=utcnow, server_default=text("SYSUTCDATETIME()"))
    location_text: Mapped[str | None] = mapped_column(Unicode(300))
    latitude: Mapped[Decimal | None] = mapped_column(Numeric(10, 7))
    longitude: Mapped[Decimal | None] = mapped_column(Numeric(10, 7))
    seal_number: Mapped[str | None] = mapped_column(Unicode(100))
    shipment_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("lab_shipments.id"))
    exception_type: Mapped[str | None] = mapped_column(Unicode(15))
    reason: Mapped[str | None] = mapped_column(Unicode(1000))
    document_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("documents.id"))
    request_id: Mapped[str | None] = mapped_column(Unicode(64))


class LabShipment(UUIDPrimaryKey, Base):
    __tablename__ = "lab_shipments"
    __table_args__ = (
        CheckConstraint(in_check("status", SHIPMENT_STATUSES), name="status"),
        CheckConstraint(in_check("environment", Environment), name="environment"),
        CheckConstraint("status <> 'CANCELLED' OR cancel_reason IS NOT NULL", name="cancel_reason"),
        Index("ix_lab_shipments_lab_status", "laboratory_org_id", "status"),
    )
    shipment_code: Mapped[str] = mapped_column(Unicode(30), unique=True)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    engagement_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("project_laboratory_engagements.id"))
    laboratory_org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"))
    status: Mapped[str] = mapped_column(Unicode(10), default="DRAFT")
    carrier: Mapped[str | None] = mapped_column(Unicode(120))
    tracking_number: Mapped[str | None] = mapped_column(Unicode(120))
    notes: Mapped[str | None] = mapped_column(Unicode(1000))
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(default=utcnow, server_default=text("SYSUTCDATETIME()"))
    dispatched_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    dispatched_at: Mapped[datetime | None]
    received_at: Mapped[datetime | None]
    cancel_reason: Mapped[str | None] = mapped_column(Unicode(1000))
    environment: Mapped[str] = mapped_column(Unicode(10), default=Environment.LIVE.value)


class LabShipmentItem(UUIDPrimaryKey, Base):
    """One sample in one shipment, with its item-level laboratory receipt."""
    __tablename__ = "lab_shipment_items"
    __table_args__ = (
        UniqueConstraint("shipment_id", "sample_id"),
        CheckConstraint(in_check("status", ITEM_STATUSES), name="status"),
        CheckConstraint("status <> 'REJECTED' OR receipt_reason IS NOT NULL", name="rejection_reason"),
        Index("uq_lab_shipment_items_open", "sample_id", unique=True, mssql_where=text("status = 'IN_SHIPMENT'")),
    )
    shipment_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("lab_shipments.id"), index=True)
    sample_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("lab_samples.id"), index=True)
    status: Mapped[str] = mapped_column(Unicode(12), default="IN_SHIPMENT")
    added_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    added_at: Mapped[datetime] = mapped_column(default=utcnow, server_default=text("SYSUTCDATETIME()"))
    receipt_condition: Mapped[str | None] = mapped_column(Unicode(500))
    receipt_seal_number: Mapped[str | None] = mapped_column(Unicode(100))
    receipt_reason: Mapped[str | None] = mapped_column(Unicode(1000))
    received_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    received_at: Mapped[datetime | None]


class LabTest(UUIDPrimaryKey, Base):
    """One requested analysis of one sample for one in-scope methodology LABORATORY rule. Created automatically at
    registration; retests are explicit and linked to the test they repeat."""
    __tablename__ = "lab_tests"
    __table_args__ = (
        CheckConstraint(in_check("status", TEST_STATUSES), name="status"),
        CheckConstraint(in_check("environment", Environment), name="environment"),
        CheckConstraint("retest_of_test_id IS NULL OR (retest_reason IS NOT NULL AND retest_requested_by IS NOT NULL)", name="retest_reason"),
        Index("uq_lab_tests_sample_rule", "sample_id", "methodology_monitoring_rule_id", unique=True,
              mssql_where=text("retest_of_test_id IS NULL AND status <> 'CANCELLED'")),
        Index("ix_lab_tests_lab_status", "laboratory_org_id", "status"),
    )
    test_code: Mapped[str] = mapped_column(Unicode(30), unique=True)
    sample_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("lab_samples.id"), index=True)
    root_sample_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("lab_samples.id"))
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"))
    laboratory_org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"))
    engagement_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("project_laboratory_engagements.id"))
    methodology_version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("methodology_versions.id"))
    methodology_monitoring_rule_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("methodology_monitoring_rules.id"))
    mrv_plan_measurement_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("mrv_plan_measurements.id"))
    status: Mapped[str] = mapped_column(Unicode(20), default="REQUESTED")
    method_reported: Mapped[str | None] = mapped_column(Unicode(500))
    retest_of_test_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("lab_tests.id"))
    retest_reason: Mapped[str | None] = mapped_column(Unicode(1000))
    retest_requested_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(default=utcnow, server_default=text("SYSUTCDATETIME()"))
    started_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    started_at: Mapped[datetime | None]
    environment: Mapped[str] = mapped_column(Unicode(10), default=Environment.LIVE.value)


class LabResult(UUIDPrimaryKey, Base):
    """Versioned analytical value. Exactly one of value_number / value_text (verbatim, never parsed or converted). Approved rows
    are immutable (trigger): the only change allowed is APPROVED → SUPERSEDED."""
    __tablename__ = "lab_results"
    __table_args__ = (
        UniqueConstraint("test_id", "version"),
        CheckConstraint(in_check("status", RESULT_STATUSES), name="status"),
        CheckConstraint(in_check("source", RESULT_SOURCES), name="source"),
        CheckConstraint(in_check("environment", Environment), name="environment"),
        CheckConstraint("(result_type = 'NUMERIC' AND value_number IS NOT NULL AND value_text IS NULL) OR "
                        "(result_type = 'TEXT' AND value_text IS NOT NULL AND value_number IS NULL)", name="one_value"),
        CheckConstraint("source <> 'LIMS_IMPORT' OR external_result_id IS NOT NULL", name="lims_external_id"),
        Index("uq_lab_results_approved", "root_sample_id", "methodology_monitoring_rule_id", unique=True,
              mssql_where=text("status = 'APPROVED'")),
        Index("uq_lab_results_external", "laboratory_org_id", "external_result_id", unique=True,
              mssql_where=text("external_result_id IS NOT NULL")),
        Index("ix_lab_results_lab_status", "laboratory_org_id", "status"),
    )
    test_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("lab_tests.id"), index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    supersedes_result_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("lab_results.id"))
    superseded_by_result_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("lab_results.id"))
    superseded_at: Mapped[datetime | None]
    sample_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("lab_samples.id"), index=True)
    root_sample_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("lab_samples.id"))
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    laboratory_org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"))
    methodology_version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("methodology_versions.id"))
    methodology_monitoring_rule_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("methodology_monitoring_rules.id"))
    mrv_plan_measurement_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("mrv_plan_measurements.id"))
    result_type: Mapped[str] = mapped_column(Unicode(10))
    value_number: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    value_text: Mapped[str | None] = mapped_column(Unicode(200))
    unit: Mapped[str | None] = mapped_column(Unicode(40))
    analysed_at: Mapped[datetime | None]
    analyst_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    method_reported: Mapped[str | None] = mapped_column(Unicode(500))
    report_document_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("documents.id"))
    source: Mapped[str] = mapped_column(Unicode(15), default="MANUAL")
    external_result_id: Mapped[str | None] = mapped_column(Unicode(120))
    status: Mapped[str] = mapped_column(Unicode(20), default="DRAFT")
    status_reason: Mapped[str | None] = mapped_column(Unicode(1000))
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(default=utcnow, server_default=text("SYSUTCDATETIME()"))
    submitted_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    submitted_at: Mapped[datetime | None]
    approved_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    approved_at: Mapped[datetime | None]
    environment: Mapped[str] = mapped_column(Unicode(10), default=Environment.LIVE.value)


class LabResultQaReview(UUIDPrimaryKey, Base):
    """Append-only laboratory QA decision with the deterministic checks it was made on."""
    __tablename__ = "lab_result_qa_reviews"
    __table_args__ = (
        CheckConstraint(in_check("decision", QA_DECISIONS), name="decision"),
        CheckConstraint("checks IS NULL OR ISJSON(checks) = 1", name="checks_json"),
    )
    result_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("lab_results.id"), index=True)
    reviewer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    decision: Mapped[str] = mapped_column(Unicode(20))
    checks: Mapped[str | None] = mapped_column(UnicodeText)
    notes: Mapped[str] = mapped_column(Unicode(2000))
    configuration_acknowledged: Mapped[bool] = mapped_column(default=False)
    reviewed_at: Mapped[datetime] = mapped_column(default=utcnow, server_default=text("SYSUTCDATETIME()"))
