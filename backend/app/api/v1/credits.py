"""Credits API (`/api/v1/credits`). Phase 9A: read-only registry-issued batches. Phase 9B: the credit ledger — inventory opening (dual
control), derived balances, reservations, INTERNAL / REGISTRY transfers, registry-evidenced retirements, reversals, holder view and manual
registry inventory reconciliation. Bodies carry movement quantities only (never a balance); every POST accepts an Idempotency-Key.
No marketplace, listing, pricing, order, checkout, payment or payout endpoint exists."""
import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, Form, Header, UploadFile, status
from sqlalchemy import select

from app.api.deps import DB, Ctx, read_upload, require_any
from app.core.errors import NotFound
from app.models import CreditPosition, CreditReservation, CreditRetirement, CreditReversal, CreditTransfer, Organization
from app.schemas.lab import DocumentRef
from app.schemas.ledger import (
    EntryOut,
    HoldingsOut,
    InventoryOut,
    NoteIn,
    OpeningOut,
    PositionOut,
    ReasonIn,
    RecipientOut,
    ReconcileIn,
    ReconcileOut,
    ReservationIn,
    ReservationOut,
    RetireIn,
    RetirementIn,
    RetirementOut,
    ReversalOut,
    TransferCompleteIn,
    TransferIn,
    TransferOut,
)
from app.schemas.registry import BatchOut, LineageOut
from app.security.permissions import P
from app.security.principal import Principal
from app.services import ledger_mappers as lm
from app.services import ledger_service as ls
from app.services import registry_access as ra
from app.services import registry_mappers as rm

router = APIRouter(prefix="/credits", tags=["credits — issued batches and ledger"])

Reader = Annotated[Principal, Depends(require_any(P.CREDITS_READ))]
LedgerUser = Annotated[Principal, Depends(require_any(P.CREDITS_READ, P.CREDITS_MANAGE, P.CREDITS_CONFIRM))]
Manager = Annotated[Principal, Depends(require_any(P.CREDITS_MANAGE))]
Confirmer = Annotated[Principal, Depends(require_any(P.CREDITS_CONFIRM))]
ManagerOrConfirmer = Annotated[Principal, Depends(require_any(P.CREDITS_MANAGE, P.CREDITS_CONFIRM))]
Retirer = Annotated[Principal, Depends(require_any(P.CREDITS_MANAGE, P.CREDITS_HOLDER_RETIRE))]
AnyCredit = Annotated[Principal, Depends(require_any(P.CREDITS_READ, P.CREDITS_MANAGE, P.CREDITS_CONFIRM, P.CREDITS_HOLDER_READ,
                                                     P.CREDITS_HOLDER_RETIRE))]
Holder = Annotated[Principal, Depends(require_any(P.CREDITS_HOLDER_READ))]
IdemKey = Annotated[str | None, Header(alias="Idempotency-Key", max_length=80)]


@router.get("/batches", response_model=list[BatchOut], summary="Registry-issued credit batches (ISSUED, plus SUPERSEDED / CANCELLED history)")
def list_batches(principal: Reader, db: DB, project_id: uuid.UUID | None = None, period_id: uuid.UUID | None = None) -> list[BatchOut]:
    if project_id:
        ra.credits_project(db, principal, project_id)
    return [rm.batch_out(db, b) for b in rm.batches(db, principal, project_id, period_id)]


@router.get("/batches/{batch_id}", response_model=BatchOut)
def get_batch(batch_id: uuid.UUID, principal: Reader, db: DB) -> BatchOut:
    b, _ = ra.batch_for(db, principal, batch_id)
    return rm.batch_out(db, b)


@router.get("/batches/{batch_id}/lineage", response_model=LineageOut,
            summary="batch → issuance → registry submission → VVB decision → … → calculation → farms → farmer codes")
def batch_lineage(batch_id: uuid.UUID, principal: Reader, db: DB) -> LineageOut:
    b, _ = ra.batch_for(db, principal, batch_id)
    return LineageOut(**rm.lineage(db, principal, b))


