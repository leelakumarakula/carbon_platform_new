"""Phase 12A — REAL concurrency and broker integration for background jobs.

Like the 9B / 10 / 11 suites, this module snapshots the test database, builds a committed world (TEST registry issuance → 9B ledger →
reservations), runs job executions from separate threads (each with its own Session / connection), then restores the snapshot.

Scenarios: the same job delivered twice concurrently; two sweeps over the same due reservations; a worker crash after partial progress
(stale lease → recovery → retry); rollback after a claim; and — through a REAL Celery worker consuming from a Redis-protocol broker —
publication, duplicate messages, an expiry sweep, and Redis going away (publication failure kept in SQL Server, republished by the
recovery tick once a — cleared — broker is back). The broker is a real Redis when REDIS_TEST_URL is set; otherwise the test-only
`fakeredis` TCP server (Redis protocol) is used. Invariants: one attempt per execution, one RESERVATION_EXPIRE entry per reservation,
batch conservation, no negative position.
"""
import os
import socket
import threading
import time
import uuid
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.context import RequestContext
from app.core.database import get_db, get_engine
from app.core.rate_limit import limiter
from app.main import create_app
from app.models import BackgroundJob, BackgroundJobAttempt, CreditBatch, CreditLedgerEntry, CreditPosition, CreditReservation
from app.models.base import utcnow
from app.models.jobs import SYSTEM_ACTOR_IDS
from app.services import ledger_service as ls
from app.services import marketplace_service as ms
from app.services import order_service as os_
from app.workers import handlers, job_service
from tests.calc_fixture import calc_scenario
from tests.test_ledger import L

SNAP = "carbon_platform_test_snap12"
LIVE_ACTOR = SYSTEM_ACTOR_IDS["LIVE"]


@dataclass
class World:
    engine: Engine
    batch_id: uuid.UUID
    issued: Any
    group_a: list[uuid.UUID]          # due after +2 h
    group_b: list[uuid.UUID]          # due after +4 h
    group_c: list[uuid.UUID]          # due after +6 h (broker integration)


def _master() -> Engine:
    return create_engine(get_settings().database_url("master"), isolation_level="AUTOCOMMIT")


@pytest.fixture(scope="module")
def world() -> Iterator[World]:
    db_name = get_settings().SQL_SERVER_DATABASE
    assert db_name.endswith("_test")
    engine = get_engine()
    engine.dispose()
    master = _master()
    with master.connect() as m:
        logical, physical = m.execute(text("SELECT name, physical_name FROM sys.master_files WHERE database_id = DB_ID(:d) AND type = 0"),
                                      {"d": db_name}).one()
        sparse = physical.rsplit("\\", 1)[0] + f"\\{SNAP}.ss"
        m.execute(text(f"CREATE DATABASE [{SNAP}] ON (NAME = [{logical}], FILENAME = '{sparse}') AS SNAPSHOT OF [{db_name}]"))
    session = Session(bind=engine, expire_on_commit=False, autoflush=False)
    try:
        app = create_app()
        app.dependency_overrides[get_db] = lambda: session
        app.state.access_log_writer = lambda _r: None
        limiter.reset()
        with TestClient(app, base_url="http://testserver") as client:
            k = calc_scenario(session, client, 84.30, 29.30, "9910 2000 3000")
            lg = L(client, session, k)
            lg.open()

            def res(hours: int) -> uuid.UUID:
                r = lg.reserve(5, expires_at=(utcnow() + timedelta(hours=hours)).isoformat() + "Z")
                assert r.status_code == 201, r.text
                return uuid.UUID(r.json()["id"])
            a = [res(1) for _ in range(6)]
            b = [res(3) for _ in range(4)]
            c = [res(5) for _ in range(3)]
            session.commit()
            batch = session.get(CreditBatch, uuid.UUID(lg.batch["id"]))
            assert batch is not None
            yield World(engine, batch.id, batch.quantity, a, b, c)
    finally:
        session.close()
        limiter.reset()
        engine.dispose()
        with master.connect() as m:
            m.execute(text(f"ALTER DATABASE [{db_name}] SET SINGLE_USER WITH ROLLBACK IMMEDIATE"))
            try:
                m.execute(text(f"RESTORE DATABASE [{db_name}] FROM DATABASE_SNAPSHOT = '{SNAP}'"))
            finally:
                m.execute(text(f"ALTER DATABASE [{db_name}] SET MULTI_USER"))
            m.execute(text(f"DROP DATABASE [{SNAP}]"))
        master.dispose()
        engine.dispose()


def _travel(monkeypatch: pytest.MonkeyPatch, hours: float) -> None:
    t = utcnow() + timedelta(hours=hours)
    for mod in (ls, ms, os_, handlers, job_service):
        monkeypatch.setattr(mod, "utcnow", lambda t=t: t)


