"""Phase 11 — revenue, project costs, revenue-share rules, farm allocations, settlement runs, farmer entitlements, payouts.

Money ledger, separate from the Phase 9B credit ledger (which stays the only credit ownership / balance record): revenue is recognized
per order item from immutable Phase 10 facts; every business value (farmer share, cost deduction, rounding, farm allocation) is a
versioned, second-person-approved configuration — nothing is hard-coded. Approved / recognized / paid records are never edited:
corrections are reversals, new versions, new runs or recovery cases. Money is `Numeric(19,4)` + ISO-4217; FLOAT is never used.
"""
import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, CheckConstraint, Date, ForeignKey, Index, Integer, Numeric, Unicode, UnicodeText, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, Environment, UUIDPrimaryKey, in_check, utcnow

MONEY = Numeric(19, 4)
PCT = Numeric(9, 6)                   # a configured percentage (0 < x ≤ 100), never a default
REVENUE_KINDS = ["RECOGNITION", "REVERSAL"]
CONFIG_STATUSES = ["DRAFT", "IN_REVIEW", "APPROVED", "SUPERSEDED"]
ROUNDING_MODES = ["HALF_UP", "HALF_EVEN", "DOWN"]        # chosen per rule version; the platform has no default
COST_STATUSES = ["PENDING_APPROVAL", "APPROVED", "REJECTED"]
SETTLEMENT_STATUSES = ["DRAFT", "CALCULATED", "PENDING_APPROVAL", "APPROVED", "COMPLETED", "REJECTED", "CANCELLED"]
PAYOUT_STATUSES = ["CALCULATED", "PENDING_APPROVAL", "APPROVED", "PAYMENT_PENDING", "PAID", "RECONCILED", "REJECTED", "CANCELLED",
                   "FAILED", "UNCONFIRMED", "ON_HOLD"]
TRANSACTION_KINDS = ["INITIATED", "PAID", "FAILED", "UNCONFIRMED", "STATUS_QUERIED"]
RECONCILIATION_RESULTS = ["MATCHED", "EXCEPTION"]
ADJUSTMENT_STATUSES = ["OPEN", "CLOSED"]


class RevenueRecord(UUIDPrimaryKey, Base):
    """Append-only (trigger). RECOGNITION: one per order item, when its payment is CONFIRMED and its 9B transfer COMPLETED (amount > 0).
    REVERSAL: one per recognition, when a refund of the order completes (amount < 0). Never edited."""
    __tablename__ = "revenue_records"
    __table_args__ = (
        CheckConstraint(in_check("kind", REVENUE_KINDS), name="kind"),
        CheckConstraint(in_check("environment", Environment), name="environment"),
        CheckConstraint("(kind = 'RECOGNITION' AND amount > 0 AND reverses_revenue_id IS NULL AND refund_id IS NULL) OR "
                        "(kind = 'REVERSAL' AND amount < 0 AND reverses_revenue_id IS NOT NULL AND refund_id IS NOT NULL)", name="kind_shape"),
        CheckConstraint("LEN(currency) = 3", name="currency_code"),
        Index("uq_revenue_records_recognition", "order_item_id", unique=True, mssql_where=text("kind = 'RECOGNITION'")),
        Index("uq_revenue_records_reversal", "reverses_revenue_id", unique=True, mssql_where=text("reverses_revenue_id IS NOT NULL")),
        Index("ix_revenue_records_scope", "project_id", "monitoring_period_id", "currency"),
    )
    revenue_code: Mapped[str] = mapped_column(Unicode(20), unique=True)        # RVN-YYYY-NNNNNN
    kind: Mapped[str] = mapped_column(Unicode(12))
    order_item_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("order_items.id"))
    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orders.id"), index=True)
    payment_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("payments.id"))
    transfer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("credit_transfers.id"))
    batch_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("credit_batches.id"))
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"))
    monitoring_period_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("monitoring_periods.id"))
    seller_organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"))   # received the money (Phase 10 payee)
    reverses_revenue_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("revenue_records.id"))
    refund_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("refunds.id"))
    amount: Mapped[Decimal] = mapped_column(MONEY)
    currency: Mapped[str] = mapped_column(Unicode(3))
    recorded_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    recorded_at: Mapped[datetime] = mapped_column(default=utcnow, server_default=text("SYSUTCDATETIME()"))
    environment: Mapped[str] = mapped_column(Unicode(10), default=Environment.LIVE.value)


