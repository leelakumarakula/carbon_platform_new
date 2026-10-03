"""Phase 12B D10 — REAL cross-connection race between an upload transaction and the orphan-deletion job.

Like the 9B / 10 / 11 / 12A concurrency suites, the module snapshots the test database, works with committed data on separate
connections, then restores the snapshot. Scenario: an object older than the grace period is not yet referenced when the orphan job
lists candidates, because the upload transaction that references it has inserted its document version but NOT committed (e.g. a
very slow request). The job's deletion transaction re-checks the key under UPDLOCK + HOLDLOCK on the unique storage-key index, so
it waits for the upload transaction:
- the upload commits  -> the job sees the reference and does NOT delete the object;
- the upload rolls back -> the object really is an orphan and is deleted (and audited).
"""
import hashlib
import os
import threading
import time
import uuid
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.context import RequestContext
from app.core.database import get_engine
from app.integrations.storage import get_storage
from app.models import AuditLog, BackgroundJob, Document, DocumentVersion, Organization
from app.models.jobs import SYSTEM_ACTOR_IDS
from app.workers import job_service

SNAP = "carbon_platform_test_snap12b"
LIVE_ACTOR = SYSTEM_ACTOR_IDS["LIVE"]
DATA = b"%PDF-1.4\n% race\n%%EOF\n"


@dataclass
class World:
    engine: Engine
    document_id: uuid.UUID


@pytest.fixture(scope="module")
def world() -> Iterator[World]:
    db_name = get_settings().SQL_SERVER_DATABASE
    assert db_name.endswith("_test")
    engine = get_engine()
    engine.dispose()
    master = create_engine(get_settings().database_url("master"), isolation_level="AUTOCOMMIT")
    with master.connect() as m:
        logical, physical = m.execute(text("SELECT name, physical_name FROM sys.master_files WHERE database_id = DB_ID(:d) AND type = 0"),
                                      {"d": db_name}).one()
        sparse = physical.rsplit("\\", 1)[0] + f"\\{SNAP}.ss"
        m.execute(text(f"CREATE DATABASE [{SNAP}] ON (NAME = [{logical}], FILENAME = '{sparse}') AS SNAPSHOT OF [{db_name}]"))
    try:
        with Session(bind=engine, expire_on_commit=False, autoflush=False) as s:
            org = Organization(code=f"T-{uuid.uuid4().hex[:8].upper()}", name="Race org", org_type="PROJECT_DEVELOPER", environment="LIVE")
            s.add(org)
            s.flush()
            doc = Document(entity_type="farmer", entity_id=uuid.uuid4(), organization_id=org.id, category="OTHER", title="race",
                           environment="LIVE", current_version=0)
            s.add(doc)
            s.commit()
            doc_id = doc.id
        yield World(engine, doc_id)
    finally:
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


@pytest.fixture(autouse=True)
def _no_broker(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "REDIS_URL", None)


def _aged_object() -> str:
    st: Any = get_storage()
    key = f"live/2026/09/{uuid.uuid4().hex}"
    st.put(key, DATA, "application/pdf")
    aged = time.time() - (get_settings().JOB_ORPHAN_GRACE_HOURS + 2) * 3600
    os.utime(st._path(key), (aged, aged))
    return key


def _race(w: World, key: str, version: int, commit: bool) -> tuple[dict, float]:
    inserted, done = threading.Event(), threading.Event()
    errors: list[BaseException] = []

    def upload_tx() -> None:
        try:
            with Session(bind=w.engine, autoflush=False) as s:
                s.add(DocumentVersion(document_id=w.document_id, version=version, file_name="race.pdf", storage_key=key,
                                      mime_type="application/pdf", size_bytes=len(DATA), checksum_sha256=hashlib.sha256(DATA).hexdigest(),
                                      scan_status="NOT_SCANNED"))
                s.flush()                                    # X lock on the storage-key index entry, not yet visible to others
                inserted.set()
                time.sleep(2.0)                              # the orphan job runs meanwhile
                s.commit() if commit else s.rollback()
        except BaseException as e:
            errors.append(e)
            inserted.set()
        finally:
            done.set()

    t = threading.Thread(target=upload_tx)
    t.start()
    assert inserted.wait(30)
    with Session(bind=w.engine, expire_on_commit=False, autoflush=False) as s:
        job, _ = job_service.enqueue(s, RequestContext(user_id=LIVE_ACTOR), "ORPHAN_FILE_SCAN", environment="LIVE", trigger_type="SERVICE",
                                     created_by=LIVE_ACTOR)
        s.commit()
        started = time.monotonic()
        assert job_service.execute(s, job.id, "race-worker:1", expected_task_name=job.task_name) == "SUCCEEDED"
        elapsed = time.monotonic() - started
        import json
        result = json.loads(s.get(BackgroundJob, job.id).result or "{}")  # type: ignore[union-attr]
    t.join(30)
    assert done.is_set() and not errors, errors
    return result, elapsed


def test_1_committed_reference_wins_over_deletion(world: World) -> None:
    key = _aged_object()
    result, elapsed = _race(world, key, 1, commit=True)
    assert get_storage().exists(key), "a referenced object was deleted"
    assert result["became_referenced"] >= 1 and elapsed >= 1.0          # the deletion transaction waited for the upload transaction
    with Session(bind=world.engine) as s:
        assert s.scalars(select(DocumentVersion).where(DocumentVersion.storage_key == key)).one()
        assert s.scalars(select(AuditLog).where(AuditLog.action == "STORAGE_ORPHAN_DELETED", AuditLog.entity_id == key)).first() is None


def test_2_rolled_back_upload_leaves_a_true_orphan_that_is_deleted(world: World) -> None:
    key = _aged_object()
    result, _elapsed = _race(world, key, 2, commit=False)
    assert not get_storage().exists(key) and result["deleted"] >= 1
    with Session(bind=world.engine) as s:
        assert s.scalars(select(DocumentVersion).where(DocumentVersion.storage_key == key)).first() is None
        assert s.scalars(select(AuditLog).where(AuditLog.action == "STORAGE_ORPHAN_DELETED", AuditLog.entity_id == key)).one()
