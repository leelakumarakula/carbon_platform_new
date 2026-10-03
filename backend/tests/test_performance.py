"""Phase 12B D31 / D33 — synthetic performance harness (pytest, TEST data only, inside the rolled-back test transaction).

D31 selected high-volume operation but set NO numeric targets, so these tests assert structural properties instead of timings:
- the verified hot-spot listings (orders, marketplace listings, refunds, finance projects) load only the caller's rows: the number of
  ORM rows loaded and SQL statements issued does not grow when thousands of other organizations' rows are added;
- results are identical to the previous Python visibility rules (`side()`, `can_see_listing()`, `can_in_org()`);
- the optional limit / offset paging returns disjoint, ordered slices covering the whole list, with the list shape unchanged;
- lazy expiry still runs on the read path (correctness guarantee, Phase 12A D5).
Timings are measured and reported as properties (`record_property`) for baselining — never asserted against an invented SLA.
Synthetic rows are clones of a real scenario's rows re-pointed at synthetic organizations; they never reach DEMO or LIVE data.
"""
import time
import uuid
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event, insert, select
from sqlalchemy.orm import Session

from app.core.context import RequestContext
from app.core.database import get_engine
from app.models import MarketplaceListing, Order, Organization, Project
from app.models.base import utcnow
from app.security.permissions import P
from app.security.principal import load_principal
from app.services import finance_service as fs
from app.services import marketplace_service as ms
from app.services import order_service as os_
from tests.conftest import make_org, make_user
from tests.test_marketplace import MP, ORD, M

NOISE = 1500


@contextmanager
def counting(model: Any) -> Iterator[dict[str, int]]:
    """Counts ORM instances of `model` loaded and SQL statements executed inside the block."""
    c = {"rows": 0, "statements": 0}

    def on_load(target: Any, *_a: Any) -> None:
        c["rows"] += 1

    def on_exec(*_a: Any) -> None:
        c["statements"] += 1
    engine = get_engine()
    event.listen(model, "load", on_load)
    event.listen(model, "refresh", on_load)
    event.listen(engine, "before_cursor_execute", on_exec)
    try:
        yield c
    finally:
        event.remove(model, "load", on_load)
        event.remove(model, "refresh", on_load)
        event.remove(engine, "before_cursor_execute", on_exec)


def fresh(db: Session) -> Session:
    """A new session on the test transaction (empty identity map), so every row the query returns is counted."""
    return Session(bind=db.connection(), join_transaction_mode="create_savepoint", expire_on_commit=False, autoflush=False)


def measured(db: Session, fn: Callable[[Session], Any]) -> Any:
    """Run `fn` in a fresh session and close it straight away (an open one would interfere with later commits of the test)."""
    s = fresh(db)
    try:
        return fn(s)
    finally:
        s.close()


def _clone(db: Session, model: Any, template: Any, n: int, overrides: Callable[[int], dict[str, Any]]) -> None:
    cols = {c.key: getattr(template, c.key) for c in model.__mapper__.column_attrs}
    rows = [{**cols, "id": uuid.uuid4(), **overrides(i)} for i in range(n)]
    for start in range(0, n, 500):
        db.execute(insert(model), rows[start:start + 500])
    db.flush()


def _orgs(db: Session, n: int) -> list[Organization]:
    return [make_org(db, org_type="PROJECT_DEVELOPER") for _ in range(n)]


def _timed(fn: Callable[[], Any]) -> tuple[Any, float]:
    t = time.perf_counter()
    out = fn()
    return out, time.perf_counter() - t


@pytest.fixture()
def scenario(client: TestClient, db: Session) -> M:
    m = M(client, db, 84.70, 29.70, "9915 3000 4000")
    m.verify_buyer()
    return m


