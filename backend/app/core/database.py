"""SQLAlchemy engine/session management for SQL Server."""
from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings


@lru_cache
def get_engine() -> Engine:
    s = get_settings()
    return create_engine(
        s.database_url(),
        echo=s.DB_ECHO,                 # refused in production (config guard)
        hide_parameters=True,           # D44: SQL parameters (names, phone / ID numbers) never reach logged errors or echo output
        pool_pre_ping=True,
        pool_size=10,
        max_overflow=20,
        # Read committed snapshot is enabled at DB level; keep default isolation here.
    )


@lru_cache
def get_session_factory() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), autoflush=False, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    """Request-scoped session. Services own commit(); anything uncommitted is rolled back."""
    db = get_session_factory()()
    try:
        yield db
    finally:
        db.rollback()
        db.close()
