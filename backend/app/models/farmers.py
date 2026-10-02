"""Farmer (spec section 7.2): profile, contacts, KYC metadata, consents, agreements, bank accounts, documents."""
import uuid
from datetime import date, datetime
from enum import Enum

from sqlalchemy import Boolean, CheckConstraint, Date, ForeignKey, Index, Unicode, UnicodeText, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, Environment, Timestamped, UUIDPrimaryKey, in_check, utcnow


class FarmerStatus(str, Enum):
    DRAFT = "DRAFT"
    REGISTERED = "REGISTERED"
    KYC_PENDING = "KYC_PENDING"
    KYC_VERIFIED = "KYC_VERIFIED"
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"


class KycIdType(str, Enum):
    NATIONAL_ID = "NATIONAL_ID"
    VOTER_ID = "VOTER_ID"
    TAX_ID = "TAX_ID"
    PASSPORT = "PASSPORT"
    DRIVING_LICENSE = "DRIVING_LICENSE"
    OTHER = "OTHER"


class Farmer(UUIDPrimaryKey, Timestamped, Base):
    __tablename__ = "farmers"
    __table_args__ = (
        CheckConstraint(in_check("status", FarmerStatus), name="status"),
        CheckConstraint(in_check("participation_type", ["INDIVIDUAL", "GROUP_MEMBER"]), name="participation_type"),
        CheckConstraint("gender IS NULL OR " + in_check("gender", ["FEMALE", "MALE", "OTHER", "UNDISCLOSED"]), name="gender"),
        CheckConstraint("kyc_id_type IS NULL OR " + in_check("kyc_id_type", KycIdType), name="kyc_id_type"),
        CheckConstraint(in_check("environment", Environment), name="environment"),
        # One login account maps to at most one farmer record.
        Index("uq_farmers_user_id", "user_id", unique=True, mssql_where=text("user_id IS NOT NULL")),
        Index("ix_farmers_kyc_id_hash", "kyc_id_hash"),
    )
    farmer_code: Mapped[str] = mapped_column(Unicode(30), unique=True)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), index=True)  # managing organization
    group_organization_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("organizations.id"))  # farmer group, if any
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))                         # self-service login
    full_name: Mapped[str] = mapped_column(Unicode(200), index=True)
    gender: Mapped[str | None] = mapped_column(Unicode(12))
    date_of_birth: Mapped[date | None] = mapped_column(Date)
    preferred_language: Mapped[str | None] = mapped_column(Unicode(10))
    participation_type: Mapped[str] = mapped_column(Unicode(15), default="INDIVIDUAL")
    address_line: Mapped[str | None] = mapped_column(Unicode(300))
    village: Mapped[str | None] = mapped_column(Unicode(120))
    sub_district: Mapped[str | None] = mapped_column(Unicode(120))
    district: Mapped[str | None] = mapped_column(Unicode(120))
    state: Mapped[str | None] = mapped_column(Unicode(120))
    postal_code: Mapped[str | None] = mapped_column(Unicode(20))
    country: Mapped[str] = mapped_column(Unicode(2))
    status: Mapped[str] = mapped_column(Unicode(15), default=FarmerStatus.DRAFT.value)
    # KYC metadata — the raw identity number is never stored (only type, last 4, keyed fingerprint).
    kyc_id_type: Mapped[str | None] = mapped_column(Unicode(20))
    kyc_id_last4: Mapped[str | None] = mapped_column(Unicode(4))
    kyc_id_hash: Mapped[str | None] = mapped_column(Unicode(64))
    kyc_document_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("documents.id"))
    kyc_possible_duplicate: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("0"))
    kyc_submitted_at: Mapped[datetime | None]
    kyc_submitted_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    kyc_verified_at: Mapped[datetime | None]
    kyc_verified_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    kyc_notes: Mapped[str | None] = mapped_column(Unicode(1000))
    registered_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    environment: Mapped[str] = mapped_column(Unicode(10), default=Environment.LIVE.value)

    contacts: Mapped[list["FarmerContact"]] = relationship(back_populates="farmer", order_by="FarmerContact.created_at")
    consents: Mapped[list["FarmerConsent"]] = relationship(back_populates="farmer", order_by="FarmerConsent.captured_at")
    agreements: Mapped[list["FarmerAgreement"]] = relationship(back_populates="farmer", order_by="FarmerAgreement.created_at")
    bank_accounts: Mapped[list["FarmerBankAccount"]] = relationship(back_populates="farmer", order_by="FarmerBankAccount.created_at")


class FarmerContact(UUIDPrimaryKey, Base):
    __tablename__ = "farmer_contacts"
    __table_args__ = (CheckConstraint(in_check("contact_type", ["PHONE", "EMAIL", "ALTERNATE_PHONE", "ADDRESS"]), name="contact_type"),)
    farmer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("farmers.id"), index=True)
    contact_type: Mapped[str] = mapped_column(Unicode(20))
    value: Mapped[str] = mapped_column(Unicode(320))
    label: Mapped[str | None] = mapped_column(Unicode(60))
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("0"))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("1"))
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(default=utcnow, server_default=text("SYSUTCDATETIME()"))

    farmer: Mapped[Farmer] = relationship(back_populates="contacts")


