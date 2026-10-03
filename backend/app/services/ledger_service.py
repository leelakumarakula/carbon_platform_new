"""Phase 9B credit ledger engine (D1–D21). Registry-issued 9A batches enter the ledger only through a dual-control opening; from then on
every balance change consumes immutable positions and creates new ones under one append-only entry, validated by the database when the
entry is posted (inputs = outputs, batch conservation, consume-once, RETIRED terminal).

Concurrency (D5, D10) — READ_COMMITTED_SNAPSHOT is ON, so no balance decision is ever made from a snapshot read:
  1. candidate positions are read WITH (UPDLOCK, HOLDLOCK, ROWLOCK) in deterministic order (batch → serial range → position id);
  2. each is consumed by a guarded UPDATE … WHERE status = 'OPEN' that must affect exactly one row;
  3. outputs are inserted and the entry is posted in the same transaction (one commit — nothing intermediate is ever visible).
A loser gets 409 INSUFFICIENT_AVAILABLE and a CREDIT_DOUBLE_SPEND_CONFLICT audit row; a deadlock victim is retried.

Registry boundary (X1, D12, D20): REGISTRY transfers and every retirement reach their final state only with registry evidence recorded by a
second person; nothing is sent to or simulated for a registry; inventory reconciliation is manual and never auto-fixes.
"""
import json
import uuid
from collections.abc import Callable
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, TypeVar

from sqlalchemy import func, select, update
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app.audit.service import record
from app.core.context import RequestContext
from app.core.errors import Conflict, NotFound, PermissionDenied, ValidationFailed
from app.models import (
    CreditBatch,
    CreditIssuance,
    CreditLedgerEntry,
    CreditOpening,
    CreditPosition,
    CreditReservation,
    CreditRetirement,
    CreditReversal,
    CreditSerialRange,
    CreditTransfer,
    Document,
    Organization,
    Project,
    RegistryAccount,
    RegistryEvent,
    WorkflowEvent,
)
from app.models.base import utcnow
from app.models.documents import DocumentCategory
from app.repositories.sequences import next_code
from app.security.permissions import P
from app.security.principal import Principal
from app.services import document_service
from app.services.workflows import (
    CREDIT_OPENING_MACHINE,
    CREDIT_RESERVATION_MACHINE,
    CREDIT_RETIREMENT_MACHINE,
    CREDIT_REVERSAL_MACHINE,
    CREDIT_TRANSFER_MACHINE,
)

T = TypeVar("T")
LOCK_HINT = "WITH (UPDLOCK, HOLDLOCK, ROWLOCK)"
RECIPIENT_ORG_TYPES = ("BUYER", "PROJECT_DEVELOPER")
TRANSFER_ENTITY, RETIREMENT_ENTITY, ACCOUNT_ENTITY = "credit_transfer", "credit_retirement", "registry_account"
PROJECT_READ = (P.CREDITS_READ, P.CREDITS_MANAGE, P.CREDITS_CONFIRM)


class InsufficientAvailable(Conflict):
    status_code, error_code, message = 409, "INSUFFICIENT_AVAILABLE", "Not enough credits are available for this operation."


def _before_post(entry: CreditLedgerEntry) -> None:
    """Test seam (fault injection): called after positions are consumed / created and before the entry is posted. No-op."""


# ---------------------------------------------------------------- access helpers
def _nf(what: str, code: str) -> NotFound:
    return NotFound(f"{what} not found.", error_code=code)


def batch_project(db: Session, batch: CreditBatch) -> Project:
    p = db.get(Project, batch.project_id)
    assert p is not None
    return p


def get_batch(db: Session, batch_id: uuid.UUID) -> CreditBatch:
    b = db.get(CreditBatch, batch_id)
    if b is None:
        raise _nf("Credit batch", "CREDIT_BATCH_NOT_FOUND")
    return b


def holds_in_batch(db: Session, batch_id: uuid.UUID, org_id: uuid.UUID) -> bool:
    return db.scalar(select(func.count()).select_from(CreditPosition).where(CreditPosition.batch_id == batch_id,
                                                                            CreditPosition.owner_organization_id == org_id)) != 0


def can_see_batch(db: Session, principal: Principal, b: CreditBatch) -> bool:
    p = batch_project(db, b)
    if any(principal.can_in_org(c, p.organization_id) for c in PROJECT_READ):
        return True
    orgs = {g.organization_id for g in principal.grants if g.organization_id and g.permissions & {P.CREDITS_MANAGE, P.CREDITS_CONFIRM}}
    return any(holds_in_batch(db, b.id, o) for o in orgs)


def visible_batch(db: Session, principal: Principal, batch_id: uuid.UUID) -> CreditBatch:
    b = get_batch(db, batch_id)
    if not can_see_batch(db, principal, b):
        raise _nf("Credit batch", "CREDIT_BATCH_NOT_FOUND")
    return b


def require_in_org(principal: Principal, org_id: uuid.UUID, *codes: str, visible: tuple[str, ...] = ()) -> None:
    if any(principal.can_in_org(c, org_id) for c in codes):
        return
    if any(principal.can_in_org(c, org_id) for c in (*visible, *PROJECT_READ, P.CREDITS_HOLDER_READ, P.CREDITS_HOLDER_RETIRE)):
        raise PermissionDenied(details={"required_permission": " or ".join(codes)})
    raise NotFound("Organization not found.", error_code="ORGANIZATION_NOT_FOUND")


def custodian_org(db: Session, position: CreditPosition) -> uuid.UUID:
    """The organization holding the registry account the credits sit in (it acts at the registry); else the owner."""
    if position.holding_registry_account_id:
        a = db.get(RegistryAccount, position.holding_registry_account_id)
        if a is not None:
            return a.organization_id
    return position.owner_organization_id


def _org(db: Session, org_id: uuid.UUID) -> Organization:
    o = db.get(Organization, org_id)
    if o is None:
        raise NotFound("Organization not found.", error_code="ORGANIZATION_NOT_FOUND")
    return o


def audit(db: Session, ctx: RequestContext, action: str, entity_type: str, entity_id: Any, orgs: list[uuid.UUID | None],
          payload: dict[str, Any], reason: str | None = None, old: dict[str, Any] | None = None) -> None:
    for org in dict.fromkeys(o for o in orgs if o):                # two-organization pattern (8B), de-duplicated
        record(db, ctx, action, entity_type, entity_id, old, payload, reason, organization_id=org)


def workflow(db: Session, ctx: RequestContext, entity_type: str, entity_id: Any, frm: str | None, to: str, reason: str | None) -> None:
    db.add(WorkflowEvent(entity_type=entity_type, entity_id=str(entity_id), from_status=frm, to_status=to, user_id=ctx.user_id, reason=reason,
                         request_id=ctx.request_id))


# ---------------------------------------------------------------- transaction runner
def _is_deadlock(e: DBAPIError) -> bool:
    return "1205" in str(e.orig) or "deadlock" in str(e.orig).lower()


def run(db: Session, ctx: RequestContext, op: Callable[[], T], *, conflict_org: uuid.UUID | None = None, batch_id: uuid.UUID | None = None,
        attempts: int = 3) -> T:
    """One transaction per attempt; deadlock victims are retried; an insufficient balance is audited as a double-spend conflict."""
    for attempt in range(attempts):
        try:
            result = op()
            db.commit()
            return result
        except InsufficientAvailable as e:
            db.rollback()
            if conflict_org is not None:
                record(db, ctx, "CREDIT_DOUBLE_SPEND_CONFLICT", "credit_batch", batch_id, None, {**e.details, "message": e.message},
                       organization_id=conflict_org)
                db.commit()
            raise
        except DBAPIError as e:
            db.rollback()
            if _is_deadlock(e) and attempt < attempts - 1:
                continue
            raise
        except Exception:
            db.rollback()
            raise
    raise AssertionError("unreachable")


