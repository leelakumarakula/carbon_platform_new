"""Document upload, versioning and download with entity-level access control (spec sections 30, 32).

Each owning module registers a resolver that decides whether a principal may read / manage the documents
of one of its entities. Files are validated by content (not filename), size-limited, malware-hook scanned,
checksummed and stored in object storage; the database keeps metadata only.

Phase 12B (D7 / D11 / D12-D17): accepted bytes are scanned synchronously BEFORE anything is written (an INFECTED file is never stored;
scanner unavailable -> refused for LIVE documents in production, otherwise stored QUARANTINED with a background rescan queued), then
written to object storage, verified (SHA-256 / size / server-side encryption), and only then recorded in the database (the caller
commits). If the commit fails the object is an orphan: unreachable, detected and deleted by the orphan-cleanup job after the grace
period. Every scan - at upload, background rescan or release - is a new row in the append-only `document_scans` history; quarantine and
release are security operations (release only after a clean rescan) and are audited.
"""
import hashlib
import time
import uuid
from collections.abc import Callable
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.audit.service import record, security_event
from app.core import metrics
from app.core.config import get_settings
from app.core.context import RequestContext
from app.core.errors import Conflict, NotFound, ServiceUnavailable, ValidationFailed
from app.integrations.malware import ScanResult, get_scanner
from app.integrations.storage import StorageError, get_storage
from app.models import Document, DocumentScan, DocumentVersion
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
    if category in (DocumentCategory.REGISTRY_SUBMISSION.value, DocumentCategory.REGISTRY_RESPONSE.value,
                    DocumentCategory.ISSUANCE_STATEMENT.value, DocumentCategory.RETIREMENT_CERTIFICATE.value,
                    DocumentCategory.REGISTRY_TRANSFER_EVIDENCE.value) and mime != "application/pdf":
        raise ValidationFailed("Registry documents must be PDF files.", error_code="UNSUPPORTED_FILE_TYPE")   # D14: PDF only in 9A
    if category in (DocumentCategory.VERIFICATION_REPORT.value, DocumentCategory.VERIFICATION_EVIDENCE.value) and mime != "application/pdf":
        # Phase 8B: documents exchanged with an external VVB are PDF only (no images that may carry EXIF / GPS)
        raise ValidationFailed("Verification documents must be PDF files.", error_code="UNSUPPORTED_FILE_TYPE")
    if category in (DocumentCategory.BUYER_KYC_DOCUMENT.value, DocumentCategory.PAYMENT_EVIDENCE.value, DocumentCategory.REFUND_EVIDENCE.value,
                    DocumentCategory.ORDER_CONFIRMATION.value, DocumentCategory.LISTING_DOCUMENT.value) and mime != "application/pdf":
        raise ValidationFailed("Marketplace documents must be PDF files.", error_code="UNSUPPORTED_FILE_TYPE")   # Phase 10 D28 / D29
    if category in (DocumentCategory.COST_EVIDENCE.value, DocumentCategory.PAYOUT_EVIDENCE.value,
                    DocumentCategory.RECONCILIATION_EVIDENCE.value) and mime != "application/pdf":
        raise ValidationFailed("Financial evidence must be a PDF file.", error_code="UNSUPPORTED_FILE_TYPE")   # Phase 11
    if category == DocumentCategory.CALCULATION_REPORT.value and mime != "application/pdf":
        raise ValidationFailed("Calculation reports are PDF files.", error_code="UNSUPPORTED_FILE_TYPE")
    if category in (DocumentCategory.LAB_REPORT.value, DocumentCategory.CUSTODY_DOCUMENT.value) and mime != "application/pdf":
        # Phase 6 decision 16: laboratory-visible documents are PDF only (no images that may carry EXIF / GPS)
        raise ValidationFailed("Laboratory reports and custody documents must be PDF files.", error_code="UNSUPPORTED_FILE_TYPE")
    if category == DocumentCategory.FIELD_PHOTO.value and mime not in IMAGE_TYPES:
        raise ValidationFailed("Field photos must be PNG, JPEG or WebP images.", error_code="UNSUPPORTED_FILE_TYPE")
    return mime


