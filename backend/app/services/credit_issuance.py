"""Phase 9A credit issuance (D5–D10, D12, D13). The registry owns the issued quantity, vintage and serial numbers; the platform records
them from registry evidence and a second person confirms.

- an issuance needs an ACCEPTED registry submission, the registry's issuance ID, date, whole-unit quantity and unit, and an
  ISSUANCE_STATEMENT PDF (or, through an API adapter, the hash of the registry's response); batches (registry-stated vintage) and serial
  ranges (verbatim) must add up exactly
- D5: issued and verified units must be explicitly configured as equivalent on the registry account (else UNIT_EQUIVALENCE_NOT_CONFIGURED);
  then the cumulative CONFIRMED issued quantity per VVB decision never exceeds the VVB-stated quantity (QUANTITY_EXCEEDS_VERIFIED)
- D6: several issuances (tranches) per accepted submission, each separately traceable
- D9: no serial is ever generated; duplicates are refused; numeric length / overlap checks only through a registry-specific parser
- D10: RECORDED → CONFIRMED by a registry.confirm holder who is not the recorder; VOIDED / CORRECTED / CANCELLED keep history; a
  correction is a new issuance with `corrects_issuance_id`
- D13: the first CONFIRMED issuance moves the project aggregate VERIFIED → ISSUED (period records stay authoritative)
- nothing here is inventory, ownership, reservation, transfer or retirement
"""
import json
import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.calculation import framework as fw
from app.core.context import RequestContext
from app.core.errors import Conflict, PermissionDenied, ValidationFailed
from app.integrations.registry import ParsedSerialRange, RegistryAdapter
from app.models import (
    CreditBatch,
    CreditIssuance,
    CreditSerialRange,
    Project,
    RegistryAccount,
    RegistryProjectRegistration,
    RegistrySubmission,
    VerificationDecision,
)
from app.models.base import utcnow
from app.models.documents import DocumentCategory
from app.repositories.sequences import next_code
from app.security.permissions import P
from app.security.principal import Principal
from app.services import project_service as psvc
from app.services import registry_access as ra
from app.services import registry_service as rs
from app.services.workflows import CREDIT_BATCH_MACHINE, CREDIT_ISSUANCE_MACHINE

ISSUED_LABEL = "Registry-issued credits"
COUNTED = ("CONFIRMED",)


# ---------------------------------------------------------------- quantity invariant (D5)
def confirmed_total(db: Session, decision_id: uuid.UUID, exclude: tuple[uuid.UUID | None, ...] = ()) -> Decimal:
    stmt = select(func.coalesce(func.sum(CreditIssuance.quantity), 0)).where(CreditIssuance.verification_decision_id == decision_id,
                                                                             CreditIssuance.status.in_(COUNTED))
    ids = [i for i in exclude if i is not None]
    if ids:
        stmt = stmt.where(CreditIssuance.id.not_in(ids))
    return Decimal(db.scalar(stmt) or 0)


def quantity_check(db: Session, account: RegistryAccount, d: VerificationDecision, unit: str, quantity: Decimal,
                   exclude: tuple[uuid.UUID | None, ...] = ()) -> None:
    if not (account.credit_unit and account.verified_unit_equivalent and unit == account.credit_unit
            and d.verified_quantity_unit == account.verified_unit_equivalent):
        raise Conflict("The registry credit unit and the VVB-stated verified unit are not configured as equivalent on this registry account "
                       "(no unit conversion is ever assumed).", error_code="UNIT_EQUIVALENCE_NOT_CONFIGURED",
                       details={"issued_unit": unit, "verified_unit": d.verified_quantity_unit, "account_credit_unit": account.credit_unit,
                                "account_verified_unit_equivalent": account.verified_unit_equivalent})
    assert d.verified_quantity is not None
    total = confirmed_total(db, d.id, exclude) + quantity
    if total > d.verified_quantity:
        raise Conflict(f"Cumulative issued quantity {total} would exceed the VVB-stated verified quantity {d.verified_quantity}.",
                       error_code="QUANTITY_EXCEEDS_VERIFIED",
                       details={"verified": str(d.verified_quantity), "already_confirmed": str(total - quantity), "requested": str(quantity)})


