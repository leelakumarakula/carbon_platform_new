"""Phase 10 — marketplace: buyer profiles and KYC, listings, orders, payments, refunds (locked decisions D1–D36).

The Phase 9B credit ledger stays the ONLY source of credit ownership and availability (D24): nothing here stores an available, remaining,
owned or sold quantity. A listing has an immutable commercial cap (`listed_quantity`); what remains of it is derived from order items under
a lock, and what can actually be bought is further limited by the seller's derived 9B AVAILABLE positions. Order items only reference the
9B batch / serial range / reservation / transfer. Money (Numeric(19,4), one ISO-4217 currency) and carbon (whole credits, Numeric(28,0))
never share a column or a calculation. No fee, tax, commission, revenue or payout exists in Phase 10 (D9, D10, D34).
"""
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Index, Integer, Numeric, Unicode, UnicodeText, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, Environment, Timestamped, UUIDPrimaryKey, in_check, utcnow

BUYER_PROFILE_STATUSES = ["DRAFT", "KYC_SUBMITTED", "KYC_VERIFIED", "KYC_RETURNED", "SUSPENDED"]
KYC_REVIEW_ACTIONS = ["SUBMITTED", "VERIFIED", "RETURNED", "SUSPENDED", "REINSTATED"]
LISTING_STATUSES = ["DRAFT", "PENDING_APPROVAL", "ACTIVE", "PAUSED", "CLOSED", "EXPIRED", "CANCELLED"]
ORDER_STATUSES = ["PLACED", "PAID", "TRANSFER_PENDING", "COMPLETED", "CANCELLED", "EXPIRED", "ATTENTION_REQUIRED", "REFUND_PENDING",
                  "REFUNDED"]
ORDER_ITEM_STATUSES = ["RESERVED", "TRANSFER_PENDING", "DELIVERED", "FAILED", "RELEASED", "EXPIRED"]
TRANSFER_KINDS = ["INTERNAL", "REGISTRY"]
PAYMENT_STATUSES = ["CREATED", "PENDING", "UNCONFIRMED", "PENDING_CONFIRMATION", "CONFIRMED", "REJECTED", "FAILED", "UNMATCHED",
                    "REFUNDED"]
PAYMENT_EVENT_OUTCOMES = ["APPLIED", "UNMATCHED", "IGNORED"]
REFUND_STATUSES = ["REQUESTED", "APPROVED", "COMPLETED", "REJECTED"]
MONEY = Numeric(19, 4)
CREDITS = Numeric(28, 0)


class BuyerProfile(UUIDPrimaryKey, Timestamped, Base):
    """Organization-level buyer profile and KYC state (D1, D2). One per BUYER organization; onboarding stays with the Platform Admin."""
    __tablename__ = "buyer_profiles"
    __table_args__ = (
        CheckConstraint(in_check("status", BUYER_PROFILE_STATUSES), name="status"),
        CheckConstraint(in_check("environment", Environment), name="environment"),
        CheckConstraint("verified_by IS NULL OR submitted_by IS NULL OR verified_by <> submitted_by", name="kyc_sod"),
        CheckConstraint("(identifier_type IS NULL AND identifier_last4 IS NULL AND identifier_hash IS NULL) OR "
                        "(identifier_type IS NOT NULL AND identifier_last4 IS NOT NULL AND identifier_hash IS NOT NULL)", name="identifier"),
        Index("uq_buyer_profiles_request_key", "request_key", unique=True, mssql_where=text("request_key IS NOT NULL")),
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), unique=True)
    status: Mapped[str] = mapped_column(Unicode(15), default="DRAFT")
    legal_name: Mapped[str] = mapped_column(Unicode(300))
    registration_number: Mapped[str | None] = mapped_column(Unicode(100))
    country: Mapped[str | None] = mapped_column(Unicode(2))
    contact_name: Mapped[str | None] = mapped_column(Unicode(200))
    contact_email: Mapped[str | None] = mapped_column(Unicode(320))
    # an optional business identifier: never stored in clear (type + last 4 + keyed fingerprint, as for farmer KYC)
    identifier_type: Mapped[str | None] = mapped_column(Unicode(40))
    identifier_last4: Mapped[str | None] = mapped_column(Unicode(4))
    identifier_hash: Mapped[str | None] = mapped_column(Unicode(64))
    submitted_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    submitted_at: Mapped[datetime | None]
    verified_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    verified_at: Mapped[datetime | None]
    return_reason: Mapped[str | None] = mapped_column(Unicode(2000))
    suspension_reason: Mapped[str | None] = mapped_column(Unicode(2000))
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    request_key: Mapped[str | None] = mapped_column(Unicode(80))
    action_key: Mapped[str | None] = mapped_column(Unicode(80))               # Idempotency-Key of the last state change
    environment: Mapped[str] = mapped_column(Unicode(10), default=Environment.LIVE.value)


