"""Farm queries."""
import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models import Farm, FarmBoundary, Farmer, FarmEvidence, FarmOverlapCheck, FarmOwnership
from app.repositories.common import paginate
from app.repositories.farmers import scope_filter
from app.schemas.common import PageParams

SORTS = {"farm_code": Farm.farm_code, "name": Farm.name, "created_at": Farm.created_at, "status": Farm.status,
         "area_hectares": Farm.area_hectares, "village": Farm.village}


def get(db: Session, farm_id: uuid.UUID) -> Farm | None:
    return db.scalars(select(Farm).where(Farm.id == farm_id).execution_options(populate_existing=True)).first()


def owner_user(db: Session, farmer_id: uuid.UUID) -> uuid.UUID | None:
    return db.scalar(select(Farmer.user_id).where(Farmer.id == farmer_id))


def list_farms(db: Session, params: PageParams, *, scope: frozenset[uuid.UUID] | None, include_self: bool, user_id: uuid.UUID,
               search: str | None, status: str | None, farmer_id: uuid.UUID | None, organization_id: uuid.UUID | None,
               environment: str | None, has_open_overlaps: bool | None) -> tuple[list[Farm], int]:
    stmt = select(Farm).join(Farmer, Farmer.id == Farm.farmer_id)
    stmt = scope_filter(stmt, Farm.organization_id, Farmer.user_id, scope, include_self, user_id)
    if search:
        like = f"%{search.strip()}%"
        stmt = stmt.where(or_(Farm.farm_code.ilike(like), Farm.name.ilike(like), Farm.village.ilike(like), Farmer.full_name.ilike(like)))
    if status:
        stmt = stmt.where(Farm.status == status)
    if farmer_id:
        stmt = stmt.where(Farm.farmer_id == farmer_id)
    if organization_id:
        stmt = stmt.where(Farm.organization_id == organization_id)
    if environment:
        stmt = stmt.where(Farm.environment == environment)
    if has_open_overlaps is not None:
        sub = select(FarmOverlapCheck.id).where(FarmOverlapCheck.farm_id == Farm.id, FarmOverlapCheck.status == "OPEN").exists()
        stmt = stmt.where(sub if has_open_overlaps else ~sub)
    return paginate(db, stmt, params, SORTS, "farm_code", Farm.id)


def boundaries(db: Session, farm_id: uuid.UUID) -> list[FarmBoundary]:
    return list(db.scalars(select(FarmBoundary).where(FarmBoundary.farm_id == farm_id).order_by(FarmBoundary.version.desc())).all())


def current_boundary(db: Session, farm_id: uuid.UUID) -> FarmBoundary | None:
    return db.scalars(select(FarmBoundary).where(FarmBoundary.farm_id == farm_id, FarmBoundary.status == "CURRENT")
                      .execution_options(populate_existing=True)).first()


def overlaps(db: Session, farm_id: uuid.UUID, include_closed: bool = True) -> list[FarmOverlapCheck]:
    stmt = select(FarmOverlapCheck).where(or_(FarmOverlapCheck.farm_id == farm_id, FarmOverlapCheck.other_farm_id == farm_id))
    if not include_closed:
        stmt = stmt.where(FarmOverlapCheck.status != "OBSOLETE")
    return list(db.scalars(stmt.order_by(FarmOverlapCheck.detected_at.desc())).all())


def open_overlap_counts(db: Session, farm_ids: list[uuid.UUID]) -> dict[uuid.UUID, int]:
    if not farm_ids:
        return {}
    rows = db.execute(select(FarmOverlapCheck.farm_id, FarmOverlapCheck.other_farm_id)
                      .where(FarmOverlapCheck.status.in_(["OPEN", "CONFIRMED_CONFLICT"]),
                             or_(FarmOverlapCheck.farm_id.in_(farm_ids), FarmOverlapCheck.other_farm_id.in_(farm_ids)))).all()
    counts: dict[uuid.UUID, int] = {}
    for a, b in rows:
        for fid in (a, b):
            if fid in farm_ids:
                counts[fid] = counts.get(fid, 0) + 1
    return counts


def ownerships(db: Session, farm_id: uuid.UUID) -> list[FarmOwnership]:
    return list(db.scalars(select(FarmOwnership).where(FarmOwnership.farm_id == farm_id).order_by(FarmOwnership.recorded_at)).all())


def evidence(db: Session, farm_id: uuid.UUID) -> list[FarmEvidence]:
    return list(db.scalars(select(FarmEvidence).where(FarmEvidence.farm_id == farm_id).order_by(FarmEvidence.created_at.desc())).all())


def count(db: Session, model: type, farm_id: uuid.UUID, **where: object) -> int:
    stmt = select(func.count()).select_from(model).where(model.farm_id == farm_id)  # type: ignore[attr-defined]
    for k, v in where.items():
        stmt = stmt.where(getattr(model, k) == v)
    return db.scalar(stmt) or 0