# ---------------------------------------------------------------- serial ranges (D9)
def _existing_serials(db: Session, registry_org_id: uuid.UUID, values: set[str], exclude_issuance: uuid.UUID | None) -> set[str]:
    if not values:
        return set()
    rows = db.execute(select(CreditSerialRange.serial_start, CreditSerialRange.serial_end, CreditBatch.status, CreditBatch.issuance_id)
                      .join(CreditBatch, CreditBatch.id == CreditSerialRange.batch_id)
                      .where(CreditSerialRange.registry_organization_id == registry_org_id,
                             CreditBatch.status.in_(("RECORDED", "ISSUED", "CANCELLED")))).all()
    used = set()
    for start, end, _, issuance_id in rows:
        if exclude_issuance is not None and issuance_id == exclude_issuance:
            continue
        used |= {x for x in (start, end) if x}
    return used & values


def _overlaps(db: Session, registry_org_id: uuid.UUID, parsed: list[ParsedSerialRange], exclude_issuance: uuid.UUID | None) -> list[str]:
    out = []
    for i, a in enumerate(parsed):
        for b in parsed[i + 1:]:
            if a.series == b.series and a.start <= b.end and b.start <= a.end:
                out.append(f"{a.series} {a.start}-{a.end} overlaps {b.start}-{b.end}")
    rows = db.execute(select(CreditSerialRange.parsed_series, CreditSerialRange.parsed_start, CreditSerialRange.parsed_end, CreditBatch.issuance_id)
                      .join(CreditBatch, CreditBatch.id == CreditSerialRange.batch_id)
                      .where(CreditSerialRange.registry_organization_id == registry_org_id, CreditSerialRange.parsed_series.is_not(None),
                             CreditBatch.status.in_(("RECORDED", "ISSUED", "CANCELLED")))).all()
    for series, start, end, issuance_id in rows:
        if exclude_issuance is not None and issuance_id == exclude_issuance:
            continue
        for a in parsed:
            if a.series == series and a.start <= int(end) and int(start) <= a.end:
                out.append(f"{a.series} {a.start}-{a.end} overlaps recorded {int(start)}-{int(end)}")
    return out


def _validate_batches(db: Session, adapter: RegistryAdapter, registry_org_id: uuid.UUID, quantity: int, batches: list[Any],
                      exclude_issuance: uuid.UUID | None) -> list[list[ParsedSerialRange | None]]:
    if sum(b.quantity for b in batches) != quantity:
        raise ValidationFailed("Batch quantities must add up to the issued quantity.", error_code="BATCH_TOTAL_MISMATCH")
    texts: list[str] = []
    parsed_all: list[list[ParsedSerialRange | None]] = []
    for b in batches:
        if sum(r.quantity for r in b.serial_ranges) != b.quantity:
            raise ValidationFailed(f"Serial range quantities must add up to the batch quantity ({b.vintage}).", error_code="RANGE_TOTAL_MISMATCH")
        parsed_batch: list[ParsedSerialRange | None] = []
        for r in b.serial_ranges:
            pr = None
            if r.serial_start is not None and r.serial_end is not None:
                texts += [r.serial_start, r.serial_end]
                pr = adapter.parse_serial_range(r.serial_start, r.serial_end)    # registry-specific parser only (MANUAL: none)
                if pr is not None and pr.end - pr.start + 1 != r.quantity:
                    raise ValidationFailed(f"Serial range {r.serial_start} – {r.serial_end} holds {pr.end - pr.start + 1} credits, not {r.quantity}.",
                                           error_code="SERIAL_RANGE_LENGTH_MISMATCH")
            parsed_batch.append(pr)
        parsed_all.append(parsed_batch)
    duplicates_in_request = {t for t in texts if texts.count(t) > 1}
    used = _existing_serials(db, registry_org_id, set(texts), exclude_issuance)
    if duplicates_in_request or used:
        raise Conflict("Serial numbers are already recorded at this registry.", error_code="DUPLICATE_SERIAL",
                       details={"serials": sorted(duplicates_in_request | used)})
    overlaps = _overlaps(db, registry_org_id, [p for b in parsed_all for p in b if p is not None], exclude_issuance)
    if overlaps:
        raise Conflict("Serial ranges overlap.", error_code="SERIAL_OVERLAP", details={"overlaps": overlaps})
    return parsed_all