class BuyerKycReview(UUIDPrimaryKey, Base):
    """Append-only KYC history (trigger): every submission and review decision."""
    __tablename__ = "buyer_kyc_reviews"
    __table_args__ = (CheckConstraint(in_check("action", KYC_REVIEW_ACTIONS), name="action"),)
    buyer_profile_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("buyer_profiles.id"), index=True)
    action: Mapped[str] = mapped_column(Unicode(12))
    actor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    note: Mapped[str | None] = mapped_column(Unicode(2000))
    document_ids: Mapped[str | None] = mapped_column(UnicodeText)            # JSON list of the BUYER_KYC_DOCUMENT ids reviewed
    created_at: Mapped[datetime] = mapped_column(default=utcnow, server_default=text("SYSUTCDATETIME()"))


class MarketplaceListing(UUIDPrimaryKey, Timestamped, Base):
    """A seller's fixed-price offer of credits of ONE 9B batch (optionally one serial range). `listed_quantity` is an immutable commercial
    cap; nothing is reserved when listing (D6). Commercial terms are frozen once approved (trigger)."""
    __tablename__ = "marketplace_listings"
    __table_args__ = (
        CheckConstraint(in_check("status", LISTING_STATUSES), name="status"),
        CheckConstraint(in_check("environment", Environment), name="environment"),
        CheckConstraint("listed_quantity > 0", name="listed_quantity_positive"),
        CheckConstraint("unit_price > 0", name="unit_price_positive"),
        CheckConstraint("min_quantity IS NULL OR min_quantity > 0", name="min_quantity_positive"),
        CheckConstraint("max_quantity IS NULL OR max_quantity >= COALESCE(min_quantity, 1)", name="max_quantity"),
        CheckConstraint("payment_window_hours BETWEEN 1 AND 720", name="payment_window"),
        CheckConstraint("approved_by IS NULL OR approved_by <> created_by", name="approval_sod"),
        CheckConstraint("status NOT IN ('ACTIVE', 'PAUSED', 'CLOSED', 'EXPIRED') OR (approved_by IS NOT NULL AND disclosure_sha256 IS NOT NULL)",
                        name="approved"),
        CheckConstraint("disclosure IS NULL OR ISJSON(disclosure) = 1", name="disclosure_json"),
        CheckConstraint("LEN(currency) = 3", name="currency_code"),
        Index("uq_marketplace_listings_open", "seller_organization_id", "batch_id", "serial_range_id", unique=True,
              mssql_where=text("status IN ('ACTIVE', 'PAUSED')")),
        Index("uq_marketplace_listings_request_key", "request_key", unique=True, mssql_where=text("request_key IS NOT NULL")),
    )
    listing_code: Mapped[str] = mapped_column(Unicode(20), unique=True)       # LST-YYYY-NNNNNN
    seller_organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), index=True)
    batch_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("credit_batches.id"), index=True)
    serial_range_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("credit_serial_ranges.id"))
    title: Mapped[str] = mapped_column(Unicode(200))
    listed_quantity: Mapped[Decimal] = mapped_column(CREDITS)                  # immutable commercial cap (whole credits)
    unit_price: Mapped[Decimal] = mapped_column(MONEY)                         # per registry-issued credit
    currency: Mapped[str] = mapped_column(Unicode(3))                          # ISO 4217
    min_quantity: Mapped[Decimal | None] = mapped_column(CREDITS)
    max_quantity: Mapped[Decimal | None] = mapped_column(CREDITS)
    payment_window_hours: Mapped[int] = mapped_column(Integer)                 # seller's hold: an order's reservations expire after this
    valid_until: Mapped[datetime | None]
    co_benefits: Mapped[str | None] = mapped_column(Unicode(2000))             # seller-stated text (spec §25), shown verbatim
    disclosure: Mapped[str | None] = mapped_column(UnicodeText)                # allow-listed snapshot frozen at approval (JSON)
    disclosure_sha256: Mapped[str | None] = mapped_column(Unicode(64))
    status: Mapped[str] = mapped_column(Unicode(20), default="DRAFT")
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    submitted_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    submitted_at: Mapped[datetime | None]
    approved_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    approved_at: Mapped[datetime | None]
    closed_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    closed_at: Mapped[datetime | None]
    close_reason: Mapped[str | None] = mapped_column(Unicode(2000))
    request_key: Mapped[str | None] = mapped_column(Unicode(80))
    action_key: Mapped[str | None] = mapped_column(Unicode(80))               # Idempotency-Key of the last state change
    environment: Mapped[str] = mapped_column(Unicode(10), default=Environment.LIVE.value)


