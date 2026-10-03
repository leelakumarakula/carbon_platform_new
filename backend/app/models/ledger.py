"""Phase 9B — credit ledger: ownership positions, reservations, transfers, retirements (decisions X1–X5, D1–D21). No marketplace,
pricing, orders, payment or payout.

UTXO-like model (D13): a position is a whole-unit quantity of one registry-issued batch and one ORIGINAL 9A registry serial range, held by
one owner in one state. Positions are never edited: an operation consumes input positions (OPEN → CONSUMED, exactly once) and creates
output positions, all under one append-only ledger entry that is validated when it is posted (inputs = outputs; batch conservation).
Balances are derived from OPEN positions — no stored available / owned / transferred / retired quantity exists.

States (X5): AVAILABLE · RESERVED · TRANSFER_PENDING · RETIREMENT_PENDING · RETIRED (terminal). Calculated and VVB-verified quantities
are never ledger states. 9A batches and serial ranges are never modified; exact sub-ranges exist only when the registry states them or a
registry-specific parser derives them (X3).
"""
import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, CheckConstraint, Date, ForeignKey, Index, Numeric, Unicode, UnicodeText, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, Environment, UUIDPrimaryKey, in_check, utcnow

POSITION_STATES = ["AVAILABLE", "RESERVED", "TRANSFER_PENDING", "RETIREMENT_PENDING", "RETIRED"]
POSITION_STATUSES = ["OPEN", "CONSUMED"]
ENTRY_TYPES = ["OPEN_INVENTORY", "RESERVE", "RESERVATION_RELEASE", "RESERVATION_EXPIRE", "TRANSFER_REQUEST", "TRANSFER_COMPLETE",
               "TRANSFER_CANCEL", "TRANSFER_REJECT", "RETIREMENT_REQUEST", "RETIREMENT_RETIRE", "RETIREMENT_REJECT", "RETIREMENT_CANCEL",
               "REVERSAL", "ISSUANCE_ADJUSTMENT"]
OPENING_STATUSES = ["REQUESTED", "CONFIRMED", "CANCELLED"]
RESERVATION_STATUSES = ["ACTIVE", "CONSUMED", "RELEASED", "EXPIRED"]
TRANSFER_KINDS = ["INTERNAL", "REGISTRY"]
TRANSFER_STATUSES = ["REQUESTED", "COMPLETED", "CANCELLED", "REJECTED"]
RETIREMENT_STATUSES = ["REQUESTED", "RETIRED", "REJECTED", "CANCELLED"]
REVERSAL_STATUSES = ["REQUESTED", "APPLIED", "REJECTED"]


class CreditLedgerEntry(UUIDPrimaryKey, Base):
    """Append-only. Inserted unposted, its positions consumed / created, then posted once (trigger validates conservation)."""
    __tablename__ = "credit_ledger_entries"
    __table_args__ = (
        CheckConstraint(in_check("entry_type", ENTRY_TYPES), name="entry_type"),
        CheckConstraint(in_check("environment", Environment), name="environment"),
        CheckConstraint("confirmed_by IS NULL OR confirmed_by <> actor_id", name="dual_control"),
        Index("uq_credit_ledger_entries_request_key", "request_key", unique=True, mssql_where=text("request_key IS NOT NULL")),
        Index("ix_credit_ledger_entries_batch", "batch_id", "created_at"),
    )
    entry_code: Mapped[str] = mapped_column(Unicode(20), unique=True)          # LEDG-YYYY-NNNNNN
    entry_type: Mapped[str] = mapped_column(Unicode(25))
    batch_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("credit_batches.id"))
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"))           # acting / owning organization
    counterparty_organization_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("organizations.id"))
    opening_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("credit_openings.id", use_alter=True))
    reservation_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("credit_reservations.id", use_alter=True))
    transfer_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("credit_transfers.id", use_alter=True))
    retirement_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("credit_retirements.id", use_alter=True))
    reversal_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("credit_reversals.id", use_alter=True))
    issuance_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("credit_issuances.id"))     # ISSUANCE_ADJUSTMENT
    quantity: Mapped[Decimal] = mapped_column(Numeric(28, 0))                  # the movement (for display); positions are authoritative
    actor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    confirmed_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    reason: Mapped[str | None] = mapped_column(Unicode(2000))
    request_key: Mapped[str | None] = mapped_column(Unicode(80))               # HTTP Idempotency-Key of the action
    posted: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(default=utcnow, server_default=text("SYSUTCDATETIME()"))
    environment: Mapped[str] = mapped_column(Unicode(10), default=Environment.LIVE.value)


