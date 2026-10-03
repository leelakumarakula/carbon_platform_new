"""Phase 9A credits API (`/api/v1/credits`) — READ-ONLY registry-issued credit batches. No inventory, ownership, reservation, transfer or
retirement endpoint exists (Phase 9B / later)."""
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.deps import DB, require_any
from app.schemas.registry import BatchOut, LineageOut
from app.security.permissions import P
from app.security.principal import Principal
from app.services import registry_access as ra
from app.services import registry_mappers as rm

router = APIRouter(prefix="/credits", tags=["credits — issued batches (read-only)"])

Reader = Annotated[Principal, Depends(require_any(P.CREDITS_READ))]


@router.get("/batches", response_model=list[BatchOut], summary="Registry-issued credit batches (ISSUED, plus SUPERSEDED / CANCELLED history)")
def list_batches(principal: Reader, db: DB, project_id: uuid.UUID | None = None, period_id: uuid.UUID | None = None) -> list[BatchOut]:
    if project_id:
        ra.credits_project(db, principal, project_id)
    return [rm.batch_out(db, b) for b in rm.batches(db, principal, project_id, period_id)]


@router.get("/batches/{batch_id}", response_model=BatchOut)
def get_batch(batch_id: uuid.UUID, principal: Reader, db: DB) -> BatchOut:
    b, _ = ra.batch_for(db, principal, batch_id)
    return rm.batch_out(db, b)


@router.get("/batches/{batch_id}/lineage", response_model=LineageOut,
            summary="batch → issuance → registry submission → VVB decision → … → calculation → farms → farmer codes")
def batch_lineage(batch_id: uuid.UUID, principal: Reader, db: DB) -> LineageOut:
    b, _ = ra.batch_for(db, principal, batch_id)
    return LineageOut(**rm.lineage(db, principal, b))
