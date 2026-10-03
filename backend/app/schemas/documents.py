import uuid

from pydantic import BaseModel, ConfigDict

from app.schemas.common import Reason, UtcDatetime


class DocumentVersionOut(BaseModel):
    version: int
    file_name: str
    mime_type: str
    size_bytes: int
    checksum_sha256: str
    scan_status: str
    uploaded_by: uuid.UUID | None
    uploaded_at: UtcDatetime


class DocumentOut(BaseModel):
    id: uuid.UUID
    entity_type: str
    entity_id: uuid.UUID
    category: str
    title: str
    sensitivity: str
    status: str
    current_version: int
    environment: str
    created_at: UtcDatetime
    versions: list[DocumentVersionOut]
    scan_state: str          # Phase 12B: PENDING_SCAN / CLEAN / NOT_SCANNED / SCANNER_UNAVAILABLE / INFECTED / QUARANTINED


def document_out(d: object) -> DocumentOut:
    from app.services.document_service import scan_state
    return DocumentOut(
        id=d.id, entity_type=d.entity_type, entity_id=d.entity_id, category=d.category, title=d.title,  # type: ignore[attr-defined]
        sensitivity=d.sensitivity, status=d.status, current_version=d.current_version,  # type: ignore[attr-defined]
        environment=d.environment, created_at=d.created_at,  # type: ignore[attr-defined]
        versions=[DocumentVersionOut(version=v.version, file_name=v.file_name, mime_type=v.mime_type, size_bytes=v.size_bytes,
                                     checksum_sha256=v.checksum_sha256, scan_status=v.scan_status, uploaded_by=v.uploaded_by,
                                     uploaded_at=v.uploaded_at) for v in d.versions],  # type: ignore[attr-defined]
        scan_state=scan_state(d),  # type: ignore[arg-type]
    )


class DocumentScanOut(BaseModel):
    """One append-only scan-history row (Phase 12B D15)."""
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    document_id: uuid.UUID
    document_version_id: uuid.UUID
    checksum_sha256: str
    result: str
    provider: str
    engine_version: str | None
    threat_name: str | None
    error_code: str | None
    detail: str | None
    trigger_type: str
    background_job_id: uuid.UUID | None
    actor_id: uuid.UUID | None
    duration_ms: int | None
    scanned_at: UtcDatetime


class SecurityDocumentOut(DocumentOut):
    """A quarantined document as the security team sees it: no file content, the owning organisation and the latest scan."""
    organization_id: uuid.UUID
    latest_scan: DocumentScanOut | None


def security_document_out(d: object) -> SecurityDocumentOut:
    scans = list(d.scans)  # type: ignore[attr-defined]
    return SecurityDocumentOut(**document_out(d).model_dump(), organization_id=d.organization_id,  # type: ignore[attr-defined]
                               latest_scan=DocumentScanOut.model_validate(scans[-1]) if scans else None)


class DocumentReasonIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: Reason


class RescanQueuedOut(BaseModel):
    job_id: uuid.UUID
