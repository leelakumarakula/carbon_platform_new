"""Server-side pagination and whitelisted sorting (spec section 38)."""
from collections.abc import Mapping
from typing import Any, TypeVar

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.core.errors import ValidationFailed
from app.schemas.common import PageParams

T = TypeVar("T")


def apply_sort(stmt: Select[Any], params: PageParams, sort_map: Mapping[str, Any], default: str) -> Select[Any]:
    key = params.sort or default
    desc = key.startswith("-")
    name = key.lstrip("-")
    if name not in sort_map:
        raise ValidationFailed(f"Cannot sort by '{name}'.", error_code="INVALID_SORT",
                               details={"allowed": sorted(sort_map)})
    col = sort_map[name]
    return stmt.order_by(col.desc() if desc else col.asc())


def paginate(db: Session, stmt: Select[Any], params: PageParams, sort_map: Mapping[str, Any],
             default_sort: str, tiebreak: Any) -> tuple[list[Any], int]:
    total = db.scalar(select(func.count()).select_from(stmt.order_by(None).subquery())) or 0
    # SQL Server requires ORDER BY for OFFSET/FETCH; add a unique tiebreaker for stable pages.
    sorted_stmt = apply_sort(stmt, params, sort_map, default_sort).order_by(tiebreak)
    rows = db.scalars(sorted_stmt.offset(params.offset).limit(params.page_size)).unique().all()
    return list(rows), int(total)