def _enqueue(w: World, job_type: str = "RETENTION_PURGE") -> uuid.UUID:
    with Session(bind=w.engine, expire_on_commit=False, autoflush=False) as s:
        job, _ = job_service.enqueue(s, RequestContext(user_id=LIVE_ACTOR), job_type, environment="LIVE", trigger_type="SERVICE",
                                     created_by=LIVE_ACTOR)
        s.commit()
        return job.id


def _race(w: World, *ops: Callable[[Session], Any]) -> list[Any]:
    barrier = threading.Barrier(len(ops))
    out: list[Any] = [None] * len(ops)

    def run(i: int, op: Callable[[Session], Any]) -> None:
        s = Session(bind=w.engine, expire_on_commit=False, autoflush=False)
        try:
            barrier.wait(timeout=30)
            out[i] = op(s)
        except Exception as e:
            out[i] = repr(e)
        finally:
            s.close()
    threads = [threading.Thread(target=run, args=(i, op)) for i, op in enumerate(ops)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=120)
    return out


def _job(w: World, job_id: uuid.UUID) -> tuple[BackgroundJob, list[BackgroundJobAttempt]]:
    with Session(bind=w.engine) as s:
        j = s.get(BackgroundJob, job_id)
        att = list(s.scalars(select(BackgroundJobAttempt).where(BackgroundJobAttempt.background_job_id == job_id)
                             .order_by(BackgroundJobAttempt.attempt_number)).all())
        assert j is not None
        s.expunge_all()
        return j, att


def invariants(w: World, expected_expired: set[uuid.UUID]) -> None:
    with Session(bind=w.engine) as s:
        total = s.scalar(select(func.sum(CreditPosition.quantity)).where(CreditPosition.batch_id == w.batch_id, CreditPosition.status == "OPEN"))
        assert total == w.issued                                                     # 9B batch conservation
        assert s.scalar(select(func.count()).select_from(CreditPosition).where(CreditPosition.quantity <= 0)) == 0
        per = dict(s.execute(select(CreditLedgerEntry.reservation_id, func.count()).where(CreditLedgerEntry.entry_type == "RESERVATION_EXPIRE",
                                                                                           CreditLedgerEntry.batch_id == w.batch_id)
                             .group_by(CreditLedgerEntry.reservation_id)).all())
        assert set(per) == expected_expired and all(n == 1 for n in per.values()), per   # each reservation expired exactly once
        st = dict(s.execute(select(CreditReservation.id, CreditReservation.status).where(CreditReservation.batch_id == w.batch_id)).all())
        assert all(st[r] == "EXPIRED" for r in expected_expired)


# ---------------------------------------------------------------- 1 the same job delivered twice at the same moment
def test_1_same_job_delivered_twice(world: World) -> None:
    jid = _enqueue(world)
    out = _race(world, lambda s: job_service.execute(s, jid, "worker-A:1"), lambda s: job_service.execute(s, jid, "worker-B:2"))
    assert sorted(out).count("SUCCEEDED") == 1, out
    assert all(o == "SUCCEEDED" or o in ("NOT_CLAIMED", "NOT_ELIGIBLE:CLAIMED", "NOT_ELIGIBLE:RUNNING", "NOT_ELIGIBLE:SUCCEEDED")
               for o in out), out
    j, att = _job(world, jid)
    assert j.status == "SUCCEEDED" and len(att) == 1


# ---------------------------------------------------------------- 2 two sweeps over the same due reservations
def test_2_two_sweeps_same_rows(world: World, monkeypatch: pytest.MonkeyPatch) -> None:
    _travel(monkeypatch, 2)
    j1, j2 = _enqueue(world, "EXPIRY_CREDIT_RESERVATIONS"), _enqueue(world, "EXPIRY_CREDIT_RESERVATIONS")
    out = _race(world, lambda s: job_service.execute(s, j1, "worker-A:1"), lambda s: job_service.execute(s, j2, "worker-B:2"))
    assert out == ["SUCCEEDED", "SUCCEEDED"], out
    import json
    total = sum(json.loads(_job(world, j)[0].result or "{}")["expired"] for j in (j1, j2))
    assert total == len(world.group_a)                                                 # never expired twice
    invariants(world, set(world.group_a))