def _scan(data: bytes, filename: str | None) -> tuple[ScanResult, int]:
    """Never raises for an engine failure: an unreachable / failing scanner is an ERROR result (never CLEAN)."""
    scanner = get_scanner()
    started = time.monotonic()
    try:
        res = scanner.scan(data, filename)
        if res.status not in ("CLEAN", "INFECTED", "NOT_SCANNED", "ERROR"):
            res = ScanResult("ERROR", scanner.name, res.engine_version, None, "scanner returned an unknown result")
    except Exception as e:                                         # ScannerUnavailable, timeout, adapter failure
        res = ScanResult("ERROR", scanner.name, None, None, f"scanner unavailable ({type(e).__name__})")
    elapsed = time.monotonic() - started
    metrics.observe("av_scan_duration_seconds", elapsed, {"provider": res.provider})
    if res.status == "ERROR":
        metrics.inc("av_scan_failures_total", {"provider": res.provider})
    return res, int(elapsed * 1000)


def _accept(db: Session, ctx: RequestContext, environment: str, entity_type: str, entity_id: uuid.UUID, data: bytes,
            filename: str | None) -> tuple[ScanResult, int]:
    """The synchronous acceptance scan (D12), before anything of the upload is written."""
    res, ms = _scan(data, filename)
    metrics.inc("av_scans_total", {"trigger": "UPLOAD", "result": res.status})
    if res.status == "INFECTED":
        security_event(db, ctx, "MALWARE_UPLOAD_BLOCKED", "CRITICAL",
                       details={"entity_type": entity_type, "entity_id": str(entity_id), "detail": res.detail, "threat": res.threat,
                                "provider": res.provider})
        db.commit()
        raise ValidationFailed("The file was rejected by the malware scanner.", error_code="MALWARE_DETECTED")
    if res.status == "ERROR" and get_settings().is_production and environment == "LIVE":
        security_event(db, ctx, "ANTIVIRUS_UNAVAILABLE", "WARNING", details={"entity_type": entity_type, "provider": res.provider})
        db.commit()
        raise ServiceUnavailable("Files cannot be accepted while the antivirus scanner is unavailable. Please try again later.",
                                 error_code="SCANNER_UNAVAILABLE")
    return res, ms


def _put_object(environment: str, data: bytes, mime: str) -> tuple[str, str]:
    """Write and verify the object BEFORE any database row of the upload exists (D7 / D11): a storage outage or an unencrypted /
    mismatched write leaves the database untouched. Returns (server-generated key, SHA-256)."""
    key = f"{environment.lower()}/{datetime.utcnow():%Y/%m}/{uuid.uuid4().hex}"
    digest = hashlib.sha256(data).hexdigest()
    storage = get_storage()
    try:
        storage.put(key, data, mime)                                # upload -> verify -> (caller's) database commit (D7 / D11)
        storage.verify(key, digest, len(data))
    except (StorageError, OSError) as e:
        metrics.inc("storage_failures_total", {"operation": "put"})
        code = e.code if isinstance(e, StorageError) else "STORAGE_UNAVAILABLE"
        raise ServiceUnavailable("The document store is unavailable or refused the file. Please try again later.",
                                 error_code="STORAGE_UNAVAILABLE", details={"reason": code}) from None
    return key, digest


def _store(db: Session, ctx: RequestContext, doc: Document, version: int, filename: str | None, data: bytes,
           mime: str, scan: tuple[ScanResult, int], obj: tuple[str, str]) -> DocumentVersion:
    """Record a version whose object is already stored and verified (the caller commits)."""
    res, ms = scan
    key, digest = obj
    v = DocumentVersion(document_id=doc.id, version=version, file_name=safe_filename(filename, mime), storage_key=key,
                        mime_type=mime, size_bytes=len(data), checksum_sha256=digest,
                        scan_status=res.status, scan_detail=(res.detail or "")[:400] or None, uploaded_by=ctx.user_id)
    db.add(v)
    db.flush()
    _history(db, doc, v, res, "UPLOAD", ctx.user_id, None, ms)
    if res.status == "ERROR":                                      # not production LIVE (refused above): quarantine + rescan
        _quarantine(db, ctx, doc, "Scanner unavailable at upload: quarantined until a clean rescan and a security release.",
                    "ANTIVIRUS_UNAVAILABLE_AT_UPLOAD", "WARNING")
        _queue_rescan(db, ctx, doc)
    return v


