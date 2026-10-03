"""Phase 9B schemas — credit ledger. Request bodies forbid unknown fields and carry only MOVEMENT quantities (whole units): no balance
(available / owned / transferred / retired), no calculated or VVB-verified quantity is ever accepted."""
import uuid
from datetime import date, datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.schemas.common import Reason, UtcDatetime

LEDGER_NOTE = "Ledger quantities derive from registry-issued credits only. Not a marketplace: no price, order or payment."
DEMO_NOTE = "DEMO — no registry-issued credits"
Whole = Annotated[int, Field(gt=0, le=10**15)]
Ref = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
Serial = Annotated[str, StringConstraints(min_length=1, max_length=200)]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ReasonIn(_Strict):
    reason: Reason


class NoteIn(_Strict):
    note: Reason


class ReservationIn(_Strict):
    batch_id: uuid.UUID
    owner_organization_id: uuid.UUID
    quantity: Whole
    purpose: Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=200)]
    purpose_reference: Annotated[str, StringConstraints(strip_whitespace=True, max_length=120)] | None = None
    recipient_organization_id: uuid.UUID | None = None
    serial_range_id: uuid.UUID | None = None
    expires_at: datetime


class TransferIn(_Strict):
    kind: Literal["INTERNAL", "REGISTRY"]
    batch_id: uuid.UUID
    sender_organization_id: uuid.UUID
    recipient_organization_id: uuid.UUID
    quantity: Whole | None = None                   # or the whole reservation
    reservation_id: uuid.UUID | None = None
    serial_range_id: uuid.UUID | None = None
    recipient_external_account_id: Ref | None = None   # REGISTRY: the recipient's registry account, as the registry identifies it
    purpose: Annotated[str, StringConstraints(strip_whitespace=True, max_length=200)] | None = None
    purpose_reference: Annotated[str, StringConstraints(strip_whitespace=True, max_length=120)] | None = None


class TransferCompleteIn(_Strict):
    registry_transfer_reference: Ref | None = None  # REGISTRY only
    document_id: uuid.UUID | None = None            # REGISTRY_TRANSFER_EVIDENCE (REGISTRY only)


class RetirementIn(_Strict):
    batch_id: uuid.UUID
    owner_organization_id: uuid.UUID
    quantity: Whole | None = None
    reservation_id: uuid.UUID | None = None
    serial_range_id: uuid.UUID | None = None
    beneficiary: Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=300)]
    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=2000)]


class RetiredSerial(_Strict):
    serial_start: Serial | None = None
    serial_end: Serial | None = None
    quantity: Whole


class RetireIn(_Strict):
    registry_retirement_reference: Ref
    retirement_date: date
    document_id: uuid.UUID                           # RETIREMENT_CERTIFICATE
    retired_serials: list[RetiredSerial] | None = Field(default=None, max_length=200)


class ReconcileLine(_Strict):
    batch_id: uuid.UUID
    registry_stated_quantity: Annotated[int, Field(ge=0, le=10**15)]


class ReconcileIn(_Strict):
    document_id: uuid.UUID                           # REGISTRY_RESPONSE statement attached to the registry account
    lines: list[ReconcileLine] = Field(max_length=500)
    note: Annotated[str, StringConstraints(strip_whitespace=True, max_length=2000)] | None = None


# ---------------------------------------------------------------- responses
class PositionOut(BaseModel):
    id: uuid.UUID
    batch_id: uuid.UUID
    batch_code: str | None
    serial_range_id: uuid.UUID
    registry_range: str
    owner_organization_id: uuid.UUID
    owner_name: str | None
    holding_external_account_id: str
    state: str
    status: str
    quantity: int
    sub_range: str | None
    parsed: bool
    reservation_id: uuid.UUID | None
    transfer_id: uuid.UUID | None
    retirement_id: uuid.UUID | None
    created_by_entry_id: uuid.UUID
    consumed_by_entry_id: uuid.UUID | None
    created_at: UtcDatetime


class Balance(BaseModel):
    owner_organization_id: uuid.UUID
    owner_name: str | None
    available: int
    reserved: int
    pending_transfer: int
    pending_retirement: int
    retired: int
    transferred_out: int


class OpeningOut(BaseModel):
    id: uuid.UUID
    opening_code: str
    batch_id: uuid.UUID
    owner_organization_id: uuid.UUID
    status: str
    requested_by_name: str | None
    requested_at: UtcDatetime
    confirmed_by_name: str | None
    confirmed_at: UtcDatetime | None
    cancel_reason: str | None
    can_confirm: bool


