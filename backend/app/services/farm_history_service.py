"""Version-preserving land / crop / practice history (spec §10; "farm history must be history-preserving").

A record has a stable record_id. Creating it inserts version 1. Amending inserts version n+1 (with a reason)
and flips the previous version's is_current flag — the content of older versions is never modified.
Retracting inserts a final version with is_retracted = 1. Reviewing sets verification_status on the
current version and is audited.
"""
import uuid
from datetime import date
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ValidationError
from sqlalchemy import false, select, true
from sqlalchemy.orm import Session

from app.audit.service import record
from app.core.context import RequestContext
from app.core.errors import Conflict, NotFound, ValidationFailed
from app.models import Farm, FarmCropHistory, FarmLandHistory, FarmPracticeHistory
from app.models.base import utcnow
from app.schemas.farms import CropHistoryIn, HistoryOut, LandHistoryIn, PracticeHistoryIn

KINDS: dict[str, tuple[type, type[BaseModel]]] = {
    "land": (FarmLandHistory, LandHistoryIn),
    "crop": (FarmCropHistory, CropHistoryIn),
    "practice": (FarmPracticeHistory, PracticeHistoryIn),
}
COMMON = {"source", "evidence_document_id", "notes"}
EDITABLE_STATUSES = {"DRAFT", "SUBMITTED", "GIS_REVIEW", "VERIFIED", "REJECTED"}


def _kind(kind: str) -> tuple[type, type[BaseModel]]:
    if kind not in KINDS:
        raise NotFound("Unknown history type.", error_code="HISTORY_KIND_NOT_FOUND")
    return KINDS[kind]


def fields_of(kind: str, row: Any) -> dict[str, Any]:
    _, schema = _kind(kind)
    return {k: getattr(row, k) for k in schema.model_fields if k not in COMMON}


def to_out(kind: str, row: Any) -> HistoryOut:
    return HistoryOut(id=row.id, record_id=row.record_id, version=row.version, is_current=row.is_current,
                      is_retracted=row.is_retracted, source=row.source, evidence_document_id=row.evidence_document_id,
                      verification_status=row.verification_status, reviewed_by=row.reviewed_by, reviewed_at=row.reviewed_at,
                      review_notes=row.review_notes, change_reason=row.change_reason, notes=row.notes,
                      recorded_by=row.recorded_by, recorded_at=row.recorded_at, fields=_jsonable(fields_of(kind, row)))


def _jsonable(d: dict[str, Any]) -> dict[str, Any]:
    def conv(v: Any) -> Any:
        if isinstance(v, Decimal):
            return format(v.normalize(), "f")  # stable text form: 2.100 and 2.1 both render as "2.1"
        return v.isoformat() if isinstance(v, date) else v
    return {k: conv(v) for k, v in d.items()}


def _check_editable(farm: Farm) -> None:
    if farm.status not in EDITABLE_STATUSES:
        raise Conflict(f"History cannot be changed while the farm is {farm.status}.", error_code="FARM_NOT_EDITABLE")


def _current(db: Session, model: type, farm_id: uuid.UUID, record_id: uuid.UUID) -> Any:
    row = db.scalars(select(model).where(model.farm_id == farm_id, model.record_id == record_id, model.is_current == true())  # type: ignore[attr-defined]
                     .execution_options(populate_existing=True)).first()
    if row is None:
        raise NotFound("History record not found.", error_code="HISTORY_NOT_FOUND")
    return row


def list_history(db: Session, farm_id: uuid.UUID, kind: str, include_retracted: bool = False) -> list[HistoryOut]:
    model, _ = _kind(kind)
    stmt: Any = select(model).where(model.farm_id == farm_id, model.is_current == true())  # type: ignore[attr-defined]
    if not include_retracted:
        stmt = stmt.where(model.is_retracted == false())  # type: ignore[attr-defined]
    rows: Any = db.scalars(stmt.order_by(model.year.desc(), model.recorded_at.desc())).all()  # type: ignore[attr-defined]
    return [to_out(kind, r) for r in rows]


def versions(db: Session, farm_id: uuid.UUID, kind: str, record_id: uuid.UUID) -> list[HistoryOut]:
    model, _ = _kind(kind)
    rows: Any = db.scalars(select(model).where(model.farm_id == farm_id, model.record_id == record_id)  # type: ignore[attr-defined]
                      .order_by(model.version)).all()  # type: ignore[attr-defined]
    if not rows:
        raise NotFound("History record not found.", error_code="HISTORY_NOT_FOUND")
    return [to_out(kind, r) for r in rows]