def _history(db: Session, doc: Document, v: DocumentVersion, res: ScanResult, trigger: str, actor_id: uuid.UUID | None,
             job_id: uuid.UUID | None, ms: int | None, error_code: str | None = None) -> DocumentScan:
    row = DocumentScan(document_id=doc.id, document_version_id=v.id, environment=doc.environment, checksum_sha256=v.checksum_sha256,
                       result=res.status, provider=res.provider[:60], engine_version=(res.engine_version or "")[:120] or None,
                       threat_name=(res.threat or "")[:200] or None,
                       error_code=error_code or ("SCANNER_UNAVAILABLE" if res.status == "ERROR" else None),
                       detail=(res.detail or "")[:400] or None, trigger_type=trigger, background_job_id=job_id, actor_id=actor_id,
                       duration_ms=ms)
    db.add(row)
    db.flush()
    return row


def _quarantine(db: Session, ctx: RequestContext, doc: Document, reason: str, event: str, severity: str) -> None:
    if doc.status == "QUARANTINED":
        return
    old = doc.status
    doc.status = "QUARANTINED"
    record(db, ctx, "DOCUMENT_QUARANTINED", doc.entity_type, doc.entity_id, {"status": old},
           {"document_id": doc.id, "status": "QUARANTINED", "category": doc.category}, reason, organization_id=doc.organization_id)
    security_event(db, ctx, event, severity, details={"document_id": str(doc.id), "reason": reason[:200]})


def _queue_rescan(db: Session, ctx: RequestContext, doc: Document, key: str | None = None) -> None:
    from app.models.jobs import SYSTEM_ACTOR_IDS
    from app.workers import job_service
    job_service.enqueue(db, ctx, "DOCUMENT_RESCAN", environment=doc.environment, trigger_type="SERVICE",
                        created_by=ctx.user_id or SYSTEM_ACTOR_IDS[doc.environment], organization_id=doc.organization_id,
                        entity_type="document", entity_id=doc.id, idempotency_key=key)


def create_document(db: Session, ctx: RequestContext, *, entity_type: str, entity_id: uuid.UUID,
                    organization_id: uuid.UUID, environment: str, category: str, title: str,
                    filename: str | None, data: bytes) -> Document:
    """Caller must already have checked that the principal may manage the owning entity."""
    if entity_type not in _RESOLVERS:
        raise ValidationFailed(f"Documents cannot be attached to {entity_type!r}.", error_code="INVALID_ENTITY")
    if category not in {c.value for c in DocumentCategory}:
        raise ValidationFailed("Unknown document category.", error_code="INVALID_CATEGORY")
    mime = _validate(data, category)
    scan = _accept(db, ctx, environment, entity_type, entity_id, data, filename)
    obj = _put_object(environment, data, mime)
    doc = Document(entity_type=entity_type, entity_id=entity_id, organization_id=organization_id, category=category,
                   title=title.strip()[:200] or category.replace("_", " ").title(), environment=environment,
                   sensitivity="RESTRICTED" if category in RESTRICTED_CATEGORIES else "INTERNAL", created_by=ctx.user_id)
    db.add(doc)
    db.flush()
    v = _store(db, ctx, doc, 1, filename, data, mime, scan, obj)
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
    scan = _accept(db, ctx, doc.environment, doc.entity_type, doc.entity_id, data, filename)
    obj = _put_object(doc.environment, data, mime)
    doc.current_version += 1
    v = _store(db, ctx, doc, doc.current_version, filename, data, mime, scan, obj)
    record(db, ctx, "DOCUMENT_VERSION_ADDED", doc.entity_type, doc.entity_id, None,
           {"document_id": doc.id, "version": v.version, "sha256": v.checksum_sha256}, organization_id=doc.organization_id)
    db.commit()
    return get_document(db, principal, document_id)


def get_document(db: Session, principal: Principal, document_id: uuid.UUID, kind: str = "read") -> Document:
    doc = db.scalars(select(Document).where(Document.id == document_id).options(selectinload(Document.versions), selectinload(Document.scans))
                     .execution_options(populate_existing=True)).first()
    if doc is None:
        raise NotFound("Document not found.", error_code="DOCUMENT_NOT_FOUND")
    _check(db, principal, doc, kind)
    return doc


def download(db: Session, ctx: RequestContext, principal: Principal, document_id: uuid.UUID,
             version: int | None = None) -> tuple[DocumentVersion, bytes]:
    doc = get_document(db, principal, document_id)
    v, data = read_verified(db, ctx, doc, version)
    record(db, ctx, "DOCUMENT_DOWNLOADED", doc.entity_type, doc.entity_id, None,
           {"document_id": doc.id, "version": v.version, "category": doc.category}, organization_id=doc.organization_id)
    db.commit()
    return v, data