def test_order_listing_reads_do_not_scale_with_other_organizations(client: TestClient, db: Session, scenario: M,
                                                                  record_property: Any) -> None:
    m = scenario
    lst = m.listing(300)
    o = m.order([(lst["id"], 10)])
    assert o.status_code == 201, o.text
    order = db.get(Order, uuid.UUID(o.json()["id"]))
    listing = db.get(MarketplaceListing, uuid.UUID(lst["id"]))
    assert order is not None and listing is not None
    buyer = load_principal(db, m.buyer.user, None)
    ctx = RequestContext(request_id="perf", user_id=m.buyer.user.id)

    with counting(Order) as base:
        before, t0 = _timed(lambda: measured(db, lambda s: os_.visible_orders(s, ctx, buyer)))
    noise = _orgs(db, 20)
    stamp = uuid.uuid4().hex[:6].upper()
    _clone(db, Order, order, NOISE, lambda i: {"order_code": f"P{stamp}{i:07d}"[:20], "request_key": None, "status": "CANCELLED",
                                                "buyer_organization_id": noise[i % 20].id, "seller_organization_id": noise[(i + 1) % 20].id})
    _clone(db, MarketplaceListing, listing, NOISE, lambda i: {"listing_code": f"Q{stamp}{i:07d}"[:20], "request_key": None,
                                                               "status": "DRAFT", "seller_organization_id": noise[i % 20].id})
    with counting(Order) as big:
        after, t1 = _timed(lambda: measured(db, lambda s: os_.visible_orders(s, ctx, buyer)))
    assert [x.id for x in after] == [x.id for x in before] == [order.id]
    assert big["rows"] == base["rows"] == 1                             # only the caller's order is loaded, not 1,500 others
    assert big["statements"] == base["statements"]
    with counting(MarketplaceListing) as lc:
        visible, t2 = _timed(lambda: measured(db, lambda s: ms.listings(s, ctx, buyer)))
    assert [x.id for x in visible] == [listing.id] and lc["rows"] == 1   # DRAFT listings of other sellers are never loaded
    record_property("orders_list_seconds_baseline", round(t0, 4))
    record_property(f"orders_list_seconds_with_{NOISE}_foreign_rows", round(t1, 4))
    record_property(f"listings_list_seconds_with_{NOISE}_foreign_rows", round(t2, 4))
    # the API keeps its response shape; optional paging works
    r = m.get(ORD)
    assert r.status_code == 200 and [x["id"] for x in r.json()["orders"]] == [str(order.id)]
    assert m.get(ORD, limit=1, offset=1).json()["orders"] == []
    assert m.get(f"{MP}/listings", limit=0).status_code == 422 and m.get(f"{MP}/listings", limit=501).status_code == 422


def test_scoped_visibility_matches_previous_python_rules(client: TestClient, db: Session, scenario: M) -> None:
    m = scenario
    lst = m.listing(300)
    draft = m.listing(50, approve=False, rng=m.range400)
    o = m.order([(lst["id"], 10)])
    assert o.status_code == 201
    outsider_org = make_org(db, org_type="BUYER")
    outsider = make_user(db, roles=[("BUYER", outsider_org)])
    platform_fin = make_user(db, roles=[("FINANCE_MANAGER", None)])     # platform-wide grant: sees every organization
    principals = [load_principal(db, u, None) for u in (m.buyer.user, m.fin.user, m.cm.user, outsider, platform_fin)]
    ctx = RequestContext(request_id="perf")
    all_orders = db.scalars(select(Order)).all()
    all_listings = db.scalars(select(MarketplaceListing)).all()
    all_projects = db.scalars(select(Project)).all()
    for p in principals:
        expect_orders = {x.id for x in all_orders if os_.side(p, x) is not None}
        assert {x.id for x in os_.visible_orders(db, ctx, p)} == expect_orders
        if p.has(P.MARKETPLACE_READ) or any(p.has(c) for c in ms.SELLER_VIEW):
            assert {x.id for x in ms.listings(db, ctx, p)} == {x.id for x in all_listings if ms.can_see_listing(p, x)}
            assert {x.id for x in ms.listings(db, ctx, p, mine=True)} == {x.id for x in all_listings if ms.is_seller_side(p, x)}
        expect_projects = {x.id for x in all_projects if any(p.can_in_org(c, x.organization_id) for c in fs.FIN_VIEW)}
        assert {x.id for x in fs.visible_projects(db, p)} == expect_projects
    seller = load_principal(db, m.cm.user, None)
    assert draft["id"] in {str(x.id) for x in ms.listings(db, ctx, seller, mine=True)}
    assert draft["id"] not in {str(x.id) for x in ms.listings(db, ctx, load_principal(db, m.buyer.user, None))}


