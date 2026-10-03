"""Phase 9B mappers. Holder output is an explicit allow-list (no farmer, farm, KYC, bank, agreement, audit or other-holder data)."""
import json
import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

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
    MethodologyVersion,
    MonitoringPeriod,
    Organization,
    Project,
    Standard,
    User,
)
from app.schemas.ledger import (
    DEMO_NOTE,
    Balance,
    EntryOut,
    HoldingOut,
    HoldingsOut,
    InventoryBatch,
    InventoryOut,
    OpeningOut,
    PositionOut,
    ReservationOut,
    RetirementOut,
    ReversalOut,
    TransferOut,
)
from app.security.permissions import P
from app.security.principal import Principal
from app.services import ledger_service as ls


def _names(db: Session, ids: set[Any]) -> dict[Any, str]:
    ids_ = {i for i in ids if i}
    return {u.id: u.full_name for u in db.scalars(select(User).where(User.id.in_(ids_))).all()} if ids_ else {}


def _org(db: Session, org_id: uuid.UUID | None) -> str | None:
    o = db.get(Organization, org_id) if org_id else None
    return o.name if o else None


def _code(db: Session, batch_id: uuid.UUID) -> str | None:
    b = db.get(CreditBatch, batch_id)
    return b.batch_code if b else None


def range_text(r: CreditSerialRange | None) -> str:
    if r is None:
        return "—"
    return f"{r.serial_start} – {r.serial_end}" if r.serial_start else f"registry range #{r.seq} (serials not supplied by the registry)"


def sub_text(p: CreditPosition) -> str | None:
    """Only registry-stated text sub-ranges; parser-derived bounds are numbers within the registry's own series (never re-formatted)."""
    if p.sub_start:
        return f"{p.sub_start} – {p.sub_end}"
    if p.parsed_series is not None:
        return f"{p.quantity} credits at positions {p.parsed_start}–{p.parsed_end} of series {p.parsed_series} (registry parser)"
    return None


def position_out(db: Session, p: CreditPosition) -> PositionOut:
    r = db.get(CreditSerialRange, p.serial_range_id)
    return PositionOut(id=p.id, batch_id=p.batch_id, batch_code=_code(db, p.batch_id), serial_range_id=p.serial_range_id,
                       registry_range=range_text(r),
                       owner_organization_id=p.owner_organization_id, owner_name=_org(db, p.owner_organization_id),
                       holding_external_account_id=p.holding_external_account_id, state=p.state, status=p.status, quantity=int(p.quantity),
                       sub_range=sub_text(p), parsed=p.parsed_series is not None, reservation_id=p.reservation_id, transfer_id=p.transfer_id,
                       retirement_id=p.retirement_id, created_by_entry_id=p.created_by_entry_id, consumed_by_entry_id=p.consumed_by_entry_id,
                       created_at=p.created_at)


def opening_out(db: Session, principal: Principal, o: CreditOpening) -> OpeningOut:
    names = _names(db, {o.requested_by, o.confirmed_by})
    return OpeningOut(id=o.id, opening_code=o.opening_code, batch_id=o.batch_id, owner_organization_id=o.owner_organization_id, status=o.status,
                      requested_by_name=names.get(o.requested_by), requested_at=o.requested_at,
                      confirmed_by_name=names.get(o.confirmed_by) if o.confirmed_by else None, confirmed_at=o.confirmed_at,
                      cancel_reason=o.cancel_reason,
                      can_confirm=o.status == "REQUESTED" and principal.can_in_org(P.CREDITS_CONFIRM, o.owner_organization_id)
                      and principal.user_id != o.requested_by)


def _int(v: Decimal | None) -> int:
    return int(v or 0)


def inventory(db: Session, principal: Principal, batches: list[CreditBatch]) -> InventoryOut:
    out = []
    for b in batches:
        p = db.get(Project, b.project_id)
        mp = db.get(MonitoringPeriod, b.monitoring_period_id)
        o = ls.opening_of(db, b.id)
        bal = ls.balances(db, b.id)
        out.append(InventoryBatch(
            batch_id=b.id, batch_code=b.batch_code, project_id=b.project_id, project_code=p.project_code if p else None,
            period_number=mp.period_number if mp else None, vintage=b.vintage, unit=b.unit, registry_name=_org(db, b.registry_organization_id),
            batch_status=b.status, issued=int(b.quantity), opening=opening_out(db, principal, o) if o else None,
            balances=[Balance(owner_organization_id=org, owner_name=_org(db, org), available=_int(d.get("AVAILABLE")),
                              reserved=_int(d.get("RESERVED")),
                              pending_transfer=_int(d.get("TRANSFER_PENDING")), pending_retirement=_int(d.get("RETIREMENT_PENDING")),
                              retired=_int(d.get("RETIRED")), transferred_out=_int(d.get("TRANSFERRED_OUT"))) for org, d in bal.items()],
            environment=b.environment))
    demo = principal.user.environment == "DEMO" and not out
    return InventoryOut(batches=out, demo_note=DEMO_NOTE if demo else None)