class RevenueShareVersion(UUIDPrimaryKey, Base):
    """A project's revenue-share configuration, versioned (DRAFT → IN_REVIEW → APPROVED → SUPERSEDED; IN_REVIEW → DRAFT when returned).
    The farmer share percentage, whether approved project costs are deducted first, and the rounding mode are entered by the author
    from the project's agreements (`source_reference`) and approved by a different person; approved versions are immutable (trigger)."""
    __tablename__ = "revenue_share_versions"
    __table_args__ = (
        CheckConstraint(in_check("status", CONFIG_STATUSES), name="status"),
        CheckConstraint(in_check("rounding_mode", ROUNDING_MODES), name="rounding_mode"),
        CheckConstraint(in_check("environment", Environment), name="environment"),
        CheckConstraint("farmer_share_pct > 0 AND farmer_share_pct <= 100", name="farmer_share"),
        CheckConstraint("effective_to IS NULL OR effective_to >= effective_from", name="dates"),
        CheckConstraint("approved_by IS NULL OR approved_by <> created_by", name="approval_sod"),
        CheckConstraint("status NOT IN ('APPROVED', 'SUPERSEDED') OR approved_by IS NOT NULL", name="approved"),
        Index("uq_revenue_share_versions_no", "project_id", "version_no", unique=True),
        Index("uq_revenue_share_versions_request_key", "request_key", unique=True, mssql_where=text("request_key IS NOT NULL")),
    )
    version_code: Mapped[str] = mapped_column(Unicode(20), unique=True)        # RSV-… is taken by 9B reservations → RSH-YYYY-NNNNNN
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    version_no: Mapped[int] = mapped_column(Integer)
    farmer_share_pct: Mapped[Decimal] = mapped_column(PCT)
    deduct_approved_costs: Mapped[bool] = mapped_column(Boolean)
    rounding_mode: Mapped[str] = mapped_column(Unicode(10))
    effective_from: Mapped[date] = mapped_column(Date)
    effective_to: Mapped[date | None] = mapped_column(Date)
    source_reference: Mapped[str] = mapped_column(Unicode(500))               # the agreement(s) / benefit-sharing document implemented
    notes: Mapped[str | None] = mapped_column(Unicode(2000))
    status: Mapped[str] = mapped_column(Unicode(12), default="DRAFT")
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(default=utcnow, server_default=text("SYSUTCDATETIME()"))
    submitted_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    approved_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    approved_at: Mapped[datetime | None]
    return_reason: Mapped[str | None] = mapped_column(Unicode(2000))
    request_key: Mapped[str | None] = mapped_column(Unicode(80))
    action_key: Mapped[str | None] = mapped_column(Unicode(80))
    environment: Mapped[str] = mapped_column(Unicode(10), default=Environment.LIVE.value)