# ---------------------------------------------------------------- position engine
def lock_positions(db: Session, batch_id: uuid.UUID, *, owner_id: uuid.UUID | None = None, state: str | None = None,
                   serial_range_id: uuid.UUID | None = None, reservation_id: uuid.UUID | None = None, transfer_id: uuid.UUID | None = None,
                   retirement_id: uuid.UUID | None = None, entry_id: uuid.UUID | None = None) -> list[CreditPosition]:
    stmt = (select(CreditPosition).with_hint(CreditPosition, LOCK_HINT, "mssql")
            .where(CreditPosition.batch_id == batch_id, CreditPosition.status == "OPEN")
            .order_by(CreditPosition.batch_id, CreditPosition.serial_range_id, CreditPosition.id)
            .execution_options(populate_existing=True))
    for col, val in ((CreditPosition.owner_organization_id, owner_id), (CreditPosition.state, state),
                     (CreditPosition.serial_range_id, serial_range_id), (CreditPosition.reservation_id, reservation_id),
                     (CreditPosition.transfer_id, transfer_id), (CreditPosition.retirement_id, retirement_id),
                     (CreditPosition.created_by_entry_id, entry_id)):
        if val is not None:
            stmt = stmt.where(col == val)
    return list(db.scalars(stmt).all())


def take(positions: list[CreditPosition], quantity: Decimal) -> list[tuple[CreditPosition, Decimal]]:
    out, need = [], quantity
    for p in positions:
        if need <= 0:
            break
        q = min(p.quantity, need)
        out.append((p, q))
        need -= q
    if need > 0:
        available = sum((p.quantity for p in positions), Decimal(0))
        raise InsufficientAvailable(f"Only {available} credits are available; {quantity} requested.",
                                    details={"requested": str(quantity), "available": str(available)})
    return out


def begin(db: Session, ctx: RequestContext, entry_type: str, batch: CreditBatch, org_id: uuid.UUID, actor: uuid.UUID, quantity: Decimal,
          *, counterparty: uuid.UUID | None = None, confirmed_by: uuid.UUID | None = None, reason: str | None = None, key: str | None = None,
          **links: Any) -> CreditLedgerEntry:
    e = CreditLedgerEntry(entry_code=next_code(db, "credit_entry", utcnow().year), entry_type=entry_type, batch_id=batch.id, organization_id=org_id,
                          counterparty_organization_id=counterparty, quantity=quantity, actor_id=actor, confirmed_by=confirmed_by,
                          reason=reason, request_key=key, posted=False, environment=batch.environment, **links)
    db.add(e)
    db.flush()
    return e


def consume(db: Session, entry: CreditLedgerEntry, p: CreditPosition) -> None:
    res = db.execute(update(CreditPosition).where(CreditPosition.id == p.id, CreditPosition.status == "OPEN")
                     .values(status="CONSUMED", consumed_by_entry_id=entry.id).execution_options(synchronize_session=False))
    if res.rowcount != 1:                                           # type: ignore[attr-defined]
        raise InsufficientAvailable("The credits were taken by a concurrent operation.", details={"position_id": str(p.id)})


def create(db: Session, entry: CreditLedgerEntry, src: CreditPosition, quantity: Decimal, state: str, *, owner: uuid.UUID | None = None,
           holding_account: uuid.UUID | None | str = "same", holding_external: str | None = None, offset: Decimal = Decimal(0),
           sub: tuple[str, str] | None = None, **links: Any) -> CreditPosition:
    """A new position from (part of) `src`: same batch and ORIGINAL registry range; parsed bounds split only if the source has them."""
    ps = pe = None
    if src.parsed_start is not None and src.parsed_series is not None:
        ps = src.parsed_start + offset
        pe = ps + quantity - 1
    whole = quantity == src.quantity and offset == 0
    n = CreditPosition(batch_id=src.batch_id, serial_range_id=src.serial_range_id, owner_organization_id=owner or src.owner_organization_id,
                       holding_registry_account_id=src.holding_registry_account_id if holding_account == "same" else holding_account,
                       holding_external_account_id=holding_external or src.holding_external_account_id, state=state, status="OPEN",
                       quantity=quantity, sub_start=sub[0] if sub else (src.sub_start if whole else None),
                       sub_end=sub[1] if sub else (src.sub_end if whole else None),
                       parsed_series=src.parsed_series if ps is not None else None, parsed_start=ps, parsed_end=pe,
                       created_by_entry_id=entry.id, environment=src.environment,
                       reservation_id=links.get("reservation_id"), transfer_id=links.get("transfer_id"), retirement_id=links.get("retirement_id"))
    db.add(n)
    return n


def move(db: Session, entry: CreditLedgerEntry, allocation: list[tuple[CreditPosition, Decimal]], state: str, **out: Any) -> list[CreditPosition]:
    """Consume each allocated position; create the moved part (new state / owner) and the remainder (unchanged state / owner)."""
    created = []
    for p, q in allocation:
        consume(db, entry, p)
        created.append(create(db, entry, p, q, state, **out))
        if q < p.quantity:
            created.append(create(db, entry, p, p.quantity - q, p.state, offset=q, reservation_id=p.reservation_id,
                                  transfer_id=p.transfer_id, retirement_id=p.retirement_id))
    return created


def post(db: Session, entry: CreditLedgerEntry) -> None:
    db.flush()
    _before_post(entry)
    entry.posted = True
    db.flush()                                                     # the trigger validates conservation here


# ---------------------------------------------------------------- idempotency
def replay(db: Session, model: Any, key: str | None) -> Any:
    if not key:
        return None
    return db.scalars(select(model).where(model.request_key == key)).first()


def entry_replay(db: Session, key: str | None, entry_type: str, **match: Any) -> CreditLedgerEntry | None:
    if not key:
        return None
    e = db.scalars(select(CreditLedgerEntry).where(CreditLedgerEntry.request_key == key)).first()
    if e is None:
        return None
    if e.entry_type != entry_type or any(getattr(e, k) != v for k, v in match.items()):
        raise Conflict("This Idempotency-Key was used for another request.", error_code="IDEMPOTENCY_KEY_REUSED")
    return e


# ---------------------------------------------------------------- lazy reservation expiry (D4)
def expire_due(db: Session, ctx: RequestContext, *, batch_ids: list[uuid.UUID] | None = None, org_ids: set[uuid.UUID] | None = None) -> int:
    stmt = select(CreditReservation.id).where(CreditReservation.status == "ACTIVE", CreditReservation.expires_at <= utcnow())
    if batch_ids is not None:
        stmt = stmt.where(CreditReservation.batch_id.in_(batch_ids or [uuid.uuid4()]))
    if org_ids is not None:
        stmt = stmt.where(CreditReservation.owner_organization_id.in_(org_ids or {uuid.uuid4()}))
    n = 0
    for rid in db.scalars(stmt).all():
        def op(rid: uuid.UUID = rid) -> bool:
            r = db.scalars(select(CreditReservation).with_hint(CreditReservation, LOCK_HINT, "mssql").where(CreditReservation.id == rid)
                           .execution_options(populate_existing=True)).one()
            if r.status != "ACTIVE" or r.expires_at > utcnow():
                return False
            _close_reservation(db, ctx, r, "EXPIRED", "RESERVATION_EXPIRE", ctx.user_id or r.created_by, "Reservation expired")
            return True
        if run(db, ctx, op):
            n += 1
    return n


def _close_reservation(db: Session, ctx: RequestContext, r: CreditReservation, to: str, entry_type: str, actor: uuid.UUID, reason: str,
                       key: str | None = None) -> None:
    b = get_batch(db, r.batch_id)
    positions = lock_positions(db, b.id, reservation_id=r.id, state="RESERVED")
    qty = sum((p.quantity for p in positions), Decimal(0))
    e = begin(db, ctx, entry_type, b, r.owner_organization_id, actor, qty, reason=reason, key=key, reservation_id=r.id)
    for p in positions:
        consume(db, e, p)
        create(db, e, p, p.quantity, "AVAILABLE")
    post(db, e)
    frm = r.status
    CREDIT_RESERVATION_MACHINE.assert_transition(frm, to)
    r.status, r.closed_at = to, utcnow()
    workflow(db, ctx, "credit_reservation", r.id, frm, to, reason)
    audit(db, ctx, f"CREDIT_RESERVATION_{to}", "credit_reservation", r.id, [r.owner_organization_id],
          {"reservation_code": r.reservation_code, "status": to, "quantity": str(r.quantity), "entry_code": e.entry_code}, reason, {"status": frm})