class FarmerConsent(UUIDPrimaryKey, Base):
    """A consent grant. Never edited except to record withdrawal; granting again creates a new row."""
    __tablename__ = "farmer_consents"
    __table_args__ = (
        CheckConstraint(in_check("status", ["GRANTED", "WITHDRAWN"]), name="status"),
        CheckConstraint(in_check("capture_method", ["PAPER_SIGNED", "DIGITAL_SIGNATURE", "VERBAL_RECORDED", "OTP", "ONLINE_CHECKBOX"]),
                        name="capture_method"),
    )
    farmer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("farmers.id"), index=True)
    consent_type: Mapped[str] = mapped_column(Unicode(40))
    consent_text_version: Mapped[str] = mapped_column(Unicode(40))
    language: Mapped[str | None] = mapped_column(Unicode(10))
    capture_method: Mapped[str] = mapped_column(Unicode(20))
    document_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("documents.id"))
    status: Mapped[str] = mapped_column(Unicode(10), default="GRANTED")
    captured_at: Mapped[datetime] = mapped_column(default=utcnow)
    captured_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    withdrawn_at: Mapped[datetime | None]
    withdrawn_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    withdrawal_reason: Mapped[str | None] = mapped_column(Unicode(1000))

    farmer: Mapped[Farmer] = relationship(back_populates="consents")


class AgreementStatus(str, Enum):
    DRAFT = "DRAFT"
    SIGNED = "SIGNED"
    TERMINATED = "TERMINATED"
    EXPIRED = "EXPIRED"
    VOID = "VOID"


class FarmerAgreement(UUIDPrimaryKey, Timestamped, Base):
    """Program-level agreement. Project participation / carbon-rights terms are added in Phase 3."""
    __tablename__ = "farmer_agreements"
    __table_args__ = (
        CheckConstraint(in_check("status", AgreementStatus), name="status"),
        CheckConstraint("effective_to IS NULL OR effective_from IS NULL OR effective_to >= effective_from", name="dates"),
    )
    farmer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("farmers.id"), index=True)
    agreement_number: Mapped[str] = mapped_column(Unicode(60), unique=True)
    agreement_type: Mapped[str] = mapped_column(Unicode(40))
    template_version: Mapped[str] = mapped_column(Unicode(40))
    counterparty_organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"))
    terms_summary: Mapped[str | None] = mapped_column(UnicodeText)
    effective_from: Mapped[date | None] = mapped_column(Date)
    effective_to: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(Unicode(12), default=AgreementStatus.DRAFT.value)
    signed_at: Mapped[datetime | None]
    signature_method: Mapped[str | None] = mapped_column(Unicode(20))
    signed_document_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("documents.id"))
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))

    farmer: Mapped[Farmer] = relationship(back_populates="agreements")


class BankAccountStatus(str, Enum):
    PENDING_VERIFICATION = "PENDING_VERIFICATION"
    VERIFIED = "VERIFIED"
    REJECTED = "REJECTED"
    INACTIVE = "INACTIVE"


class FarmerBankAccount(UUIDPrimaryKey, Timestamped, Base):
    """Account number is Fernet-encrypted; API responses only ever show the last 4 digits."""
    __tablename__ = "farmer_bank_accounts"
    __table_args__ = (CheckConstraint(in_check("status", BankAccountStatus), name="status"),)
    farmer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("farmers.id"), index=True)
    account_holder_name: Mapped[str] = mapped_column(Unicode(200))
    bank_name: Mapped[str] = mapped_column(Unicode(200))
    branch_name: Mapped[str | None] = mapped_column(Unicode(200))
    routing_code: Mapped[str] = mapped_column(Unicode(30))  # IFSC / SWIFT / sort code
    account_number_enc: Mapped[str] = mapped_column(Unicode(500))
    account_last4: Mapped[str] = mapped_column(Unicode(4))
    account_number_hash: Mapped[str] = mapped_column(Unicode(64), index=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("0"))
    status: Mapped[str] = mapped_column(Unicode(25), default=BankAccountStatus.PENDING_VERIFICATION.value)
    proof_document_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("documents.id"))
    verified_at: Mapped[datetime | None]
    verified_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    review_notes: Mapped[str | None] = mapped_column(Unicode(1000))
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))

    farmer: Mapped[Farmer] = relationship(back_populates="bank_accounts")


class FarmerDocument(UUIDPrimaryKey, Base):
    __tablename__ = "farmer_documents"
    __table_args__ = (CheckConstraint(in_check("review_status", ["UNREVIEWED", "ACCEPTED", "REJECTED"]), name="review_status"),)
    farmer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("farmers.id"), index=True)
    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("documents.id"), unique=True)
    review_status: Mapped[str] = mapped_column(Unicode(12), default="UNREVIEWED")
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    reviewed_at: Mapped[datetime | None]
    review_notes: Mapped[str | None] = mapped_column(Unicode(1000))
    created_at: Mapped[datetime] = mapped_column(default=utcnow, server_default=text("SYSUTCDATETIME()"))
