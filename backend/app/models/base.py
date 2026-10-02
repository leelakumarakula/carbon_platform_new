"""Declarative base and shared column conventions (spec section 7: uniqueidentifier, datetime2, decimal)."""
import uuid
from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import MetaData, Unicode, Uuid, text
from sqlalchemy.dialects.mssql import DATETIME2
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


def utcnow() -> datetime:
    """Timestamps are stored as naive UTC in datetime2."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)
    type_annotation_map = {datetime: DATETIME2(), uuid.UUID: Uuid(), str: Unicode(255)}  # noqa: RUF012


class Environment(str, Enum):
    LIVE = "LIVE"
    DEMO = "DEMO"   # spec section 43: all demo data is marked and never mixed with real records


def in_check(column: str, values: type[Enum] | list[str]) -> str:
    vals = [v.value for v in values] if isinstance(values, type) else values
    return f"{column} IN ({', '.join(repr(v) for v in vals)})"


class UUIDPrimaryKey:
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)


class Timestamped:
    created_at: Mapped[datetime] = mapped_column(default=utcnow, server_default=text("SYSUTCDATETIME()"))
    updated_at: Mapped[datetime] = mapped_column(default=utcnow, onupdate=utcnow, server_default=text("SYSUTCDATETIME()"))