# ---------------------------------------------------------------- opening (D2)
def request_opening(db: Session, ctx: RequestContext, principal: Principal, batch_id: uuid.UUID, key: str | None) -> CreditOpening:
    if (prior := replay(db, CreditOpening, key)) is not None:
        return prior                                               # type: ignore[no-any-return]
    b = get_batch(db, batch_id)
    p = batch_project(db, b)
    account = db.get(RegistryAccount, b.registry_account_id)
    assert account is not None
    if not can_see_batch(db, principal, b):
        raise _nf("Credit batch", "CREDIT_BATCH_NOT_FOUND")
    require_in_org(principal, account.organization_id, P.CREDITS_MANAGE)
    issuance = db.get(CreditIssuance, b.issuance_id)
    if b.status != "ISSUED" or issuance is None or issuance.status != "CONFIRMED":
        raise Conflict(f"Only a registry-issued batch (ISSUED, confirmed issuance) enters the ledger (this batch is {b.status}).",
                       error_code="BATCH_NOT_ISSUED")
    if db.scalars(select(CreditOpening).where(CreditOpening.batch_id == b.id, CreditOpening.status.in_(("REQUESTED", "CONFIRMED")))).first():
        raise Conflict("This batch is already opened (or awaiting confirmation) in the ledger.", error_code="OPENING_EXISTS")
    o = CreditOpening(opening_code=next_code(db, "credit_opening", utcnow().year), batch_id=b.id, owner_organization_id=account.organization_id,
                      holding_registry_account_id=account.id, status="REQUESTED", requested_by=principal.user_id, request_key=key,
                      environment=b.environment)
    db.add(o)
    db.flush()
    workflow(db, ctx, "credit_opening", o.id, None, "REQUESTED", None)
    audit(db, ctx, "CREDIT_INVENTORY_OPENED", "credit_opening", o.id, [account.organization_id, p.organization_id],
          {"opening_code": o.opening_code, "batch_code": b.batch_code, "quantity": str(b.quantity), "owner_organization_id": account.organization_id,
           "status": "REQUESTED"})
    db.commit()
    return o


def _opening(db: Session, principal: Principal, opening_id: uuid.UUID) -> CreditOpening:
    o = db.get(CreditOpening, opening_id)
    if o is None or not can_see_batch(db, principal, get_batch(db, o.batch_id)):
        raise _nf("Ledger opening", "CREDIT_OPENING_NOT_FOUND")
    return o


def confirm_opening(db: Session, ctx: RequestContext, principal: Principal, opening_id: uuid.UUID, key: str | None) -> CreditOpening:
    o = _opening(db, principal, opening_id)
    if entry_replay(db, key, "OPEN_INVENTORY", opening_id=o.id) is not None:
        return o
    require_in_org(principal, o.owner_organization_id, P.CREDITS_CONFIRM)
    if o.requested_by == principal.user_id:
        raise PermissionDenied("The opening must be confirmed by someone other than the requester.", error_code="SEPARATION_OF_DUTIES")
    b = get_batch(db, o.batch_id)
    account = db.get(RegistryAccount, o.holding_registry_account_id)
    assert account is not None

    def op() -> CreditOpening:
        db.refresh(o)
        db.refresh(b)
        if o.status != "REQUESTED":
            raise Conflict(f"The opening is {o.status}.", error_code="OPENING_NOT_REQUESTED")
        if b.status != "ISSUED":
            raise Conflict(f"The batch is {b.status}.", error_code="BATCH_NOT_ISSUED")
        e = begin(db, ctx, "OPEN_INVENTORY", b, o.owner_organization_id, o.requested_by, b.quantity, confirmed_by=principal.user_id, key=key,
                  opening_id=o.id)
        for r in db.scalars(select(CreditSerialRange).where(CreditSerialRange.batch_id == b.id).order_by(CreditSerialRange.seq)).all():
            db.add(CreditPosition(batch_id=b.id, serial_range_id=r.id, owner_organization_id=o.owner_organization_id,
                                  holding_registry_account_id=account.id, holding_external_account_id=account.external_account_id,
                                  state="AVAILABLE", status="OPEN", quantity=r.quantity, parsed_series=r.parsed_series,
                                  parsed_start=r.parsed_start, parsed_end=r.parsed_end, created_by_entry_id=e.id, environment=b.environment))
        post(db, e)
        CREDIT_OPENING_MACHINE.assert_transition(o.status, "CONFIRMED")
        o.status, o.confirmed_by, o.confirmed_at, o.entry_id = "CONFIRMED", principal.user_id, utcnow(), e.id
        workflow(db, ctx, "credit_opening", o.id, "REQUESTED", "CONFIRMED", None)
        audit(db, ctx, "CREDIT_INVENTORY_CONFIRMED", "credit_opening", o.id, [o.owner_organization_id, batch_project(db, b).organization_id],
              {"opening_code": o.opening_code, "batch_code": b.batch_code, "entry_code": e.entry_code, "quantity": str(b.quantity),
               "label": "Registry-issued credits opened in the ledger (AVAILABLE)"}, None, {"status": "REQUESTED"})
        return o
    return run(db, ctx, op)


def cancel_opening(db: Session, ctx: RequestContext, principal: Principal, opening_id: uuid.UUID, reason: str) -> CreditOpening:
    o = _opening(db, principal, opening_id)
    require_in_org(principal, o.owner_organization_id, P.CREDITS_MANAGE, P.CREDITS_CONFIRM)
    if o.status == "CANCELLED":
        return o
    CREDIT_OPENING_MACHINE.assert_transition(o.status, "CANCELLED")
    o.status, o.cancelled_by, o.cancelled_at, o.cancel_reason = "CANCELLED", principal.user_id, utcnow(), reason
    workflow(db, ctx, "credit_opening", o.id, "REQUESTED", "CANCELLED", reason)
    audit(db, ctx, "CREDIT_INVENTORY_OPENING_CANCELLED", "credit_opening", o.id, [o.owner_organization_id], {"status": "CANCELLED"}, reason)
    db.commit()
    return o


# ---------------------------------------------------------------- reservations (D4)
def _recipient(db: Session, org_id: uuid.UUID, environment: str) -> Organization:
    o = _org(db, org_id)
    if o.status != "ACTIVE" or o.environment != environment or o.org_type not in RECIPIENT_ORG_TYPES:
        raise Conflict("The recipient must be an active buyer or project-developer organization of the same environment.",
                       error_code="INVALID_RECIPIENT")
    return o


def naive_utc(dt: datetime) -> datetime:
    """Times are stored as naive UTC (platform convention)."""
    return dt.astimezone(timezone.utc).replace(tzinfo=None) if dt.tzinfo is not None else dt


def _source(db: Session, b: CreditBatch, serial_range_id: uuid.UUID | None) -> None:
    if serial_range_id is not None:
        r = db.get(CreditSerialRange, serial_range_id)
        if r is None or r.batch_id != b.id:
            raise NotFound("Serial range not found in this batch.", error_code="SERIAL_RANGE_NOT_FOUND")


