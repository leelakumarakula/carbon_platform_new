"""Phase 9A — registry submission and credit issuance (decisions D1–D18). Registries are external counterparties (organizations with
org_type REGISTRY, no registry users); every record here is owned by the project's organization.

Three quantities stay separate and are never copied into each other:
  calculated (Phase 7 run) ≠ VVB-stated verified (Phase 8B decision) ≠ registry-issued (credit batches below)

- registry account: the developer's account at a registry; adapter selected per account (MANUAL by default); explicit unit equivalence
  and document checklist are configuration (never assumed)
- project registration: an external fact recorded with evidence (PENDING → REGISTERED / REJECTED)
- registry submission: one period's CURRENT VERIFIED VVB decision; frozen snapshot + SHA-256; idempotency key before any external call
- registry events: append-only log of every external interaction (payload hashes, never raw payloads)
- issuance (RECORDED → CONFIRMED by a second person; VOIDED / CORRECTED / CANCELLED keep history) → credit batches (vintage stated by
  the registry, whole units) → serial ranges exactly as the registry supplied them (never generated)
- nothing here is available inventory, ownership, reservation, transfer or retirement (Phase 9B / later)
"""
import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, CheckConstraint, Date, ForeignKey, Index, Numeric, Unicode, UnicodeText, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, Environment, UUIDPrimaryKey, in_check, utcnow

ACCOUNT_STATUSES = ["ACTIVE", "CLOSED"]
REGISTRATION_STATUSES = ["PENDING", "REGISTERED", "REJECTED"]
OPEN_REGISTRATION_STATUSES = ("PENDING", "REGISTERED")
RSUB_STATUSES = ["DRAFT", "FROZEN", "SUBMITTING", "SUBMISSION_UNCONFIRMED", "SUBMITTED", "ACCEPTED", "REJECTED", "WITHDRAWN", "CANCELLED",
                 "INVALIDATED"]
OPEN_RSUB_STATUSES = ("DRAFT", "FROZEN", "SUBMITTING", "SUBMISSION_UNCONFIRMED", "SUBMITTED", "ACCEPTED")
EXTERNAL_RSUB_STATUSES = ("SUBMITTING", "SUBMISSION_UNCONFIRMED", "SUBMITTED", "ACCEPTED")     # the registry may know about it
REGISTRY_EVENT_TYPES = ["SUBMIT_ATTEMPT", "SUBMIT_CONFIRMED", "TIMEOUT", "STATUS_QUERIED", "QUERY_RECEIVED", "RESPONSE_RECORDED", "ERROR",
                        "RECONCILED", "MISMATCH", "SOURCE_SUPERSEDED", "DOCUMENT_ATTACHED", "EXTERNAL_REFERENCE_RECORDED"]
ISSUANCE_STATUSES = ["RECORDED", "CONFIRMED", "VOIDED", "CORRECTED", "CANCELLED"]
ISSUANCE_SOURCES = ["MANUAL", "API"]
BATCH_STATUSES = ["RECORDED", "ISSUED", "VOIDED", "SUPERSEDED", "CANCELLED"]