class CreditPosition(UUIDPrimaryKey, Base):
    """Immutable; consumed exactly once (trigger). RETIRED positions are terminal and can never be consumed."""
    __tablename__ = "credit_positions"
    __table_args__ = (
        CheckConstraint(in_check("state", POSITION_STATES), name="state"),
        CheckConstraint(in_check("status", POSITION_STATUSES), name="status"),
        CheckConstraint(in_check("environment", Environment), name="environment"),
        CheckConstraint("quantity > 0", name="quantity_positive"),
        CheckConstraint("(status = 'OPEN' AND consumed_by_entry_id IS NULL) OR (status = 'CONSUMED' AND consumed_by_entry_id IS NOT NULL)",
                        name="consumed_link"),
        CheckConstraint("NOT (state = 'RETIRED' AND status = 'CONSUMED')", name="retired_terminal"),
        CheckConstraint("(sub_start IS NULL AND sub_end IS NULL) OR (sub_start IS NOT NULL AND sub_end IS NOT NULL)", name="sub_range_pair"),
        CheckConstraint("(parsed_series IS NULL AND parsed_start IS NULL AND parsed_end IS NULL) OR "
                        "(parsed_series IS NOT NULL AND parsed_start IS NOT NULL AND parsed_end IS NOT NULL AND parsed_end >= parsed_start "
                        "AND parsed_end - parsed_start + 1 = quantity)", name="parsed_bounds"),
        Index("ix_credit_positions_open", "batch_id", "serial_range_id", "owner_organization_id", "state", mssql_where=text("status = 'OPEN'")),
        Index("ix_credit_positions_created_by", "created_by_entry_id"),
        Index("ix_credit_positions_consumed_by", "consumed_by_entry_id"),
    )
    batch_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("credit_batches.id"))
    serial_range_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("credit_serial_ranges.id"))   # the ORIGINAL 9A registry range
    owner_organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), index=True)
    holding_registry_account_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("registry_accounts.id"))  # if recorded on the platform
    holding_external_account_id: Mapped[str] = mapped_column(Unicode(120))     # the registry account holding the credits
    state: Mapped[str] = mapped_column(Unicode(20))
    status: Mapped[str] = mapped_column(Unicode(10), default="OPEN")
    quantity: Mapped[Decimal] = mapped_column(Numeric(28, 0))
    sub_start: Mapped[str | None] = mapped_column(Unicode(200))               # registry-stated sub-range (verbatim) only
    sub_end: Mapped[str | None] = mapped_column(Unicode(200))
    parsed_series: Mapped[str | None] = mapped_column(Unicode(120))           # registry-specific parser only
    parsed_start: Mapped[Decimal | None] = mapped_column(Numeric(38, 0))
    parsed_end: Mapped[Decimal | None] = mapped_column(Numeric(38, 0))
    reservation_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("credit_reservations.id"))
    transfer_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("credit_transfers.id"))
    retirement_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("credit_retirements.id"))
    created_by_entry_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("credit_ledger_entries.id"))
    consumed_by_entry_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("credit_ledger_entries.id"))
    created_at: Mapped[datetime] = mapped_column(default=utcnow, server_default=text("SYSUTCDATETIME()"))
    environment: Mapped[str] = mapped_column(Unicode(10), default=Environment.LIVE.value)


