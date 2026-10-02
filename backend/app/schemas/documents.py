import uuid

from pydantic import BaseModel

from app.schemas.common import UtcDatetime


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


def document_out(d: object) -> DocumentOut:
    return DocumentOut(
        id=d.id, entity_type=d.entity_type, entity_id=d.entity_id, category=d.category, title=d.title,  # type: ignore[attr-defined]
        sensitivity=d.sensitivity, status=d.status, current_version=d.current_version,  # type: ignore[attr-defined]
        environment=d.environment, created_at=d.created_at,  # type: ignore[attr-defined]
        versions=[DocumentVersionOut(version=v.version, file_name=v.file_name, mime_type=v.mime_type, size_bytes=v.size_bytes,
                                     checksum_sha256=v.checksum_sha256, scan_status=v.scan_status, uploaded_by=v.uploaded_by,
                                     uploaded_at=v.uploaded_at) for v in d.versions],  # type: ignore[attr-defined]
    )