class RegistryAccount(UUIDPrimaryKey, Base):
    __tablename__ = "registry_accounts"
    __table_args__ = (
        CheckConstraint(in_check("status", ACCOUNT_STATUSES), name="status"),
        CheckConstraint(in_check("environment", Environment), name="environment"),
        CheckConstraint("(credit_unit IS NULL AND verified_unit_equivalent IS NULL) OR "
                        "(credit_unit IS NOT NULL AND verified_unit_equivalent IS NOT NULL)", name="unit_equivalence"),
        CheckConstraint("document_checklist IS NULL OR ISJSON(document_checklist) = 1", name="checklist_json"),
        CheckConstraint("status <> 'CLOSED' OR closed_reason IS NOT NULL", name="closed_reason"),
        Index("uq_registry_accounts_external", "registry_organization_id", "external_account_id", unique=True),
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), index=True)   # owner (project developer)
    registry_organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"))       # counterparty (org_type REGISTRY)
    external_account_id: Mapped[str] = mapped_column(Unicode(120))                                   # as the registry identifies it
    label: Mapped[str] = mapped_column(Unicode(200))
    adapter_code: Mapped[str] = mapped_column(Unicode(30), default="MANUAL")
    credit_unit: Mapped[str | None] = mapped_column(Unicode(40))                 # D5: registry credit unit, e.g. as on its statements
    verified_unit_equivalent: Mapped[str | None] = mapped_column(Unicode(40))    # D5: explicitly 1 credit unit = 1 of this verified unit
    document_checklist: Mapped[str | None] = mapped_column(UnicodeText)          # D16: JSON [{code, title, source}] — configuration
    status: Mapped[str] = mapped_column(Unicode(10), default="ACTIVE")
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(default=utcnow, server_default=text("SYSUTCDATETIME()"))
    closed_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    closed_at: Mapped[datetime | None]
    closed_reason: Mapped[str | None] = mapped_column(Unicode(1000))
    environment: Mapped[str] = mapped_column(Unicode(10), default=Environment.LIVE.value)


class RegistryProjectRegistration(UUIDPrimaryKey, Base):
    __tablename__ = "registry_project_registrations"
    __table_args__ = (
        CheckConstraint(in_check("status", REGISTRATION_STATUSES), name="status"),
        CheckConstraint(in_check("environment", Environment), name="environment"),
        CheckConstraint("status <> 'REGISTERED' OR (external_project_id IS NOT NULL AND evidence_document_id IS NOT NULL "
                        "AND recorded_by IS NOT NULL)", name="registered_evidence"),
        CheckConstraint("status <> 'REJECTED' OR (response_reason IS NOT NULL AND evidence_document_id IS NOT NULL)", name="rejected_evidence"),
        Index("uq_registry_registrations_external", "registry_organization_id", "external_project_id", unique=True,
              mssql_where=text("external_project_id IS NOT NULL")),
        Index("uq_registry_registrations_open", "project_id", "registry_organization_id", unique=True,
              mssql_where=text("status IN ('PENDING', 'REGISTERED')")),
    )
    registration_code: Mapped[str] = mapped_column(Unicode(20), unique=True)    # RREG-YYYY-NNNNNN
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    registry_account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("registry_accounts.id"))
    registry_organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"))
    status: Mapped[str] = mapped_column(Unicode(12), default="PENDING")
    external_project_id: Mapped[str | None] = mapped_column(Unicode(120))       # registry-assigned
    registered_on: Mapped[date | None] = mapped_column(Date)                      # registry-stated registration date
    evidence_document_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("documents.id"))
    response_reason: Mapped[str | None] = mapped_column(Unicode(2000))
    notes: Mapped[str | None] = mapped_column(Unicode(2000))
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(default=utcnow, server_default=text("SYSUTCDATETIME()"))
    recorded_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))   # who recorded the registry's answer
    recorded_at: Mapped[datetime | None]
    environment: Mapped[str] = mapped_column(Unicode(10), default=Environment.LIVE.value)