class CreditOpening(UUIDPrimaryKey, Base):
    """'Open in ledger' (D2): requested, then confirmed by a second person; creates the initial AVAILABLE positions."""
    __tablename__ = "credit_openings"
    __table_args__ = (
        CheckConstraint(in_check("status", OPENING_STATUSES), name="status"),
        CheckConstraint(in_check("environment", Environment), name="environment"),
        CheckConstraint("confirmed_by IS NULL OR confirmed_by <> requested_by", name="dual_control"),
        CheckConstraint("status <> 'CONFIRMED' OR (confirmed_by IS NOT NULL AND entry_id IS NOT NULL)", name="confirmed"),
        CheckConstraint("status <> 'CANCELLED' OR cancel_reason IS NOT NULL", name="cancel_reason"),
        Index("uq_credit_openings_batch", "batch_id", unique=True, mssql_where=text("status IN ('REQUESTED', 'CONFIRMED')")),
        Index("uq_credit_openings_request_key", "request_key", unique=True, mssql_where=text("request_key IS NOT NULL")),
    )
    opening_code: Mapped[str] = mapped_column(Unicode(20), unique=True)        # OPN-YYYY-NNNNNN
    batch_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("credit_batches.id"))
    owner_organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"))     # the holding account's organization
    holding_registry_account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("registry_accounts.id"))
    status: Mapped[str] = mapped_column(Unicode(12), default="REQUESTED")
    requested_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    requested_at: Mapped[datetime] = mapped_column(default=utcnow, server_default=text("SYSUTCDATETIME()"))
    confirmed_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    confirmed_at: Mapped[datetime | None]
    cancelled_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    cancelled_at: Mapped[datetime | None]
    cancel_reason: Mapped[str | None] = mapped_column(Unicode(2000))
    entry_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("credit_ledger_entries.id"))
    request_key: Mapped[str | None] = mapped_column(Unicode(80))
    environment: Mapped[str] = mapped_column(Unicode(10), default=Environment.LIVE.value)


class CreditReservation(UUIDPrimaryKey, Base):
    """ACTIVE → CONSUMED / RELEASED / EXPIRED (D4). purpose_reference stays generic (a later order may reference it)."""
    __tablename__ = "credit_reservations"
    __table_args__ = (
        CheckConstraint(in_check("status", RESERVATION_STATUSES), name="status"),
        CheckConstraint(in_check("environment", Environment), name="environment"),
        CheckConstraint("quantity > 0", name="quantity_positive"),
        CheckConstraint("status <> 'RELEASED' OR (released_by IS NOT NULL AND release_reason IS NOT NULL)", name="release_reason"),
        Index("uq_credit_reservations_request_key", "request_key", unique=True, mssql_where=text("request_key IS NOT NULL")),
        Index("ix_credit_reservations_active", "batch_id", "expires_at", mssql_where=text("status = 'ACTIVE'")),
    )
    reservation_code: Mapped[str] = mapped_column(Unicode(20), unique=True)    # RSV-YYYY-NNNNNN
    batch_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("credit_batches.id"))
    serial_range_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("credit_serial_ranges.id"))
    owner_organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), index=True)
    recipient_organization_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("organizations.id"))
    purpose: Mapped[str] = mapped_column(Unicode(200))
    purpose_reference: Mapped[str | None] = mapped_column(Unicode(120))
    quantity: Mapped[Decimal] = mapped_column(Numeric(28, 0))
    expires_at: Mapped[datetime]
    status: Mapped[str] = mapped_column(Unicode(10), default="ACTIVE")
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(default=utcnow, server_default=text("SYSUTCDATETIME()"))
    released_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    released_at: Mapped[datetime | None]
    release_reason: Mapped[str | None] = mapped_column(Unicode(2000))
    closed_at: Mapped[datetime | None]                                         # consumed / released / expired at
    request_key: Mapped[str | None] = mapped_column(Unicode(80))
    environment: Mapped[str] = mapped_column(Unicode(10), default=Environment.LIVE.value)


