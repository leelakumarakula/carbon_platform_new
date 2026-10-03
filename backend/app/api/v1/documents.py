import uuid
from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Response, UploadFile

from app.api.deps import DB, ActivePrincipal, Ctx, read_upload, require
from app.schemas.documents import (
    DocumentOut,
    DocumentReasonIn,
    DocumentScanOut,
    RescanQueuedOut,
    SecurityDocumentOut,
    document_out,
    security_document_out,
)
from app.security.permissions import P
from app.security.principal import Principal
from app.services import document_service as svc

# Access to a document is decided by the owning entity's resolver (farmer / farm / …). The Phase 12B security operations
# (quarantine list, scan history, quarantine, rescan, release) are for security users only and never return file content.
router = APIRouter(prefix="/evidence/documents", tags=["documents"])
CanSecRead = Annotated[Principal, Depends(require(P.SECURITY_READ))]
CanSecManage = Annotated[Principal, Depends(require(P.SECURITY_MANAGE))]


@router.get("/quarantined", response_model=list[SecurityDocumentOut], summary="Quarantined documents of your environment (security)")
def quarantined(principal: CanSecRead, db: DB) -> list[SecurityDocumentOut]:
    return [security_document_out(d) for d in svc.quarantined(db, principal)]


@router.get("/{document_id}/scans", response_model=list[DocumentScanOut], summary="Append-only antivirus scan history (security)")
def scans(document_id: uuid.UUID, principal: CanSecRead, db: DB) -> list[DocumentScanOut]:
    return [DocumentScanOut.model_validate(s) for s in svc.scan_history(db, principal, document_id)]


@router.post("/{document_id}/quarantine", response_model=SecurityDocumentOut, summary="Place a document on security hold")
def quarantine(document_id: uuid.UUID, body: DocumentReasonIn, principal: CanSecManage, db: DB, ctx: Ctx) -> SecurityDocumentOut:
    return security_document_out(svc.quarantine_document(db, ctx, principal, document_id, body.reason))


@router.post("/{document_id}/rescan", response_model=RescanQueuedOut, status_code=202, summary="Queue a background antivirus rescan")
def rescan(document_id: uuid.UUID, principal: CanSecManage, db: DB, ctx: Ctx) -> RescanQueuedOut:
    return RescanQueuedOut(job_id=svc.request_rescan(db, ctx, principal, document_id))


@router.post("/{document_id}/release", response_model=SecurityDocumentOut,
             summary="Release a quarantined document — only after a clean rescan of every version, performed now")
def release(document_id: uuid.UUID, body: DocumentReasonIn, principal: CanSecManage, db: DB, ctx: Ctx) -> SecurityDocumentOut:
    return security_document_out(svc.release(db, ctx, principal, document_id, body.reason))


@router.get("/{document_id}", response_model=DocumentOut)
def get_document(document_id: uuid.UUID, principal: ActivePrincipal, db: DB) -> DocumentOut:
    return document_out(svc.get_document(db, principal, document_id))


@router.post("/{document_id}/versions", response_model=DocumentOut, summary="Upload a new version (previous versions are kept)")
def add_version(document_id: uuid.UUID, principal: ActivePrincipal, db: DB, ctx: Ctx, file: Annotated[UploadFile, File()]) -> DocumentOut:
    return document_out(svc.add_version(db, ctx, principal, document_id, file.filename, read_upload(file)))


@router.get("/{document_id}/download", summary="Download the current (or ?version=N) file; every download is audited")
def download(document_id: uuid.UUID, principal: ActivePrincipal, db: DB, ctx: Ctx, version: int | None = None) -> Response:
    v, data = svc.download(db, ctx, principal, document_id, version)
    return Response(content=data, media_type=v.mime_type, headers={
        "Content-Disposition": f"attachment; filename*=UTF-8''{quote(v.file_name)}",
        "X-Content-Type-Options": "nosniff",
        "Content-Security-Policy": "default-src 'none'; sandbox",
        "Cache-Control": "no-store",
    })
