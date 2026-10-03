"""Document upload, versioning and download with entity-level access control (spec sections 30, 32).

Each owning module registers a resolver that decides whether a principal may read / manage the documents
of one of its entities. Files are validated by content (not filename), size-limited, malware-hook scanned,
checksummed and stored in object storage; the database keeps metadata only.

Note: the file is written to storage before the DB transaction commits. If the commit fails the file is
orphaned (harmless, unreachable); an orphan-sweep job is planned with the Celery workers (Phase 12).
"""
import hashlib
import uuid
from collections.abc import Callable
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.audit.service import record, security_event
from app.core.config import get_settings
from app.core.context import RequestContext
from app.core.errors import Conflict, NotFound, ValidationFailed
from app.integrations.malware import get_scanner
from app.integrations.storage import get_storage
from app.models import Document, DocumentVersion
from app.models.documents import RESTRICTED_CATEGORIES, DocumentCategory
from app.rules.file_types import GEOSPATIAL_TYPES, safe_filename, sniff
from app.security.principal import Principal

# kind: "read" | "manage" | "restricted"
Resolver = Callable[[Session, Principal, uuid.UUID, str], None]
_RESOLVERS: dict[str, Resolver] = {}

IMAGE_TYPES = frozenset({"image/png", "image/jpeg", "image/webp"})


def register_resolver(entity_type: str, fn: Resolver) -> None:
    _RESOLVERS[entity_type] = fn


def _check(db: Session, principal: Principal, doc: Document, kind: str) -> None:
    resolver = _RESOLVERS.get(doc.entity_type)
    if resolver is None:
        raise NotFound("Document not found.", error_code="DOCUMENT_NOT_FOUND")
    if kind == "read" and doc.sensitivity == "RESTRICTED":
        kind = "restricted"
    resolver(db, principal, doc.entity_id, kind)


def _validate(data: bytes, category: str) -> str:
    s = get_settings()
    if not data:
        raise ValidationFailed("The file is empty.", error_code="EMPTY_FILE")
    if len(data) > s.MAX_UPLOAD_BYTES:
        raise ValidationFailed(f"The file is larger than {s.MAX_UPLOAD_BYTES // (1024 * 1024)} MB.", error_code="FILE_TOO_LARGE",
                               details={"max_bytes": s.MAX_UPLOAD_BYTES})
    mime = sniff(data)
    if mime is None:
        raise ValidationFailed("Unsupported file type. Upload a PDF, PNG, JPEG or WebP (or GeoJSON/KML for boundaries).",
                               error_code="UNSUPPORTED_FILE_TYPE")
    if category == DocumentCategory.GEOSPATIAL_FILE.value and mime not in GEOSPATIAL_TYPES:
        raise ValidationFailed("Boundary files must be GeoJSON or KML.", error_code="UNSUPPORTED_FILE_TYPE")
    if category != DocumentCategory.GEOSPATIAL_FILE.value and mime in GEOSPATIAL_TYPES:
        raise ValidationFailed("GeoJSON/KML files can only be uploaded as boundary files.", error_code="UNSUPPORTED_FILE_TYPE")
    if category == DocumentCategory.CALCULATION_REPORT.value and mime != "application/pdf":
        raise ValidationFailed("Calculation reports are PDF files.", error_code="UNSUPPORTED_FILE_TYPE")
    if category in (DocumentCategory.LAB_REPORT.value, DocumentCategory.CUSTODY_DOCUMENT.value) and mime != "application/pdf":
        # Phase 6 decision 16: laboratory-visible documents are PDF only (no images that may carry EXIF / GPS)
        raise ValidationFailed("Laboratory reports and custody documents must be PDF files.", error_code="UNSUPPORTED_FILE_TYPE")
    if category == DocumentCategory.FIELD_PHOTO.value and mime not in IMAGE_TYPES:
        raise ValidationFailed("Field photos must be PNG, JPEG or WebP images.", error_code="UNSUPPORTED_FILE_TYPE")
    return mime


def _store(db: Session, ctx: RequestContext, doc: Document, version: int, filename: str | None, data: bytes,
           mime: str) -> DocumentVersion:
    scan = get_scanner().scan(data)
    if scan.status == "INFECTED":
        security_event(db, ctx, "MALWARE_UPLOAD_BLOCKED", "CRITICAL",
                       details={"entity_type": doc.entity_type, "entity_id": str(doc.entity_id), "detail": scan.detail})
        db.commit()
        raise ValidationFailed("The file was rejected by the malware scanner.", error_code="MALWARE_DETECTED")
    now = datetime.utcnow()
    key = f"{doc.environment.lower()}/{now:%Y/%m}/{uuid.uuid4().hex}"
    get_storage().put(key, data, mime)
    v = DocumentVersion(document_id=doc.id, version=version, file_name=safe_filename(filename, mime), storage_key=key,
                        mime_type=mime, size_bytes=len(data), checksum_sha256=hashlib.sha256(data).hexdigest(),
                        scan_status=scan.status, scan_detail=scan.detail, uploaded_by=ctx.user_id)
    db.add(v)
    return v


