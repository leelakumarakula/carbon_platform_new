"""SQL-side organization scoping (Phase 12B D32).

`org_predicate(principal, codes, column)` is the SQL form of `any(principal.can_in_org(c, row.<column>) for c in codes)`:
- a platform-wide grant of any of the codes -> every row (TRUE);
- otherwise rows whose organization is one where the caller holds one of the codes (a NULL organization never matches);
- no grant at all -> no row (FALSE).
It lets listings filter in the database instead of loading whole tables and filtering in Python, with exactly the same visibility.
"""
from collections.abc import Iterable
from typing import Any

from sqlalchemy import ColumnElement, false, select, true
from sqlalchemy.orm import Session

from app.security.principal import Principal


def org_predicate(principal: Principal, codes: Iterable[str], column: Any) -> ColumnElement[bool]:
    codes = tuple(codes)
    if any(principal.has_platform(c) for c in codes):
        return true()
    orgs = {g.organization_id for g in principal.grants if g.organization_id is not None and any(c in g.permissions for c in codes)}
    return column.in_(sorted(orgs, key=str)) if orgs else false()


def preload(db: Session, model: Any, ids: Iterable[Any]) -> None:
    """Load rows by primary key in bulk so mappers' per-row `db.get` calls are served from the identity map (no N+1)."""
    wanted = sorted({i for i in ids if i is not None}, key=str)
    for start in range(0, len(wanted), 1000):
        db.scalars(select(model).where(model.id.in_(wanted[start:start + 1000]))).all()