def create_reservation(db: Session, ctx: RequestContext, principal: Principal, data: Any, key: str | None) -> CreditReservation:
    if (prior := replay(db, CreditReservation, key)) is not None:
        return prior                                               # type: ignore[no-any-return]
    b = visible_batch(db, principal, data.batch_id)
    require_in_org(principal, data.owner_organization_id, P.CREDITS_MANAGE)
    _source(db, b, data.serial_range_id)
    if data.recipient_organization_id is not None:
        _recipient(db, data.recipient_organization_id, b.environment)
    expires_at = naive_utc(data.expires_at)
    if expires_at <= utcnow():
        raise ValidationFailed("A reservation must expire in the future.", error_code="EXPIRY_IN_PAST")
    expire_due(db, ctx, batch_ids=[b.id])
    qty = Decimal(data.quantity)

    def op() -> CreditReservation:
        r = CreditReservation(reservation_code=next_code(db, "credit_reservation", utcnow().year), batch_id=b.id,
                              serial_range_id=data.serial_range_id, owner_organization_id=data.owner_organization_id,
                              recipient_organization_id=data.recipient_organization_id, purpose=data.purpose,
                              purpose_reference=data.purpose_reference, quantity=qty, expires_at=expires_at, status="ACTIVE",
                              created_by=principal.user_id, request_key=key, environment=b.environment)
        db.add(r)
        db.flush()
        alloc = take(lock_positions(db, b.id, owner_id=data.owner_organization_id, state="AVAILABLE", serial_range_id=data.serial_range_id), qty)
        e = begin(db, ctx, "RESERVE", b, data.owner_organization_id, principal.user_id, qty, counterparty=data.recipient_organization_id,
                  reservation_id=r.id)
        move(db, e, alloc, "RESERVED", reservation_id=r.id)
        post(db, e)
        workflow(db, ctx, "credit_reservation", r.id, None, "ACTIVE", data.purpose)
        audit(db, ctx, "CREDIT_RESERVATION_CREATED", "credit_reservation", r.id, [r.owner_organization_id],
              {"reservation_code": r.reservation_code, "batch_code": b.batch_code, "quantity": str(qty), "purpose": r.purpose,
               "purpose_reference": r.purpose_reference, "expires_at": r.expires_at, "entry_code": e.entry_code})
        return r
    return run(db, ctx, op, conflict_org=data.owner_organization_id, batch_id=b.id)


def _reservation(db: Session, principal: Principal, reservation_id: uuid.UUID) -> CreditReservation:
    r = db.get(CreditReservation, reservation_id)
    if r is None or not can_see_batch(db, principal, get_batch(db, r.batch_id)):
        raise _nf("Reservation", "CREDIT_RESERVATION_NOT_FOUND")
    return r


def release_reservation(db: Session, ctx: RequestContext, principal: Principal, reservation_id: uuid.UUID, reason: str,
                        key: str | None) -> CreditReservation:
    r = _reservation(db, principal, reservation_id)
    if entry_replay(db, key, "RESERVATION_RELEASE", reservation_id=r.id) is not None:
        return r
    require_in_org(principal, r.owner_organization_id, P.CREDITS_MANAGE)
    expire_due(db, ctx, batch_ids=[r.batch_id])

    def op() -> CreditReservation:
        db.refresh(r)
        if r.status != "ACTIVE":
            raise Conflict(f"The reservation is {r.status}.", error_code="RESERVATION_NOT_ACTIVE")
        r.released_by, r.released_at, r.release_reason = principal.user_id, utcnow(), reason
        _close_reservation(db, ctx, r, "RELEASED", "RESERVATION_RELEASE", principal.user_id, reason, key)
        return r
    return run(db, ctx, op)


def _from_reservation(db: Session, ctx: RequestContext, principal: Principal, reservation_id: uuid.UUID, owner_id: uuid.UUID,
                      batch: CreditBatch) -> tuple[CreditReservation, list[tuple[CreditPosition, Decimal]]]:
    r = db.scalars(select(CreditReservation).with_hint(CreditReservation, LOCK_HINT, "mssql").where(CreditReservation.id == reservation_id)
                   .execution_options(populate_existing=True)).first()
    if r is None or r.batch_id != batch.id or r.owner_organization_id != owner_id:
        raise NotFound("Reservation not found.", error_code="CREDIT_RESERVATION_NOT_FOUND")
    if r.status != "ACTIVE":
        raise Conflict(f"The reservation is {r.status}.", error_code="RESERVATION_NOT_ACTIVE")
    positions = lock_positions(db, batch.id, reservation_id=r.id, state="RESERVED")
    CREDIT_RESERVATION_MACHINE.assert_transition(r.status, "CONSUMED")
    r.status, r.closed_at = "CONSUMED", utcnow()
    workflow(db, ctx, "credit_reservation", r.id, "ACTIVE", "CONSUMED", None)
    audit(db, ctx, "CREDIT_RESERVATION_CONSUMED", "credit_reservation", r.id, [r.owner_organization_id],
          {"reservation_code": r.reservation_code, "status": "CONSUMED"}, None, {"status": "ACTIVE"})
    return r, [(p, p.quantity) for p in positions]


# ---------------------------------------------------------------- transfers (D6, D7)
def request_transfer(db: Session, ctx: RequestContext, principal: Principal, data: Any, key: str | None) -> CreditTransfer:
    if (prior := replay(db, CreditTransfer, key)) is not None:
        return prior                                               # type: ignore[no-any-return]
    b = visible_batch(db, principal, data.batch_id)
    require_in_org(principal, data.sender_organization_id, P.CREDITS_MANAGE)
    _source(db, b, data.serial_range_id)
    _recipient(db, data.recipient_organization_id, b.environment)
    if data.kind == "INTERNAL" and data.recipient_organization_id == data.sender_organization_id:
        raise ValidationFailed("An internal transfer needs a different recipient organization.", error_code="SAME_PARTY")
    if data.kind == "REGISTRY" and not data.recipient_external_account_id:
        raise ValidationFailed("A registry transfer needs the recipient's registry account.", error_code="RECIPIENT_ACCOUNT_REQUIRED")
    if data.reservation_id is None and data.quantity is None:
        raise ValidationFailed("Give a quantity or a reservation.", error_code="QUANTITY_REQUIRED")
    expire_due(db, ctx, batch_ids=[b.id])

    def op() -> CreditTransfer:
        t = CreditTransfer(transfer_code=next_code(db, "credit_transfer", utcnow().year), kind=data.kind, batch_id=b.id,
                           serial_range_id=data.serial_range_id, reservation_id=data.reservation_id,
                           registry_organization_id=b.registry_organization_id,
                           sender_organization_id=data.sender_organization_id, recipient_organization_id=data.recipient_organization_id,
                           recipient_external_account_id=data.recipient_external_account_id if data.kind == "REGISTRY" else None,
                           quantity=Decimal(data.quantity or 1), purpose=data.purpose, purpose_reference=data.purpose_reference, status="REQUESTED",
                           requested_by=principal.user_id, request_key=key, environment=b.environment)
        if data.reservation_id is not None:
            _, alloc = _from_reservation(db, ctx, principal, data.reservation_id, data.sender_organization_id, b)
            t.quantity = sum((q for _, q in alloc), Decimal(0))
        else:
            alloc = take(lock_positions(db, b.id, owner_id=data.sender_organization_id, state="AVAILABLE", serial_range_id=data.serial_range_id),
                         Decimal(data.quantity))
        db.add(t)
        db.flush()
        e = begin(db, ctx, "TRANSFER_REQUEST", b, data.sender_organization_id, principal.user_id, t.quantity,
                  counterparty=data.recipient_organization_id, transfer_id=t.id, reservation_id=data.reservation_id)
        move(db, e, alloc, "TRANSFER_PENDING", transfer_id=t.id)
        post(db, e)
        workflow(db, ctx, "credit_transfer", t.id, None, "REQUESTED", data.purpose)
        audit(db, ctx, "CREDIT_TRANSFER_REQUESTED", "credit_transfer", t.id, [t.sender_organization_id, t.recipient_organization_id],
              {"transfer_code": t.transfer_code, "kind": t.kind, "batch_code": b.batch_code, "quantity": str(t.quantity),
               "recipient_organization_id": t.recipient_organization_id, "entry_code": e.entry_code})
        return t
    return run(db, ctx, op, conflict_org=data.sender_organization_id, batch_id=b.id)


def _transfer(db: Session, principal: Principal, transfer_id: uuid.UUID) -> CreditTransfer:
    t = db.get(CreditTransfer, transfer_id)
    if t is None or not (can_see_batch(db, principal, get_batch(db, t.batch_id))
                         or any(principal.can_in_org(c, t.recipient_organization_id) for c in (P.CREDITS_MANAGE, P.CREDITS_CONFIRM))):
        raise _nf("Transfer", "CREDIT_TRANSFER_NOT_FOUND")
    return t


def _pending_custodians(db: Session, positions: list[CreditPosition]) -> set[uuid.UUID]:
    return {custodian_org(db, p) for p in positions}


def _require_confirmer(principal: Principal, custodians: set[uuid.UUID], requested_by: uuid.UUID) -> None:
    for org in custodians:
        require_in_org(principal, org, P.CREDITS_CONFIRM)
    if principal.user_id == requested_by:
        raise PermissionDenied("This must be confirmed by someone other than the requester.", error_code="SEPARATION_OF_DUTIES",
                               details={"reasons": ["you requested this operation"]})


