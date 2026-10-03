"""Phase 12A job handlers — thin adapters from an allow-listed job to EXISTING domain services.

Rules (locked):
- No business rule lives here. Expiry calls the Phase 9B / 10 functions that already lock the row (UPDLOCK, HOLDLOCK, ROWLOCK),
  re-check the deadline and the state, write the ledger / workflow / audit records and commit one short transaction per object
  (`ledger_service.run`, deadlock retry included). Running a sweep twice, or two sweeps at once, expires each object at most once.
- Lazy expiry on reads and writes is unchanged and remains the correctness guarantee; a sweep only makes expiry timely.
- A payment reported by the buyer (PENDING_CONFIRMATION) does not stop reservation expiry (Phase 10 behaviour): the reservation sweep
  expires it at its deadline; a later confirmation routes the order to ATTENTION_REQUIRED through the existing human workflow.
- Work is bounded: keyset batches of JOB_BATCH_SIZE and a cooperative time budget below the task's soft time limit.
- Nothing here recognizes / reverses revenue, settles, pays, confirms, approves, reconciles, issues, transfers or retires anything.
"""
import time
import uuid
from collections.abc import Callable, Iterator, Sequence
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.audit.service import record
from app.core import metrics
from app.core.config import get_settings
from app.core.context import RequestContext
from app.core.errors import AppError, NotFound
from app.integrations.malware import get_scanner
from app.integrations.storage import KEY_PATTERN, StorageError, get_deletion_storage, get_storage
from app.models import BackgroundJob, CreditReservation, Document, DocumentScan, DocumentVersion, MarketplaceListing, Order
from app.models.base import utcnow
from app.services import ledger_service as ls
from app.services import marketplace_service as ms
from app.services import order_service as os_
from app.workers import joblog

Handler = Callable[[Session, RequestContext, BackgroundJob, float], dict[str, Any]]


class SweepItemErrors(AppError):
    status_code, error_code, message = 409, "SWEEP_ITEM_ERRORS", "Some objects could not be processed; see the job result."


def _keyset(db: Session, model: Any, due_col: Any, filters: Sequence[Any], size: int, deadline: float
            ) -> Iterator[list[tuple[uuid.UUID, datetime]]]:
    """Batches of (id, due) ordered by (due, id); keyset pagination guarantees progress even when an object is skipped."""
    last: tuple[datetime, uuid.UUID] | None = None
    while time.monotonic() < deadline:
        stmt = select(model.id, due_col).where(*filters)
        if last is not None:
            stmt = stmt.where(or_(due_col > last[0], and_(due_col == last[0], model.id > last[1])))
        rows = [(r[0], r[1]) for r in db.execute(stmt.order_by(due_col, model.id).limit(size)).all()]
        db.commit()                                                   # end the read transaction before the per-object writes
        if not rows:
            return
        yield rows
        if len(rows) < size:
            return
        last = (rows[-1][1], rows[-1][0])


def _process(db: Session, ctx: RequestContext, job: BackgroundJob, label: str, ids: list[uuid.UUID], one: Callable[[uuid.UUID], bool],
             counts: dict[str, int]) -> None:
    for oid in ids:
        counts["examined"] += 1
        try:
            if one(oid):
                counts[label] += 1
        except AppError as e:                                         # a business refusal of one object: record it, keep sweeping
            db.rollback()
            counts["item_errors"] += 1
            joblog.event("job_item_error", job_id=job.id, job_code=job.job_code, entity_type=label, entity_id=oid, error_code=e.error_code)


def _finish(counts: dict[str, int], complete: bool) -> dict[str, Any]:
    out: dict[str, Any] = {**counts, "complete": complete}
    if counts["item_errors"]:
        raise SweepItemErrors(details=out)
    return out


# ---------------------------------------------------------------- 9B credit reservations
def expire_credit_reservations(db: Session, ctx: RequestContext, job: BackgroundJob, deadline: float) -> dict[str, Any]:
    s = get_settings()
    counts = {"examined": 0, "expired": 0, "item_errors": 0}
    complete = True

    def one(rid: uuid.UUID) -> bool:
        def op() -> bool:
            r = ls.lock_reservation(db, rid)                           # UPDLOCK / HOLDLOCK / ROWLOCK, fresh state
            if r is None or r.status != "ACTIVE" or r.expires_at > utcnow() or r.environment != job.environment:
                return False                                           # consumed / released / expired / extended meanwhile
            assert ctx.user_id is not None
            ls.expire_reservation_in_tx(db, ctx, r, ctx.user_id)       # the same entry as lazy expiry (RESERVATION_EXPIRE)
            return True
        return bool(ls.run(db, ctx, op))

    filters = [CreditReservation.status == "ACTIVE", CreditReservation.environment == job.environment,
               CreditReservation.expires_at <= utcnow()]
    for batch in _keyset(db, CreditReservation, CreditReservation.expires_at, filters, s.JOB_BATCH_SIZE, deadline):
        _process(db, ctx, job, "expired", [b[0] for b in batch], one, counts)
    if time.monotonic() >= deadline:
        complete = False
    return _finish(counts, complete)


