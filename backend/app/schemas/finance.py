"""Phase 11 schemas — revenue, sharing configuration, costs, settlements, payouts. Request bodies forbid unknown fields. Money is Decimal
(never a float) with an ISO-4217 currency. No request carries a revenue amount, an entitlement, a payout amount or a settlement figure:
those are calculated by the server. The only typed amounts are a project cost actually incurred and a bank statement line."""
import uuid
from datetime import date
from decimal import Decimal
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.schemas.common import Reason, UtcDatetime
from app.schemas.lab import DocumentRef
from app.schemas.marketplace import Currency

Pct = Annotated[Decimal, Field(gt=0, le=100, max_digits=9, decimal_places=6)]
SignedMoney = Annotated[Decimal, Field(max_digits=19, decimal_places=4)]
StatementMoney = Annotated[Decimal, Field(ge=0, max_digits=19, decimal_places=4)]
Ref120 = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
Ref500 = Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=500)]
Note = Annotated[str, StringConstraints(strip_whitespace=True, max_length=2000)] | None


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ReasonIn(_Strict):
    reason: Reason


class OptionalReasonIn(_Strict):
    reason: Note = None


# ---------------------------------------------------------------- finance project picker
class PeriodRef(BaseModel):
    id: uuid.UUID
    period_number: int
    name: str
    start_date: date
    end_date: date


class ProjectFarmRef(BaseModel):
    project_farm_id: uuid.UUID
    farm_name: str | None
    farmer_name: str | None
    status: str


class FinanceProjectOut(BaseModel):
    id: uuid.UUID
    project_code: str
    name: str
    organization_id: uuid.UUID
    environment: str
    periods: list[PeriodRef]
    farms: list[ProjectFarmRef]


# ---------------------------------------------------------------- revenue
class RecognizeIn(_Strict):
    order_item_id: uuid.UUID


class ReverseRefundIn(_Strict):
    refund_id: uuid.UUID


class RevenueOut(BaseModel):
    id: uuid.UUID
    revenue_code: str
    kind: str
    amount: Decimal
    currency: str
    project_id: uuid.UUID
    monitoring_period_id: uuid.UUID
    order_code: str | None
    order_item_code: str | None
    payment_code: str | None
    transfer_code: str | None
    batch_code: str | None
    reverses_revenue_code: str | None
    refund_code: str | None
    seller_organization_id: uuid.UUID
    settled_in_run_code: str | None
    recorded_at: UtcDatetime
    environment: str


# ---------------------------------------------------------------- revenue-share versions and farm allocations
class ShareVersionIn(_Strict):
    project_id: uuid.UUID
    farmer_share_pct: Pct                                         # from the project's agreements — the platform has no default
    deduct_approved_costs: bool
    rounding_mode: Literal["HALF_UP", "HALF_EVEN", "DOWN"]
    effective_from: date
    effective_to: date | None = None
    source_reference: Ref500
    notes: Note = None


class ShareVersionOut(BaseModel):
    id: uuid.UUID
    version_code: str
    project_id: uuid.UUID
    version_no: int
    farmer_share_pct: Decimal
    deduct_approved_costs: bool
    rounding_mode: str
    effective_from: date
    effective_to: date | None
    source_reference: str
    notes: str | None
    status: str
    created_by_name: str | None
    approved_by_name: str | None
    approved_at: UtcDatetime | None
    return_reason: str | None
    created_at: UtcDatetime
    environment: str


class AllocationLineIn(_Strict):
    project_farm_id: uuid.UUID
    share_pct: Pct


class AllocationIn(_Strict):
    project_id: uuid.UUID
    monitoring_period_id: uuid.UUID
    basis_reference: Ref500
    lines: Annotated[list[AllocationLineIn], Field(min_length=1, max_length=5000)]


class AllocationLineOut(BaseModel):
    id: uuid.UUID
    project_farm_id: uuid.UUID
    farm_id: uuid.UUID
    farm_name: str | None
    farmer_id: uuid.UUID
    farmer_name: str | None
    share_pct: Decimal


class AllocationOut(BaseModel):
    id: uuid.UUID
    version_code: str
    project_id: uuid.UUID
    monitoring_period_id: uuid.UUID
    period_number: int | None
    version_no: int
    basis_reference: str
    status: str
    total_pct: Decimal
    lines: list[AllocationLineOut]
    created_by_name: str | None
    approved_by_name: str | None
    approved_at: UtcDatetime | None
    return_reason: str | None
    created_at: UtcDatetime
    environment: str


# ---------------------------------------------------------------- costs
class CostIn(_Strict):
    project_id: uuid.UUID
    monitoring_period_id: uuid.UUID | None = None
    category: Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=60)]
    description: Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=1000)]
    amount: SignedMoney                                           # negative only to correct an approved cost (corrects_cost_id)
    currency: Currency
    incurred_on: date
    external_reference: Annotated[str, StringConstraints(strip_whitespace=True, max_length=120)] | None = None
    corrects_cost_id: uuid.UUID | None = None