# ================================================================ Phase 9B — credit ledger
@router.get("/inventory", response_model=InventoryOut,
            summary="Derived balances per batch and owner: Issued (registry) · Available · Reserved · Pending transfer / retirement · "
                    "Transferred out · Retired")
def inventory(principal: LedgerUser, db: DB, ctx: Ctx, project_id: uuid.UUID | None = None) -> InventoryOut:
    batches = ls.visible_batches(db, principal, project_id)
    ls.expire_due(db, ctx, batch_ids=[b.id for b in batches])
    return lm.inventory(db, principal, batches)


@router.get("/batches/{batch_id}/positions", response_model=list[PositionOut])
def positions(batch_id: uuid.UUID, principal: LedgerUser, db: DB, include_consumed: bool = False) -> list[PositionOut]:
    b = ls.visible_batch(db, principal, batch_id)
    stmt = select(CreditPosition).where(CreditPosition.batch_id == b.id)
    if not include_consumed:
        stmt = stmt.where(CreditPosition.status == "OPEN")
    return [lm.position_out(db, p) for p in db.scalars(stmt.order_by(CreditPosition.serial_range_id, CreditPosition.created_at)).all()]


@router.post("/batches/{batch_id}/open", response_model=OpeningOut, status_code=status.HTTP_201_CREATED,
             summary="Request to open a registry-issued (ISSUED) batch in the ledger; a second person confirms")
def request_opening(batch_id: uuid.UUID, principal: Manager, db: DB, ctx: Ctx, key: IdemKey = None) -> OpeningOut:
    return lm.opening_out(db, principal, ls.request_opening(db, ctx, principal, batch_id, key))


@router.post("/openings/{opening_id}/confirm", response_model=OpeningOut, summary="Confirm the opening (credits.confirm; never the requester)")
def confirm_opening(opening_id: uuid.UUID, principal: Confirmer, db: DB, ctx: Ctx, key: IdemKey = None) -> OpeningOut:
    return lm.opening_out(db, principal, ls.confirm_opening(db, ctx, principal, opening_id, key))


@router.post("/openings/{opening_id}/cancel", response_model=OpeningOut)
def cancel_opening(opening_id: uuid.UUID, body: ReasonIn, principal: ManagerOrConfirmer, db: DB, ctx: Ctx, key: IdemKey = None) -> OpeningOut:
    return lm.opening_out(db, principal, ls.cancel_opening(db, ctx, principal, opening_id, body.reason))


# ---------------------------------------------------------------- reservations
def _visible(db: DB, principal: Principal, rows: list[Any]) -> list[Any]:
    return [r for r in rows if ls.can_see_batch(db, principal, ls.get_batch(db, r.batch_id))]


@router.get("/reservations", response_model=list[ReservationOut])
def list_reservations(principal: LedgerUser, db: DB, batch_id: uuid.UUID | None = None) -> list[ReservationOut]:
    stmt = select(CreditReservation)
    if batch_id:
        stmt = stmt.where(CreditReservation.batch_id == batch_id)
    rows = _visible(db, principal, list(db.scalars(stmt.order_by(CreditReservation.created_at.desc())).all()))
    return [lm.reservation_out(db, r) for r in rows]


@router.post("/reservations", response_model=ReservationOut, status_code=status.HTTP_201_CREATED,
             summary="Reserve available credits (purpose_reference stays generic); consumes AVAILABLE positions")
def create_reservation(body: ReservationIn, principal: Manager, db: DB, ctx: Ctx, key: IdemKey = None) -> ReservationOut:
    return lm.reservation_out(db, ls.create_reservation(db, ctx, principal, body, key))


@router.post("/reservations/expire-due", summary="Expire every due reservation of the caller's organizations (lazy expiry also runs on reads)")
def expire_due(principal: Manager, db: DB, ctx: Ctx, key: IdemKey = None) -> dict[str, int]:
    orgs = {g.organization_id for g in principal.grants if g.organization_id and P.CREDITS_MANAGE in g.permissions}
    return {"expired": ls.expire_due(db, ctx, org_ids=orgs)}


