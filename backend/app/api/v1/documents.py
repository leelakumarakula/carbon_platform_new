import uuid
from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, File, Response, UploadFile

from app.api.deps import DB, ActivePrincipal, Ctx, read_upload
from app.schemas.documents import DocumentOut, document_out
from app.services import document_service as svc

# Access to a document is decided by the owning entity's resolver (farmer / farm / …).
router = APIRouter(prefix="/evidence/documents", tags=["documents"])


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