class FarmAllocationVersion(UUIDPrimaryKey, Base):
    """The approved, versioned per-period allocation table (D12 B) that splits a project period's farmer share across farms; lines must
    total exactly 100 before submission. Author ≠ approver; approved versions immutable (trigger); a change is a new version."""
    __tablename__ = "farm_allocation_versions"
    __table_args__ = (
        CheckConstraint(in_check("status", CONFIG_STATUSES), name="status"),
        CheckConstraint(in_check("environment", Environment), name="environment"),
        CheckConstraint("approved_by IS NULL OR approved_by <> created_by", name="approval_sod"),
        CheckConstraint("status NOT IN ('APPROVED', 'SUPERSEDED') OR approved_by IS NOT NULL", name="approved"),
        Index("uq_farm_allocation_versions_no", "project_id", "monitoring_period_id", "version_no", unique=True),
        Index("uq_farm_allocation_versions_request_key", "request_key", unique=True, mssql_where=text("request_key IS NOT NULL")),
    )
    version_code: Mapped[str] = mapped_column(Unicode(20), unique=True)        # FAL-YYYY-NNNNNN
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    monitoring_period_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("monitoring_periods.id"))
    version_no: Mapped[int] = mapped_column(Integer)
    basis_reference: Mapped[str] = mapped_column(Unicode(500))                # how the shares were established (document / decision)
    status: Mapped[str] = mapped_column(Unicode(12), default="DRAFT")
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(default=utcnow, server_default=text("SYSUTCDATETIME()"))
    submitted_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    approved_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    approved_at: Mapped[datetime | None]
    return_reason: Mapped[str | None] = mapped_column(Unicode(2000))
    request_key: Mapped[str | None] = mapped_column(Unicode(80))
    action_key: Mapped[str | None] = mapped_column(Unicode(80))
    environment: Mapped[str] = mapped_column(Unicode(10), default=Environment.LIVE.value)


class FarmAllocationLine(UUIDPrimaryKey, Base):
    """One farm participation's share of the period's farmer share (paid to the participation's farmer). Immutable once submitted."""
    __tablename__ = "farm_allocation_lines"
    __table_args__ = (
        CheckConstraint("share_pct > 0 AND share_pct <= 100", name="share"),
        Index("uq_farm_allocation_lines_farm", "allocation_version_id", "project_farm_id", unique=True),
    )
    allocation_version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("farm_allocation_versions.id"), index=True)
    project_farm_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("project_farms.id"))
    farm_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("farms.id"))
    farmer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("farmers.id"))
    share_pct: Mapped[Decimal] = mapped_column(PCT)


class ProjectCost(UUIDPrimaryKey, Base):
    """A cost actually incurred by the project (category supplied by the recorder, evidence required). Deducted from revenue only when
    the approved revenue-share version says so. PENDING_APPROVAL → APPROVED / REJECTED (approver ≠ recorder); final states frozen."""
    __tablename__ = "project_costs"
    __table_args__ = (
        CheckConstraint(in_check("status", COST_STATUSES), name="status"),
        CheckConstraint(in_check("environment", Environment), name="environment"),
        CheckConstraint("amount <> 0", name="amount_nonzero"),
        CheckConstraint("approved_by IS NULL OR approved_by <> created_by", name="approval_sod"),
        CheckConstraint("status <> 'REJECTED' OR reject_reason IS NOT NULL", name="reject_reason"),
        CheckConstraint("LEN(currency) = 3", name="currency_code"),
        Index("uq_project_costs_request_key", "request_key", unique=True, mssql_where=text("request_key IS NOT NULL")),
    )
    cost_code: Mapped[str] = mapped_column(Unicode(20), unique=True)           # PCS-YYYY-NNNNNN
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    monitoring_period_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("monitoring_periods.id"))
    category: Mapped[str] = mapped_column(Unicode(60))
    description: Mapped[str] = mapped_column(Unicode(1000))
    amount: Mapped[Decimal] = mapped_column(MONEY)                             # a correction of an approved cost is a new negative cost
    currency: Mapped[str] = mapped_column(Unicode(3))
    incurred_on: Mapped[date] = mapped_column(Date)
    external_reference: Mapped[str | None] = mapped_column(Unicode(120))
    corrects_cost_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("project_costs.id"))
    status: Mapped[str] = mapped_column(Unicode(20), default="PENDING_APPROVAL")
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(default=utcnow, server_default=text("SYSUTCDATETIME()"))
    approved_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    approved_at: Mapped[datetime | None]
    reject_reason: Mapped[str | None] = mapped_column(Unicode(2000))
    request_key: Mapped[str | None] = mapped_column(Unicode(80))
    action_key: Mapped[str | None] = mapped_column(Unicode(80))
    environment: Mapped[str] = mapped_column(Unicode(10), default=Environment.LIVE.value)