# ---------------------------------------------------------------- recording
def _batch_transition(db: Session, ctx: RequestContext, b: CreditBatch, p: Project, to: str, reason: str | None) -> None:
    frm = b.status
    CREDIT_BATCH_MACHINE.assert_transition(frm, to)
    b.status = to
    ra.workflow(db, ctx, "credit_batch", b.id, frm, to, reason)
    ra.audit(db, ctx, f"CREDIT_BATCH_{to}", "credit_batch", b.id, p.organization_id,
             {"batch_code": b.batch_code, "status": to, "quantity": str(b.quantity), "unit": b.unit, "vintage": b.vintage}, reason, {"status": frm})


def _issuance_transition(db: Session, ctx: RequestContext, i: CreditIssuance, p: Project, to: str, action: str, reason: str | None,
                         **extra: Any) -> None:
    frm = i.status
    CREDIT_ISSUANCE_MACHINE.assert_transition(frm, to)
    i.status = to
    ra.workflow(db, ctx, "credit_issuance", i.id, frm, to, reason)
    ra.audit(db, ctx, action, "credit_issuance", i.id, p.organization_id,
             {"issuance_code": i.issuance_code, "status": to, "external_issuance_id": i.external_issuance_id, **extra}, reason, {"status": frm})


def batches_of(db: Session, issuance_id: uuid.UUID) -> list[CreditBatch]:
    return list(db.scalars(select(CreditBatch).where(CreditBatch.issuance_id == issuance_id).order_by(CreditBatch.seq)).all())


def ranges_of(db: Session, batch_id: uuid.UUID) -> list[CreditSerialRange]:
    return list(db.scalars(select(CreditSerialRange).where(CreditSerialRange.batch_id == batch_id).order_by(CreditSerialRange.seq)).all())


def issuances_of(db: Session, submission_id: uuid.UUID) -> list[CreditIssuance]:
    return list(db.scalars(select(CreditIssuance).where(CreditIssuance.registry_submission_id == submission_id)
                           .order_by(CreditIssuance.recorded_at)).all())


def _api_evidence(db: Session, adapter: RegistryAdapter, account: RegistryAccount, s: RegistrySubmission, data: Any) -> str:
    reg = db.get(RegistryProjectRegistration, s.registration_id)
    assert reg is not None and reg.external_project_id is not None
    found = next((x for x in adapter.get_issuances(ra.account_ref(db, account), reg.external_project_id)
                  if x.external_issuance_id == data.external_issuance_id), None)
    stated = None if found is None else (found.issuance_date, found.quantity, found.unit,
                                         [(b.vintage, b.quantity, [(r.serial_start, r.serial_end, r.quantity) for r in b.serial_ranges])
                                          for b in found.batches])
    given = (data.issuance_date, data.quantity, data.unit,
             [(b.vintage, b.quantity, [(r.serial_start, r.serial_end, r.quantity) for r in b.serial_ranges]) for b in data.batches])
    if found is None or stated != given:
        ra.event(db, account, "MISMATCH", None, submission_id=s.id, external_ref=data.external_issuance_id, outcome="ISSUANCE",
                 note="The recorded issuance does not match the registry's response")
        db.commit()
        raise Conflict("The issuance does not match what the registry returns.", error_code="ISSUANCE_MISMATCH")
    return found.payload_sha256 or fw.sha256({"issuance": str(given)})