@router.post("/reservations/{reservation_id}/release", response_model=ReservationOut)
def release_reservation(reservation_id: uuid.UUID, body: ReasonIn, principal: Manager, db: DB, ctx: Ctx, key: IdemKey = None) -> ReservationOut:
    return lm.reservation_out(db, ls.release_reservation(db, ctx, principal, reservation_id, body.reason, key))


# ---------------------------------------------------------------- transfers
@router.get("/recipients", response_model=list[RecipientOut],
            summary="Organizations that may receive credits (active buyer / project-developer organizations of an environment)")
def recipients(principal: Manager, db: DB, environment: str = "LIVE") -> list[RecipientOut]:
    rows = db.scalars(select(Organization).where(Organization.org_type.in_(ls.RECIPIENT_ORG_TYPES), Organization.status == "ACTIVE",
                                                 Organization.environment == environment).order_by(Organization.name)).all()
    return [RecipientOut(id=o.id, code=o.code, name=o.name, org_type=o.org_type) for o in rows]


@router.get("/transfers", response_model=list[TransferOut])
def list_transfers(principal: AnyCredit, db: DB, batch_id: uuid.UUID | None = None) -> list[TransferOut]:
    stmt = select(CreditTransfer)
    if batch_id:
        stmt = stmt.where(CreditTransfer.batch_id == batch_id)
    rows = []
    for t in db.scalars(stmt.order_by(CreditTransfer.requested_at.desc())).all():
        try:
            rows.append(ls._transfer(db, principal, t.id))
        except NotFound:
            continue
    return [lm.transfer_out(db, principal, t) for t in rows]


@router.post("/transfers", response_model=TransferOut, status_code=status.HTTP_201_CREATED,
             summary="Request an INTERNAL (beneficial) or REGISTRY transfer; credits become TRANSFER_PENDING. No price, order or payment")
def request_transfer(body: TransferIn, principal: Manager, db: DB, ctx: Ctx, key: IdemKey = None) -> TransferOut:
    return lm.transfer_out(db, principal, ls.request_transfer(db, ctx, principal, body, key))


@router.post("/transfers/{transfer_id}/documents", response_model=DocumentRef, status_code=status.HTTP_201_CREATED,
             summary="Attach the registry's transfer evidence (REGISTRY_TRANSFER_EVIDENCE, PDF)")
def transfer_document(transfer_id: uuid.UUID, principal: ManagerOrConfirmer, db: DB, ctx: Ctx, file: Annotated[UploadFile, File()],
                      title: Annotated[str | None, Form(max_length=200)] = None) -> DocumentRef:
    d = ls.upload(db, ctx, principal, ls.TRANSFER_ENTITY, transfer_id, file.filename, read_upload(file), title)
    return DocumentRef(document_id=d.id, category=d.category, title=d.title, file_name=None, sha256=None, uploaded_at=d.created_at)


@router.post("/transfers/{transfer_id}/complete", response_model=TransferOut,
             summary="Complete atomically (second person); REGISTRY transfers need the registry reference and evidence")
def complete_transfer(transfer_id: uuid.UUID, principal: Confirmer, db: DB, ctx: Ctx, body: TransferCompleteIn | None = None,
                      key: IdemKey = None) -> TransferOut:
    return lm.transfer_out(db, principal, ls.complete_transfer(db, ctx, principal, transfer_id, body, key))


@router.post("/transfers/{transfer_id}/cancel", response_model=TransferOut)
def cancel_transfer(transfer_id: uuid.UUID, body: ReasonIn, principal: Manager, db: DB, ctx: Ctx, key: IdemKey = None) -> TransferOut:
    return lm.transfer_out(db, principal, ls.close_transfer(db, ctx, principal, transfer_id, "CANCELLED", body.reason, key))


