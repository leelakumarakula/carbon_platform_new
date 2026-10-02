"""Standard / route and activity catalog (spec section 7.5). Reference data only: no methodology logic,
no eligibility or applicability rules (those are Phase 4). Entries are deactivated, never deleted."""
import uuid

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.audit.service import record, snapshot
from app.core.context import RequestContext
from app.core.errors import Conflict, NotFound, ValidationFailed
from app.models import Activity, Standard, StandardActivity
from app.schemas.projects import ActivityIn, ActivityOut, ActivityUpdate, StandardIn, StandardOut, StandardUpdate
from app.security.permissions import P
from app.security.principal import Principal

STANDARD_FIELDS = ("code", "name", "owner_name", "program_type", "description", "source_url", "status", "environment")
ACTIVITY_FIELDS = ("code", "name", "category", "description", "status", "environment")


def _links(db: Session) -> list[tuple[uuid.UUID, uuid.UUID]]:
    return [(r[0], r[1]) for r in db.execute(select(StandardActivity.standard_id, StandardActivity.activity_id)).all()]


def standard_out(s: Standard, links: list[tuple[uuid.UUID, uuid.UUID]]) -> StandardOut:
    return StandardOut.model_validate({**{f: getattr(s, f) for f in STANDARD_FIELDS}, "id": s.id,
                                       "activity_ids": [a for (st, a) in links if st == s.id]})


def activity_out(a: Activity, links: list[tuple[uuid.UUID, uuid.UUID]]) -> ActivityOut:
    return ActivityOut.model_validate({**{f: getattr(a, f) for f in ACTIVITY_FIELDS}, "id": a.id,
                                       "standard_ids": [st for (st, x) in links if x == a.id]})


def list_standards(db: Session, environment: str | None = None, active_only: bool = False) -> list[StandardOut]:
    stmt = select(Standard)
    if environment:
        stmt = stmt.where(Standard.environment == environment)
    if active_only:
        stmt = stmt.where(Standard.status == "ACTIVE")
    links = _links(db)
    return [standard_out(s, links) for s in db.scalars(stmt.order_by(Standard.name)).all()]


def list_activities(db: Session, environment: str | None = None, standard_id: uuid.UUID | None = None,
                    active_only: bool = False) -> list[ActivityOut]:
    stmt = select(Activity)
    if environment:
        stmt = stmt.where(Activity.environment == environment)
    if active_only:
        stmt = stmt.where(Activity.status == "ACTIVE")
    if standard_id:
        stmt = stmt.join(StandardActivity, StandardActivity.activity_id == Activity.id).where(StandardActivity.standard_id == standard_id)
    links = _links(db)
    return [activity_out(a, links) for a in db.scalars(stmt.order_by(Activity.name)).all()]


def _manage(principal: Principal) -> None:
    principal.require_in_org(P.STANDARDS_MANAGE, None)  # catalog is platform reference data


def create_standard(db: Session, ctx: RequestContext, principal: Principal, data: StandardIn) -> StandardOut:
    _manage(principal)
    if db.scalars(select(Standard).where(Standard.code == data.code)).first():
        raise Conflict(f"A standard with code {data.code} already exists.", error_code="CODE_EXISTS")
    s = Standard(created_by=principal.user_id, **data.model_dump())
    db.add(s)
    db.flush()
    record(db, ctx, "STANDARD_CREATED", "standard", s.id, None, snapshot(s, STANDARD_FIELDS))
    db.commit()
    return standard_out(s, _links(db))


def update_standard(db: Session, ctx: RequestContext, principal: Principal, standard_id: uuid.UUID, data: StandardUpdate) -> StandardOut:
    _manage(principal)
    s = db.get(Standard, standard_id)
    if s is None:
        raise NotFound("Standard not found.", error_code="STANDARD_NOT_FOUND")
    changes = data.model_dump(exclude_unset=True)
    old = {k: getattr(s, k) for k in changes}
    for k, v in changes.items():
        setattr(s, k, v)
    if old != changes:
        record(db, ctx, "STANDARD_UPDATED", "standard", s.id, old, changes)
    db.commit()
    return standard_out(s, _links(db))


def create_activity(db: Session, ctx: RequestContext, principal: Principal, data: ActivityIn) -> ActivityOut:
    _manage(principal)
    if db.scalars(select(Activity).where(Activity.code == data.code)).first():
        raise Conflict(f"An activity with code {data.code} already exists.", error_code="CODE_EXISTS")
    a = Activity(created_by=principal.user_id, **data.model_dump(exclude={"standard_ids"}))
    db.add(a)
    db.flush()
    record(db, ctx, "ACTIVITY_CREATED", "activity", a.id, None, snapshot(a, ACTIVITY_FIELDS))
    for sid in data.standard_ids:
        _link(db, ctx, principal, a, sid)
    db.commit()
    return activity_out(a, _links(db))


def update_activity(db: Session, ctx: RequestContext, principal: Principal, activity_id: uuid.UUID, data: ActivityUpdate) -> ActivityOut:
    _manage(principal)
    a = db.get(Activity, activity_id)
    if a is None:
        raise NotFound("Activity not found.", error_code="ACTIVITY_NOT_FOUND")
    changes = data.model_dump(exclude_unset=True)
    old = {k: getattr(a, k) for k in changes}
    for k, v in changes.items():
        setattr(a, k, v)
    if old != changes:
        record(db, ctx, "ACTIVITY_UPDATED", "activity", a.id, old, changes)
    db.commit()
    return activity_out(a, _links(db))


def _link(db: Session, ctx: RequestContext, principal: Principal, a: Activity, standard_id: uuid.UUID) -> None:
    s = db.get(Standard, standard_id)
    if s is None:
        raise NotFound("Standard not found.", error_code="STANDARD_NOT_FOUND")
    if s.environment != a.environment:
        raise ValidationFailed("Demo and live catalog entries cannot be linked.", error_code="ENVIRONMENT_MISMATCH")
    if db.get(StandardActivity, (s.id, a.id)):
        raise Conflict("This activity is already linked to the standard.", error_code="ALREADY_LINKED")
    db.add(StandardActivity(standard_id=s.id, activity_id=a.id, created_by=principal.user_id))
    try:
        with db.begin_nested():
            db.flush()
    except IntegrityError as e:
        raise Conflict("This activity is already linked to the standard.", error_code="ALREADY_LINKED") from e
    record(db, ctx, "ACTIVITY_LINKED_TO_STANDARD", "activity", a.id, None, {"standard_id": s.id, "standard_code": s.code})


def link_activity(db: Session, ctx: RequestContext, principal: Principal, activity_id: uuid.UUID, standard_id: uuid.UUID) -> ActivityOut:
    _manage(principal)
    a = db.get(Activity, activity_id)
    if a is None:
        raise NotFound("Activity not found.", error_code="ACTIVITY_NOT_FOUND")
    _link(db, ctx, principal, a, standard_id)
    db.commit()
    return activity_out(a, _links(db))


def is_linked(db: Session, standard_id: uuid.UUID, activity_id: uuid.UUID) -> bool:
    return db.get(StandardActivity, (standard_id, activity_id)) is not None