class ListingDocument(UUIDPrimaryKey, Base):
    """A document the seller published on a listing (visible to buyers). Restricted categories are refused."""
    __tablename__ = "listing_documents"
    listing_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("marketplace_listings.id"), index=True)
    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("documents.id"), unique=True)
    published_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(default=utcnow, server_default=text("SYSUTCDATETIME()"))


class Order(UUIDPrimaryKey, Timestamped, Base):
    """One buyer, one seller, one currency (D12). Gross amounts only — no fee or tax line (D9, D10)."""
    __tablename__ = "orders"
    __table_args__ = (
        CheckConstraint(in_check("status", ORDER_STATUSES), name="status"),
        CheckConstraint(in_check("transfer_kind", TRANSFER_KINDS), name="transfer_kind"),
        CheckConstraint(in_check("environment", Environment), name="environment"),
        CheckConstraint("buyer_organization_id <> seller_organization_id", name="distinct_parties"),
        CheckConstraint("subtotal > 0 AND total = subtotal", name="total"),
        CheckConstraint("transfer_kind <> 'REGISTRY' OR recipient_registry_account IS NOT NULL", name="registry_account"),
        CheckConstraint("LEN(currency) = 3", name="currency_code"),
        Index("uq_orders_request_key", "request_key", unique=True, mssql_where=text("request_key IS NOT NULL")),
        Index("ix_orders_parties", "buyer_organization_id", "seller_organization_id", "status"),
    )
    order_code: Mapped[str] = mapped_column(Unicode(20), unique=True)         # ORD-YYYY-NNNNNN
    buyer_organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"))
    seller_organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"))
    currency: Mapped[str] = mapped_column(Unicode(3))
    subtotal: Mapped[Decimal] = mapped_column(MONEY)
    total: Mapped[Decimal] = mapped_column(MONEY)                              # = subtotal (no fee, no tax in Phase 10)
    transfer_kind: Mapped[str] = mapped_column(Unicode(10), default="INTERNAL")
    recipient_registry_account: Mapped[str | None] = mapped_column(Unicode(120))   # REGISTRY: the buyer's account as the registry knows it
    status: Mapped[str] = mapped_column(Unicode(20), default="PLACED")
    expires_at: Mapped[datetime]                                               # payment deadline = the item reservations' expiry
    placed_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    placed_at: Mapped[datetime] = mapped_column(default=utcnow, server_default=text("SYSUTCDATETIME()"))
    paid_at: Mapped[datetime | None]
    completed_at: Mapped[datetime | None]
    closed_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    closed_at: Mapped[datetime | None]
    close_reason: Mapped[str | None] = mapped_column(Unicode(2000))           # cancellation / expiry / refund
    attention_reason: Mapped[str | None] = mapped_column(Unicode(2000))
    request_key: Mapped[str | None] = mapped_column(Unicode(80))
    action_key: Mapped[str | None] = mapped_column(Unicode(80))               # Idempotency-Key of the last state change
    environment: Mapped[str] = mapped_column(Unicode(10), default=Environment.LIVE.value)