def read_verified(db: Session, ctx: RequestContext, doc: Document, version: int | None = None) -> tuple[DocumentVersion, bytes]:
    """The stored bytes after the integrity re-hash. No permission check and no audit: the caller does both (e.g. the VVB allow-list)."""
    if doc.status == "QUARANTINED":
        raise Conflict("This document is quarantined and cannot be downloaded.", error_code="DOCUMENT_QUARANTINED")
    wanted = version or doc.current_version
    v = next((x for x in doc.versions if x.version == wanted), None)
    if v is None:
        raise NotFound("Document version not found.", error_code="DOCUMENT_VERSION_NOT_FOUND")
    if not v.storage_key.startswith(doc.environment.lower() + "/"):   # a key never crosses environments
        security_event(db, ctx, "DOCUMENT_ENVIRONMENT_MISMATCH", "CRITICAL", details={"document_id": str(doc.id), "version": v.version})
        db.commit()
        raise Conflict("The stored file failed its integrity check. It has been reported.", error_code="DOCUMENT_INTEGRITY_FAILURE")
    try:
        data = get_storage().get(v.storage_key)
    except (StorageError, OSError):
        metrics.inc("storage_failures_total", {"operation": "get"})
        raise ServiceUnavailable("The document store is unavailable. Please try again later.", error_code="STORAGE_UNAVAILABLE") from None
    if hashlib.sha256(data).hexdigest() != v.checksum_sha256:
        security_event(db, ctx, "DOCUMENT_INTEGRITY_FAILURE", "CRITICAL", details={"document_id": str(doc.id), "version": v.version})
        db.commit()
        raise Conflict("The stored file failed its integrity check. It has been reported.", error_code="DOCUMENT_INTEGRITY_FAILURE")
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
                           .options(selectinload(Document.versions), selectinload(Document.scans)).order_by(Document.created_at)).all())


# ---------------------------------------------------------------- Phase 12B — scan state, rescans, quarantine and release (D12–D16)
def scan_state(doc: Document) -> str:
    """PENDING_SCAN (no scan history yet, e.g. accepted before Phase 12B) · CLEAN · NOT_SCANNED (test / demo signature scanner, explicitly
    not an antivirus result) · SCANNER_UNAVAILABLE (latest scan could not complete) · INFECTED · QUARANTINED (security hold)."""
    current = next((v for v in doc.versions if v.version == doc.current_version), None)
    latest = next((s for s in reversed(doc.scans) if current is not None and s.document_version_id == current.id), None)
    result = latest.result if latest else None
    if any(s.result == "INFECTED" for s in doc.scans) and doc.status == "QUARANTINED":
        return "INFECTED"
    if result == "ERROR":
        return "SCANNER_UNAVAILABLE"
    if doc.status == "QUARANTINED":
        return "QUARANTINED"
    return {"CLEAN": "CLEAN", "NOT_SCANNED": "NOT_SCANNED"}.get(result or "", "PENDING_SCAN")


def rescan(db: Session, ctx: RequestContext, doc: Document, trigger: str, job_id: uuid.UUID | None = None) -> list[DocumentScan]:
    """Scan every version again (stored bytes, integrity-checked first). Appends history rows; an INFECTED result quarantines the
    document (it can no longer be downloaded or referenced). Never releases anything. The caller commits."""
    rows: list[DocumentScan] = []
    storage = get_storage()
    for v in doc.versions:
        try:
            data = storage.get(v.storage_key)
        except (StorageError, OSError):
            metrics.inc("storage_failures_total", {"operation": "get"})
            rows.append(_history(db, doc, v, ScanResult("ERROR", get_scanner().name, None, None, "stored file unavailable"), trigger,
                                 ctx.user_id, job_id, None, "STORAGE_UNAVAILABLE"))
            continue
        if hashlib.sha256(data).hexdigest() != v.checksum_sha256:
            security_event(db, ctx, "DOCUMENT_INTEGRITY_FAILURE", "CRITICAL", details={"document_id": str(doc.id), "version": v.version})
            rows.append(_history(db, doc, v, ScanResult("ERROR", get_scanner().name, None, None, "stored bytes do not match SHA-256"),
                                 trigger, ctx.user_id, job_id, None, "INTEGRITY_FAILURE"))
            continue
        res, ms = _scan(data, v.file_name)
        metrics.inc("av_scans_total", {"trigger": trigger, "result": res.status})
        rows.append(_history(db, doc, v, res, trigger, ctx.user_id, job_id, ms))
    if any(r.result == "INFECTED" for r in rows):
        threats = sorted({r.threat_name or "unknown" for r in rows if r.result == "INFECTED"})
        _quarantine(db, ctx, doc, f"Rescan detected malware ({', '.join(threats)[:150]}).", "DOCUMENT_RESCAN_INFECTED", "CRITICAL")
    record(db, ctx, "DOCUMENT_RESCANNED", doc.entity_type, doc.entity_id, None,
           {"document_id": doc.id, "trigger": trigger, "results": [r.result for r in rows]}, organization_id=doc.organization_id)
    return rows


