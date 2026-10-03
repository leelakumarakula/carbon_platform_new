"""Phase 10 schemas — marketplace. Request bodies forbid unknown fields. Carbon quantities are whole credits (int); money is Decimal (never a
float) with an ISO-4217 currency; no request carries an available, remaining, owned or sold quantity, a fee or a tax."""
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.schemas.common import Email, Reason, UtcDatetime
from app.schemas.lab import DocumentRef

Whole = Annotated[int, Field(gt=0, le=10**15)]
Money = Annotated[Decimal, Field(gt=0, max_digits=19, decimal_places=4)]
Currency = Annotated[str, StringConstraints(strip_whitespace=True, to_upper=True, pattern=r"^[A-Za-z]{3}$")]
Text200 = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
Opt120 = Annotated[str, StringConstraints(strip_whitespace=True, max_length=120)] | None


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ReasonIn(_Strict):
    reason: Reason


class OptionalReasonIn(_Strict):
    reason: Annotated[str, StringConstraints(strip_whitespace=True, max_length=2000)] | None = None


# ---------------------------------------------------------------- buyer profile / KYC
class BuyerProfileIn(_Strict):
    organization_id: uuid.UUID | None = None
    legal_name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=300)]
    registration_number: Annotated[str, StringConstraints(strip_whitespace=True, max_length=100)] | None = None
    country: Annotated[str, StringConstraints(strip_whitespace=True, to_upper=True, pattern=r"^[A-Za-z]{2}$")] | None = None
    contact_name: Annotated[str, StringConstraints(strip_whitespace=True, max_length=200)] | None = None
    contact_email: Email | None = None
    identifier_type: Annotated[str, StringConstraints(strip_whitespace=True, max_length=40)] | None = None
    identifier: Annotated[str, StringConstraints(strip_whitespace=True, min_length=4, max_length=60)] | None = None  # stored as last4 + hash


class OrgIn(_Strict):
    organization_id: uuid.UUID | None = None


class ReviewIn(_Strict):
    note: Annotated[str, StringConstraints(strip_whitespace=True, max_length=2000)] | None = None


class KycReviewOut(BaseModel):
    action: str
    actor_name: str | None
    note: str | None
    created_at: datetime