def entry_out(db: Session, e: CreditLedgerEntry) -> EntryOut:
    names = _names(db, {e.actor_id, e.confirmed_by})
    inputs = db.scalars(select(CreditPosition).where(CreditPosition.consumed_by_entry_id == e.id)).all()
    outputs = db.scalars(select(CreditPosition).where(CreditPosition.created_by_entry_id == e.id)).all()
    return EntryOut(id=e.id, entry_code=e.entry_code, entry_type=e.entry_type, batch_id=e.batch_id, organization_id=e.organization_id,
                    counterparty_organization_id=e.counterparty_organization_id, quantity=int(e.quantity), actor_name=names.get(e.actor_id),
                    confirmed_by_name=names.get(e.confirmed_by) if e.confirmed_by else None, reason=e.reason, created_at=e.created_at,
                    inputs=[position_out(db, p) for p in inputs], outputs=[position_out(db, p) for p in outputs])


def reservation_out(db: Session, r: CreditReservation) -> ReservationOut:
    names = _names(db, {r.created_by})
    return ReservationOut(id=r.id, reservation_code=r.reservation_code, batch_id=r.batch_id, batch_code=_code(db, r.batch_id),
                          owner_organization_id=r.owner_organization_id, recipient_organization_id=r.recipient_organization_id, purpose=r.purpose,
                          purpose_reference=r.purpose_reference, quantity=int(r.quantity), expires_at=r.expires_at, status=r.status,
                          created_by_name=names.get(r.created_by), created_at=r.created_at, release_reason=r.release_reason, closed_at=r.closed_at)


def transfer_out(db: Session, principal: Principal, t: CreditTransfer) -> TransferOut:
    names = _names(db, {t.requested_by, t.completed_by})
    pending = list(db.scalars(select(CreditPosition).where(CreditPosition.transfer_id == t.id, CreditPosition.status == "OPEN",
                                                           CreditPosition.state == "TRANSFER_PENDING")).all())
    custodians = {ls.custodian_org(db, p) for p in pending} or {t.sender_organization_id}
    can = t.status == "REQUESTED" and principal.user_id != t.requested_by and all(principal.can_in_org(P.CREDITS_CONFIRM, o) for o in custodians)
    return TransferOut(id=t.id, transfer_code=t.transfer_code, kind=t.kind, batch_id=t.batch_id, batch_code=_code(db, t.batch_id),
                       sender_organization_id=t.sender_organization_id, sender_name=_org(db, t.sender_organization_id),
                       recipient_organization_id=t.recipient_organization_id, recipient_name=_org(db, t.recipient_organization_id),
                       recipient_external_account_id=t.recipient_external_account_id, quantity=int(t.quantity), purpose=t.purpose,
                       purpose_reference=t.purpose_reference, reservation_id=t.reservation_id, status=t.status,
                       requested_by_name=names.get(t.requested_by), requested_at=t.requested_at,
                       completed_by_name=names.get(t.completed_by) if t.completed_by else None, completed_at=t.completed_at,
                       registry_transfer_reference=t.registry_transfer_reference, evidence_document_id=t.evidence_document_id,
                       close_reason=t.close_reason, can_complete=can,
                       completion_entry_id=db.scalar(select(CreditLedgerEntry.id).where(CreditLedgerEntry.transfer_id == t.id,
                                                                                        CreditLedgerEntry.entry_type == "TRANSFER_COMPLETE")))