@router.post("/transfers/{transfer_id}/reject", response_model=TransferOut)
def reject_transfer(transfer_id: uuid.UUID, body: ReasonIn, principal: Confirmer, db: DB, ctx: Ctx, key: IdemKey = None) -> TransferOut:
    return lm.transfer_out(db, principal, ls.close_transfer(db, ctx, principal, transfer_id, "REJECTED", body.reason, key))


# ---------------------------------------------------------------- retirements
@router.get("/retirements", response_model=list[RetirementOut])
def list_retirements(principal: AnyCredit, db: DB, batch_id: uuid.UUID | None = None) -> list[RetirementOut]:
    stmt = select(CreditRetirement)
    if batch_id:
        stmt = stmt.where(CreditRetirement.batch_id == batch_id)
    rows = []
    for r in db.scalars(stmt.order_by(CreditRetirement.requested_at.desc())).all():
        try:
            rows.append(ls._retirement(db, principal, r.id))
        except NotFound:
            continue
    return [lm.retirement_out(db, principal, r) for r in rows]


@router.post("/retirements", response_model=RetirementOut, status_code=status.HTTP_201_CREATED,
             summary="Request retirement (owner's credit manager or holder); credits become RETIREMENT_PENDING")
def request_retirement(body: RetirementIn, principal: Retirer, db: DB, ctx: Ctx, key: IdemKey = None) -> RetirementOut:
    return lm.retirement_out(db, principal, ls.request_retirement(db, ctx, principal, body, key))


@router.post("/retirements/{retirement_id}/documents", response_model=DocumentRef, status_code=status.HTTP_201_CREATED,
             summary="Attach the registry's retirement certificate (RETIREMENT_CERTIFICATE, PDF)")
def retirement_document(retirement_id: uuid.UUID, principal: ManagerOrConfirmer, db: DB, ctx: Ctx, file: Annotated[UploadFile, File()],
                        title: Annotated[str | None, Form(max_length=200)] = None) -> DocumentRef:
    d = ls.upload(db, ctx, principal, ls.RETIREMENT_ENTITY, retirement_id, file.filename, read_upload(file), title)
    return DocumentRef(document_id=d.id, category=d.category, title=d.title, file_name=None, sha256=None, uploaded_at=d.created_at)


@router.post("/retirements/{retirement_id}/retire", response_model=RetirementOut,
             summary="Record the registry retirement (reference + certificate + registry-stated serials; second person) — permanent")
def retire(retirement_id: uuid.UUID, body: RetireIn, principal: Confirmer, db: DB, ctx: Ctx, key: IdemKey = None) -> RetirementOut:
    return lm.retirement_out(db, principal, ls.retire(db, ctx, principal, retirement_id, body, key))


@router.post("/retirements/{retirement_id}/cancel", response_model=RetirementOut)
def cancel_retirement(retirement_id: uuid.UUID, body: ReasonIn, principal: Retirer, db: DB, ctx: Ctx, key: IdemKey = None) -> RetirementOut:
    return lm.retirement_out(db, principal, ls.close_retirement(db, ctx, principal, retirement_id, "CANCELLED", body.reason, key))


@router.post("/retirements/{retirement_id}/reject", response_model=RetirementOut)
def reject_retirement(retirement_id: uuid.UUID, body: ReasonIn, principal: Confirmer, db: DB, ctx: Ctx, key: IdemKey = None) -> RetirementOut:
    return lm.retirement_out(db, principal, ls.close_retirement(db, ctx, principal, retirement_id, "REJECTED", body.reason, key))


@router.get("/retirements/{retirement_id}/lineage",
            summary="retirement → ledger entries → positions → batch → issuance → registry submission → VVB decision → … → farmer codes")