class SettlementRun(UUIDPrimaryKey, Base):
    """One deterministic calculation for a project period in one currency with one approved revenue-share version and one approved
    allocation version. Inputs are frozen by link rows + SHA-256; an approved run is never recalculated — changed inputs need a new run."""
    __tablename__ = "settlement_runs"
    __table_args__ = (
        CheckConstraint(in_check("status", SETTLEMENT_STATUSES), name="status"),
        CheckConstraint(in_check("environment", Environment), name="environment"),
        CheckConstraint("approved_by IS NULL OR approved_by <> calculated_by", name="approval_sod"),
        CheckConstraint("status IN ('DRAFT', 'CANCELLED') OR input_sha256 IS NOT NULL", name="calculated"),
        CheckConstraint("LEN(currency) = 3", name="currency_code"),
        Index("uq_settlement_runs_request_key", "request_key", unique=True, mssql_where=text("request_key IS NOT NULL")),
    )
    run_code: Mapped[str] = mapped_column(Unicode(20), unique=True)            # SET-YYYY-NNNNNN
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"))       # the project organization (payer)
    monitoring_period_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("monitoring_periods.id"))
    currency: Mapped[str] = mapped_column(Unicode(3))
    revenue_share_version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("revenue_share_versions.id"))
    allocation_version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("farm_allocation_versions.id"))
    calculation_version: Mapped[str | None] = mapped_column(Unicode(20))
    gross_revenue: Mapped[Decimal | None] = mapped_column(MONEY)              # Σ included recognitions + reversals
    deducted_costs: Mapped[Decimal | None] = mapped_column(MONEY)
    distributable: Mapped[Decimal | None] = mapped_column(MONEY)
    farmer_total: Mapped[Decimal | None] = mapped_column(MONEY)               # Σ rounded entitlement lines
    developer_residual: Mapped[Decimal | None] = mapped_column(MONEY)         # distributable − farmer_total
    input_snapshot: Mapped[str | None] = mapped_column(UnicodeText)           # canonical JSON of every input
    input_sha256: Mapped[str | None] = mapped_column(Unicode(64))
    status: Mapped[str] = mapped_column(Unicode(20), default="DRAFT")
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(default=utcnow, server_default=text("SYSUTCDATETIME()"))
    calculated_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    calculated_at: Mapped[datetime | None]
    approved_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    approved_at: Mapped[datetime | None]
    close_reason: Mapped[str | None] = mapped_column(Unicode(2000))
    request_key: Mapped[str | None] = mapped_column(Unicode(80))
    action_key: Mapped[str | None] = mapped_column(Unicode(80))
    environment: Mapped[str] = mapped_column(Unicode(10), default=Environment.LIVE.value)


class SettlementRevenueItem(UUIDPrimaryKey, Base):
    """Freezes which revenue records a run includes. `active` drops to 0 only when the run is rejected / cancelled (trigger); a revenue
    record is in at most one active run (filtered unique index) — no duplicate settlement."""
    __tablename__ = "settlement_revenue_items"
    __table_args__ = (
        Index("uq_settlement_revenue_items_active", "revenue_record_id", unique=True, mssql_where=text("active = 1")),
    )
    settlement_run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("settlement_runs.id"), index=True)
    revenue_record_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("revenue_records.id"))
    amount: Mapped[Decimal] = mapped_column(MONEY)
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("1"))


class SettlementCostItem(UUIDPrimaryKey, Base):
    """Freezes which approved costs a run deducted (only when its revenue-share version deducts costs); at most one active run each."""
    __tablename__ = "settlement_cost_items"
    __table_args__ = (
        Index("uq_settlement_cost_items_active", "project_cost_id", unique=True, mssql_where=text("active = 1")),
    )
    settlement_run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("settlement_runs.id"), index=True)
    project_cost_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("project_costs.id"))
    amount: Mapped[Decimal] = mapped_column(MONEY)
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("1"))