class RegistrySubmission(UUIDPrimaryKey, Base):
    __tablename__ = "registry_submissions"
    __table_args__ = (
        CheckConstraint(in_check("status", RSUB_STATUSES), name="status"),
        CheckConstraint(in_check("environment", Environment), name="environment"),
        CheckConstraint("status IN ('DRAFT', 'CANCELLED', 'INVALIDATED') OR (snapshot IS NOT NULL AND snapshot_sha256 IS NOT NULL "
                        "AND idempotency_key IS NOT NULL)", name="frozen_snapshot"),
        CheckConstraint("snapshot IS NULL OR ISJSON(snapshot) = 1", name="snapshot_json"),
        CheckConstraint("status NOT IN ('SUBMITTED', 'ACCEPTED', 'REJECTED', 'WITHDRAWN') OR external_submission_id IS NOT NULL",
                        name="external_reference"),
        CheckConstraint("status NOT IN ('ACCEPTED', 'REJECTED') OR response_document_id IS NOT NULL OR response_payload_sha256 IS NOT NULL",
                        name="response_evidence"),
        CheckConstraint("status <> 'REJECTED' OR response_reason IS NOT NULL", name="rejection_reason"),
        CheckConstraint("status NOT IN ('WITHDRAWN', 'CANCELLED', 'INVALIDATED') OR closed_reason IS NOT NULL", name="closed_reason"),
        Index("uq_registry_submissions_open_period", "monitoring_period_id", unique=True,
              mssql_where=text("status IN ('DRAFT', 'FROZEN', 'SUBMITTING', 'SUBMISSION_UNCONFIRMED', 'SUBMITTED', 'ACCEPTED')")),
        Index("uq_registry_submissions_external", "registry_organization_id", "external_submission_id", unique=True,
              mssql_where=text("external_submission_id IS NOT NULL")),
        Index("uq_registry_submissions_idempotency", "idempotency_key", unique=True, mssql_where=text("idempotency_key IS NOT NULL")),
        Index("uq_registry_submissions_request_key", "client_request_key", unique=True, mssql_where=text("client_request_key IS NOT NULL")),
    )
    submission_code: Mapped[str] = mapped_column(Unicode(20), unique=True)      # RSUB-YYYY-NNNNNN
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    monitoring_period_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("monitoring_periods.id"))
    registration_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("registry_project_registrations.id"))
    registry_account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("registry_accounts.id"))
    registry_organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"))
    verification_decision_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("verification_decisions.id"))
    verification_submission_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("verification_submissions.id"))
    previous_submission_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("registry_submissions.id"))
    status: Mapped[str] = mapped_column(Unicode(25), default="DRAFT")
    snapshot: Mapped[str | None] = mapped_column(UnicodeText)                    # registry-submission-v1 (canonical JSON)
    snapshot_sha256: Mapped[str | None] = mapped_column(Unicode(64))
    idempotency_key: Mapped[str | None] = mapped_column(Unicode(64))             # generated at freeze, sent with any external call
    client_request_key: Mapped[str | None] = mapped_column(Unicode(80))          # optional HTTP Idempotency-Key of the create request
    external_submission_id: Mapped[str | None] = mapped_column(Unicode(120))
    submission_evidence_document_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("documents.id"))
    response_document_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("documents.id"))
    response_payload_sha256: Mapped[str | None] = mapped_column(Unicode(64))
    external_response_ref: Mapped[str | None] = mapped_column(Unicode(120))
    response_reason: Mapped[str | None] = mapped_column(Unicode(2000))
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(default=utcnow, server_default=text("SYSUTCDATETIME()"))
    frozen_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    frozen_at: Mapped[datetime | None]
    submitted_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    submitted_at: Mapped[datetime | None]
    response_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    response_at: Mapped[datetime | None]
    closed_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    closed_at: Mapped[datetime | None]
    closed_reason: Mapped[str | None] = mapped_column(Unicode(2000))
    environment: Mapped[str] = mapped_column(Unicode(10), default=Environment.LIVE.value)


