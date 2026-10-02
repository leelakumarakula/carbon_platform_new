import uuid

from fastapi import APIRouter
from pydantic import BaseModel

from app.api.deps import DB, ActivePrincipal, Paging
from app.schemas.common import Page, UtcDatetime
from app.services import notification_service as svc

router = APIRouter(prefix="/notifications", tags=["notifications"])


class NotificationOut(BaseModel):
    id: uuid.UUID
    event_type: str
    channel: str
    title: str
    body: str | None
    entity_type: str | None
    entity_id: str | None
    link: str | None
    status: str
    sent_at: UtcDatetime | None
    read_at: UtcDatetime | None
    created_at: UtcDatetime


class Count(BaseModel):
    unread: int


class Marked(BaseModel):
    marked: int


@router.get("", response_model=Page[NotificationOut], summary="My notifications")
def mine(principal: ActivePrincipal, db: DB, paging: Paging, unread_only: bool = False) -> Page[NotificationOut]:
    rows, total = svc.list_mine(db, principal.user_id, paging, unread_only)
    return Page(items=[NotificationOut.model_validate(r, from_attributes=True) for r in rows], total=total,
                page=paging.page, page_size=paging.page_size)


@router.get("/unread-count", response_model=Count)
def unread(principal: ActivePrincipal, db: DB) -> Count:
    return Count(unread=svc.unread_count(db, principal.user_id))


@router.post("/{notification_id}/read", response_model=Marked)
def read_one(notification_id: uuid.UUID, principal: ActivePrincipal, db: DB) -> Marked:
    return Marked(marked=svc.mark_read(db, principal.user_id, notification_id))


@router.post("/read-all", response_model=Marked)
def read_all(principal: ActivePrincipal, db: DB) -> Marked:
    return Marked(marked=svc.mark_read(db, principal.user_id))

