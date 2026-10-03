"""Restore verification (Phase 12B-III, D27). `manage.py verify-restore --database <name>` checks a restored (or any) database and
records the result. It is READ-ONLY: the only write is one append-only probe inside a transaction that is always rolled back.

Checks:
1. connectivity — the session is on exactly the named database;
2. migration state — `alembic_version` equals the code's head;
3. schema — every table, column, index, constraint and trigger of the committed schema manifest (`app/ops/schema_manifest.json`,
   regenerated with `manage.py schema-manifest` and kept equal to the live test schema by the test suite) exists; no trigger disabled;
4. append-only protection — an UPDATE on `document_scans` is refused by its trigger (rolled back);
5. ledger conservation — per credit batch, OPEN positions sum to the batch quantity; no unposted ledger entry;
6. settlement reproducibility — every calculated settlement run re-verifies (hash, figures, entitlements, inputs);
7. calculation-report content hashes;
8. organization scoping — the SQL scoping predicate returns nothing for a caller without grants and everything for a platform grant;
9. optionally (`--objects N`) a sample of document versions is verified against object storage (size + SHA-256);
10. row counts per table, optionally compared with a source database (`--compare-with`, used by restore drills);
11. optionally DBCC CHECKDB (`--checkdb`).
"""
import json
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.ops.sqlserver import check_name, database_engine

MANIFEST = Path(__file__).with_name("schema_manifest.json")


def code_head() -> str | None:
    from alembic.config import Config
    from alembic.script import ScriptDirectory
    backend = Path(__file__).resolve().parents[2]
    cfg = Config(str(backend / "alembic.ini"))
    cfg.set_main_option("script_location", str(backend / "alembic"))
    return ScriptDirectory.from_config(cfg).get_current_head()


def build_manifest(conn: Any) -> dict[str, Any]:
    """The schema as SQL Server sees it: tables -> columns, plus named indexes, constraints and triggers (sorted, deterministic)."""
    cols: dict[str, list[str]] = {}
    for t, c in conn.execute(text("SELECT t.name, c.name FROM sys.tables t JOIN sys.columns c ON c.object_id = t.object_id "
                                  "WHERE t.is_ms_shipped = 0 ORDER BY t.name, c.column_id")):
        cols.setdefault(t, []).append(c)
    idx = sorted(f"{t}.{i}" for t, i in conn.execute(text(
        "SELECT t.name, i.name FROM sys.indexes i JOIN sys.tables t ON t.object_id = i.object_id WHERE i.name IS NOT NULL "
        "AND t.is_ms_shipped = 0")))
    cons = sorted(f"{t}.{n}" for t, n in conn.execute(text(
        "SELECT t.name, o.name FROM sys.objects o JOIN sys.tables t ON t.object_id = o.parent_object_id "
        "WHERE o.type IN ('C', 'F', 'PK', 'UQ', 'D') AND t.is_ms_shipped = 0 AND o.name NOT LIKE 'DF\\_\\_%' ESCAPE '\\'")))
    trg = sorted(f"{t}.{n}" for t, n in conn.execute(text(
        "SELECT t.name, tr.name FROM sys.triggers tr JOIN sys.tables t ON t.object_id = tr.parent_id")))
    return {"tables": {k: sorted(v) for k, v in sorted(cols.items())}, "indexes": idx, "constraints": cons, "triggers": trg}


@dataclass
class Report:
    database: str
    started_at: str
    checks: list[dict[str, Any]] = field(default_factory=list)
    row_counts: dict[str, int] = field(default_factory=dict)
    seconds: float = 0.0

    @property
    def ok(self) -> bool:
        return all(c["ok"] for c in self.checks)

    def add(self, name: str, ok: bool, detail: Any = None) -> None:
        self.checks.append({"name": name, "ok": bool(ok), "detail": detail})

    def as_dict(self) -> dict[str, Any]:
        return {"database": self.database, "ok": self.ok, "started_at": self.started_at, "seconds": self.seconds,
                "checks": self.checks, "row_counts": self.row_counts}


def _counts(conn: Any) -> dict[str, int]:
    return {t: int(n) for t, n in conn.execute(text(
        "SELECT t.name, SUM(p.rows) FROM sys.tables t JOIN sys.partitions p ON p.object_id = t.object_id AND p.index_id IN (0, 1) "
        "WHERE t.is_ms_shipped = 0 GROUP BY t.name ORDER BY t.name"))}