def _evidence(db: Session, entity: str, entity_id: uuid.UUID, document_id: uuid.UUID, category: str) -> None:
    document_service.require_attached(db, document_id, entity, entity_id, {category})


def complete_transfer(db: Session, ctx: RequestContext, principal: Principal, transfer_id: uuid.UUID, data: Any, key: str | None
                      ) -> CreditTransfer:
    t = _transfer(db, principal, transfer_id)
    if entry_replay(db, key, "TRANSFER_COMPLETE", transfer_id=t.id) is not None:
        return t
    b = get_batch(db, t.batch_id)
    pending = list(db.scalars(select(CreditPosition).where(CreditPosition.transfer_id == t.id, CreditPosition.status == "OPEN",
                                                           CreditPosition.state == "TRANSFER_PENDING")).all())
    _require_confirmer(principal, _pending_custodians(db, pending) or {t.sender_organization_id}, t.requested_by)
    if t.kind == "REGISTRY":
        if data is None or not data.registry_transfer_reference or data.document_id is None:
            raise ValidationFailed("A registry transfer completes only with the registry's transfer reference and evidence (PDF).",
                                   error_code="REGISTRY_EVIDENCE_REQUIRED")
        _evidence(db, TRANSFER_ENTITY, t.id, data.document_id, DocumentCategory.REGISTRY_TRANSFER_EVIDENCE.value)
        if db.scalars(select(CreditTransfer).where(CreditTransfer.registry_organization_id == t.registry_organization_id,
                                                   CreditTransfer.registry_transfer_reference == data.registry_transfer_reference,
                                                   CreditTransfer.id != t.id)).first():
            raise Conflict("This registry transfer reference is already recorded.", error_code="DUPLICATE_REGISTRY_REFERENCE")

    def op() -> CreditTransfer:
        db.refresh(t)
        if t.status != "REQUESTED":
            raise Conflict(f"The transfer is {t.status}.", error_code="TRANSFER_NOT_REQUESTED")
        positions = lock_positions(db, b.id, transfer_id=t.id, state="TRANSFER_PENDING")
        e = begin(db, ctx, "TRANSFER_COMPLETE", b, t.sender_organization_id, t.requested_by, t.quantity, counterparty=t.recipient_organization_id,
                  confirmed_by=principal.user_id, key=key, transfer_id=t.id)
        for p in positions:
            consume(db, e, p)
            if t.kind == "INTERNAL":
                create(db, e, p, p.quantity, "AVAILABLE", owner=t.recipient_organization_id)
            else:
                create(db, e, p, p.quantity, "AVAILABLE", owner=t.recipient_organization_id, holding_account=None,
                       holding_external=t.recipient_external_account_id)
        post(db, e)
        CREDIT_TRANSFER_MACHINE.assert_transition(t.status, "COMPLETED")
        t.status, t.completed_by, t.completed_at = "COMPLETED", principal.user_id, utcnow()
        if t.kind == "REGISTRY":
            t.registry_transfer_reference, t.evidence_document_id = data.registry_transfer_reference, data.document_id
        workflow(db, ctx, "credit_transfer", t.id, "REQUESTED", "COMPLETED", None)
        audit(db, ctx, "CREDIT_TRANSFER_COMPLETED", "credit_transfer", t.id, [t.sender_organization_id, t.recipient_organization_id],
              {"transfer_code": t.transfer_code, "kind": t.kind, "quantity": str(t.quantity), "entry_code": e.entry_code,
               "registry_transfer_reference": t.registry_transfer_reference, "evidence_document_id": t.evidence_document_id},
              None, {"status": "REQUESTED"})
        return t
    return run(db, ctx, op)


def close_transfer(db: Session, ctx: RequestContext, principal: Principal, transfer_id: uuid.UUID, to: str, reason: str,
                   key: str | None) -> CreditTransfer:
    """CANCELLED by the sender side; REJECTED by a confirmer. The pending credits return to the sender as AVAILABLE."""
    t = _transfer(db, principal, transfer_id)
    entry_type = "TRANSFER_CANCEL" if to == "CANCELLED" else "TRANSFER_REJECT"
    if entry_replay(db, key, entry_type, transfer_id=t.id) is not None:
        return t
    b = get_batch(db, t.batch_id)
    if to == "CANCELLED":
        require_in_org(principal, t.sender_organization_id, P.CREDITS_MANAGE)
    else:
        pending = list(db.scalars(select(CreditPosition).where(CreditPosition.transfer_id == t.id, CreditPosition.status == "OPEN")).all())
        _require_confirmer(principal, _pending_custodians(db, pending) or {t.sender_organization_id}, t.requested_by)

    def op() -> CreditTransfer:
        db.refresh(t)
        if t.status != "REQUESTED":
            raise Conflict(f"The transfer is {t.status}.", error_code="TRANSFER_NOT_REQUESTED")
        positions = lock_positions(db, b.id, transfer_id=t.id, state="TRANSFER_PENDING")
        e = begin(db, ctx, entry_type, b, t.sender_organization_id, principal.user_id, t.quantity, reason=reason, key=key, transfer_id=t.id)
        for p in positions:
            consume(db, e, p)
            create(db, e, p, p.quantity, "AVAILABLE")
        post(db, e)
        CREDIT_TRANSFER_MACHINE.assert_transition(t.status, to)
        t.status, t.closed_by, t.closed_at, t.close_reason = to, principal.user_id, utcnow(), reason
        workflow(db, ctx, "credit_transfer", t.id, "REQUESTED", to, reason)
        audit(db, ctx, f"CREDIT_TRANSFER_{to}", "credit_transfer", t.id, [t.sender_organization_id, t.recipient_organization_id],
              {"transfer_code": t.transfer_code, "status": to, "entry_code": e.entry_code}, reason, {"status": "REQUESTED"})
        return t
    return run(db, ctx, op)


# ---------------------------------------------------------------- retirements (D9, X1)
def request_retirement(db: Session, ctx: RequestContext, principal: Principal, data: Any, key: str | None) -> CreditRetirement:
    if (prior := replay(db, CreditRetirement, key)) is not None:
        return prior                                               # type: ignore[no-any-return]
    b = get_batch(db, data.batch_id)
    owner = data.owner_organization_id
    if not (can_see_batch(db, principal, b) or (principal.can_in_org(P.CREDITS_HOLDER_RETIRE, owner) and holds_in_batch(db, b.id, owner))):
        raise _nf("Credit batch", "CREDIT_BATCH_NOT_FOUND")
    require_in_org(principal, owner, P.CREDITS_MANAGE, P.CREDITS_HOLDER_RETIRE)
    _source(db, b, data.serial_range_id)
    if data.reservation_id is None and data.quantity is None:
        raise ValidationFailed("Give a quantity or a reservation.", error_code="QUANTITY_REQUIRED")
    expire_due(db, ctx, batch_ids=[b.id])

    def op() -> CreditRetirement:
        r = CreditRetirement(retirement_code=next_code(db, "credit_retirement", utcnow().year), batch_id=b.id, serial_range_id=data.serial_range_id,
                             reservation_id=data.reservation_id, registry_organization_id=b.registry_organization_id, owner_organization_id=owner,
                             quantity=Decimal(data.quantity or 1), beneficiary=data.beneficiary, reason=data.reason, status="REQUESTED",
                             requested_by=principal.user_id, request_key=key, environment=b.environment)
        if data.reservation_id is not None:
            _, alloc = _from_reservation(db, ctx, principal, data.reservation_id, owner, b)
            r.quantity = sum((q for _, q in alloc), Decimal(0))
        else:
            alloc = take(lock_positions(db, b.id, owner_id=owner, state="AVAILABLE", serial_range_id=data.serial_range_id), Decimal(data.quantity))
        db.add(r)
        db.flush()
        e = begin(db, ctx, "RETIREMENT_REQUEST", b, owner, principal.user_id, r.quantity, retirement_id=r.id, reservation_id=data.reservation_id)
        move(db, e, alloc, "RETIREMENT_PENDING", retirement_id=r.id)
        post(db, e)
        workflow(db, ctx, "credit_retirement", r.id, None, "REQUESTED", data.reason)
        custodians = _pending_custodians(db, [p for p, _ in alloc])
        audit(db, ctx, "CREDIT_RETIREMENT_REQUESTED", "credit_retirement", r.id, [owner, *custodians],
              {"retirement_code": r.retirement_code, "batch_code": b.batch_code, "quantity": str(r.quantity), "beneficiary": r.beneficiary,
               "entry_code": e.entry_code})
        return r
    return run(db, ctx, op, conflict_org=owner, batch_id=b.id)