def create_document(db: Session, ctx: RequestContext, *, entity_type: str, entity_id: uuid.UUID,
                    organization_id: uuid.UUID, environment: str, category: str, title: str,
                    filename: str | None, data: bytes) -> Document:
    """Caller must already have checked that the principal may manage the owning entity."""
    if entity_type not in _RESOLVERS:
        raise ValidationFailed(f"Documents cannot be attached to {entity_type!r}.", error_code="INVALID_ENTITY")
    if category not in {c.value for c in DocumentCategory}:
        raise ValidationFailed("Unknown document category.", error_code="INVALID_CATEGORY")
    mime = _validate(data, category)
    doc = Document(entity_type=entity_type, entity_id=entity_id, organization_id=organization_id, category=category,
                   title=title.strip()[:200] or category.replace("_", " ").title(), environment=environment,
                   sensitivity="RESTRICTED" if category in RESTRICTED_CATEGORIES else "INTERNAL", created_by=ctx.user_id)
    db.add(doc)
    db.flush()
    v = _store(db, ctx, doc, 1, filename, data, mime)
    record(db, ctx, "DOCUMENT_UPLOADED", entity_type, entity_id, None,
           {"document_id": doc.id, "category": category, "file_name": v.file_name, "sha256": v.checksum_sha256,
            "size_bytes": v.size_bytes, "scan_status": v.scan_status}, organization_id=organization_id)
    return doc


def add_version(db: Session, ctx: RequestContext, principal: Principal, document_id: uuid.UUID,
                filename: str | None, data: bytes) -> Document:
    doc = get_document(db, principal, document_id, "manage")
    if doc.status != "ACTIVE":
        raise Conflict("Only active documents can receive new versions.", error_code="DOCUMENT_NOT_ACTIVE")
    mime = _validate(data, doc.category)
    doc.current_version += 1
    v = _store(db, ctx, doc, doc.current_version, filename, data, mime)
    record(db, ctx, "DOCUMENT_VERSION_ADDED", doc.entity_type, doc.entity_id, None,
           {"document_id": doc.id, "version": v.version, "sha256": v.checksum_sha256}, organization_id=doc.organization_id)
    db.commit()
    return get_document(db, principal, document_id)


def get_document(db: Session, principal: Principal, document_id: uuid.UUID, kind: str = "read") -> Document:
    doc = db.scalars(select(Document).where(Document.id == document_id).options(selectinload(Document.versions))
                     .execution_options(populate_existing=True)).first()
    if doc is None:
        raise NotFound("Document not found.", error_code="DOCUMENT_NOT_FOUND")
    _check(db, principal, doc, kind)
    return doc


def download(db: Session, ctx: RequestContext, principal: Principal, document_id: uuid.UUID,
             version: int | None = None) -> tuple[DocumentVersion, bytes]:
    doc = get_document(db, principal, document_id)
    if doc.status == "QUARANTINED":
        raise Conflict("This document is quarantined and cannot be downloaded.", error_code="DOCUMENT_QUARANTINED")
    wanted = version or doc.current_version
    v = next((x for x in doc.versions if x.version == wanted), None)
    if v is None:
        raise NotFound("Document version not found.", error_code="DOCUMENT_VERSION_NOT_FOUND")
    data = get_storage().get(v.storage_key)
    if hashlib.sha256(data).hexdigest() != v.checksum_sha256:
        security_event(db, ctx, "DOCUMENT_INTEGRITY_FAILURE", "CRITICAL", details={"document_id": str(doc.id), "version": v.version})
        db.commit()
        raise Conflict("The stored file failed its integrity check. It has been reported.", error_code="DOCUMENT_INTEGRITY_FAILURE")
    record(db, ctx, "DOCUMENT_DOWNLOADED", doc.entity_type, doc.entity_id, None,
           {"document_id": doc.id, "version": v.version, "category": doc.category}, organization_id=doc.organization_id)
    db.commit()
    return v, data


def require_attached(db: Session, document_id: uuid.UUID | None, entity_type: str, entity_id: uuid.UUID,
                     categories: set[str] | None = None) -> Document | None:
    """A document referenced by a business record must belong to the same entity (no cross-linking)."""
    if document_id is None:
        return None
    doc = db.get(Document, document_id)
    if doc is None or doc.entity_type != entity_type or doc.entity_id != entity_id:
        raise ValidationFailed("The referenced document does not belong to this record.", error_code="DOCUMENT_NOT_ATTACHED")
    if categories and doc.category not in categories:
        raise ValidationFailed(f"The referenced document must be one of: {', '.join(sorted(categories))}.",
                               error_code="DOCUMENT_WRONG_CATEGORY")
    if doc.status != "ACTIVE":
        raise ValidationFailed("The referenced document is not active.", error_code="DOCUMENT_NOT_ACTIVE")
    return doc


def list_for(db: Session, entity_type: str, entity_id: uuid.UUID) -> list[Document]:
    return list(db.scalars(select(Document).where(Document.entity_type == entity_type, Document.entity_id == entity_id)
                           .options(selectinload(Document.versions)).order_by(Document.created_at)).all())