class FarmerEntitlement(UUIDPrimaryKey, Base):
    """Append-only (trigger): one allocation line's calculated share in one run (rounded per the version's rounding mode)."""
    __tablename__ = "farmer_entitlements"
    __table_args__ = (
        Index("uq_farmer_entitlements_line", "settlement_run_id", "allocation_line_id", unique=True),
        Index("ix_farmer_entitlements_farmer", "farmer_id", "settlement_run_id"),
    )
    settlement_run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("settlement_runs.id"), index=True)
    allocation_line_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("farm_allocation_lines.id"))
    project_farm_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("project_farms.id"))
    farm_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("farms.id"))
    farmer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("farmers.id"))
    share_pct: Mapped[Decimal] = mapped_column(PCT)
    amount: Mapped[Decimal] = mapped_column(MONEY)
    currency: Mapped[str] = mapped_column(Unicode(3))
    created_at: Mapped[datetime] = mapped_column(default=utcnow, server_default=text("SYSUTCDATETIME()"))


class Payout(UUIDPrimaryKey, Base):
    """What one farmer is owed by one approved run (Σ that farmer's entitlement lines, > 0 — never typed by a client). Lifecycle D20;
    calculator ≠ approver ≠ executor (checks); a VERIFIED Phase 2 bank account is referenced (never copied, last 4 only)."""
    __tablename__ = "payouts"
    __table_args__ = (
        CheckConstraint(in_check("status", PAYOUT_STATUSES), name="status"),
        CheckConstraint(in_check("environment", Environment), name="environment"),
        CheckConstraint("amount > 0", name="amount_positive"),
        CheckConstraint("approved_by IS NULL OR approved_by <> calculated_by", name="approval_sod"),
        CheckConstraint("executed_by IS NULL OR approved_by IS NULL OR executed_by <> approved_by", name="execution_sod"),
        CheckConstraint("status NOT IN ('APPROVED', 'PAYMENT_PENDING', 'PAID', 'RECONCILED', 'UNCONFIRMED') OR bank_account_id IS NOT NULL",
                        name="bank_account"),
        CheckConstraint("status NOT IN ('PAID', 'RECONCILED') OR (external_reference IS NOT NULL AND executed_by IS NOT NULL)",
                        name="paid_evidence"),
        CheckConstraint("LEN(currency) = 3", name="currency_code"),
        Index("uq_payouts_open", "settlement_run_id", "farmer_id", unique=True,
              mssql_where=text("status IN ('CALCULATED', 'PENDING_APPROVAL', 'APPROVED', 'ON_HOLD', 'PAYMENT_PENDING', 'UNCONFIRMED', 'PAID', "
                               "'RECONCILED')")),
        Index("uq_payouts_external", "adapter_code", "external_reference", unique=True, mssql_where=text("external_reference IS NOT NULL")),
        Index("uq_payouts_request_key", "request_key", unique=True, mssql_where=text("request_key IS NOT NULL")),
    )
    payout_code: Mapped[str] = mapped_column(Unicode(20), unique=True)         # PYT-YYYY-NNNNNN
    settlement_run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("settlement_runs.id"), index=True)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"))       # payer (project organization)
    farmer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("farmers.id"), index=True)
    amount: Mapped[Decimal] = mapped_column(MONEY)
    currency: Mapped[str] = mapped_column(Unicode(3))
    status: Mapped[str] = mapped_column(Unicode(20), default="CALCULATED")
    adapter_code: Mapped[str] = mapped_column(Unicode(20), default="MANUAL")
    bank_account_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("farmer_bank_accounts.id"))
    bank_last4: Mapped[str | None] = mapped_column(Unicode(4))
    external_reference: Mapped[str | None] = mapped_column(Unicode(120))
    evidence_document_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("documents.id"))
    replaces_payout_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("payouts.id"))
    calculated_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    calculated_at: Mapped[datetime] = mapped_column(default=utcnow, server_default=text("SYSUTCDATETIME()"))
    approved_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    approved_at: Mapped[datetime | None]
    executed_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    paid_at: Mapped[datetime | None]
    reconciled_at: Mapped[datetime | None]
    reason: Mapped[str | None] = mapped_column(Unicode(2000))                 # rejection / cancellation / failure / hold reason
    request_key: Mapped[str | None] = mapped_column(Unicode(80))
    action_key: Mapped[str | None] = mapped_column(Unicode(80))
    environment: Mapped[str] = mapped_column(Unicode(10), default=Environment.LIVE.value)