def _retirement(db: Session, principal: Principal, retirement_id: uuid.UUID) -> CreditRetirement:
    r = db.get(CreditRetirement, retirement_id)
    if r is None or not (can_see_batch(db, principal, get_batch(db, r.batch_id))
                         or any(principal.can_in_org(c, r.owner_organization_id) for c in (P.CREDITS_HOLDER_READ, P.CREDITS_HOLDER_RETIRE))):
        raise _nf("Retirement", "CREDIT_RETIREMENT_NOT_FOUND")
    return r


def retire(db: Session, ctx: RequestContext, principal: Principal, retirement_id: uuid.UUID, data: Any, key: str | None) -> CreditRetirement:
    r = _retirement(db, principal, retirement_id)
    if entry_replay(db, key, "RETIREMENT_RETIRE", retirement_id=r.id) is not None:
        return r
    b = get_batch(db, r.batch_id)
    pending = list(db.scalars(select(CreditPosition).where(CreditPosition.retirement_id == r.id, CreditPosition.status == "OPEN",
                                                           CreditPosition.state == "RETIREMENT_PENDING")).all())
    _require_confirmer(principal, _pending_custodians(db, pending) or {r.owner_organization_id}, r.requested_by)
    _evidence(db, RETIREMENT_ENTITY, r.id, data.document_id, DocumentCategory.RETIREMENT_CERTIFICATE.value)
    serials = [s.model_dump() for s in data.retired_serials] if data.retired_serials else None
    if serials is not None and sum(s["quantity"] for s in serials) != int(r.quantity):
        raise ValidationFailed("The registry-stated retired serials must add up to the retired quantity.", error_code="RETIRED_SERIALS_MISMATCH")
    if db.scalars(select(CreditRetirement).where(CreditRetirement.registry_organization_id == r.registry_organization_id,
                                                 CreditRetirement.registry_retirement_reference == data.registry_retirement_reference,
                                                 CreditRetirement.id != r.id)).first():
        raise Conflict("This registry retirement reference is already recorded.", error_code="DUPLICATE_REGISTRY_REFERENCE")

    def op() -> CreditRetirement:
        db.refresh(r)
        if r.status != "REQUESTED":
            raise Conflict(f"The retirement is {r.status}.", error_code="RETIREMENT_NOT_REQUESTED")
        positions = lock_positions(db, b.id, retirement_id=r.id, state="RETIREMENT_PENDING")
        e = begin(db, ctx, "RETIREMENT_RETIRE", b, r.owner_organization_id, r.requested_by, r.quantity, confirmed_by=principal.user_id, key=key,
                  retirement_id=r.id)
        single = serials[0] if serials is not None and len(serials) == 1 and len(positions) == 1 else None
        for p in positions:
            consume(db, e, p)
            create(db, e, p, p.quantity, "RETIRED", retirement_id=r.id,
                   sub=(single["serial_start"], single["serial_end"]) if single and single.get("serial_start") else None)
        post(db, e)
        CREDIT_RETIREMENT_MACHINE.assert_transition(r.status, "RETIRED")
        r.status, r.retired_by, r.retired_at = "RETIRED", principal.user_id, utcnow()
        r.registry_retirement_reference, r.retirement_date = data.registry_retirement_reference, data.retirement_date
        r.certificate_document_id = data.document_id
        r.retired_serials = json.dumps(serials) if serials is not None else None
        workflow(db, ctx, "credit_retirement", r.id, "REQUESTED", "RETIRED", None)
        audit(db, ctx, "CREDIT_RETIREMENT_RETIRED", "credit_retirement", r.id, [r.owner_organization_id, *_pending_custodians(db, positions)],
              {"retirement_code": r.retirement_code, "quantity": str(r.quantity), "registry_retirement_reference": r.registry_retirement_reference,
               "retirement_date": r.retirement_date, "certificate_document_id": r.certificate_document_id, "retired_serials": serials,
               "entry_code": e.entry_code, "label": "Retired at the registry (registry evidence recorded) — permanent"},
              None, {"status": "REQUESTED"})
        return r
    return run(db, ctx, op)


def close_retirement(db: Session, ctx: RequestContext, principal: Principal, retirement_id: uuid.UUID, to: str, reason: str,
                     key: str | None) -> CreditRetirement:
    r = _retirement(db, principal, retirement_id)
    entry_type = "RETIREMENT_CANCEL" if to == "CANCELLED" else "RETIREMENT_REJECT"
    if entry_replay(db, key, entry_type, retirement_id=r.id) is not None:
        return r
    b = get_batch(db, r.batch_id)
    if to == "CANCELLED":
        require_in_org(principal, r.owner_organization_id, P.CREDITS_MANAGE, P.CREDITS_HOLDER_RETIRE)
    else:
        pending = list(db.scalars(select(CreditPosition).where(CreditPosition.retirement_id == r.id, CreditPosition.status == "OPEN")).all())
        _require_confirmer(principal, _pending_custodians(db, pending) or {r.owner_organization_id}, r.requested_by)

    def op() -> CreditRetirement:
        db.refresh(r)
        if r.status != "REQUESTED":
            raise Conflict(f"The retirement is {r.status}.", error_code="RETIREMENT_NOT_REQUESTED")
        positions = lock_positions(db, b.id, retirement_id=r.id, state="RETIREMENT_PENDING")
        e = begin(db, ctx, entry_type, b, r.owner_organization_id, principal.user_id, r.quantity, reason=reason, key=key, retirement_id=r.id)
        for p in positions:
            consume(db, e, p)
            create(db, e, p, p.quantity, "AVAILABLE")
        post(db, e)
        CREDIT_RETIREMENT_MACHINE.assert_transition(r.status, to)
        r.status, r.closed_by, r.closed_at, r.close_reason = to, principal.user_id, utcnow(), reason
        workflow(db, ctx, "credit_retirement", r.id, "REQUESTED", to, reason)
        audit(db, ctx, f"CREDIT_RETIREMENT_{to}", "credit_retirement", r.id, [r.owner_organization_id],
              {"retirement_code": r.retirement_code, "status": to, "entry_code": e.entry_code}, reason, {"status": "REQUESTED"})
        return r
    return run(db, ctx, op)


# ---------------------------------------------------------------- reversals (D14)
def request_reversal(db: Session, ctx: RequestContext, principal: Principal, entry_id: uuid.UUID, reason: str, key: str | None) -> CreditReversal:
    if (prior := replay(db, CreditReversal, key)) is not None:
        return prior                                               # type: ignore[no-any-return]
    e = entry_for(db, principal, entry_id)
    t = db.get(CreditTransfer, e.transfer_id) if e.transfer_id else None
    if e.entry_type != "TRANSFER_COMPLETE" or t is None or t.kind != "INTERNAL":
        raise Conflict("Only a completed INTERNAL transfer can be reversed (registry acts and retirements are never reversed internally).",
                       error_code="REVERSAL_NOT_ALLOWED")
    require_in_org(principal, t.sender_organization_id, P.CREDITS_MANAGE)
    _untouched_outputs(db, e)
    if db.scalars(select(CreditReversal).where(CreditReversal.reversed_entry_id == e.id, CreditReversal.status.in_(("REQUESTED",
                                                                                                                    "APPLIED")))).first():
        raise Conflict("A reversal of this entry already exists.", error_code="REVERSAL_EXISTS")
    v = CreditReversal(reversal_code=next_code(db, "credit_reversal", utcnow().year), reversed_entry_id=e.id, batch_id=e.batch_id, reason=reason,
                       status="REQUESTED", requested_by=principal.user_id, request_key=key, environment=e.environment)
    db.add(v)
    db.flush()
    workflow(db, ctx, "credit_reversal", v.id, None, "REQUESTED", reason)
    audit(db, ctx, "CREDIT_LEDGER_REVERSAL_REQUESTED", "credit_reversal", v.id, [t.sender_organization_id, t.recipient_organization_id],
          {"reversal_code": v.reversal_code, "entry_code": e.entry_code, "transfer_code": t.transfer_code}, reason)
    db.commit()
    return v


