"""In-app notifications (spec section 19). Delivery channels other than IN_APP are added with their adapter."""
import uuid
from collections.abc import Iterable

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.core.errors import NotFound
from app.models import Notification
from app.models.base import utcnow
from app.repositories.common import paginate
from app.schemas.common import PageParams


def notify(db: Session, recipients: Iterable[uuid.UUID | None], event_type: str, title: str, body: str | None = None,
           entity_type: str | None = None, entity_id: object = None, link: str | None = None) -> int:
    """Queue in-app notifications in the caller's transaction (de-duplicated recipients, None ignored)."""
    now = utcnow()
    count = 0
    for rid in {r for r in recipients if r}:
        db.add(Notification(recipient_user_id=rid, event_type=event_type, channel="IN_APP", title=title[:200],
                            body=body[:2000] if body else None, entity_type=entity_type,
                            entity_id=str(entity_id) if entity_id else None, link=link, status="SENT", sent_at=now))
        count += 1
    return count


def list_mine(db: Session, user_id: uuid.UUID, params: PageParams, unread_only: bool) -> tuple[list[Notification], int]:
    stmt = select(Notification).where(Notification.recipient_user_id == user_id)
    if unread_only:
        stmt = stmt.where(Notification.read_at.is_(None))
    return paginate(db, stmt, params, {"created_at": Notification.created_at}, "-created_at", Notification.id)


def unread_count(db: Session, user_id: uuid.UUID) -> int:
    return db.scalar(select(func.count()).select_from(Notification)
                     .where(Notification.recipient_user_id == user_id, Notification.read_at.is_(None))) or 0


def mark_read(db: Session, user_id: uuid.UUID, notification_id: uuid.UUID | None = None) -> int:
    stmt = update(Notification).where(Notification.recipient_user_id == user_id, Notification.read_at.is_(None))
    if notification_id:
        target = db.get(Notification, notification_id)
        if target is None or target.recipient_user_id != user_id:
            raise NotFound("Notification not found.", error_code="NOTIFICATION_NOT_FOUND")
        stmt = stmt.where(Notification.id == notification_id)
    n = db.execute(stmt.values(read_at=utcnow())).rowcount
    db.commit()
    return int(n or 0)