class CreditTransfer(UUIDPrimaryKey, Base):
    """INTERNAL (beneficial, same holding account) or REGISTRY (evidence-backed). No price, payment or order."""
    __tablename__ = "credit_transfers"
    __table_args__ = (
        CheckConstraint(in_check("kind", TRANSFER_KINDS), name="kind"),
        CheckConstraint(in_check("status", TRANSFER_STATUSES), name="status"),
        CheckConstraint(in_check("environment", Environment), name="environment"),
        CheckConstraint("quantity > 0", name="quantity_positive"),
        CheckConstraint("completed_by IS NULL OR completed_by <> requested_by", name="dual_control"),
        CheckConstraint("kind <> 'REGISTRY' OR recipient_external_account_id IS NOT NULL", name="registry_recipient_account"),
        CheckConstraint("NOT (status = 'COMPLETED' AND kind = 'REGISTRY') OR (registry_transfer_reference IS NOT NULL AND "
                        "evidence_document_id IS NOT NULL)", name="registry_evidence"),
        CheckConstraint("status NOT IN ('CANCELLED', 'REJECTED') OR close_reason IS NOT NULL", name="close_reason"),
        CheckConstraint("sender_organization_id <> recipient_organization_id OR kind = 'REGISTRY'", name="distinct_parties"),
        Index("uq_credit_transfers_registry_ref", "registry_organization_id", "registry_transfer_reference", unique=True,
              mssql_where=text("registry_transfer_reference IS NOT NULL")),
        Index("uq_credit_transfers_request_key", "request_key", unique=True, mssql_where=text("request_key IS NOT NULL")),
    )
    transfer_code: Mapped[str] = mapped_column(Unicode(20), unique=True)       # TRF-YYYY-NNNNNN
    kind: Mapped[str] = mapped_column(Unicode(10))
    batch_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("credit_batches.id"))
    serial_range_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("credit_serial_ranges.id"))
    reservation_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("credit_reservations.id"))
    registry_organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"))
    sender_organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), index=True)
    recipient_organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), index=True)
    recipient_external_account_id: Mapped[str | None] = mapped_column(Unicode(120))     # REGISTRY: as the registry identifies it
    quantity: Mapped[Decimal] = mapped_column(Numeric(28, 0))
    purpose: Mapped[str | None] = mapped_column(Unicode(200))
    purpose_reference: Mapped[str | None] = mapped_column(Unicode(120))
    status: Mapped[str] = mapped_column(Unicode(12), default="REQUESTED")
    requested_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    requested_at: Mapped[datetime] = mapped_column(default=utcnow, server_default=text("SYSUTCDATETIME()"))
    completed_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    completed_at: Mapped[datetime | None]
    registry_transfer_reference: Mapped[str | None] = mapped_column(Unicode(120))
    evidence_document_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("documents.id"))
    closed_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    closed_at: Mapped[datetime | None]
    close_reason: Mapped[str | None] = mapped_column(Unicode(2000))
    request_key: Mapped[str | None] = mapped_column(Unicode(80))
    environment: Mapped[str] = mapped_column(Unicode(10), default=Environment.LIVE.value)