def _untouched_outputs(db: Session, e: CreditLedgerEntry) -> list[CreditPosition]:
    outputs = list(db.scalars(select(CreditPosition).where(CreditPosition.created_by_entry_id == e.id)).all())
    if not outputs or any(p.status != "OPEN" or p.state != "AVAILABLE" for p in outputs):
        raise Conflict("The transferred credits were already used; reverse the later operations first.", error_code="REVERSAL_NOT_POSSIBLE")
    return outputs


def decide_reversal(db: Session, ctx: RequestContext, principal: Principal, reversal_id: uuid.UUID, apply: bool, note: str,
                    key: str | None) -> CreditReversal:
    v = db.get(CreditReversal, reversal_id)
    if v is None or not can_see_batch(db, principal, get_batch(db, v.batch_id)):
        raise _nf("Reversal", "CREDIT_REVERSAL_NOT_FOUND")
    if entry_replay(db, key, "REVERSAL", reversal_id=v.id) is not None:
        return v
    e0 = db.get(CreditLedgerEntry, v.reversed_entry_id)
    assert e0 is not None and e0.transfer_id is not None
    t = db.get(CreditTransfer, e0.transfer_id)
    assert t is not None
    outputs = list(db.scalars(select(CreditPosition).where(CreditPosition.created_by_entry_id == e0.id)).all())
    _require_confirmer(principal, _pending_custodians(db, outputs) or {t.sender_organization_id}, v.requested_by)
    b = get_batch(db, v.batch_id)

    def op() -> CreditReversal:
        db.refresh(v)
        if v.status != "REQUESTED":
            raise Conflict(f"The reversal is {v.status}.", error_code="REVERSAL_NOT_REQUESTED")
        to = "APPLIED" if apply else "REJECTED"
        entry_code = None
        if apply:
            current = lock_positions(db, b.id, entry_id=e0.id)
            if len(current) != len(outputs) or any(p.state != "AVAILABLE" for p in current):
                raise Conflict("The transferred credits were already used.", error_code="REVERSAL_NOT_POSSIBLE")
            e = begin(db, ctx, "REVERSAL", b, t.recipient_organization_id, v.requested_by, sum((p.quantity for p in current), Decimal(0)),
                      counterparty=t.sender_organization_id, confirmed_by=principal.user_id, reason=v.reason, key=key, reversal_id=v.id,
                      transfer_id=t.id)
            for p in current:
                consume(db, e, p)
                create(db, e, p, p.quantity, "AVAILABLE", owner=t.sender_organization_id)
            post(db, e)
            v.entry_id, entry_code = e.id, e.entry_code
        CREDIT_REVERSAL_MACHINE.assert_transition(v.status, to)
        v.status, v.decided_by, v.decided_at, v.decision_note = to, principal.user_id, utcnow(), note
        workflow(db, ctx, "credit_reversal", v.id, "REQUESTED", to, note)
        audit(db, ctx, "CREDIT_LEDGER_REVERSAL" if apply else "CREDIT_LEDGER_REVERSAL_REJECTED", "credit_reversal", v.id,
              [t.sender_organization_id, t.recipient_organization_id],
              {"reversal_code": v.reversal_code, "status": to, "reversed_entry_code": e0.entry_code, "entry_code": entry_code}, note,
              {"status": "REQUESTED"})
        return v
    return run(db, ctx, op)


# ---------------------------------------------------------------- 9A correction / cancellation guard (X4, D14)
def ledger_guard(db: Session, batch_ids: list[uuid.UUID]) -> None:
    """LEDGER_ACTIVITY_EXISTS unless every opened batch is untouched (only its OPEN_INVENTORY entry; positions AVAILABLE, original owner)."""
    for bid in batch_ids:
        opening = db.scalars(select(CreditOpening).where(CreditOpening.batch_id == bid, CreditOpening.status == "CONFIRMED")).first()
        if opening is None:
            continue
        other = db.scalar(select(func.count()).select_from(CreditLedgerEntry).where(CreditLedgerEntry.batch_id == bid,
                                                                                     CreditLedgerEntry.entry_type != "OPEN_INVENTORY"))
        positions = db.scalars(select(CreditPosition).where(CreditPosition.batch_id == bid)).all()
        untouched = other == 0 and all(p.status == "OPEN" and p.state == "AVAILABLE" and p.owner_organization_id == opening.owner_organization_id
                                       and p.created_by_entry_id == opening.entry_id for p in positions)
        if not untouched:
            raise Conflict("Credits of this batch were already reserved, transferred or retired in the ledger; the issuance cannot be "
                           "corrected or cancelled here.", error_code="LEDGER_ACTIVITY_EXISTS", details={"batch_id": str(bid)})


def issuance_adjustment(db: Session, ctx: RequestContext, principal: Principal, issuance: CreditIssuance, batch_ids: list[uuid.UUID],
                        reason: str) -> None:
    """Explicit ISSUANCE_ADJUSTMENT for untouched opened batches (closes their positions); pending openings are cancelled. Caller commits."""
    ledger_guard(db, batch_ids)
    for bid in batch_ids:
        for o in db.scalars(select(CreditOpening).where(CreditOpening.batch_id == bid, CreditOpening.status == "REQUESTED")).all():
            o.status, o.cancelled_by, o.cancelled_at, o.cancel_reason = "CANCELLED", principal.user_id, utcnow(), reason
            workflow(db, ctx, "credit_opening", o.id, "REQUESTED", "CANCELLED", reason)
        opening = db.scalars(select(CreditOpening).where(CreditOpening.batch_id == bid, CreditOpening.status == "CONFIRMED")).first()
        if opening is None:
            continue
        b = get_batch(db, bid)
        positions = lock_positions(db, bid)
        qty = sum((p.quantity for p in positions), Decimal(0))
        e = begin(db, ctx, "ISSUANCE_ADJUSTMENT", b, opening.owner_organization_id, principal.user_id, qty, reason=reason, issuance_id=issuance.id)
        for p in positions:
            consume(db, e, p)
        post(db, e)
        audit(db, ctx, "CREDIT_ISSUANCE_ADJUSTMENT", "credit_batch", b.id, [opening.owner_organization_id],
              {"batch_code": b.batch_code, "entry_code": e.entry_code, "quantity": str(qty), "issuance_code": issuance.issuance_code,
               "note": "Untouched ledger inventory closed because the registry corrected / cancelled the issuance"}, reason)


# ---------------------------------------------------------------- reconciliation (D12, D20)
def reconcile_account(db: Session, ctx: RequestContext, principal: Principal, account_id: uuid.UUID, data: Any, key: str | None) -> RegistryEvent:
    a = db.get(RegistryAccount, account_id)
    if a is None:
        raise _nf("Registry account", "REGISTRY_ACCOUNT_NOT_FOUND")
    require_in_org(principal, a.organization_id, P.CREDITS_MANAGE)
    if key and (prior := db.scalars(select(RegistryEvent).where(RegistryEvent.idempotency_key == key)).first()) is not None:
        return prior
    document_service.require_attached(db, data.document_id, ACCOUNT_ENTITY, a.id, {DocumentCategory.REGISTRY_RESPONSE.value})
    held: dict[uuid.UUID, Decimal] = {}
    for bid, q in db.execute(select(CreditPosition.batch_id, func.sum(CreditPosition.quantity))
                             .where(CreditPosition.holding_registry_account_id == a.id, CreditPosition.status == "OPEN",
                                    CreditPosition.state != "RETIRED").group_by(CreditPosition.batch_id)).all():
        held[bid] = Decimal(q)
    stated = {line.batch_id: Decimal(line.registry_stated_quantity) for line in data.lines}
    mismatches = []
    for bid in sorted(set(held) | set(stated), key=str):
        b = db.get(CreditBatch, bid)
        if held.get(bid, Decimal(0)) != stated.get(bid, Decimal(0)):
            mismatches.append({"batch": b.batch_code if b else str(bid), "platform": str(held.get(bid, 0)), "registry": str(stated.get(bid, 0))})
    kind = "MISMATCH" if mismatches else "RECONCILED"
    ev = RegistryEvent(registry_account_id=a.id, event_type=kind, actor_id=principal.user_id, adapter_code=a.adapter_code, idempotency_key=key,
                       outcome="INVENTORY", document_id=data.document_id, environment=a.environment,
                       note=(json.dumps(mismatches) if mismatches else data.note)[:2000] if (mismatches or data.note) else None)
    db.add(ev)
    db.flush()
    audit(db, ctx, "CREDIT_RECONCILIATION_MISMATCH" if mismatches else "CREDIT_RECONCILIATION_PERFORMED", "registry_account", a.id,
          [a.organization_id],
          {"mismatches": mismatches, "lines": len(data.lines), "document_id": data.document_id,
           "note": "Compared with the registry account statement; nothing was changed automatically"}, data.note)
    db.commit()
    return ev