class OrderItem(UUIDPrimaryKey, Base):
    """One listing → one 9B batch (+ optional serial range) → its own 9B reservation, later its own 9B transfer (D13). Price and quantity
    are immutable (trigger); only the status and the 9B links change."""
    __tablename__ = "order_items"
    __table_args__ = (
        CheckConstraint(in_check("status", ORDER_ITEM_STATUSES), name="status"),
        CheckConstraint("quantity > 0", name="quantity_positive"),
        CheckConstraint("unit_price > 0 AND line_total = unit_price * quantity", name="line_total"),
        Index("uq_order_items_reservation", "reservation_id", unique=True, mssql_where=text("reservation_id IS NOT NULL")),
        Index("uq_order_items_transfer", "transfer_id", unique=True, mssql_where=text("transfer_id IS NOT NULL")),
        Index("ix_order_items_listing", "listing_id", "status"),
    )
    item_code: Mapped[str] = mapped_column(Unicode(30), unique=True)          # ORD-YYYY-NNNNNN-n
    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orders.id"), index=True)
    listing_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("marketplace_listings.id"))
    batch_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("credit_batches.id"))
    serial_range_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("credit_serial_ranges.id"))
    quantity: Mapped[Decimal] = mapped_column(CREDITS)
    unit_price: Mapped[Decimal] = mapped_column(MONEY)
    line_total: Mapped[Decimal] = mapped_column(MONEY)
    reservation_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("credit_reservations.id"))   # the current 9B reservation
    transfer_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("credit_transfers.id"))         # the current 9B transfer
    status: Mapped[str] = mapped_column(Unicode(20), default="RESERVED")


class Payment(UUIDPrimaryKey, Timestamped, Base):
    """A buyer payment towards one order. MANUAL (evidence + seller-finance confirmation) is the only runtime adapter (D15, D33); the amount
    must equal the order total in the same currency (no partial payment). Final states are immutable (trigger)."""
    __tablename__ = "payments"
    __table_args__ = (
        CheckConstraint(in_check("status", PAYMENT_STATUSES), name="status"),
        CheckConstraint(in_check("environment", Environment), name="environment"),
        CheckConstraint("amount > 0", name="amount_positive"),
        CheckConstraint("confirmed_by IS NULL OR confirmed_by <> recorded_by", name="dual_control"),
        CheckConstraint("adapter_code <> 'MANUAL' OR status IN ('PENDING_CONFIRMATION', 'CONFIRMED', 'REJECTED', 'UNMATCHED', 'REFUNDED')",
                        name="manual_states"),
        CheckConstraint("status <> 'CONFIRMED' OR confirmed_by IS NOT NULL", name="confirmed"),
        CheckConstraint("LEN(currency) = 3", name="currency_code"),
        Index("uq_payments_open", "order_id", unique=True,
              mssql_where=text("status IN ('CREATED', 'PENDING', 'UNCONFIRMED', 'PENDING_CONFIRMATION', 'CONFIRMED')")),
        Index("uq_payments_external", "adapter_code", "external_reference", unique=True, mssql_where=text("external_reference IS NOT NULL")),
        Index("uq_payments_request_key", "request_key", unique=True, mssql_where=text("request_key IS NOT NULL")),
    )
    payment_code: Mapped[str] = mapped_column(Unicode(20), unique=True)       # PAY-YYYY-NNNNNN
    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orders.id"), index=True)
    payee_organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"))     # the seller (D16)
    payer_organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"))
    adapter_code: Mapped[str] = mapped_column(Unicode(20))
    amount: Mapped[Decimal] = mapped_column(MONEY)
    currency: Mapped[str] = mapped_column(Unicode(3))
    status: Mapped[str] = mapped_column(Unicode(25))
    external_reference: Mapped[str | None] = mapped_column(Unicode(120))     # bank / provider reference
    evidence_document_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("documents.id"))
    recorded_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    confirmed_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    confirmed_at: Mapped[datetime | None]
    rejected_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    rejected_at: Mapped[datetime | None]
    reject_reason: Mapped[str | None] = mapped_column(Unicode(2000))
    note: Mapped[str | None] = mapped_column(Unicode(2000))
    request_key: Mapped[str | None] = mapped_column(Unicode(80))
    action_key: Mapped[str | None] = mapped_column(Unicode(80))               # Idempotency-Key of the last state change
    environment: Mapped[str] = mapped_column(Unicode(10), default=Environment.LIVE.value)