class RegistryEvent(UUIDPrimaryKey, Base):
    """Append-only (trigger): every interaction with the external registry, manual or through an adapter."""
    __tablename__ = "registry_events"
    __table_args__ = (
        CheckConstraint(in_check("event_type", REGISTRY_EVENT_TYPES), name="event_type"),
        CheckConstraint(in_check("environment", Environment), name="environment"),
        Index("ix_registry_events_submission", "submission_id", "occurred_at"),
    )
    registry_account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("registry_accounts.id"))
    registration_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("registry_project_registrations.id"))
    submission_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("registry_submissions.id"))
    issuance_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("credit_issuances.id"))
    event_type: Mapped[str] = mapped_column(Unicode(30))
    actor_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    occurred_at: Mapped[datetime] = mapped_column(default=utcnow, server_default=text("SYSUTCDATETIME()"))
    adapter_code: Mapped[str] = mapped_column(Unicode(30))
    idempotency_key: Mapped[str | None] = mapped_column(Unicode(64))
    external_ref: Mapped[str | None] = mapped_column(Unicode(120))
    payload_sha256: Mapped[str | None] = mapped_column(Unicode(64))             # hash only — raw registry payloads are not stored
    outcome: Mapped[str | None] = mapped_column(Unicode(40))
    checklist_item: Mapped[str | None] = mapped_column(Unicode(60))
    note: Mapped[str | None] = mapped_column(Unicode(2000))
    document_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("documents.id"))
    environment: Mapped[str] = mapped_column(Unicode(10), default=Environment.LIVE.value)


class CreditIssuance(UUIDPrimaryKey, Base):
    __tablename__ = "credit_issuances"
    __table_args__ = (
        CheckConstraint(in_check("status", ISSUANCE_STATUSES), name="status"),
        CheckConstraint(in_check("source", ISSUANCE_SOURCES), name="source"),
        CheckConstraint(in_check("environment", Environment), name="environment"),
        CheckConstraint("quantity > 0", name="quantity_positive"),
        CheckConstraint("evidence_document_id IS NOT NULL OR api_response_sha256 IS NOT NULL", name="evidence"),
        CheckConstraint("confirmed_by IS NULL OR confirmed_by <> recorded_by", name="dual_control"),
        CheckConstraint("status <> 'VOIDED' OR void_reason IS NOT NULL", name="void_reason"),
        CheckConstraint("status <> 'CANCELLED' OR (cancel_reason IS NOT NULL AND cancel_document_id IS NOT NULL)", name="cancel_evidence"),
        CheckConstraint("status NOT IN ('CONFIRMED', 'CORRECTED', 'CANCELLED') OR confirmed_by IS NOT NULL", name="confirmed"),
        Index("uq_credit_issuances_external", "registry_organization_id", "external_issuance_id", unique=True,
              mssql_where=text("status = 'CONFIRMED'")),
        Index("uq_credit_issuances_request_key", "client_request_key", unique=True, mssql_where=text("client_request_key IS NOT NULL")),
        Index("ix_credit_issuances_submission", "registry_submission_id", "status"),
    )
    issuance_code: Mapped[str] = mapped_column(Unicode(20), unique=True)        # ISS-YYYY-NNNNNN
    registry_submission_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("registry_submissions.id"))
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    monitoring_period_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("monitoring_periods.id"))
    registry_account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("registry_accounts.id"))
    registry_organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"))
    verification_decision_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("verification_decisions.id"))
    external_issuance_id: Mapped[str] = mapped_column(Unicode(120))
    issuance_date: Mapped[date] = mapped_column(Date)                            # registry-stated
    quantity: Mapped[Decimal] = mapped_column(Numeric(28, 0))                    # registry-stated, whole units (D7)
    unit: Mapped[str] = mapped_column(Unicode(40))                               # registry-stated credit unit
    source: Mapped[str] = mapped_column(Unicode(10), default="MANUAL")
    evidence_document_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("documents.id"))   # ISSUANCE_STATEMENT
    api_response_sha256: Mapped[str | None] = mapped_column(Unicode(64))
    corrects_issuance_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("credit_issuances.id"))
    corrected_by_issuance_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("credit_issuances.id"))
    correction_reason: Mapped[str | None] = mapped_column(Unicode(2000))
    client_request_key: Mapped[str | None] = mapped_column(Unicode(80))
    status: Mapped[str] = mapped_column(Unicode(12), default="RECORDED")
    recorded_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    recorded_at: Mapped[datetime] = mapped_column(default=utcnow, server_default=text("SYSUTCDATETIME()"))
    confirmed_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    confirmed_at: Mapped[datetime | None]
    voided_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    voided_at: Mapped[datetime | None]
    void_reason: Mapped[str | None] = mapped_column(Unicode(2000))
    cancelled_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    cancelled_at: Mapped[datetime | None]
    cancel_reason: Mapped[str | None] = mapped_column(Unicode(2000))
    cancel_document_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("documents.id"))
    environment: Mapped[str] = mapped_column(Unicode(10), default=Environment.LIVE.value)


