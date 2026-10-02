"""Notifications (spec section 19). In-app now; email/SMS/WhatsApp go through a provider adapter later."""
import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, Unicode, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDPrimaryKey, in_check, utcnow


class Notification(UUIDPrimaryKey, Base):
    __tablename__ = "notifications"
    __table_args__ = (
        CheckConstraint(in_check("channel", ["IN_APP", "EMAIL", "SMS", "WHATSAPP"]), name="channel"),
        CheckConstraint(in_check("status", ["PENDING", "SENT", "FAILED"]), name="status"),
        Index("ix_notifications_recipient_unread", "recipient_user_id", "read_at"),
    )
    recipient_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    event_type: Mapped[str] = mapped_column(Unicode(60))
    channel: Mapped[str] = mapped_column(Unicode(10), default="IN_APP")
    title: Mapped[str] = mapped_column(Unicode(200))
    body: Mapped[str | None] = mapped_column(Unicode(2000))
    entity_type: Mapped[str | None] = mapped_column(Unicode(40))
    entity_id: Mapped[str | None] = mapped_column(Unicode(64))
    link: Mapped[str | None] = mapped_column(Unicode(300))
    status: Mapped[str] = mapped_column(Unicode(10), default="PENDING")
    sent_at: Mapped[datetime | None]
    read_at: Mapped[datetime | None]
    error: Mapped[str | None] = mapped_column(Unicode(1000))
    retry_count: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    created_at: Mapped[datetime] = mapped_column(default=utcnow, server_default=text("SYSUTCDATETIME()"))