class PaymentEvent(UUIDPrimaryKey, Base):
    """Append-only provider events (trigger); (provider, external event id) is unique, so a duplicate can never be applied twice. Only the
    payload's SHA-256 is kept — never raw card or account data."""
    __tablename__ = "payment_events"
    __table_args__ = (
        CheckConstraint(in_check("outcome", PAYMENT_EVENT_OUTCOMES), name="outcome"),
        Index("uq_payment_events_external", "provider", "external_event_id", unique=True),
    )
    payment_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("payments.id"), index=True)
    provider: Mapped[str] = mapped_column(Unicode(20))
    external_event_id: Mapped[str] = mapped_column(Unicode(120))
    external_payment_id: Mapped[str | None] = mapped_column(Unicode(120))
    event_type: Mapped[str] = mapped_column(Unicode(30))
    payload_sha256: Mapped[str] = mapped_column(Unicode(64))
    outcome: Mapped[str] = mapped_column(Unicode(10))
    note: Mapped[str | None] = mapped_column(Unicode(2000))
    received_at: Mapped[datetime] = mapped_column(default=utcnow, server_default=text("SYSUTCDATETIME()"))


class Refund(UUIDPrimaryKey, Timestamped, Base):
    """Money only — a refund never changes a carbon quantity or ownership (D19). Requested and approved by different people."""
    __tablename__ = "refunds"
    __table_args__ = (
        CheckConstraint(in_check("status", REFUND_STATUSES), name="status"),
        CheckConstraint(in_check("environment", Environment), name="environment"),
        CheckConstraint("amount > 0", name="amount_positive"),
        CheckConstraint("approved_by IS NULL OR approved_by <> requested_by", name="dual_control"),
        CheckConstraint("status <> 'COMPLETED' OR (approved_by IS NOT NULL AND external_reference IS NOT NULL)", name="completed"),
        CheckConstraint("status <> 'REJECTED' OR reject_reason IS NOT NULL", name="reject_reason"),
        CheckConstraint("LEN(currency) = 3", name="currency_code"),
        Index("uq_refunds_open", "payment_id", unique=True, mssql_where=text("status IN ('REQUESTED', 'APPROVED', 'COMPLETED')")),
        Index("uq_refunds_request_key", "request_key", unique=True, mssql_where=text("request_key IS NOT NULL")),
    )
    refund_code: Mapped[str] = mapped_column(Unicode(20), unique=True)        # RFD-YYYY-NNNNNN
    payment_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("payments.id"), index=True)
    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orders.id"), index=True)
    amount: Mapped[Decimal] = mapped_column(MONEY)                             # the whole payment (partial refunds are not implemented)
    currency: Mapped[str] = mapped_column(Unicode(3))
    # credits were already delivered — money-only remediation
    after_transfer: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("0"))
    reason: Mapped[str] = mapped_column(Unicode(2000))
    status: Mapped[str] = mapped_column(Unicode(12), default="REQUESTED")
    requested_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    approved_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    approved_at: Mapped[datetime | None]
    completed_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    completed_at: Mapped[datetime | None]
    external_reference: Mapped[str | None] = mapped_column(Unicode(120))
    evidence_document_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("documents.id"))
    rejected_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    reject_reason: Mapped[str | None] = mapped_column(Unicode(2000))
    request_key: Mapped[str | None] = mapped_column(Unicode(80))
    action_key: Mapped[str | None] = mapped_column(Unicode(80))               # Idempotency-Key of the last state change
    environment: Mapped[str] = mapped_column(Unicode(10), default=Environment.LIVE.value)