class CreditBatch(UUIDPrimaryKey, Base):
    """A registry-issued block of credits (not one row per credit). ISSUED only once its issuance is CONFIRMED."""
    __tablename__ = "credit_batches"
    __table_args__ = (
        CheckConstraint(in_check("status", BATCH_STATUSES), name="status"),
        CheckConstraint(in_check("environment", Environment), name="environment"),
        CheckConstraint("quantity > 0", name="quantity_positive"),
        Index("ix_credit_batches_project_period", "project_id", "monitoring_period_id"),
    )
    batch_code: Mapped[str] = mapped_column(Unicode(20), unique=True)            # CB-YYYY-NNNNNN
    issuance_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("credit_issuances.id"), index=True)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"))
    monitoring_period_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("monitoring_periods.id"))
    registry_organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"))
    registry_account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("registry_accounts.id"))
    verification_decision_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("verification_decisions.id"))
    methodology_version_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("methodology_versions.id"))
    standard_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("standards.id"))
    seq: Mapped[int]
    vintage: Mapped[str] = mapped_column(Unicode(60))                            # registry-stated (D8), never computed
    quantity: Mapped[Decimal] = mapped_column(Numeric(28, 0))
    unit: Mapped[str] = mapped_column(Unicode(40))
    status: Mapped[str] = mapped_column(Unicode(12), default="RECORDED")
    created_at: Mapped[datetime] = mapped_column(default=utcnow, server_default=text("SYSUTCDATETIME()"))
    environment: Mapped[str] = mapped_column(Unicode(10), default=Environment.LIVE.value)


class CreditSerialRange(UUIDPrimaryKey, Base):
    """Registry serial block exactly as supplied (D9). `is_current` marks ranges of ISSUED / CANCELLED batches (uniqueness applies)."""
    __tablename__ = "credit_serial_ranges"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="quantity_positive"),
        CheckConstraint("(serial_start IS NULL AND serial_end IS NULL) OR (serial_start IS NOT NULL AND serial_end IS NOT NULL)",
                        name="serial_pair"),
        CheckConstraint("(parsed_series IS NULL AND parsed_start IS NULL AND parsed_end IS NULL) OR "
                        "(parsed_series IS NOT NULL AND parsed_start IS NOT NULL AND parsed_end IS NOT NULL AND parsed_end >= parsed_start)",
                        name="parsed_bounds"),
        CheckConstraint(in_check("environment", Environment), name="environment"),
        Index("uq_credit_serial_ranges_start", "registry_organization_id", "serial_start", unique=True,
              mssql_where=text("serial_start IS NOT NULL AND is_current = 1")),
        Index("uq_credit_serial_ranges_end", "registry_organization_id", "serial_end", unique=True,
              mssql_where=text("serial_end IS NOT NULL AND is_current = 1")),
    )
    batch_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("credit_batches.id"), index=True)
    registry_organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"))
    seq: Mapped[int]
    serial_start: Mapped[str | None] = mapped_column(Unicode(200))
    serial_end: Mapped[str | None] = mapped_column(Unicode(200))
    quantity: Mapped[Decimal] = mapped_column(Numeric(28, 0))
    parsed_series: Mapped[str | None] = mapped_column(Unicode(120))              # registry-specific parser only
    parsed_start: Mapped[Decimal | None] = mapped_column(Numeric(38, 0))
    parsed_end: Mapped[Decimal | None] = mapped_column(Numeric(38, 0))
    is_current: Mapped[bool] = mapped_column(Boolean, default=False)
    environment: Mapped[str] = mapped_column(Unicode(10), default=Environment.LIVE.value)