# ---------------------------------------------------------------- 10 marketplace orders, then listings (Phase 10 lock order)
def expire_marketplace_objects(db: Session, ctx: RequestContext, job: BackgroundJob, deadline: float) -> dict[str, Any]:
    s = get_settings()
    counts = {"examined": 0, "orders_expired": 0, "listings_expired": 0, "item_errors": 0}

    def order(oid: uuid.UUID) -> bool:
        o = db.get(Order, oid, populate_existing=True)
        # expire_if_due locks the order → its reservations, re-checks PLACED / deadline / a held payment, then expires all together
        return o is not None and o.environment == job.environment and os_.expire_if_due(db, ctx, o)

    def listing(lid: uuid.UUID) -> bool:
        lst = db.get(MarketplaceListing, lid, populate_existing=True)
        return lst is not None and lst.environment == job.environment and ms.expire_listing_if_due(db, ctx, lst)

    now = utcnow()
    for batch in _keyset(db, Order, Order.expires_at, [Order.status == "PLACED", Order.environment == job.environment, Order.expires_at <= now],
                         s.JOB_BATCH_SIZE, deadline):
        _process(db, ctx, job, "orders_expired", [b[0] for b in batch], order, counts)
    for batch in _keyset(db, MarketplaceListing, MarketplaceListing.valid_until,
                         [MarketplaceListing.status.in_(("ACTIVE", "PAUSED")), MarketplaceListing.environment == job.environment,
                          MarketplaceListing.valid_until.is_not(None), MarketplaceListing.valid_until <= now], s.JOB_BATCH_SIZE, deadline):
        _process(db, ctx, job, "listings_expired", [b[0] for b in batch], listing, counts)
    return _finish(counts, time.monotonic() < deadline)


# ---------------------------------------------------------------- orphan stored files (Phase 12B D10: detect, then delete safely)
def scan_orphan_files(db: Session, ctx: RequestContext, job: BackgroundJob, deadline: float) -> dict[str, Any]:
    """An object is an orphan CANDIDATE only if it has a server-generated key, no document version references it, and it is older than
    JOB_ORPHAN_GRACE_HOURS (uploads in flight, uncommitted transactions and retries are younger). Each candidate is then re-checked
    inside its own transaction under UPDLOCK + HOLDLOCK on the storage key (a key-range lock: a concurrent insert of a version
    referencing that key waits until this transaction ends) and deleted only if still unreferenced — with the separate deletion
    identity (D8). Every deletion is audited. Without a deletion identity, candidates are reported and nothing is deleted."""
    storage = get_storage()
    deleter = get_deletion_storage()
    cutoff = utcnow() - timedelta(hours=get_settings().JOB_ORPHAN_GRACE_HOURS)
    counts = {"scanned": 0, "referenced": 0, "orphan_candidates": 0, "recent_unreferenced": 0, "unrecognized_keys": 0, "deleted": 0,
              "became_referenced": 0, "delete_failures": 0}
    sample: list[str] = []
    chunk: list[Any] = []

    def delete_one(key: str, size: int, modified: datetime) -> None:
        assert deleter is not None
        hit = db.scalars(select(DocumentVersion.id).with_hint(DocumentVersion, "WITH (UPDLOCK, HOLDLOCK)", "mssql")
                         .where(DocumentVersion.storage_key == key)).first()
        if hit is not None:                                          # referenced after the scan: never delete
            db.rollback()
            counts["became_referenced"] += 1
            return
        try:
            deleter.delete(key)
        except (StorageError, OSError):
            db.rollback()
            counts["delete_failures"] += 1
            metrics.inc("storage_failures_total", {"operation": "delete"})
            return
        record(db, ctx, "STORAGE_ORPHAN_DELETED", "storage_object", key, None,
               {"key": key, "size_bytes": size, "last_modified": modified, "environment": job.environment, "job_code": job.job_code})
        db.commit()
        counts["deleted"] += 1
        metrics.inc("orphan_objects_deleted_total", {"environment": job.environment})

    def flush() -> None:
        keys = [o.key for o in chunk]
        refs = set(db.scalars(select(DocumentVersion.storage_key).where(DocumentVersion.storage_key.in_(keys))).all())
        db.commit()
        for o in chunk:
            counts["scanned"] += 1
            if o.key in refs:
                counts["referenced"] += 1
            elif not KEY_PATTERN.match(o.key):
                counts["unrecognized_keys"] += 1                        # not a document object (e.g. a temp file): never deleted
            elif o.modified_at > cutoff:
                counts["recent_unreferenced"] += 1                       # possibly an upload in flight: never a candidate yet
            else:
                counts["orphan_candidates"] += 1
                if len(sample) < 20:
                    sample.append(o.key)
                if deleter is not None:
                    delete_one(o.key, o.size_bytes, o.modified_at)
        chunk.clear()

    complete = True
    for obj in storage.iter_objects(job.environment.lower() + "/"):
        chunk.append(obj)
        if len(chunk) >= 500:
            flush()
            if time.monotonic() >= deadline:
                complete = False
                break
    if chunk:
        flush()
    return {**counts, "sample_candidates": sample, "grace_hours": get_settings().JOB_ORPHAN_GRACE_HOURS,
            "deletion": "ENABLED" if deleter is not None else "DISABLED (no deletion identity configured)", "complete": complete}