def verify_restore(database: str, *, compare_with: str | None = None, objects: int = 0, checkdb: bool = False) -> Report:
    check_name(database)
    rep = Report(database, datetime.now(timezone.utc).isoformat(timespec="seconds"))
    started = time.monotonic()
    eng = database_engine(database)
    try:
        try:
            with eng.connect() as c:
                actual = c.execute(text("SELECT DB_NAME()")).scalar()
        except Exception as e:
            rep.add("connectivity", False, f"cannot connect ({type(e).__name__})")
            return rep
        rep.add("connectivity", actual == database, actual)
        if actual != database:
            return rep
        with eng.connect() as c:
            _schema_checks(c, rep)
            rep.row_counts = _counts(c)
        _append_only_probe(eng, rep)
        with Session(bind=eng) as s:
            _ledger(s, rep)
            _settlements(s, rep)
            _reports(s, rep)
            _scoping(s, rep)
            if objects:
                _objects(s, rep, objects)
        if compare_with:
            _compare(compare_with, rep)
        if checkdb:
            try:
                with eng.connect() as c:
                    c.execute(text(f"DBCC CHECKDB ([{database}]) WITH NO_INFOMSGS, ALL_ERRORMSGS"))
                rep.add("dbcc_checkdb", True)
            except Exception as e:
                rep.add("dbcc_checkdb", False, str(e)[:300])
        return rep
    finally:
        rep.seconds = round(time.monotonic() - started, 2)
        eng.dispose()


def _schema_checks(c: Any, rep: Report) -> None:
    try:
        version = c.execute(text("SELECT version_num FROM dbo.alembic_version")).scalar()
    except Exception as e:
        rep.add("migration_head", False, f"alembic_version unreadable ({type(e).__name__})")
        return
    head = code_head()
    rep.add("migration_head", version == head, {"database": version, "code": head})
    if not MANIFEST.exists():
        rep.add("schema_manifest", False, "app/ops/schema_manifest.json is missing (manage.py schema-manifest)")
        return
    want = json.loads(MANIFEST.read_text(encoding="utf-8"))
    rep.add("schema_manifest_head", want.get("head") == head, {"manifest": want.get("head"), "code": head})
    have = build_manifest(c)
    missing_tables = sorted(set(want["tables"]) - set(have["tables"]))
    missing_columns = sorted(f"{t}.{col}" for t, cs in want["tables"].items() if t in have["tables"]
                             for col in cs if col not in have["tables"][t])
    rep.add("tables", not missing_tables, {"expected": len(want["tables"]), "missing": missing_tables})
    rep.add("columns", not missing_columns, {"missing": missing_columns[:50]})
    for kind in ("indexes", "constraints", "triggers"):
        missing = sorted(set(want[kind]) - set(have[kind]))
        rep.add(kind, not missing, {"expected": len(want[kind]), "missing": missing[:50]})
    disabled = [n for (n,) in c.execute(text("SELECT name FROM sys.triggers WHERE parent_class = 1 AND is_disabled = 1"))]
    rep.add("triggers_enabled", not disabled, {"disabled": disabled})


def _append_only_probe(eng: Any, rep: Report) -> None:
    with eng.connect() as c:
        t = c.begin()
        try:
            c.execute(text("UPDATE dbo.document_scans SET result = result WHERE 1 = 0"))
            rep.add("append_only_probe", False, "document_scans accepted an UPDATE (trigger missing or disabled)")
        except Exception as e:
            rep.add("append_only_probe", "append-only" in str(e), "document_scans UPDATE refused by its trigger")
        finally:
            if t.is_active:
                t.rollback()


def _ledger(s: Session, rep: Report) -> None:
    from app.models import CreditBatch, CreditLedgerEntry, CreditPosition
    totals: dict[uuid.UUID, Decimal] = {bid: Decimal(q) for bid, q in s.execute(
        select(CreditPosition.batch_id, func.sum(CreditPosition.quantity)).where(CreditPosition.status == "OPEN")
        .group_by(CreditPosition.batch_id)).all()}
    bad = []
    for batch_id, total in totals.items():
        b = s.get(CreditBatch, batch_id)
        if b is None or Decimal(total) != Decimal(b.quantity):
            bad.append({"batch_id": str(batch_id), "open_total": str(total), "batch_quantity": str(b.quantity) if b else None})
    unposted = s.scalar(select(func.count()).select_from(CreditLedgerEntry).where(CreditLedgerEntry.posted == False))  # noqa: E712
    rep.add("ledger_conservation", not bad and not unposted, {"batches_checked": len(totals), "violations": bad[:20],
                                                              "unposted_entries": unposted})


