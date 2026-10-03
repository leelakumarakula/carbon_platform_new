"""Generic document store (spec sections 7.9 and 32). Files live in object storage; the DB keeps metadata.

A document belongs to one business entity (entity_type/entity_id) and organization. Each upload is an
immutable document_versions row (append-only trigger); a new upload creates a new version.
"""
import uuid
from datetime import datetime
from enum import Enum

from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, Index, Integer, Unicode, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, Environment, UUIDPrimaryKey, in_check, utcnow


class DocumentCategory(str, Enum):
    KYC_ID = "KYC_ID"
    LAND_TITLE = "LAND_TITLE"
    LEASE_AGREEMENT = "LEASE_AGREEMENT"
    LAND_RECORD = "LAND_RECORD"
    CONSENT_FORM = "CONSENT_FORM"
    AGREEMENT = "AGREEMENT"
    BANK_PROOF = "BANK_PROOF"
    FIELD_PHOTO = "FIELD_PHOTO"
    INPUT_RECORD = "INPUT_RECORD"
    GEOSPATIAL_FILE = "GEOSPATIAL_FILE"
    PROJECT_DESIGN = "PROJECT_DESIGN"        # Phase 3: project description / design documents
    CARBON_RIGHTS = "CARBON_RIGHTS"          # Phase 3: carbon-rights evidence (agreements, assignments)
    BASELINE_DATA = "BASELINE_DATA"          # Phase 3: baseline-period data sources
    METHODOLOGY_DOCUMENT = "METHODOLOGY_DOCUMENT"  # Phase 4: authoritative methodology source documents
    LAB_REPORT = "LAB_REPORT"                # Phase 6: laboratory report for a result (PDF only)
    CUSTODY_DOCUMENT = "CUSTODY_DOCUMENT"    # Phase 6: chain-of-custody form for a shipment (PDF only)
    CALCULATION_REPORT = "CALCULATION_REPORT"  # Phase 8A: generated calculation report of an APPROVED run (PDF only)
    VERIFICATION_REPORT = "VERIFICATION_REPORT"  # Phase 8B: the external VVB's verification report (PDF only)
    VERIFICATION_EVIDENCE = "VERIFICATION_EVIDENCE"  # Phase 8B: project evidence answering a VVB finding / corrective action (PDF only)
    REGISTRY_SUBMISSION = "REGISTRY_SUBMISSION"  # Phase 9A: a document sent to the registry with a submission (PDF only)
    REGISTRY_RESPONSE = "REGISTRY_RESPONSE"  # Phase 9A: registry receipt / query / acceptance / rejection / registration evidence (PDF)
    ISSUANCE_STATEMENT = "ISSUANCE_STATEMENT"  # Phase 9A: the registry's issuance statement backing recorded batches / serials (PDF)
    RETIREMENT_CERTIFICATE = "RETIREMENT_CERTIFICATE"  # Phase 9B: the registry's retirement certificate (PDF only)
    REGISTRY_TRANSFER_EVIDENCE = "REGISTRY_TRANSFER_EVIDENCE"  # Phase 9B: registry evidence of a transfer between accounts (PDF only)
    BUYER_KYC_DOCUMENT = "BUYER_KYC_DOCUMENT"  # Phase 10: a buyer organization's KYC document (restricted, PDF only)
    PAYMENT_EVIDENCE = "PAYMENT_EVIDENCE"      # Phase 10: buyer's evidence of a payment for an order (PDF only)
    REFUND_EVIDENCE = "REFUND_EVIDENCE"        # Phase 10: evidence of a completed refund (PDF only)
    ORDER_CONFIRMATION = "ORDER_CONFIRMATION"  # Phase 10: deterministic order confirmation (generated PDF; not a tax invoice)
    LISTING_DOCUMENT = "LISTING_DOCUMENT"      # Phase 10: a document the seller publishes on a listing (PDF only, buyer-visible)
    COST_EVIDENCE = "COST_EVIDENCE"            # Phase 11: evidence of a project cost actually incurred (PDF only)
    PAYOUT_EVIDENCE = "PAYOUT_EVIDENCE"        # Phase 11: remittance proof of a manual payout (PDF only, restricted)
    RECONCILIATION_EVIDENCE = "RECONCILIATION_EVIDENCE"  # Phase 11: bank / provider statement for reconciliation (PDF only, restricted)
    OTHER = "OTHER"


RESTRICTED_CATEGORIES = frozenset({DocumentCategory.KYC_ID.value, DocumentCategory.BANK_PROOF.value,
                                   DocumentCategory.BUYER_KYC_DOCUMENT.value, DocumentCategory.PAYOUT_EVIDENCE.value,
                                   DocumentCategory.RECONCILIATION_EVIDENCE.value})


