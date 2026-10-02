"""Farmer queries."""
import uuid

from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.models import Farm, Farmer, Organization
from app.repositories.common import paginate
from app.schemas.common import PageParams

SORTS = {"farmer_code": Farmer.farmer_code, "full_name": Farmer.full_name, "created_at": Farmer.created_at,
         "status": Farmer.status, "village": Farmer.village, "district": Farmer.district}


def get(db: Session, farmer_id: uuid.UUID) -> Farmer | None:
    return db.scalars(select(Farmer).where(Farmer.id == farmer_id)
                      .options(selectinload(Farmer.contacts), selectinload(Farmer.consents), selectinload(Farmer.agreements),
                               selectinload(Farmer.bank_accounts))
                      .execution_options(populate_existing=True)).first()


def get_by_user(db: Session, user_id: uuid.UUID) -> Farmer | None:
    return db.scalars(select(Farmer).where(Farmer.user_id == user_id)).first()


def scope_filter(stmt: Select, org_col: object, owner_col: object, scope: frozenset[uuid.UUID] | None, include_self: bool,
                 user_id: uuid.UUID) -> Select:
    if scope is None:
        return stmt
    clauses = []
    if scope:
        clauses.append(org_col.in_(list(scope)))  # type: ignore[attr-defined]
    if include_self:
        clauses.append(owner_col == user_id)
    return stmt.where(or_(*clauses))


def list_farmers(db: Session, params: PageParams, *, scope: frozenset[uuid.UUID] | None, include_self: bool, user_id: uuid.UUID,
                 search: str | None, status: str | None, organization_id: uuid.UUID | None, environment: str | None
                 ) -> tuple[list[Farmer], int]:
    stmt = scope_filter(select(Farmer), Farmer.organization_id, Farmer.user_id, scope, include_self, user_id)
    if search:
        like = f"%{search.strip()}%"
        stmt = stmt.where(or_(Farmer.full_name.ilike(like), Farmer.farmer_code.ilike(like), Farmer.village.ilike(like),
                              Farmer.district.ilike(like)))
    if status:
        stmt = stmt.where(Farmer.status == status)
    if organization_id:
        stmt = stmt.where(Farmer.organization_id == organization_id)
    if environment:
        stmt = stmt.where(Farmer.environment == environment)
    return paginate(db, stmt, params, SORTS, "farmer_code", Farmer.id)


def farm_counts(db: Session, farmer_ids: list[uuid.UUID]) -> dict[uuid.UUID, int]:
    if not farmer_ids:
        return {}
    return dict(db.execute(select(Farm.farmer_id, func.count()).where(Farm.farmer_id.in_(farmer_ids))
                           .group_by(Farm.farmer_id)).tuples().all())


def org_names(db: Session, org_ids: set[uuid.UUID]) -> dict[uuid.UUID, str]:
    if not org_ids:
        return {}
    return dict(db.execute(select(Organization.id, Organization.name).where(Organization.id.in_(list(org_ids)))).tuples().all())


def kyc_duplicates(db: Session, kyc_hash: str, environment: str, exclude_id: uuid.UUID) -> list[uuid.UUID]:
    return list(db.scalars(select(Farmer.id).where(Farmer.kyc_id_hash == kyc_hash, Farmer.environment == environment,
                                                   Farmer.id != exclude_id)).all())