def test_paging_is_disjoint_ordered_and_complete(client: TestClient, db: Session, scenario: M) -> None:
    m = scenario
    project = db.scalars(select(Project).where(Project.organization_id == m.seller.id)).first()
    assert project is not None
    noise = _orgs(db, 5)
    stamp = uuid.uuid4().hex[:6].upper()
    _clone(db, Project, project, 230, lambda i: {"project_code": f"PERF-{stamp}-{i:05d}", "organization_id": noise[i % 5].id})
    viewer = load_principal(db, make_user(db, roles=[("FINANCE_MANAGER", None)]), None)
    full = [x.id for x in fs.visible_projects(db, viewer)]
    pages: list[uuid.UUID] = []
    for offset in range(0, len(full) + 100, 100):
        pages += [x.id for x in fs.visible_projects(db, viewer, limit=100, offset=offset)]
    assert pages == full and len(set(pages)) == len(pages) >= 231
    scoped = load_principal(db, m.fin.user, None)                          # organization-scoped: none of the 230 synthetic projects
    with counting(Project) as c:
        mine = measured(db, lambda s: fs.visible_projects(s, scoped))
    assert {x.organization_id for x in mine} == {m.seller.id} and c["rows"] == len(mine)


def test_lazy_expiry_still_runs_on_the_read_path(client: TestClient, db: Session, scenario: M, monkeypatch: pytest.MonkeyPatch) -> None:
    """Phase 12A D5 / D24: correctness never depends on the sweep job (or Redis). A due order expires when its party lists orders."""
    m = scenario
    lst = m.listing(300, valid_until=(utcnow() + timedelta(hours=72)).isoformat() + "Z")
    o = m.order([(lst["id"], 10)])
    assert o.status_code == 201
    later = utcnow() + timedelta(hours=48)
    for mod in (os_, ms):
        monkeypatch.setattr(mod, "utcnow", lambda t=later: t)
    monkeypatch.setattr("app.services.ledger_service.utcnow", lambda t=later: t)
    rows = os_.visible_orders(db, RequestContext(request_id="perf", user_id=m.buyer.user.id), load_principal(db, m.buyer.user, None))
    assert [x.status for x in rows if str(x.id) == o.json()["id"]] == ["EXPIRED"]
    placed = os_.visible_orders(db, RequestContext(request_id="perf"), load_principal(db, m.buyer.user, None), "PLACED")
    assert o.json()["id"] not in {str(x.id) for x in placed}


# ---------------------------------------------------------------- Phase 12B-III operational volumes (baselines, no SLA — D31)
def _report(name: str, seconds: float, record_property: Any, **extra: Any) -> None:
    """Records a measurement; with PERF_REPORT=<file> set, appends it there as a JSON line (used for the phase report)."""
    import json
    import os
    record_property(name, round(seconds, 4))
    path = os.environ.get("PERF_REPORT")
    if path:
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps({"measurement": name, "seconds": round(seconds, 4), **extra}) + "\n")