# ---------------------------------------------------------------- views
def balances(db: Session, batch_id: uuid.UUID) -> dict[uuid.UUID, dict[str, Decimal]]:
    """Derived per owner from OPEN positions (D3); transferred out from completed transfers net of applied reversals."""
    out: dict[uuid.UUID, dict[str, Decimal]] = {}
    for owner, state, q in db.execute(select(CreditPosition.owner_organization_id, CreditPosition.state, func.sum(CreditPosition.quantity))
                                      .where(CreditPosition.batch_id == batch_id, CreditPosition.status == "OPEN")
                                      .group_by(CreditPosition.owner_organization_id, CreditPosition.state)).all():
        out.setdefault(owner, {})[state] = Decimal(q)
    for sender, q in db.execute(select(CreditTransfer.sender_organization_id, func.sum(CreditTransfer.quantity))
                                .where(CreditTransfer.batch_id == batch_id, CreditTransfer.status == "COMPLETED")
                                .group_by(CreditTransfer.sender_organization_id)).all():
        out.setdefault(sender, {})["TRANSFERRED_OUT"] = Decimal(q)
    for v in db.scalars(select(CreditReversal).where(CreditReversal.batch_id == batch_id, CreditReversal.status == "APPLIED")).all():
        e = db.get(CreditLedgerEntry, v.entry_id) if v.entry_id else None
        if e is not None and e.counterparty_organization_id is not None:
            d = out.setdefault(e.counterparty_organization_id, {})
            d["TRANSFERRED_OUT"] = d.get("TRANSFERRED_OUT", Decimal(0)) - e.quantity
    return out


def visible_batches(db: Session, principal: Principal, project_id: uuid.UUID | None = None) -> list[CreditBatch]:
    orgs = {g.organization_id for g in principal.grants if g.organization_id and g.permissions & set(PROJECT_READ)}
    stmt = select(CreditBatch).join(Project, Project.id == CreditBatch.project_id).where(CreditBatch.status.in_(("ISSUED", "SUPERSEDED",
                                                                                                                 "CANCELLED")))
    holder_orgs = {g.organization_id for g in principal.grants if g.organization_id and g.permissions & {P.CREDITS_MANAGE, P.CREDITS_CONFIRM}}
    held = set(db.scalars(select(CreditPosition.batch_id).where(CreditPosition.owner_organization_id.in_(holder_orgs or {uuid.uuid4()}))).all())
    stmt = stmt.where(Project.organization_id.in_(orgs or {uuid.uuid4()}) | CreditBatch.id.in_(held or {uuid.uuid4()}))
    if project_id:
        stmt = stmt.where(CreditBatch.project_id == project_id)
    return list(db.scalars(stmt.order_by(CreditBatch.batch_code)).all())


def opening_of(db: Session, batch_id: uuid.UUID) -> CreditOpening | None:
    return db.scalars(select(CreditOpening).where(CreditOpening.batch_id == batch_id).order_by(CreditOpening.requested_at.desc())).first()


def entry_for(db: Session, principal: Principal, entry_id: uuid.UUID) -> CreditLedgerEntry:
    e = db.get(CreditLedgerEntry, entry_id)
    if e is None or not can_see_batch(db, principal, get_batch(db, e.batch_id)):
        raise _nf("Ledger entry", "CREDIT_ENTRY_NOT_FOUND")
    return e


def holder_positions(db: Session, principal: Principal) -> list[CreditPosition]:
    orgs = {g.organization_id for g in principal.grants if g.organization_id and P.CREDITS_HOLDER_READ in g.permissions}
    if not orgs:
        return []
    expire_due(db, RequestContext(request_id="lazy-expiry", user_id=principal.user_id), org_ids=orgs)
    return list(db.scalars(select(CreditPosition).where(CreditPosition.owner_organization_id.in_(orgs), CreditPosition.status == "OPEN")
                           .order_by(CreditPosition.batch_id, CreditPosition.serial_range_id, CreditPosition.id)).all())


def upload(db: Session, ctx: RequestContext, principal: Principal, entity: str, entity_id: uuid.UUID, filename: str | None, data: bytes,
           title: str | None) -> Document:
    """Registry evidence for a transfer / retirement (custodian side) or a registry account statement (account owner)."""
    if entity == TRANSFER_ENTITY:
        t = _transfer(db, principal, entity_id)
        org, category, env = t.sender_organization_id, DocumentCategory.REGISTRY_TRANSFER_EVIDENCE.value, t.environment
        positions = list(db.scalars(select(CreditPosition).where(CreditPosition.transfer_id == t.id, CreditPosition.status == "OPEN")).all())
        orgs = _pending_custodians(db, positions) or {org}
    elif entity == RETIREMENT_ENTITY:
        r = _retirement(db, principal, entity_id)
        org, category, env = r.owner_organization_id, DocumentCategory.RETIREMENT_CERTIFICATE.value, r.environment
        positions = list(db.scalars(select(CreditPosition).where(CreditPosition.retirement_id == r.id, CreditPosition.status == "OPEN")).all())
        orgs = _pending_custodians(db, positions) or {org}
    else:
        a = db.get(RegistryAccount, entity_id)
        if a is None:
            raise _nf("Registry account", "REGISTRY_ACCOUNT_NOT_FOUND")
        org, category, env, orgs = a.organization_id, DocumentCategory.REGISTRY_RESPONSE.value, a.environment, {a.organization_id}
    if not any(principal.can_in_org(c, o) for o in orgs for c in (P.CREDITS_MANAGE, P.CREDITS_CONFIRM)):
        raise PermissionDenied(details={"required_permission": "credits.manage or credits.confirm (custodian)"})
    doc = document_service.create_document(db, ctx, entity_type=entity, entity_id=entity_id, organization_id=next(iter(orgs)), environment=env,
                                           category=category, title=title or category.replace("_", " ").title(), filename=filename, data=data)
    audit(db, ctx, "CREDIT_EVIDENCE_UPLOADED", entity, entity_id, [org, *orgs], {"document_id": doc.id, "category": category})
    db.commit()
    return doc


def _doc_resolver(kind_entity: str) -> Any:
    def resolve(db: Session, principal: Principal, entity_id: uuid.UUID, kind: str) -> None:
        nf = NotFound("Document not found.", error_code="DOCUMENT_NOT_FOUND")
        if kind == "manage":
            raise PermissionDenied("Registry evidence is immutable; upload a new document instead.", error_code="DOCUMENT_IMMUTABLE")
        try:
            if kind_entity == TRANSFER_ENTITY:
                _transfer(db, principal, entity_id)
            elif kind_entity == RETIREMENT_ENTITY:
                _retirement(db, principal, entity_id)
            else:
                a = db.get(RegistryAccount, entity_id)
                if a is None or not any(principal.can_in_org(c, a.organization_id) for c in (*PROJECT_READ, P.REGISTRY_READ)):
                    raise nf
        except NotFound:
            raise nf from None
    return resolve


for _entity in (TRANSFER_ENTITY, RETIREMENT_ENTITY, ACCOUNT_ENTITY):
    document_service.register_resolver(_entity, _doc_resolver(_entity))