# ---------------------------------------------------------------- document rescans (Phase 12B D12 / D15)
def rescan_documents(db: Session, ctx: RequestContext, job: BackgroundJob, deadline: float) -> dict[str, Any]:
    """One document (job entity) or a batch: documents of the job's environment whose current version has no CLEAN scan yet (accepted
    before Phase 12B, by a test scanner, or while the scanner was unavailable) and no INFECTED result. Each document is rescanned in its
    own transaction; an INFECTED result quarantines it. A rescan never releases a document (D16)."""
    from app.services import document_service as ds
    counts = {"documents": 0, "clean": 0, "infected": 0, "not_scanned": 0, "errors": 0}

    def one(doc: Document) -> None:
        rows = ds.rescan(db, ctx, doc, "RESCAN", job.id)
        db.commit()
        counts["documents"] += 1
        for r in rows:
            key = {"CLEAN": "clean", "INFECTED": "infected", "NOT_SCANNED": "not_scanned"}.get(r.result, "errors")
            counts[key] += 1

    if job.entity_type == "document" and job.entity_id:
        doc = db.get(Document, uuid.UUID(job.entity_id))
        if doc is None or doc.environment != job.environment:
            raise NotFound("Document not found in this environment.", error_code="DOCUMENT_NOT_FOUND")
        one(doc)
        return {**counts, "complete": True}
    if get_scanner().name == "signature":
        return {**counts, "complete": True, "skipped": True,
                "message": "No antivirus engine is configured (test-signature scanner only); a batch rescan would add no information."}
    current = (select(DocumentVersion.id).where(DocumentVersion.document_id == Document.id, DocumentVersion.version == Document.current_version)
               .scalar_subquery())
    clean = select(DocumentScan.id).where(DocumentScan.document_version_id == current, DocumentScan.result == "CLEAN").exists()
    infected = select(DocumentScan.id).where(DocumentScan.document_id == Document.id, DocumentScan.result == "INFECTED").exists()
    last: uuid.UUID | None = None
    complete = True
    while True:
        if time.monotonic() >= deadline:
            complete = False
            break
        stmt = select(Document.id).where(Document.environment == job.environment, ~clean, ~infected)
        if last is not None:
            stmt = stmt.where(Document.id > last)
        ids = list(db.scalars(stmt.order_by(Document.id).limit(get_settings().JOB_BATCH_SIZE)).all())
        db.commit()
        if not ids:
            break
        for did in ids:
            doc = db.get(Document, did, populate_existing=True)
            if doc is not None:
                one(doc)
        last = ids[-1]
    return {**counts, "complete": complete}


# ---------------------------------------------------------------- retention purge (infrastructure only)
# A retention rule may be added here ONLY with a formally approved retention policy. None exists (Phases 1–11 define no retention
# period), so this list is empty and the job purges nothing. Audit, workflow, security, ledger, financial, calculation, laboratory,
# verification and issuance records are never eligible.
RETENTION_POLICIES: tuple[Any, ...] = ()


def retention_purge(db: Session, ctx: RequestContext, job: BackgroundJob, deadline: float) -> dict[str, Any]:
    if not RETENTION_POLICIES:
        joblog.event("retention_not_configured", job_id=job.id, job_code=job.job_code, environment=job.environment,
                     reason="No retention policy is configured; nothing was purged.")
        return {"policies_configured": 0, "purged": 0, "message": "No retention policy is configured; nothing was purged."}
    raise AssertionError("retention policies require an approved policy and an implementation review")   # pragma: no cover