def record(db: Session, ctx: RequestContext, principal: Principal, submission_id: uuid.UUID, data: Any, request_key: str | None = None,
           corrects: CreditIssuance | None = None, correction_reason: str | None = None, adapter: RegistryAdapter | None = None
           ) -> CreditIssuance:
    s, p = ra.submission_for(db, principal, submission_id, P.REGISTRY_MANAGE)
    if request_key:
        prior = db.scalars(select(CreditIssuance).where(CreditIssuance.client_request_key == request_key)).first()
        if prior is not None:
            if prior.registry_submission_id != s.id:
                raise Conflict("This Idempotency-Key was used for another request.", error_code="IDEMPOTENCY_KEY_REUSED")
            return prior
    if s.status != "ACCEPTED":
        raise Conflict(f"Issuances are recorded only on an ACCEPTED registry submission (it is {s.status}).", error_code="SUBMISSION_NOT_ACCEPTED")
    rs.check_source(db, ctx, s)
    account = db.get(RegistryAccount, s.registry_account_id)
    d = db.get(VerificationDecision, s.verification_decision_id)
    assert account is not None and d is not None
    impl = ra.adapter_for(account, adapter)
    quantity = Decimal(data.quantity)
    exclude = (corrects.id if corrects else None,)
    quantity_check(db, account, d, data.unit, quantity, exclude)
    dup = select(CreditIssuance).where(CreditIssuance.registry_organization_id == s.registry_organization_id,
                                       CreditIssuance.external_issuance_id == data.external_issuance_id,
                                       CreditIssuance.status.in_(("RECORDED", "CONFIRMED")))
    if corrects is not None:
        dup = dup.where(CreditIssuance.id != corrects.id)
    if db.scalars(dup).first():
        raise Conflict("This registry issuance is already recorded.", error_code="DUPLICATE_EXTERNAL_ISSUANCE")
    parsed = _validate_batches(db, impl, s.registry_organization_id, data.quantity, data.batches, corrects.id if corrects else None)
    api_hash = None
    if data.source == "API":
        if impl.mode != "API":
            raise Conflict("This registry account has no API adapter; record the issuance with the issuance statement.",
                           error_code="MANUAL_ACTION_REQUIRED")
        api_hash = _api_evidence(db, impl, account, s, data)
    else:
        if data.document_id is None:
            raise ValidationFailed("The registry's issuance statement (ISSUANCE_STATEMENT PDF) is required.", error_code="EVIDENCE_REQUIRED")
        rs._evidence(db, ra.SUBMISSION_ENTITY, s.id, data.document_id, {DocumentCategory.ISSUANCE_STATEMENT.value})
    snap = json.loads(s.snapshot or "{}")
    meth = snap.get("methodology") or {}
    std = snap.get("standard") or {}
    i = CreditIssuance(issuance_code=next_code(db, "credit_issuance", utcnow().year), registry_submission_id=s.id, project_id=p.id,
                       monitoring_period_id=s.monitoring_period_id, registry_account_id=account.id,
                       registry_organization_id=s.registry_organization_id,
                       verification_decision_id=d.id, external_issuance_id=data.external_issuance_id, issuance_date=data.issuance_date,
                       quantity=quantity, unit=data.unit, source=data.source,
                       evidence_document_id=data.document_id if data.source == "MANUAL" else None,
                       api_response_sha256=api_hash, corrects_issuance_id=corrects.id if corrects else None, correction_reason=correction_reason,
                       client_request_key=request_key, status="RECORDED", recorded_by=principal.user_id, environment=p.environment)
    db.add(i)
    db.flush()
    for n, (b, pb) in enumerate(zip(data.batches, parsed, strict=True), start=1):
        batch = CreditBatch(batch_code=next_code(db, "credit_batch", utcnow().year), issuance_id=i.id, project_id=p.id,
                            monitoring_period_id=s.monitoring_period_id, registry_organization_id=s.registry_organization_id,
                            registry_account_id=account.id, verification_decision_id=d.id,
                            methodology_version_id=uuid.UUID(meth["version_id"]) if meth.get("version_id") else None,
                            standard_id=uuid.UUID(std["id"]) if std.get("id") else None, seq=n, vintage=b.vintage, quantity=Decimal(b.quantity),
                            unit=data.unit, status="RECORDED", environment=p.environment)
        db.add(batch)
        db.flush()
        for m, (r, pr) in enumerate(zip(b.serial_ranges, pb, strict=True), start=1):
            db.add(CreditSerialRange(batch_id=batch.id, registry_organization_id=s.registry_organization_id, seq=m, serial_start=r.serial_start,
                                     serial_end=r.serial_end, quantity=Decimal(r.quantity), parsed_series=pr.series if pr else None,
                                     parsed_start=Decimal(pr.start) if pr else None, parsed_end=Decimal(pr.end) if pr else None,
                                     is_current=False, environment=p.environment))
        ra.workflow(db, ctx, "credit_batch", batch.id, None, "RECORDED", None)
    ra.event(db, account, "EXTERNAL_REFERENCE_RECORDED", principal.user_id, submission_id=s.id, issuance_id=i.id,
             external_ref=data.external_issuance_id, document_id=i.evidence_document_id, payload_sha256=api_hash, outcome="ISSUANCE_RECORDED")
    ra.workflow(db, ctx, "credit_issuance", i.id, None, "RECORDED", correction_reason)
    ra.audit(db, ctx, "CREDIT_ISSUANCE_CORRECTION_RECORDED" if corrects else "CREDIT_ISSUANCE_RECORDED", "credit_issuance", i.id, p.organization_id,
             {"issuance_code": i.issuance_code, "external_issuance_id": i.external_issuance_id, "issuance_date": i.issuance_date,
              "quantity": str(quantity), "unit": i.unit, "source": i.source, "evidence_document_id": i.evidence_document_id,
              "api_response_sha256": api_hash, "batches": len(data.batches), "corrects_issuance_id": i.corrects_issuance_id,
              "label": f"{ISSUED_LABEL} — registry-stated"}, correction_reason)
    db.commit()
    return i


