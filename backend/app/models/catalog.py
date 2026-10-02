"""Standard / crediting route and activity catalog (spec section 7.5, section 9).

Phase 3 stores the reference entries a project links to. Methodologies, versions and the rules engine are
Phase 4; nothing here encodes eligibility or applicability rules. Entries are environment-scoped so DEMO
catalog entries can never be selected by LIVE projects.
"""
import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, Unicode, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, Environment, Timestamped, UUIDPrimaryKey, in_check, utcnow

PROGRAM_TYPES = ["VOLUNTARY", "COMPLIANCE", "OTHER"]
CATALOG_STATUSES = ["ACTIVE", "INACTIVE"]


class Standard(UUIDPrimaryKey, Timestamped, Base):
    __tablename__ = "standards"
    __table_args__ = (
        CheckConstraint(in_check("program_type", PROGRAM_TYPES), name="program_type"),
        CheckConstraint(in_check("status", CATALOG_STATUSES), name="status"),
        CheckConstraint(in_check("environment", Environment), name="environment"),
    )
    code: Mapped[str] = mapped_column(Unicode(40), unique=True)
    name: Mapped[str] = mapped_column(Unicode(200))
    owner_name: Mapped[str | None] = mapped_column(Unicode(200))       # programme owner / administrator
    program_type: Mapped[str] = mapped_column(Unicode(15))
    description: Mapped[str | None] = mapped_column(Unicode(2000))
    source_url: Mapped[str | None] = mapped_column(Unicode(500))
    status: Mapped[str] = mapped_column(Unicode(10), default="ACTIVE")
    environment: Mapped[str] = mapped_column(Unicode(10), default=Environment.LIVE.value)
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))


class Activity(UUIDPrimaryKey, Timestamped, Base):
    __tablename__ = "activities"
    __table_args__ = (
        CheckConstraint(in_check("status", CATALOG_STATUSES), name="status"),
        CheckConstraint(in_check("environment", Environment), name="environment"),
    )
    code: Mapped[str] = mapped_column(Unicode(40), unique=True)
    name: Mapped[str] = mapped_column(Unicode(200))
    category: Mapped[str | None] = mapped_column(Unicode(60))
    description: Mapped[str | None] = mapped_column(Unicode(2000))
    status: Mapped[str] = mapped_column(Unicode(10), default="ACTIVE")
    environment: Mapped[str] = mapped_column(Unicode(10), default=Environment.LIVE.value)
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))


class StandardActivity(Base):
    """Which activities are offered under which standard / route (a catalog link, not an eligibility rule)."""
    __tablename__ = "standard_activities"
    standard_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("standards.id"), primary_key=True)
    activity_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("activities.id"), primary_key=True, index=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(default=utcnow, server_default=text("SYSUTCDATETIME()"))