def retirement_lineage(retirement_id: uuid.UUID, principal: AnyCredit, db: DB) -> dict[str, Any]:
    r = ls._retirement(db, principal, retirement_id)
    out = lm.ledger_lineage(db, principal, r)
    b = ls.get_batch(db, r.batch_id)
    p = ls.batch_project(db, b)
    if any(principal.can_in_org(c, p.organization_id) for c in ls.PROJECT_READ):
        out["batch_lineage"] = rm.lineage(db, principal, b)       # holders get the ledger chain only (no farm / farmer data)
    return out


# ---------------------------------------------------------------- ledger entries and reversals
@router.get("/entries/{entry_id}", response_model=EntryOut)
def get_entry(entry_id: uuid.UUID, principal: LedgerUser, db: DB) -> EntryOut:
    return lm.entry_out(db, ls.entry_for(db, principal, entry_id))


@router.post("/entries/{entry_id}/reverse", response_model=ReversalOut, status_code=status.HTTP_201_CREATED,
             summary="Request a compensating REVERSAL of a completed INTERNAL transfer (a second person applies it)")
def request_reversal(entry_id: uuid.UUID, body: ReasonIn, principal: Manager, db: DB, ctx: Ctx, key: IdemKey = None) -> ReversalOut:
    return lm.reversal_out(db, ls.request_reversal(db, ctx, principal, entry_id, body.reason, key))


@router.get("/reversals", response_model=list[ReversalOut])
def list_reversals(principal: LedgerUser, db: DB) -> list[ReversalOut]:
    rows = _visible(db, principal, list(db.scalars(select(CreditReversal).order_by(CreditReversal.requested_at.desc())).all()))
    return [lm.reversal_out(db, v) for v in rows]


@router.post("/reversals/{reversal_id}/apply", response_model=ReversalOut)
def apply_reversal(reversal_id: uuid.UUID, body: NoteIn, principal: Confirmer, db: DB, ctx: Ctx, key: IdemKey = None) -> ReversalOut:
    return lm.reversal_out(db, ls.decide_reversal(db, ctx, principal, reversal_id, True, body.note, key))


@router.post("/reversals/{reversal_id}/reject", response_model=ReversalOut)
def reject_reversal(reversal_id: uuid.UUID, body: NoteIn, principal: Confirmer, db: DB, ctx: Ctx, key: IdemKey = None) -> ReversalOut:
    return lm.reversal_out(db, ls.decide_reversal(db, ctx, principal, reversal_id, False, body.note, key))


# ---------------------------------------------------------------- holders and reconciliation
@router.get("/holdings", response_model=HoldingsOut, summary="Own positions of the caller's organization (holder view, allow-listed)")
def holdings(principal: Holder, db: DB) -> HoldingsOut:
    return lm.holdings(db, principal, ls.holder_positions(db, principal))


@router.post("/accounts/{account_id}/statements", response_model=DocumentRef, status_code=status.HTTP_201_CREATED,
             summary="Attach a registry account statement (REGISTRY_RESPONSE, PDF) for manual reconciliation")
def account_statement(account_id: uuid.UUID, principal: Manager, db: DB, ctx: Ctx, file: Annotated[UploadFile, File()],
                      title: Annotated[str | None, Form(max_length=200)] = None) -> DocumentRef:
    d = ls.upload(db, ctx, principal, ls.ACCOUNT_ENTITY, account_id, file.filename, read_upload(file), title)
    return DocumentRef(document_id=d.id, category=d.category, title=d.title, file_name=None, sha256=None, uploaded_at=d.created_at)


@router.post("/accounts/{account_id}/reconcile", response_model=ReconcileOut,
             summary="Compare platform positions held in the registry account with the registry statement (records MISMATCH; never auto-fixes)")
def reconcile(account_id: uuid.UUID, body: ReconcileIn, principal: Manager, db: DB, ctx: Ctx, key: IdemKey = None) -> ReconcileOut:
    e = ls.reconcile_account(db, ctx, principal, account_id, body, key)
    return ReconcileOut(event_id=e.id, event_type=e.event_type, note=e.note, occurred_at=e.occurred_at)