def test_operational_volume_baselines(client: TestClient, db: Session, scenario: M, record_property: Any) -> None:
    from app.models import AuditLog, BackgroundJob, Document, DocumentVersion
    from app.models.jobs import SYSTEM_ACTOR_IDS
    from app.services import document_service
    from app.workers import job_service
    from tests.conftest import login
    m = scenario
    stamp = uuid.uuid4().hex[:6].upper()
    # ---- 200 organizations, 2,000 projects: finance list scoped vs platform-wide
    project = db.scalars(select(Project).where(Project.organization_id == m.seller.id)).first()
    assert project is not None
    orgs = _orgs(db, 200)
    _clone(db, Project, project, 2000, lambda i: {"project_code": f"OPS-{stamp}-{i:05d}", "organization_id": orgs[i % 200].id})
    scoped = load_principal(db, m.fin.user, None)
    with counting(Project) as c:
        mine, t = _timed(lambda: measured(db, lambda s: fs.visible_projects(s, scoped)))
    assert c["rows"] == len(mine) <= 5
    _report("finance_projects_scoped_2000_foreign", t, record_property, rows=len(mine), statements=c["statements"])
    platform = load_principal(db, make_user(db, roles=[("FINANCE_MANAGER", None)]), None)
    page, t = _timed(lambda: measured(db, lambda s: fs.visible_projects(s, platform, limit=100, offset=1000)))
    assert len(page) == 100
    _report("finance_projects_platform_page_100_of_2000", t, record_property)
    # ---- audit-heavy: 5,000 audit rows, paged admin listing
    db.execute(insert(AuditLog), [{"action": "PERF_SYNTHETIC", "entity_type": "perf", "entity_id": f"{stamp}-{i}", "occurred_at": utcnow()}
                                  for i in range(5000)])
    db.flush()
    admin = make_user(db, roles=[("PLATFORM_ADMIN", None)])
    h = login(client, admin)
    r, t = _timed(lambda: client.get("/api/v1/admin/audit-logs", headers=h, params={"action": "PERF_SYNTHETIC", "page": 3, "page_size": 50}))
    assert r.status_code == 200 and len(r.json()["items"]) == 50 and r.json()["total"] >= 5000
    _report("audit_logs_page_50_of_5000", t, record_property)
    # ---- background job queue: 2,000 queued jobs, operations listing (bounded)
    ctx = RequestContext(request_id="perf", user_id=SYSTEM_ACTOR_IDS["LIVE"])
    tmpl, _ = job_service.enqueue(db, ctx, "RETENTION_PURGE", environment="LIVE", trigger_type="SERVICE", created_by=SYSTEM_ACTOR_IDS["LIVE"])
    db.flush()
    _clone(db, BackgroundJob, tmpl, 2000, lambda i: {"job_code": f"JP{stamp}{i:06d}"[:20], "idempotency_key": None})
    jr, t = _timed(lambda: client.get("/api/v1/jobs", headers=h, params={"limit": 100}))
    assert jr.status_code == 200 and len(jr.json()) == 100
    _report("jobs_list_100_of_2000_queued", t, record_property)
    # ---- document metadata: 300 documents on one entity, eager-loaded list
    doc = Document(entity_type="farmer", entity_id=uuid.uuid4(), organization_id=m.seller.id, category="OTHER", title="perf",
                   environment="LIVE")
    db.add(doc)
    db.flush()
    v = DocumentVersion(document_id=doc.id, version=1, file_name="p.pdf", storage_key=f"live/2026/10/{uuid.uuid4().hex}",
                        mime_type="application/pdf", size_bytes=1, checksum_sha256="0" * 64, scan_status="NOT_SCANNED")
    db.add(v)
    db.flush()
    eid = uuid.uuid4()
    _clone(db, Document, doc, 300, lambda i: {"entity_id": eid})
    with counting(Document) as c:
        docs, t = _timed(lambda: measured(db, lambda s: document_service.list_for(s, "farmer", eid)))
    assert len(docs) == 300 and c["statements"] <= 6          # list + 2 eager loads (+ session transaction statements), not 300+
    _report("documents_list_300_on_one_entity", t, record_property, statements=c["statements"])