def _security_document(db: Session, principal: Principal, document_id: uuid.UUID) -> Document:
    doc = db.scalars(select(Document).where(Document.id == document_id)
                     .options(selectinload(Document.versions), selectinload(Document.scans))
                     .execution_options(populate_existing=True)).first()
    if doc is None or doc.environment != principal.user.environment:       # environment isolation (D49)
        raise NotFound("Document not found.", error_code="DOCUMENT_NOT_FOUND")
    return doc


def quarantined(db: Session, principal: Principal) -> list[Document]:
    return list(db.scalars(select(Document).where(Document.status == "QUARANTINED", Document.environment == principal.user.environment)
                           .options(selectinload(Document.versions), selectinload(Document.scans)).order_by(Document.created_at.desc())))


def scan_history(db: Session, principal: Principal, document_id: uuid.UUID) -> list[DocumentScan]:
    doc = _security_document(db, principal, document_id)
    return list(db.scalars(select(DocumentScan).where(DocumentScan.document_id == doc.id).order_by(DocumentScan.scanned_at)))


def quarantine_document(db: Session, ctx: RequestContext, principal: Principal, document_id: uuid.UUID, reason: str) -> Document:
    doc = _security_document(db, principal, document_id)
    if doc.status != "QUARANTINED":
        _quarantine(db, ctx, doc, reason, "DOCUMENT_QUARANTINED_MANUALLY", "WARNING")
        db.commit()
    return _security_document(db, principal, document_id)          # sessions keep objects after commit: reload the scan history


def request_rescan(db: Session, ctx: RequestContext, principal: Principal, document_id: uuid.UUID) -> uuid.UUID:
    """Queue a background rescan (Phase 12A job, allow-listed task); published after commit."""
    from app.models import BackgroundJob
    from app.workers import job_service
    doc = _security_document(db, principal, document_id)
    _queue_rescan(db, ctx, doc)
    db.commit()
    job = db.scalars(select(BackgroundJob).where(BackgroundJob.entity_type == "document", BackgroundJob.entity_id == str(doc.id))
                     .order_by(BackgroundJob.created_at.desc())).first()
    assert job is not None
    job_service.publish(db, job.id)
    return job.id


def release(db: Session, ctx: RequestContext, principal: Principal, document_id: uuid.UUID, reason: str) -> Document:
    """D16: a security user releases a quarantined document only after a clean rescan of every version, performed now. Any non-CLEAN
    result (INFECTED, ERROR, NOT_SCANNED by a test scanner) keeps it quarantined; the scan rows are kept either way."""
    doc = _security_document(db, principal, document_id)
    if doc.status != "QUARANTINED":
        raise Conflict("Only a quarantined document can be released.", error_code="DOCUMENT_NOT_QUARANTINED")
    rows = rescan(db, ctx, doc, "RELEASE")
    if not rows or any(r.result != "CLEAN" for r in rows):
        record(db, ctx, "DOCUMENT_RELEASE_REFUSED", doc.entity_type, doc.entity_id, None,
               {"document_id": doc.id, "results": [r.result for r in rows]}, reason, organization_id=doc.organization_id)
        db.commit()
        raise Conflict("The document stays quarantined: the release rescan was not CLEAN for every version.",
                       error_code="DOCUMENT_RELEASE_REFUSED", details={"results": [r.result for r in rows]})
    doc.status = "ACTIVE"
    record(db, ctx, "DOCUMENT_RELEASED", doc.entity_type, doc.entity_id, {"status": "QUARANTINED"},
           {"document_id": doc.id, "status": "ACTIVE", "scans": [str(r.id) for r in rows]}, reason, organization_id=doc.organization_id)
    security_event(db, ctx, "DOCUMENT_RELEASED", "INFO", details={"document_id": str(doc.id)})
    db.commit()
    return _security_document(db, principal, document_id)