def retirement_out(db: Session, principal: Principal, r: CreditRetirement) -> RetirementOut:
    names = _names(db, {r.requested_by, r.retired_by})
    pending = list(db.scalars(select(CreditPosition).where(CreditPosition.retirement_id == r.id, CreditPosition.status == "OPEN",
                                                           CreditPosition.state == "RETIREMENT_PENDING")).all())
    custodians = {ls.custodian_org(db, p) for p in pending} or {r.owner_organization_id}
    can = r.status == "REQUESTED" and principal.user_id != r.requested_by and all(principal.can_in_org(P.CREDITS_CONFIRM, o) for o in custodians)
    return RetirementOut(id=r.id, retirement_code=r.retirement_code, batch_id=r.batch_id, batch_code=_code(db, r.batch_id),
                         owner_organization_id=r.owner_organization_id, owner_name=_org(db, r.owner_organization_id), quantity=int(r.quantity),
                         beneficiary=r.beneficiary, reason=r.reason, status=r.status, requested_by_name=names.get(r.requested_by),
                         requested_at=r.requested_at, retired_by_name=names.get(r.retired_by) if r.retired_by else None, retired_at=r.retired_at,
                         registry_retirement_reference=r.registry_retirement_reference, retirement_date=r.retirement_date,
                         certificate_document_id=r.certificate_document_id,
                         retired_serials=json.loads(r.retired_serials) if r.retired_serials else None, close_reason=r.close_reason, can_retire=can)


def reversal_out(db: Session, v: CreditReversal) -> ReversalOut:
    names = _names(db, {v.requested_by, v.decided_by})
    return ReversalOut(id=v.id, reversal_code=v.reversal_code, reversed_entry_id=v.reversed_entry_id, batch_id=v.batch_id, reason=v.reason,
                       status=v.status, requested_by_name=names.get(v.requested_by),
                       decided_by_name=names.get(v.decided_by) if v.decided_by else None, decision_note=v.decision_note, entry_id=v.entry_id)


def holdings(db: Session, principal: Principal, positions: list[CreditPosition]) -> HoldingsOut:
    out = []
    for p in positions:
        b = db.get(CreditBatch, p.batch_id)
        assert b is not None
        proj = db.get(Project, b.project_id)
        mp = db.get(MonitoringPeriod, b.monitoring_period_id)
        mv = db.get(MethodologyVersion, b.methodology_version_id) if b.methodology_version_id else None
        std = db.get(Standard, b.standard_id) if b.standard_id else None
        i = db.get(CreditIssuance, b.issuance_id)
        out.append(HoldingOut(position_id=p.id, batch_id=b.id, batch_code=b.batch_code, owner_organization_id=p.owner_organization_id,
                              state=p.state, quantity=int(p.quantity),
                              project_code=proj.project_code if proj else None, project_name=proj.name if proj else None,
                              period_number=mp.period_number if mp else None, vintage=b.vintage,
                              methodology=mv.version_label if mv else None, standard=std.code if std else None,
                              registry_name=_org(db, b.registry_organization_id), issuance_code=i.issuance_code if i else None,
                              external_issuance_id=i.external_issuance_id if i else None,
                              registry_range=range_text(db.get(CreditSerialRange, p.serial_range_id)),
                              sub_range=sub_text(p), environment=p.environment))
    demo = principal.user.environment == "DEMO" and not out
    return HoldingsOut(holdings=out, demo_note=DEMO_NOTE if demo else None)


def ledger_lineage(db: Session, principal: Principal, retirement: CreditRetirement) -> dict[str, Any]:
    """retirement → entries → positions (consumed chain) → serial range → batch → (9A batch lineage)."""
    chain: list[dict[str, Any]] = [{"kind": "CREDIT_RETIREMENT", "code": retirement.retirement_code, "status": retirement.status,
                                    "registry_retirement_reference": retirement.registry_retirement_reference}]
    frontier = list(db.scalars(select(CreditPosition).where(CreditPosition.retirement_id == retirement.id)).all())
    seen: set[uuid.UUID] = set()
    while frontier:
        p = frontier.pop()
        if p.created_by_entry_id in seen:
            continue
        seen.add(p.created_by_entry_id)
        e = db.get(CreditLedgerEntry, p.created_by_entry_id)
        if e is None:
            continue
        chain.append({"kind": "LEDGER_ENTRY", "code": e.entry_code, "type": e.entry_type, "quantity": int(e.quantity)})
        frontier += list(db.scalars(select(CreditPosition).where(CreditPosition.consumed_by_entry_id == e.id)).all())
    b = db.get(CreditBatch, retirement.batch_id)
    chain.append({"kind": "CREDIT_BATCH", "id": str(retirement.batch_id), "code": b.batch_code if b else None})
    return {"chain": chain}