class PayoutTransaction(UUIDPrimaryKey, Base):
    """Append-only (trigger): every execution step — initiated, paid (with evidence), failed, unconfirmed, provider status query."""
    __tablename__ = "payout_transactions"
    __table_args__ = (CheckConstraint(in_check("kind", TRANSACTION_KINDS), name="kind"),)
    payout_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("payouts.id"), index=True)
    kind: Mapped[str] = mapped_column(Unicode(20))
    adapter_code: Mapped[str] = mapped_column(Unicode(20))
    external_reference: Mapped[str | None] = mapped_column(Unicode(120))
    amount: Mapped[Decimal] = mapped_column(MONEY)
    currency: Mapped[str] = mapped_column(Unicode(3))
    evidence_document_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("documents.id"))
    note: Mapped[str | None] = mapped_column(Unicode(2000))
    actor_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(default=utcnow, server_default=text("SYSUTCDATETIME()"))


class PayoutReconciliation(UUIDPrimaryKey, Base):
    """Append-only (trigger): a bank / provider statement compared with the paid payout. MATCHED (amount, currency and reference agree)
    makes the payout RECONCILED; EXCEPTION leaves it PAID until a later MATCHED resolution. Reconciler ≠ executor (service)."""
    __tablename__ = "payout_reconciliations"
    __table_args__ = (CheckConstraint(in_check("result", RECONCILIATION_RESULTS), name="result"),)
    payout_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("payouts.id"), index=True)
    result: Mapped[str] = mapped_column(Unicode(10))
    statement_reference: Mapped[str] = mapped_column(Unicode(120))
    statement_amount: Mapped[Decimal] = mapped_column(MONEY)
    statement_currency: Mapped[str] = mapped_column(Unicode(3))
    statement_date: Mapped[date] = mapped_column(Date)
    evidence_document_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("documents.id"))
    note: Mapped[str | None] = mapped_column(Unicode(2000))
    reconciled_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(default=utcnow, server_default=text("SYSUTCDATETIME()"))


class PayoutAdjustment(UUIDPrimaryKey, Base):
    """A recovery case: a revenue reversal whose original revenue was already paid out. Never an automatic clawback — the case records
    the facts and is closed manually with a resolution (policy D29 stays a business decision)."""
    __tablename__ = "payout_adjustments"
    __table_args__ = (
        CheckConstraint(in_check("status", ADJUSTMENT_STATUSES), name="status"),
        CheckConstraint(in_check("environment", Environment), name="environment"),
        CheckConstraint("status <> 'CLOSED' OR (closed_by IS NOT NULL AND resolution IS NOT NULL)", name="closed"),
        Index("uq_payout_adjustments_reversal", "reversal_revenue_id", unique=True),
    )
    adjustment_code: Mapped[str] = mapped_column(Unicode(20), unique=True)     # ADJ-YYYY-NNNNNN
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"))
    reversal_revenue_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("revenue_records.id"))
    original_settlement_run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("settlement_runs.id"))
    amount: Mapped[Decimal] = mapped_column(MONEY)                             # the reversed gross revenue (negative)
    currency: Mapped[str] = mapped_column(Unicode(3))
    status: Mapped[str] = mapped_column(Unicode(10), default="OPEN")
    created_at: Mapped[datetime] = mapped_column(default=utcnow, server_default=text("SYSUTCDATETIME()"))
    closed_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    closed_at: Mapped[datetime | None]
    resolution: Mapped[str | None] = mapped_column(Unicode(2000))
    environment: Mapped[str] = mapped_column(Unicode(10), default=Environment.LIVE.value)