def confirm(db: Session, ctx: RequestContext, principal: Principal, issuance_id: uuid.UUID, note: str | None) -> CreditIssuance:
    i, s, p = ra.issuance_for(db, principal, issuance_id, P.REGISTRY_CONFIRM)
    if i.status != "RECORDED":
        raise Conflict(f"Only a RECORDED issuance can be confirmed (it is {i.status}).", error_code="ISSUANCE_NOT_RECORDED")
    if principal.user_id == i.recorded_by:
        raise PermissionDenied("The issuance must be confirmed by someone other than the person who recorded it.",
                               error_code="SEPARATION_OF_DUTIES", details={"reasons": ["you recorded this issuance"]})
    db.scalars(select(RegistrySubmission).where(RegistrySubmission.id == s.id).with_for_update()).one()   # serialize confirmations
    if s.status != "ACCEPTED":
        raise Conflict(f"The registry submission is {s.status}.", error_code="SUBMISSION_NOT_ACCEPTED")
    account = db.get(RegistryAccount, i.registry_account_id)
    d = db.get(VerificationDecision, i.verification_decision_id)
    assert account is not None and d is not None
    quantity_check(db, account, d, i.unit, i.quantity, (i.id, i.corrects_issuance_id))
    original = db.get(CreditIssuance, i.corrects_issuance_id) if i.corrects_issuance_id else None
    try:
        if original is not None:
            if original.status != "CONFIRMED":
                raise Conflict(f"The corrected issuance is {original.status}.", error_code="ISSUANCE_NOT_CONFIRMED")
            original.corrected_by_issuance_id = i.id
            _issuance_transition(db, ctx, original, p, "CORRECTED", "CREDIT_ISSUANCE_CORRECTED", i.correction_reason, corrected_by=i.issuance_code)
            for b in batches_of(db, original.id):
                _batch_transition(db, ctx, b, p, "SUPERSEDED", f"Corrected by {i.issuance_code}")
                for r in ranges_of(db, b.id):
                    r.is_current = False
            db.flush()
        i.confirmed_by, i.confirmed_at = principal.user_id, utcnow()
        _issuance_transition(db, ctx, i, p, "CONFIRMED", "CREDIT_ISSUANCE_CONFIRMED", note, quantity=str(i.quantity), unit=i.unit)
        for b in batches_of(db, i.id):
            _batch_transition(db, ctx, b, p, "ISSUED", None)
            for r in ranges_of(db, b.id):
                r.is_current = True
        db.flush()
    except IntegrityError:
        db.rollback()
        raise Conflict("A registry reference or serial number of this issuance is already confirmed.",
                       error_code="DUPLICATE_REGISTRY_REFERENCE") from None
    if p.status == "VERIFIED":
        psvc.transition_to(db, ctx, p, "ISSUED", "PROJECT_STATUS_CHANGED", "FIRST_ISSUANCE_CONFIRMED",
                           "First registry issuance confirmed (aggregate status; periods are authoritative)")
    db.commit()
    return i