def _verifier(s: Session, codes: frozenset[str]) -> Any:
    """A synthetic, read-only, platform-scope principal used only to call existing verification functions."""
    from app.models import User
    from app.models.jobs import SYSTEM_ACTOR_IDS
    from app.security.principal import Grant, Principal
    user = s.get(User, SYSTEM_ACTOR_IDS["LIVE"])
    return Principal(user=user, session_id=None,  # type: ignore[arg-type]  # None only if the SYSTEM actor is missing (reported)
                     grants=(Grant(uuid.uuid4(), "RESTORE_VERIFIER", "PLATFORM", None, codes),))


def _settlements(s: Session, rep: Report) -> None:
    from app.models import SettlementRun
    from app.security.permissions import P
    from app.services import settlement_service
    runs = s.scalars(select(SettlementRun.id).where(SettlementRun.input_snapshot.is_not(None))).all()
    principal = _verifier(s, frozenset({P.SETTLEMENT_READ}))
    bad = []
    for rid in runs:
        try:
            r = settlement_service.verify(s, principal, rid)
            if not r["reproducible"]:
                bad.append(r["run_code"])
        except Exception as e:
            bad.append(f"{rid}: {type(e).__name__}")
    rep.add("settlement_reproducibility", not bad, {"runs_checked": len(runs), "failures": bad[:20]})


def _reports(s: Session, rep: Report) -> None:
    from app.calculation import framework as fw
    from app.models import CalculationReport
    bad = [r.report_code for r in s.scalars(select(CalculationReport)).all() if fw.sha256(json.loads(r.content)) != r.content_sha256]
    total = s.scalar(select(func.count()).select_from(CalculationReport))
    rep.add("calculation_report_hashes", not bad, {"reports_checked": total, "failures": bad[:20]})


def _scoping(s: Session, rep: Report) -> None:
    from app.models import Project
    from app.security.permissions import P
    from app.security.principal import Principal
    from app.security.scoping import org_predicate
    nobody = Principal(user=None, session_id=None, grants=())  # type: ignore[arg-type]
    platform = _verifier(s, frozenset({P.PROJECTS_READ}))
    none_seen = s.scalar(select(func.count()).select_from(Project).where(org_predicate(nobody, (P.PROJECTS_READ,), Project.organization_id)))
    all_seen = s.scalar(select(func.count()).select_from(Project).where(org_predicate(platform, (P.PROJECTS_READ,), Project.organization_id)))
    total = s.scalar(select(func.count()).select_from(Project))
    rep.add("organization_scoping", none_seen == 0 and all_seen == total, {"no_grant": none_seen, "platform": all_seen, "total": total})


def _objects(s: Session, rep: Report, sample: int) -> None:
    from app.integrations.storage import StorageError, get_storage
    from app.models import DocumentVersion
    storage = get_storage()
    rows = s.scalars(select(DocumentVersion).order_by(DocumentVersion.uploaded_at.desc()).limit(sample)).all()
    bad = []
    for v in rows:
        try:
            storage.verify(v.storage_key, v.checksum_sha256, v.size_bytes)
        except (StorageError, OSError) as e:
            bad.append({"document_version_id": str(v.id), "problem": getattr(e, "code", type(e).__name__)})
    rep.add("document_objects", not bad, {"sampled": len(rows), "storage": storage.name, "failures": bad[:20]})


def _compare(source: str, rep: Report) -> None:
    eng = database_engine(source)
    try:
        with eng.connect() as c:
            src = _counts(c)
    finally:
        eng.dispose()
    diff = {t: {"source": src.get(t), "restored": rep.row_counts.get(t)} for t in sorted(set(src) | set(rep.row_counts))
            if src.get(t) != rep.row_counts.get(t)}
    rep.add("row_counts_match_source", not diff, {"source": source, "tables": len(src), "differences": dict(list(diff.items())[:20])})