class CostOut(BaseModel):
    id: uuid.UUID
    cost_code: str
    project_id: uuid.UUID
    monitoring_period_id: uuid.UUID | None
    category: str
    description: str
    amount: Decimal
    currency: str
    incurred_on: date
    external_reference: str | None
    corrects_cost_id: uuid.UUID | None
    status: str
    created_by_name: str | None
    approved_by_name: str | None
    reject_reason: str | None
    settled_in_run_code: str | None
    documents: list[DocumentRef]
    created_at: UtcDatetime
    environment: str


# ---------------------------------------------------------------- settlements
class SettlementIn(_Strict):
    project_id: uuid.UUID
    monitoring_period_id: uuid.UUID
    currency: Currency
    revenue_share_version_id: uuid.UUID
    allocation_version_id: uuid.UUID


class EntitlementOut(BaseModel):
    id: uuid.UUID
    allocation_line_id: uuid.UUID
    project_farm_id: uuid.UUID
    farm_id: uuid.UUID
    farm_name: str | None
    farmer_id: uuid.UUID
    farmer_name: str | None
    share_pct: Decimal
    amount: Decimal
    currency: str


class SettlementOut(BaseModel):
    id: uuid.UUID
    run_code: str
    project_id: uuid.UUID
    project_code: str | None
    monitoring_period_id: uuid.UUID
    period_number: int | None
    currency: str
    revenue_share_version_code: str | None
    allocation_version_code: str | None
    calculation_version: str | None
    gross_revenue: Decimal | None
    deducted_costs: Decimal | None
    distributable: Decimal | None
    farmer_total: Decimal | None
    developer_residual: Decimal | None
    input_sha256: str | None
    status: str
    created_by_name: str | None
    calculated_by_name: str | None
    calculated_at: UtcDatetime | None
    approved_by_name: str | None
    approved_at: UtcDatetime | None
    close_reason: str | None
    revenue_count: int
    cost_count: int
    entitlements: list[EntitlementOut]
    created_at: UtcDatetime
    environment: str


class VerifyOut(BaseModel):
    run_code: str
    calculation_version: str | None
    input_sha256: str | None
    hash_ok: bool
    figures_ok: bool
    entitlements_ok: bool
    inputs_ok: bool
    reproducible: bool


# ---------------------------------------------------------------- payouts
class ConfirmPaidIn(_Strict):
    external_reference: Ref120
    document_id: uuid.UUID
    note: Note = None


class ReconcileIn(_Strict):
    statement_reference: Ref120
    statement_amount: StatementMoney
    statement_currency: Currency
    statement_date: date
    document_id: uuid.UUID
    note: Note = None


class TransactionOut(BaseModel):
    kind: str
    adapter_code: str
    external_reference: str | None
    amount: Decimal
    currency: str
    note: str | None
    actor_name: str | None
    created_at: UtcDatetime


class ReconciliationOut(BaseModel):
    id: uuid.UUID
    result: str
    statement_reference: str
    statement_amount: Decimal
    statement_currency: str
    statement_date: date
    note: str | None
    reconciled_by_name: str | None
    created_at: UtcDatetime


class PayoutOut(BaseModel):
    id: uuid.UUID
    payout_code: str
    settlement_run_id: uuid.UUID
    run_code: str | None
    farmer_id: uuid.UUID
    farmer_name: str | None
    amount: Decimal
    currency: str
    status: str
    adapter_code: str
    bank_last4: str | None                                        # never the account number
    external_reference: str | None
    replaces_payout_code: str | None
    reason: str | None
    calculated_by_name: str | None
    approved_by_name: str | None
    executed_by_name: str | None
    paid_at: UtcDatetime | None
    reconciled_at: UtcDatetime | None
    calculated_at: UtcDatetime
    transactions: list[TransactionOut]
    reconciliations: list[ReconciliationOut]
    documents: list[DocumentRef]
    environment: str


class MyPayoutOut(BaseModel):
    """Farmer self-service: own payouts only, no internal actor names or documents."""
    payout_code: str
    amount: Decimal
    currency: str
    status: str
    project_code: str | None
    period_number: int | None
    bank_last4: str | None
    paid_at: UtcDatetime | None
    reconciled_at: UtcDatetime | None
    calculated_at: UtcDatetime


class MyPayoutsOut(BaseModel):
    farmer_linked: bool
    payouts: list[MyPayoutOut]
    note: str | None


class AdjustmentOut(BaseModel):
    id: uuid.UUID
    adjustment_code: str
    project_id: uuid.UUID
    reversal_revenue_code: str | None
    original_run_code: str | None
    amount: Decimal
    currency: str
    status: str
    resolution: str | None
    closed_by_name: str | None
    closed_at: UtcDatetime | None
    created_at: UtcDatetime


class ResolutionIn(_Strict):
    resolution: Reason


class SummaryOut(BaseModel):
    revenue: list[dict[str, Any]]
    costs_by_category: list[dict[str, Any]]
    settlements: list[dict[str, Any]]
    payouts_by_status: list[dict[str, Any]]
    open_recovery_cases: int
    demo_note: str | None