# ---------------------------------------------------------------- 3 worker crash after partial progress; 4 rollback after claim
def test_3_worker_crash_then_recovery(world: World, monkeypatch: pytest.MonkeyPatch) -> None:
    _travel(monkeypatch, 4)
    jid = _enqueue(world, "EXPIRY_CREDIT_RESERVATIONS")
    with Session(bind=world.engine, expire_on_commit=False, autoflush=False) as s:     # the "dead" worker claims, starts …
        assert job_service._claim(s, jid, "dead-worker:9") and job_service._start(s, jid, "dead-worker:9") is not None
        ctx = RequestContext(request_id="dead", user_id=LIVE_ACTOR)

        def first() -> bool:                                                          # … commits one expiry, then crashes
            r = ls.lock_reservation(s, world.group_b[0])
            assert r is not None and r.status == "ACTIVE"
            ls.expire_reservation_in_tx(s, ctx, r, LIVE_ACTOR)
            return True
        ls.run(s, ctx, first)
    with Session(bind=world.engine) as s:
        assert job_service.recover(s)["stale_runs_recovered"] == 0                      # the lease is still valid: nothing stolen
    _travel(monkeypatch, 4 + (get_settings().JOB_STALE_AFTER_SECONDS + 120) / 3600)
    with Session(bind=world.engine) as s:
        assert job_service.recover(s)["stale_runs_recovered"] == 1
        job_service.recover(s)                                                         # retry due → QUEUED
        assert job_service.execute(s, jid, "worker-C:3") == "SUCCEEDED"
    j, att = _job(world, jid)
    assert [a.status for a in att] == ["ABANDONED", "SUCCEEDED"] and att[0].error_code == "WORKER_LOST"
    import json
    assert json.loads(j.result or "{}")["expired"] == len(world.group_b) - 1           # the committed partial work is not redone
    invariants(world, set(world.group_a) | set(world.group_b))
    # 4: a claim whose start transaction rolled back is recovered and runs once
    j4 = _enqueue(world)
    with Session(bind=world.engine) as s:
        assert job_service._claim(s, j4, "worker-D:4")
        s.rollback()
    _travel(monkeypatch, 6 + (2 * get_settings().JOB_STALE_AFTER_SECONDS) / 3600)
    with Session(bind=world.engine) as s:
        assert job_service.recover(s)["stale_claims_requeued"] >= 1
        assert job_service.execute(s, j4, "worker-E:5") == "SUCCEEDED"
    assert len(_job(world, j4)[1]) == 1


# ---------------------------------------------------------------- 5 a real Celery worker over the Redis protocol
def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _wait(w: World, jid: uuid.UUID, status: str, seconds: float = 45) -> BackgroundJob:
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        j, _ = _job(w, jid)
        if j.status == status:
            return j
        time.sleep(0.25)
    raise AssertionError(f"job {jid} did not reach {status} (is {_job(w, jid)[0].status})")


def test_5_real_worker_over_redis_protocol(world: World, monkeypatch: pytest.MonkeyPatch) -> None:
    real = os.environ.get("REDIS_TEST_URL")
    server: Any = None
    if real:
        url = real
    else:
        fakeredis = pytest.importorskip("fakeredis", reason="no REDIS_TEST_URL and no test-only fakeredis server")
        port = _free_port()

        def start_server() -> Any:
            srv = fakeredis.TcpFakeServer(("127.0.0.1", port), server_type="redis")
            srv.daemon_threads = True
            threading.Thread(target=srv.serve_forever, daemon=True).start()
            return srv
        server = start_server()
        url = f"redis://127.0.0.1:{port}/0"
    from celery.contrib.testing.worker import start_worker

    from app.workers.celery_app import celery_app
    monkeypatch.setattr(get_settings(), "REDIS_URL", url)
    celery_app.conf.broker_url = url
    celery_app.loader.import_default_modules()
    _travel(monkeypatch, 6.5)                                                          # group C is due (worker threads share the patch)
    try:
        with start_worker(celery_app, pool="solo", perform_ping_check=False, shutdown_timeout=10, queues=["default", "maintenance"]):
            # publication after commit → the worker claims, runs and records the job
            jid = _enqueue(world)
            with Session(bind=world.engine) as s:
                assert job_service.publish(s, jid) is True
            _wait(world, jid, "SUCCEEDED")
            # a duplicated Redis message is a no-op
            j, _ = _job(world, jid)
            job_service._send(j, job_service.spec_of(j))  # type: ignore[arg-type]
            time.sleep(3)
            assert len(_job(world, jid)[1]) == 1
            # an expiry sweep through the broker
            sweep = _enqueue(world, "EXPIRY_CREDIT_RESERVATIONS")
            with Session(bind=world.engine) as s:
                job_service.publish(s, sweep)
            _wait(world, sweep, "SUCCEEDED")
            invariants(world, set(world.group_a) | set(world.group_b) | set(world.group_c))
            if server is not None:
                # Redis goes away: the job is kept in SQL Server with the publication error …
                server.shutdown()
                server.server_close()
                lost = _enqueue(world)
                with Session(bind=world.engine) as s:
                    assert job_service.publish(s, lost) is False
                j, _ = _job(world, lost)
                assert j.status == "QUEUED" and (j.last_publish_error or "").startswith("BROKER_UNAVAILABLE")
                # … and a new (empty — Redis cleared) broker comes back: the recovery tick republishes from SQL Server
                server = start_server()
                with Session(bind=world.engine) as s:
                    assert job_service.recover(s)["republished"] >= 1
                _wait(world, lost, "SUCCEEDED", 90)
                assert len(_job(world, lost)[1]) == 1
    finally:
        celery_app.conf.broker_url = None
        if server is not None:
            server.shutdown()
            server.server_close()