class InventoryBatch(BaseModel):
    batch_id: uuid.UUID
    batch_code: str
    project_id: uuid.UUID
    project_code: str | None
    period_number: int | None
    vintage: str
    unit: str
    registry_name: str | None
    batch_status: str
    issued: int
    opening: OpeningOut | None
    balances: list[Balance]
    environment: str


class InventoryOut(BaseModel):
    batches: list[InventoryBatch]
    note: str = LEDGER_NOTE
    demo_note: str | None


class EntryOut(BaseModel):
    id: uuid.UUID
    entry_code: str
    entry_type: str
    batch_id: uuid.UUID
    organization_id: uuid.UUID
    counterparty_organization_id: uuid.UUID | None
    quantity: int
    actor_name: str | None
    confirmed_by_name: str | None
    reason: str | None
    created_at: UtcDatetime
    inputs: list[PositionOut]
    outputs: list[PositionOut]


class ReservationOut(BaseModel):
    id: uuid.UUID
    reservation_code: str
    batch_id: uuid.UUID
    batch_code: str | None
    owner_organization_id: uuid.UUID
    recipient_organization_id: uuid.UUID | None
    purpose: str
    purpose_reference: str | None
    quantity: int
    expires_at: UtcDatetime
    status: str
    created_by_name: str | None
    created_at: UtcDatetime
    release_reason: str | None
    closed_at: UtcDatetime | None
    order_code: str | None = None               # Phase 10: an order-linked reservation is released through the order


class TransferOut(BaseModel):
    id: uuid.UUID
    transfer_code: str
    kind: str
    batch_id: uuid.UUID
    batch_code: str | None
    sender_organization_id: uuid.UUID
    sender_name: str | None
    recipient_organization_id: uuid.UUID
    recipient_name: str | None
    recipient_external_account_id: str | None
    quantity: int
    purpose: str | None
    purpose_reference: str | None
    reservation_id: uuid.UUID | None
    status: str
    requested_by_name: str | None
    requested_at: UtcDatetime
    completed_by_name: str | None
    completed_at: UtcDatetime | None
    registry_transfer_reference: str | None
    evidence_document_id: uuid.UUID | None
    close_reason: str | None
    completion_entry_id: uuid.UUID | None
    can_complete: bool
    order_code: str | None = None               # Phase 10: an order-linked transfer is completed / rejected through the order


class RetirementOut(BaseModel):
    id: uuid.UUID
    retirement_code: str
    batch_id: uuid.UUID
    batch_code: str | None
    owner_organization_id: uuid.UUID
    owner_name: str | None
    quantity: int
    beneficiary: str
    reason: str
    status: str
    requested_by_name: str | None
    requested_at: UtcDatetime
    retired_by_name: str | None
    retired_at: UtcDatetime | None
    registry_retirement_reference: str | None
    retirement_date: date | None
    certificate_document_id: uuid.UUID | None
    retired_serials: list[dict[str, Any]] | None
    close_reason: str | None
    can_retire: bool


class ReversalOut(BaseModel):
    id: uuid.UUID
    reversal_code: str
    reversed_entry_id: uuid.UUID
    batch_id: uuid.UUID
    reason: str
    status: str
    requested_by_name: str | None
    decided_by_name: str | None
    decision_note: str | None
    entry_id: uuid.UUID | None


class HoldingOut(BaseModel):
    """Holder (e.g. buyer) view — allow-listed: no farmer, farm, GPS, KYC, bank, agreement, audit or other-holder data."""
    position_id: uuid.UUID
    batch_id: uuid.UUID
    batch_code: str
    owner_organization_id: uuid.UUID
    state: str
    quantity: int
    project_code: str | None
    project_name: str | None
    period_number: int | None
    vintage: str
    methodology: str | None
    standard: str | None
    registry_name: str | None
    issuance_code: str | None
    external_issuance_id: str | None
    registry_range: str
    sub_range: str | None
    environment: str


class HoldingsOut(BaseModel):
    holdings: list[HoldingOut]
    demo_note: str | None
    note: str = LEDGER_NOTE


class ReconcileOut(BaseModel):
    event_id: uuid.UUID
    event_type: str
    note: str | None
    occurred_at: UtcDatetime


class RecipientOut(BaseModel):
    id: uuid.UUID
    code: str
    name: str
    org_type: str