class CreditRetirement(UUIDPrimaryKey, Base):
    """REQUESTED → RETIRED only with registry evidence (X1) / REJECTED / CANCELLED. RETIRED is permanent."""
    __tablename__ = "credit_retirements"
    __table_args__ = (
        CheckConstraint(in_check("status", RETIREMENT_STATUSES), name="status"),
        CheckConstraint(in_check("environment", Environment), name="environment"),
        CheckConstraint("quantity > 0", name="quantity_positive"),
        CheckConstraint("retired_by IS NULL OR retired_by <> requested_by", name="dual_control"),
        CheckConstraint("status <> 'RETIRED' OR (registry_retirement_reference IS NOT NULL AND certificate_document_id IS NOT NULL "
                        "AND retired_by IS NOT NULL AND retirement_date IS NOT NULL)", name="registry_evidence"),
        CheckConstraint("retired_serials IS NULL OR ISJSON(retired_serials) = 1", name="retired_serials_json"),
        CheckConstraint("status NOT IN ('CANCELLED', 'REJECTED') OR close_reason IS NOT NULL", name="close_reason"),
        Index("uq_credit_retirements_registry_ref", "registry_organization_id", "registry_retirement_reference", unique=True,
              mssql_where=text("registry_retirement_reference IS NOT NULL")),
        Index("uq_credit_retirements_request_key", "request_key", unique=True, mssql_where=text("request_key IS NOT NULL")),
    )
    retirement_code: Mapped[str] = mapped_column(Unicode(20), unique=True)     # RET-YYYY-NNNNNN
    batch_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("credit_batches.id"))
    serial_range_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("credit_serial_ranges.id"))
    reservation_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("credit_reservations.id"))
    registry_organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"))
    owner_organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), index=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(28, 0))
    beneficiary: Mapped[str] = mapped_column(Unicode(300))                     # as named on the retirement claim
    reason: Mapped[str] = mapped_column(Unicode(2000))                         # claim / purpose text
    status: Mapped[str] = mapped_column(Unicode(12), default="REQUESTED")
    requested_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    requested_at: Mapped[datetime] = mapped_column(default=utcnow, server_default=text("SYSUTCDATETIME()"))
    retired_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    retired_at: Mapped[datetime | None]
    registry_retirement_reference: Mapped[str | None] = mapped_column(Unicode(120))
    retirement_date: Mapped[date | None] = mapped_column(Date)                 # registry-stated
    certificate_document_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("documents.id"))
    retired_serials: Mapped[str | None] = mapped_column(UnicodeText)           # registry-stated, verbatim JSON [{start, end, quantity}]
    closed_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    closed_at: Mapped[datetime | None]
    close_reason: Mapped[str | None] = mapped_column(Unicode(2000))
    request_key: Mapped[str | None] = mapped_column(Unicode(80))
    environment: Mapped[str] = mapped_column(Unicode(10), default=Environment.LIVE.value)


class CreditReversal(UUIDPrimaryKey, Base):
    """Compensating REVERSAL of an internal mistake (D14): requested, then applied by a second person. Never un-retires."""
    __tablename__ = "credit_reversals"
    __table_args__ = (
        CheckConstraint(in_check("status", REVERSAL_STATUSES), name="status"),
        CheckConstraint(in_check("environment", Environment), name="environment"),
        CheckConstraint("decided_by IS NULL OR decided_by <> requested_by", name="dual_control"),
        Index("uq_credit_reversals_open", "reversed_entry_id", unique=True, mssql_where=text("status IN ('REQUESTED', 'APPLIED')")),
        Index("uq_credit_reversals_request_key", "request_key", unique=True, mssql_where=text("request_key IS NOT NULL")),
    )
    reversal_code: Mapped[str] = mapped_column(Unicode(20), unique=True)       # REV-YYYY-NNNNNN
    reversed_entry_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("credit_ledger_entries.id"))
    batch_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("credit_batches.id"))
    reason: Mapped[str] = mapped_column(Unicode(2000))
    status: Mapped[str] = mapped_column(Unicode(10), default="REQUESTED")
    requested_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    requested_at: Mapped[datetime] = mapped_column(default=utcnow, server_default=text("SYSUTCDATETIME()"))
    decided_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    decided_at: Mapped[datetime | None]
    decision_note: Mapped[str | None] = mapped_column(Unicode(2000))
    entry_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("credit_ledger_entries.id"))
    request_key: Mapped[str | None] = mapped_column(Unicode(80))
    environment: Mapped[str] = mapped_column(Unicode(10), default=Environment.LIVE.value)