def add(db: Session, ctx: RequestContext, farm: Farm, kind: str, data: BaseModel) -> HistoryOut:
    model, _ = _kind(kind)
    _check_editable(farm)
    row = model(farm_id=farm.id, record_id=uuid.uuid4(), version=1, is_current=True, recorded_by=ctx.user_id,
                **data.model_dump())
    db.add(row)
    db.flush()
    record(db, ctx, "FARM_HISTORY_RECORDED", "farm", farm.id, None,
           {"kind": kind, "record_id": row.record_id, **_jsonable(data.model_dump())}, organization_id=farm.organization_id)
    return to_out(kind, row)


def amend(db: Session, ctx: RequestContext, farm: Farm, kind: str, record_id: uuid.UUID, changes: dict[str, Any],
          reason: str) -> HistoryOut:
    model, schema = _kind(kind)
    _check_editable(farm)
    cur = _current(db, model, farm.id, record_id)
    if cur.is_retracted:
        raise Conflict("A retracted record cannot be amended.", error_code="HISTORY_RETRACTED")
    merged = {k: getattr(cur, k) for k in schema.model_fields} | changes
    try:
        validated = schema.model_validate(merged)
    except ValidationError as e:
        raise ValidationFailed("The amended record is invalid.", details={"errors": [
            {"field": ".".join(str(p) for p in err["loc"]), "message": err["msg"]} for err in e.errors()]}) from e
    new_values = validated.model_dump()
    old_values = {k: getattr(cur, k) for k in new_values}
    if new_values == old_values:
        raise ValidationFailed("Nothing changed.", error_code="NO_CHANGES")
    cur.is_current = False
    db.flush()
    row = model(farm_id=farm.id, record_id=record_id, version=cur.version + 1, is_current=True, change_reason=reason,
                recorded_by=ctx.user_id, **new_values)
    db.add(row)
    db.flush()
    diff_old = {k: v for k, v in old_values.items() if new_values[k] != v}
    record(db, ctx, "FARM_HISTORY_AMENDED", "farm", farm.id, {"kind": kind, "record_id": record_id, "version": cur.version,
                                                              **_jsonable(diff_old)},
           {"kind": kind, "record_id": record_id, "version": row.version, **_jsonable({k: new_values[k] for k in diff_old})},
           reason, organization_id=farm.organization_id)
    return to_out(kind, row)


def retract(db: Session, ctx: RequestContext, farm: Farm, kind: str, record_id: uuid.UUID, reason: str) -> HistoryOut:
    model, schema = _kind(kind)
    _check_editable(farm)
    cur = _current(db, model, farm.id, record_id)
    if cur.is_retracted:
        raise Conflict("This record is already retracted.", error_code="HISTORY_RETRACTED")
    cur.is_current = False
    db.flush()
    row = model(farm_id=farm.id, record_id=record_id, version=cur.version + 1, is_current=True, is_retracted=True,
                change_reason=reason, recorded_by=ctx.user_id, **{k: getattr(cur, k) for k in schema.model_fields})
    db.add(row)
    db.flush()
    record(db, ctx, "FARM_HISTORY_RETRACTED", "farm", farm.id, {"kind": kind, "record_id": record_id, "version": cur.version},
           {"version": row.version, "is_retracted": True}, reason, organization_id=farm.organization_id)
    return to_out(kind, row)


def review(db: Session, ctx: RequestContext, farm: Farm, kind: str, record_id: uuid.UUID, status: str, notes: str) -> HistoryOut:
    model, _ = _kind(kind)
    cur = _current(db, model, farm.id, record_id)
    if cur.is_retracted:
        raise Conflict("A retracted record cannot be reviewed.", error_code="HISTORY_RETRACTED")
    old = cur.verification_status
    cur.verification_status, cur.reviewed_by, cur.reviewed_at, cur.review_notes = status, ctx.user_id, utcnow(), notes
    record(db, ctx, "FARM_HISTORY_REVIEWED", "farm", farm.id, {"kind": kind, "record_id": record_id, "verification_status": old},
           {"verification_status": status}, notes, organization_id=farm.organization_id)
    return to_out(kind, cur)


def counts(db: Session, farm_id: uuid.UUID) -> dict[str, int]:
    from sqlalchemy import func
    out = {}
    for kind, (model, _) in KINDS.items():
        out[kind] = db.scalar(select(func.count()).select_from(model).where(
            model.farm_id == farm_id, model.is_current == true(), model.is_retracted == false())) or 0  # type: ignore[attr-defined]
    return out