def void(db: Session, ctx: RequestContext, principal: Principal, issuance_id: uuid.UUID, reason: str) -> CreditIssuance:
    i, _, p = ra.issuance_for(db, principal, issuance_id, P.REGISTRY_MANAGE)
    if i.status != "RECORDED":
        raise Conflict(f"Only a RECORDED (unconfirmed) issuance can be voided (it is {i.status}).", error_code="ISSUANCE_NOT_RECORDED")
    i.voided_by, i.voided_at, i.void_reason = principal.user_id, utcnow(), reason
    _issuance_transition(db, ctx, i, p, "VOIDED", "CREDIT_ISSUANCE_VOIDED", reason)
    for b in batches_of(db, i.id):
        _batch_transition(db, ctx, b, p, "VOIDED", reason)
    db.commit()
    return i


def cancel(db: Session, ctx: RequestContext, principal: Principal, issuance_id: uuid.UUID, reason: str, document_id: uuid.UUID) -> CreditIssuance:
    """The registry cancelled a confirmed issuance (registry evidence required). Serials stay allocated; history is kept."""
    i, s, p = ra.issuance_for(db, principal, issuance_id, P.REGISTRY_MANAGE)
    if i.status != "CONFIRMED":
        raise Conflict(f"Only a CONFIRMED issuance can be cancelled (it is {i.status}).", error_code="ISSUANCE_NOT_CONFIRMED")
    rs._evidence(db, ra.SUBMISSION_ENTITY, s.id, document_id, {DocumentCategory.ISSUANCE_STATEMENT.value, DocumentCategory.REGISTRY_RESPONSE.value})
    i.cancelled_by, i.cancelled_at, i.cancel_reason, i.cancel_document_id = principal.user_id, utcnow(), reason, document_id
    _issuance_transition(db, ctx, i, p, "CANCELLED", "CREDIT_ISSUANCE_CANCELLED", reason, document_id=document_id)
    for b in batches_of(db, i.id):
        _batch_transition(db, ctx, b, p, "CANCELLED", reason)
    account = db.get(RegistryAccount, i.registry_account_id)
    assert account is not None
    ra.event(db, account, "RESPONSE_RECORDED", principal.user_id, submission_id=s.id, issuance_id=i.id, document_id=document_id,
             outcome="ISSUANCE_CANCELLED", note=reason)
    db.commit()
    return i


def correct(db: Session, ctx: RequestContext, principal: Principal, issuance_id: uuid.UUID, data: Any, reason: str,
            adapter: RegistryAdapter | None = None) -> CreditIssuance:
    original, s, _ = ra.issuance_for(db, principal, issuance_id, P.REGISTRY_MANAGE)
    if original.status != "CONFIRMED":
        raise Conflict(f"Only a CONFIRMED issuance can be corrected (it is {original.status}).", error_code="ISSUANCE_NOT_CONFIRMED")
    if db.scalars(select(CreditIssuance).where(CreditIssuance.corrects_issuance_id == original.id, CreditIssuance.status == "RECORDED")).first():
        raise Conflict("A correction of this issuance is already awaiting confirmation.", error_code="CORRECTION_PENDING")
    return record(db, ctx, principal, s.id, data, corrects=original, correction_reason=reason, adapter=adapter)
