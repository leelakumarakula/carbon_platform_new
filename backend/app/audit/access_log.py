"""Writes api_access_logs rows in their own short transaction (never the request's)."""
import logging
from typing import Any

from app.core.database import get_session_factory
from app.models import ApiAccessLog

log = logging.getLogger("app.access")


def db_access_log_writer(entry: dict[str, Any]) -> None:
    with get_session_factory()() as db:
        db.add(ApiAccessLog(**entry))
        db.commit()