class BuyerProfileOut(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    organization_name: str | None
    organization_code: str | None
    status: str
    legal_name: str
    registration_number: str | None
    country: str | None
    contact_name: str | None
    contact_email: str | None
    identifier_type: str | None
    identifier_last4: str | None
    submitted_by_name: str | None
    submitted_at: datetime | None
    verified_by_name: str | None
    verified_at: datetime | None
    return_reason: str | None
    suspension_reason: str | None
    documents: list[DocumentRef]
    reviews: list[KycReviewOut]
    environment: str
    can_edit: bool
    can_review: bool


class BuyerProfileView(BaseModel):
    organization_id: uuid.UUID | None
    organization_name: str | None
    profile: BuyerProfileOut | None
    note: str


# ---------------------------------------------------------------- listings
class ListingIn(_Strict):
    seller_organization_id: uuid.UUID
    batch_id: uuid.UUID
    serial_range_id: uuid.UUID | None = None
    title: Text200
    listed_quantity: Whole
    unit_price: Money
    currency: Currency
    min_quantity: Whole | None = None
    max_quantity: Whole | None = None
    payment_window_hours: Annotated[int, Field(ge=1, le=720)]
    valid_until: UtcDatetime | None = None
    co_benefits: Annotated[str, StringConstraints(strip_whitespace=True, max_length=2000)] | None = None


class ListingOut(BaseModel):
    id: uuid.UUID
    listing_code: str
    title: str
    seller_organization_id: uuid.UUID
    seller_name: str | None
    batch_id: uuid.UUID
    batch_code: str | None
    serial_range_id: uuid.UUID | None
    listed_quantity: int
    remaining_quantity: int                     # derived: listed − committed order items
    available_quantity: int                     # derived: min(remaining, seller's 9B AVAILABLE) — 0 unless ACTIVE
    unit_price: Decimal
    currency: str
    min_quantity: int | None
    max_quantity: int | None
    payment_window_hours: int
    valid_until: datetime | None
    co_benefits: str | None
    disclosure: dict[str, Any]
    disclosure_sha256: str | None
    status: str
    created_by_name: str | None
    approved_by_name: str | None
    approved_at: datetime | None
    close_reason: str | None
    documents: list[DocumentRef]
    environment: str
    seller_side: bool
    can_manage: bool
    can_approve: bool


class ListingsOut(BaseModel):
    listings: list[ListingOut]
    demo_note: str | None
    note: str


# ---------------------------------------------------------------- orders
class OrderItemIn(_Strict):
    listing_id: uuid.UUID
    quantity: Whole


class OrderIn(_Strict):
    buyer_organization_id: uuid.UUID
    items: Annotated[list[OrderItemIn], Field(min_length=1, max_length=50)]
    transfer_kind: Literal["INTERNAL", "REGISTRY"] = "INTERNAL"
    recipient_registry_account: Opt120 = None


class OrderItemOut(BaseModel):
    id: uuid.UUID
    item_code: str
    listing_id: uuid.UUID
    listing_code: str | None
    batch_id: uuid.UUID
    batch_code: str | None
    vintage: str | None
    project_code: str | None
    quantity: int
    unit_price: Decimal
    line_total: Decimal
    status: str
    reservation_code: str | None
    reservation_status: str | None
    transfer_id: uuid.UUID | None
    transfer_code: str | None
    transfer_status: str | None
    can_complete: bool


class PaymentOut(BaseModel):
    id: uuid.UUID
    payment_code: str
    order_id: uuid.UUID
    order_code: str | None
    adapter_code: str
    amount: Decimal
    currency: str
    status: str
    external_reference: str | None
    evidence_document_id: uuid.UUID | None
    recorded_by_name: str | None
    recorded_at: datetime
    confirmed_by_name: str | None
    confirmed_at: datetime | None
    reject_reason: str | None
    payer_name: str | None
    payee_name: str | None
    can_confirm: bool
    can_refund: bool


class RefundOut(BaseModel):
    id: uuid.UUID
    refund_code: str
    payment_id: uuid.UUID
    payment_code: str | None
    order_id: uuid.UUID
    order_code: str | None
    amount: Decimal
    currency: str
    after_transfer: bool
    reason: str
    status: str
    requested_by_name: str | None
    approved_by_name: str | None
    completed_at: datetime | None
    external_reference: str | None
    reject_reason: str | None
    can_approve: bool
    can_complete: bool


class OrderOut(BaseModel):
    id: uuid.UUID
    order_code: str
    buyer_organization_id: uuid.UUID
    buyer_name: str | None
    seller_organization_id: uuid.UUID
    seller_name: str | None
    currency: str
    subtotal: Decimal
    total: Decimal
    status: str
    transfer_kind: str
    recipient_registry_account: str | None
    expires_at: datetime
    placed_at: datetime
    paid_at: datetime | None
    completed_at: datetime | None
    close_reason: str | None
    attention_reason: str | None
    items: list[OrderItemOut]
    payments: list[PaymentOut]
    refunds: list[RefundOut]
    documents: list[DocumentRef]
    environment: str
    viewer_side: str
    can_cancel: bool
    can_pay: bool
    can_retry: bool


class OrderListOut(BaseModel):
    orders: list[OrderOut]
    demo_note: str | None


# ---------------------------------------------------------------- payments / refunds
class PaymentIn(_Strict):
    order_id: uuid.UUID
    amount: Money
    currency: Currency
    external_reference: Opt120 = None
    document_id: uuid.UUID                    # PAYMENT_EVIDENCE attached to the order
    note: Annotated[str, StringConstraints(strip_whitespace=True, max_length=2000)] | None = None


class RefundCompleteIn(_Strict):
    external_reference: Opt120 = None
    document_id: uuid.UUID | None = None      # REFUND_EVIDENCE attached to the refund (manual refunds)


class TransferCompleteIn(_Strict):
    registry_transfer_reference: Opt120 = None
    document_id: uuid.UUID | None = None


class LineageOut(BaseModel):
    chain: list[dict[str, Any]]