class DocumentStatus(str, Enum):
    ACTIVE = "ACTIVE"
    QUARANTINED = "QUARANTINED"
    ARCHIVED = "ARCHIVED"


class ScanStatus(str, Enum):
    NOT_SCANNED = "NOT_SCANNED"
    CLEAN = "CLEAN"
    INFECTED = "INFECTED"
    ERROR = "ERROR"


class Document(UUIDPrimaryKey, Base):
    __tablename__ = "documents"
    __table_args__ = (
        CheckConstraint(in_check("category", DocumentCategory), name="category"),
        CheckConstraint(in_check("status", DocumentStatus), name="status"),
        CheckConstraint(in_check("sensitivity", ["RESTRICTED", "INTERNAL"]), name="sensitivity"),
        CheckConstraint(in_check("environment", Environment), name="environment"),
        Index("ix_documents_entity", "entity_type", "entity_id"),
    )
    entity_type: Mapped[str] = mapped_column(Unicode(40))
    entity_id: Mapped[uuid.UUID]
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), index=True)
    category: Mapped[str] = mapped_column(Unicode(30))
    title: Mapped[str] = mapped_column(Unicode(200))
    sensitivity: Mapped[str] = mapped_column(Unicode(12), default="INTERNAL")
    status: Mapped[str] = mapped_column(Unicode(15), default=DocumentStatus.ACTIVE.value)
    current_version: Mapped[int] = mapped_column(Integer, default=1)
    environment: Mapped[str] = mapped_column(Unicode(10), default=Environment.LIVE.value)
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(default=utcnow, server_default=text("SYSUTCDATETIME()"))

    versions: Mapped[list["DocumentVersion"]] = relationship(back_populates="document", order_by="DocumentVersion.version")
    scans: Mapped[list["DocumentScan"]] = relationship(viewonly=True, order_by="DocumentScan.scanned_at")   # Phase 12B: append-only history


class DocumentVersion(UUIDPrimaryKey, Base):
    """Immutable (append-only trigger)."""
    __tablename__ = "document_versions"
    __table_args__ = (
        UniqueConstraint("document_id", "version"),
        CheckConstraint(in_check("scan_status", ScanStatus), name="scan_status"),
    )
    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("documents.id"))
    version: Mapped[int] = mapped_column(Integer)
    file_name: Mapped[str] = mapped_column(Unicode(200))
    storage_key: Mapped[str] = mapped_column(Unicode(400), unique=True)
    mime_type: Mapped[str] = mapped_column(Unicode(100))
    size_bytes: Mapped[int] = mapped_column(BigInteger)
    checksum_sha256: Mapped[str] = mapped_column(Unicode(64), index=True)
    scan_status: Mapped[str] = mapped_column(Unicode(15))
    scan_detail: Mapped[str | None] = mapped_column(Unicode(400))
    uploaded_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    uploaded_at: Mapped[datetime] = mapped_column(default=utcnow, server_default=text("SYSUTCDATETIME()"))

    document: Mapped[Document] = relationship(back_populates="versions")


SCAN_RESULTS = ["CLEAN", "INFECTED", "NOT_SCANNED", "ERROR"]
SCAN_TRIGGERS = ["UPLOAD", "RESCAN", "RELEASE"]


class DocumentScan(UUIDPrimaryKey, Base):
    """Phase 12B D15 — append-only antivirus scan history (trigger): every acceptance scan, background rescan and release rescan is a new
    row; nothing is overwritten. The document version's own `scan_status` stays the immutable acceptance result."""
    __tablename__ = "document_scans"
    __table_args__ = (
        CheckConstraint(in_check("result", SCAN_RESULTS), name="result"),
        CheckConstraint(in_check("trigger_type", SCAN_TRIGGERS), name="trigger_type"),
        CheckConstraint(in_check("environment", Environment), name="environment"),
        Index("ix_document_scans_document", "document_id", "scanned_at"),
        Index("ix_document_scans_version", "document_version_id", "scanned_at"),
    )
    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("documents.id"))
    document_version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("document_versions.id"))
    environment: Mapped[str] = mapped_column(Unicode(10))
    checksum_sha256: Mapped[str] = mapped_column(Unicode(64))           # the bytes that were scanned
    result: Mapped[str] = mapped_column(Unicode(15))
    provider: Mapped[str] = mapped_column(Unicode(60))                  # scanner identity
    engine_version: Mapped[str | None] = mapped_column(Unicode(120))
    threat_name: Mapped[str | None] = mapped_column(Unicode(200))
    error_code: Mapped[str | None] = mapped_column(Unicode(60))
    detail: Mapped[str | None] = mapped_column(Unicode(400))
    trigger_type: Mapped[str] = mapped_column(Unicode(10))
    background_job_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("background_jobs.id"))
    actor_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    scanned_at: Mapped[datetime] = mapped_column(default=utcnow, server_default=text("SYSUTCDATETIME()"))
