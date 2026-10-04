"""Phase 12B-I — storage and document safety.

- SigV4: the stdlib signer reproduces the AWS-documented example signatures (known-answer tests).
- Object storage (MinIO via S3 APIs) against the TEST-only stub server (tests/s3_stub.py): SSE-S3 required, SHA-256 verified,
  server-generated keys only, one bucket per environment, application identity cannot delete, versioning keeps prior versions,
  public bucket policy / disabled versioning fail health, signature and payload tampering refused.
- Documents end to end on the S3 backend: upload -> verify -> DB commit, authorized and audited download, cross-org refusal, wrong
  environment key, storage outage never leaves a half-created document.
- Antivirus (TEST: EICAR + test double): clean / infected / unavailable, production LIVE refuses without a scanner, append-only scan
  history, quarantine, background rescan, release only after a clean rescan, RBAC.
- Orphan cleanup: only aged, unreferenced, server-generated keys; referenced / recent / unrecognized never deleted; a reference
  appearing after the scan is honoured; no deletion identity -> nothing deleted.
- Local -> MinIO migration: copy + verify, idempotent, originals untouched, mismatches reported.
"""
import hashlib
import json
import os
import time as _time
import uuid
from collections.abc import Iterator
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.context import RequestContext
from app.integrations import malware, storage
from app.integrations.malware import EICAR
from app.integrations.s3 import S3Client, S3Error, canonical_query, sign
from app.integrations.storage import LocalFileStorage, S3ObjectStorage, StorageError
from app.models import AuditLog, BackgroundJob, Document, DocumentScan, DocumentVersion, SecurityEvent
from app.models.jobs import SYSTEM_ACTOR_IDS
from app.services.storage_migration import migrate_local_to
from app.workers import handlers, job_service
from tests.av_fixture import TestDoubleScanner
from tests.conftest import Actor, login, make_user
from tests.phase2 import PDF, create_farmer, dev_org, staff, upload
from tests.s3_stub import APP_KEY, APP_SECRET, DELETE_KEY, DELETE_SECRET, REGION, S3Stub

D = "/api/v1/evidence/documents"


@pytest.fixture(autouse=True)
def _no_broker(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "REDIS_URL", None)          # job publication is recorded on the row, never sent


@pytest.fixture()
def s3(monkeypatch: pytest.MonkeyPatch) -> Iterator[S3Stub]:
    stub = S3Stub().start()
    s = get_settings()
    for k, v in {"STORAGE_BACKEND": "s3", "OBJECT_STORAGE_ENDPOINT": stub.endpoint, "OBJECT_STORAGE_REGION": REGION,
                 "OBJECT_STORAGE_ACCESS_KEY": APP_KEY, "OBJECT_STORAGE_SECRET_KEY": APP_SECRET, "OBJECT_STORAGE_BUCKET_PREFIX": "carbon",
                 "OBJECT_STORAGE_DELETE_ACCESS_KEY": DELETE_KEY, "OBJECT_STORAGE_DELETE_SECRET_KEY": DELETE_SECRET}.items():
        monkeypatch.setattr(s, k, v)
    storage.get_storage.cache_clear()
    try:
        yield stub
    finally:
        storage.get_storage.cache_clear()
        stub.stop()


@pytest.fixture()
def world(db: Session, client: TestClient) -> dict:
    org = dev_org(db)
    pm = staff(db, client, org, "PROJECT_MANAGER")
    farmer = create_farmer(client, pm.headers, org)
    sec = make_user(db, roles=[("SECURITY_ADMIN", None)])
    padm = make_user(db, roles=[("PLATFORM_ADMIN", None)])
    return {"org": org, "pm": pm, "farmer": farmer, "url": f"/api/v1/farmers/{farmer['id']}/documents",
            "sec": Actor(sec, login(client, sec)), "padm": Actor(padm, login(client, padm))}


def _key(env: str = "live") -> str:
    return f"{env}/2026/10/{uuid.uuid4().hex}"


def _up(client: TestClient, world: dict, content: bytes = PDF) -> dict:
    """Upload through the farmer endpoint (it answers with the id) and return the full document."""
    r = upload(client, world["pm"].headers, world["url"], "LAND_RECORD", content)
    assert r.status_code == 201, r.text
    return client.get(f"{D}/{r.json()['id']}", headers=world["pm"].headers).json()


def _scans(db: Session, doc_id: str) -> list[DocumentScan]:
    return list(db.scalars(select(DocumentScan).where(DocumentScan.document_id == uuid.UUID(doc_id)).order_by(DocumentScan.scanned_at)))


# ---------------------------------------------------------------- SigV4 known-answer tests (AWS S3 documentation examples)
_AK, _SK, _DATE, _HOST = "AKIAIOSFODNN7EXAMPLE", "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY", "20130524T000000Z", "examplebucket.s3.amazonaws.com"
_EMPTY = hashlib.sha256(b"").hexdigest()


@pytest.mark.parametrize("method,path,query,extra,expected", [
    ("GET", "/test.txt", {}, {"range": "bytes=0-9"}, "f0e8bdb87c964420e857bd35b5d6ed310bd44f0170aba48dd91039c6036bdb41"),
    ("GET", "/", {"lifecycle": ""}, {}, "fea454ca298b7da1c68078a5d1bdbfbbe0d65c699e0f91ac7a200a0136783543"),
    ("GET", "/", {"max-keys": "2", "prefix": "J"}, {}, "34b48302e7b5fa45bde8084f4b7868a86f0a534bc59db6670ed5711ef69dc6f7"),
])
def test_sigv4_matches_aws_documented_examples(method: str, path: str, query: dict, extra: dict, expected: str) -> None:
    headers = {"host": _HOST, "x-amz-date": _DATE, "x-amz-content-sha256": _EMPTY, **extra}
    auth = sign(method, path, query, headers, _EMPTY, _AK, _SK, "us-east-1", _DATE)
    assert auth.endswith(f"Signature={expected}") and "Credential=AKIAIOSFODNN7EXAMPLE/20130524/us-east-1/s3/aws4_request" in auth
    assert canonical_query({"prefix": "J", "max-keys": "2"}) == "max-keys=2&prefix=J"


def test_s3_xml_with_a_dtd_is_refused() -> None:
    from xml.etree.ElementTree import ParseError

    from app.integrations.s3 import _parse
    with pytest.raises(ParseError):
        _parse(b'<?xml version="1.0"?><!DOCTYPE x [<!ENTITY a "aaaa">]><Error><Code>&a;</Code></Error>')


# ---------------------------------------------------------------- object storage over the S3 protocol
def test_s3_put_verify_get_with_sse_and_per_environment_buckets(s3: S3Stub) -> None:
    st = storage.get_storage()
    assert isinstance(st, S3ObjectStorage)
    live, demo = _key("live"), _key("demo")
    st.put(live, b"live bytes", "application/pdf")
    st.put(demo, b"demo bytes", "application/pdf")
    st.verify(live, hashlib.sha256(b"live bytes").hexdigest(), 10)
    assert st.get(live) == b"live bytes" and st.exists(demo)
    assert live in s3.buckets["carbon-live"].objects and demo in s3.buckets["carbon-demo"].objects       # a key never crosses buckets
    assert live not in s3.buckets["carbon-demo"].objects
    v = s3.buckets["carbon-live"].current(live)
    assert v is not None and v.headers["x-amz-server-side-encryption"] == "AES256"
    assert v.headers["x-amz-meta-sha256"] == hashlib.sha256(b"live bytes").hexdigest()
    with pytest.raises(StorageError, match="SHA-256"):
        st.verify(live, "0" * 64, 10)
    assert st.health() == []
    assert {o.key for o in st.iter_objects("live/")} >= {live} and demo not in {o.key for o in st.iter_objects("live/")}


@pytest.mark.parametrize("bad", ["../etc/passwd", "live/../demo/2026/10/" + "a" * 32, "live/2026/10/ABC", "prod/2026/10/" + "a" * 32,
                                 "live/2026/10/" + "a" * 32 + "/x", ""])
def test_only_server_generated_keys_are_accepted(s3: S3Stub, bad: str) -> None:
    st = storage.get_storage()
    before = len(s3.requests)
    with pytest.raises(StorageError) as e:
        st.put(bad, b"x", "application/pdf")
    assert e.value.code == "INVALID_STORAGE_KEY" and len(s3.requests) == before      # refused before any request


def test_unencrypted_write_is_refused(s3: S3Stub) -> None:
    s3.encrypt = False
    with pytest.raises(StorageError) as e:
        storage.get_storage().put(_key(), b"x", "application/pdf")
    assert e.value.code == "STORAGE_NOT_ENCRYPTED"
    key = _key()
    s3.put_raw("carbon-live", key, b"plain", encrypted=False)
    with pytest.raises(StorageError) as e2:
        storage.get_storage().verify(key, hashlib.sha256(b"plain").hexdigest(), 5)
    assert e2.value.code == "STORAGE_NOT_ENCRYPTED"


def test_signature_identity_and_payload_are_enforced(s3: S3Stub) -> None:
    wrong = S3Client(s3.endpoint, REGION, APP_KEY, "not-the-secret")
    r = wrong.request("GET", "carbon-live", query={"list-type": "2", "prefix": "live/"})
    assert r.status == 403 and S3Client.error(r).code == "SignatureDoesNotMatch"
    unknown = S3Client(s3.endpoint, REGION, "nobody", APP_SECRET)
    assert unknown.request("GET", "carbon-live", query={"versioning": ""}).status == 403
    app = S3Client(s3.endpoint, REGION, APP_KEY, APP_SECRET)
    lying = app.request("PUT", "carbon-live", _key(), body=b"actual bytes", payload_sha256=hashlib.sha256(b"other").hexdigest(),
                        headers={"x-amz-server-side-encryption": "AES256"})
    assert lying.status == 400 and S3Client.error(lying).code == "XAmzContentSHA256Mismatch"


def test_application_identity_cannot_delete_and_versions_survive(s3: S3Stub) -> None:
    st = storage.get_storage()
    key = _key()
    st.put(key, b"v1", "application/pdf")
    st.put(key, b"v2", "application/pdf")
    assert [v.data for v in s3.buckets["carbon-live"].objects[key]] == [b"v1", b"v2"]               # versioning keeps v1
    app = S3Client(s3.endpoint, REGION, APP_KEY, APP_SECRET)
    r = app.request("DELETE", "carbon-live", key)
    assert r.status == 403 and S3Client.error(r).code == "AccessDenied" and st.exists(key)
    assert not hasattr(st, "delete")                                                                   # no delete on the app adapter
    deleter = storage.get_deletion_storage()
    assert deleter is not None and not isinstance(deleter, S3ObjectStorage)
    deleter.delete(key)
    assert not st.exists(key) and [v.data for v in s3.buckets["carbon-live"].objects[key][:2]] == [b"v1", b"v2"]  # recoverable


def test_no_deletion_identity_means_no_deletion(s3: S3Stub, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "OBJECT_STORAGE_DELETE_ACCESS_KEY", None)
    assert storage.get_deletion_storage() is None


def test_health_flags_public_policy_and_disabled_versioning(s3: S3Stub) -> None:
    st = storage.get_storage()
    s3.buckets["carbon-demo"].versioning = False
    s3.buckets["carbon-live"].policy = json.dumps({"Statement": [{"Effect": "Allow", "Principal": {"AWS": ["*"]}, "Action": "s3:GetObject"}]})
    problems = st.health()
    assert any("carbon-demo" in p and "versioning" in p for p in problems) and any("carbon-live" in p and "public" in p for p in problems)
    s3.buckets["carbon-live"].policy = json.dumps({"Statement": [{"Effect": "Allow", "Principal": {"AWS": ["arn:aws:iam::1:user/app"]}}]})
    s3.buckets["carbon-demo"].versioning = True
    assert st.health() == []
    s3.buckets["carbon-live"].policy = "not json"
    assert any("public" in p for p in st.health())                       # an unreadable policy is treated as unsafe


def test_listing_follows_continuation_tokens(s3: S3Stub) -> None:
    keys = {_key() for _ in range(5)}
    for k in keys:
        s3.put_raw("carbon-live", k, b"x")
    s3.page_size = 2
    assert keys <= {o.key for o in storage.get_storage().iter_objects("live/")}


def test_production_refuses_local_storage(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "APP_ENV", "production")
    storage.get_storage.cache_clear()
    try:
        with pytest.raises(RuntimeError, match="not allowed in production"):
            storage.get_storage()
    finally:
        monkeypatch.setattr(get_settings(), "APP_ENV", "test")
        storage.get_storage.cache_clear()


# ---------------------------------------------------------------- documents end to end on the S3 backend
def test_upload_download_on_s3_is_verified_authorized_and_audited(client: TestClient, db: Session, s3: S3Stub, world: dict) -> None:
    r = upload(client, world["pm"].headers, world["url"], "LAND_RECORD", PDF)
    assert r.status_code == 201, r.text
    doc = r.json()
    v = db.scalars(select(DocumentVersion).where(DocumentVersion.document_id == uuid.UUID(doc["id"]))).one()
    obj = s3.buckets["carbon-live"].current(v.storage_key)
    assert obj is not None and obj.data == PDF and obj.headers["x-amz-server-side-encryption"] == "AES256"
    assert v.checksum_sha256 == hashlib.sha256(PDF).hexdigest()
    d = client.get(f"{D}/{doc['id']}/download", headers=world["pm"].headers)
    assert d.status_code == 200 and d.content == PDF and d.headers["cache-control"] == "no-store"
    assert db.scalars(select(AuditLog).where(AuditLog.action == "DOCUMENT_DOWNLOADED", AuditLog.entity_id == world["farmer"]["id"])).first()
    other = staff(db, client, dev_org(db), "PROJECT_MANAGER")                                         # another organisation
    assert client.get(f"{D}/{doc['id']}/download", headers=other.headers).status_code in (403, 404)
    obj.data = PDF.replace(b"Catalog", b"Catalo9")                                                    # tampered at rest
    t = client.get(f"{D}/{doc['id']}/download", headers=world["pm"].headers)
    assert t.status_code == 409 and t.json()["error_code"] == "DOCUMENT_INTEGRITY_FAILURE"


def test_storage_outage_leaves_no_document(client: TestClient, db: Session, s3: S3Stub, world: dict) -> None:
    before = db.scalar(select(func.count()).select_from(Document))
    s3.fail_puts = True
    r = upload(client, world["pm"].headers, world["url"], "LAND_RECORD", PDF)
    assert r.status_code == 503 and r.json()["error_code"] == "STORAGE_UNAVAILABLE"
    s3.fail_puts, s3.encrypt = False, False
    r2 = upload(client, world["pm"].headers, world["url"], "LAND_RECORD", PDF)
    assert r2.status_code == 503 and r2.json()["details"]["reason"] == "STORAGE_NOT_ENCRYPTED"
    db.expire_all()
    assert db.scalar(select(func.count()).select_from(Document)) == before                              # nothing half-created


def test_a_key_from_another_environment_is_refused(client: TestClient, db: Session, world: dict) -> None:
    r = upload(client, world["pm"].headers, world["url"], "LAND_RECORD", PDF)
    doc = db.get(Document, uuid.UUID(r.json()["id"]))
    assert doc is not None
    bad = _key("demo")
    storage.get_storage().put(bad, PDF, "application/pdf")
    doc.current_version = 2
    db.add(DocumentVersion(document_id=doc.id, version=2, file_name="x.pdf", storage_key=bad, mime_type="application/pdf",
                           size_bytes=len(PDF), checksum_sha256=hashlib.sha256(PDF).hexdigest(), scan_status="NOT_SCANNED"))
    db.commit()
    d = client.get(f"{D}/{doc.id}/download", headers=world["pm"].headers)
    assert d.status_code == 409 and d.json()["error_code"] == "DOCUMENT_INTEGRITY_FAILURE"
    assert db.scalars(select(SecurityEvent).where(SecurityEvent.event_type == "DOCUMENT_ENVIRONMENT_MISMATCH")).first()


# ---------------------------------------------------------------- antivirus
def test_signature_scanner_reports_not_scanned_never_clean(client: TestClient, db: Session, world: dict) -> None:
    doc = _up(client, world)
    assert doc["scan_state"] == "NOT_SCANNED"
    rows = _scans(db, doc["id"])
    assert [(s.result, s.trigger_type, s.provider) for s in rows] == [("NOT_SCANNED", "UPLOAD", "signature")]


def test_clean_scan_with_test_double(client: TestClient, db: Session, world: dict, av: TestDoubleScanner) -> None:
    doc = _up(client, world)
    assert doc["scan_state"] == "CLEAN" and doc["versions"][0]["scan_status"] == "CLEAN"
    s = _scans(db, doc["id"])[0]
    assert (s.result, s.provider, s.engine_version, s.checksum_sha256) == ("CLEAN", "test-double", "test-double-1", hashlib.sha256(PDF).hexdigest())
    assert av.calls == 1


def test_infected_upload_is_refused_and_nothing_is_stored(client: TestClient, db: Session, world: dict, av: TestDoubleScanner) -> None:
    before = (db.scalar(select(func.count()).select_from(Document)), sum(1 for _ in storage.get_storage().iter_objects("live/")))
    r = upload(client, world["pm"].headers, world["url"], "OTHER", b"%PDF-1.4\n" + EICAR, "x.pdf")
    assert r.status_code == 422 and r.json()["error_code"] == "MALWARE_DETECTED"
    db.expire_all()
    after = (db.scalar(select(func.count()).select_from(Document)), sum(1 for _ in storage.get_storage().iter_objects("live/")))
    assert after == before                                                                               # no document, no object
    ev = db.scalars(select(SecurityEvent).where(SecurityEvent.event_type == "MALWARE_UPLOAD_BLOCKED")).all()
    assert ev and json.loads(ev[-1].details or "{}").get("threat") == "EICAR-Test-File"


def test_scanner_unavailable_outside_production_quarantines_and_queues_rescan(client: TestClient, db: Session, world: dict,
                                                                            av: TestDoubleScanner) -> None:
    av.mode = "unavailable"
    doc = _up(client, world)
    assert doc["status"] == "QUARANTINED" and doc["scan_state"] == "SCANNER_UNAVAILABLE"
    assert client.get(f"{D}/{doc['id']}/download", headers=world["pm"].headers).json()["error_code"] == "DOCUMENT_QUARANTINED"
    job = db.scalars(select(BackgroundJob).where(BackgroundJob.job_type == "DOCUMENT_RESCAN", BackgroundJob.entity_id == doc["id"])).one()
    assert job.environment == "LIVE" and job.status == "QUEUED"
    av.mode = "clean"
    assert job_service.execute(db, job.id, "test-worker:1", expected_task_name=job.task_name) == "SUCCEEDED"
    db.expire_all()
    assert [s.result for s in _scans(db, doc["id"])] == ["ERROR", "CLEAN"]
    assert db.get(Document, uuid.UUID(doc["id"])).status == "QUARANTINED"                              # a rescan never releases  # type: ignore[union-attr]


def test_production_live_upload_refused_without_scanner(client: TestClient, db: Session, world: dict, av: TestDoubleScanner,
                                                        monkeypatch: pytest.MonkeyPatch) -> None:
    av.mode = "unavailable"
    malware.get_scanner()                                         # resolved before the production switch (the double is TEST-only)
    storage.get_storage()
    before = db.scalar(select(func.count()).select_from(Document))
    monkeypatch.setattr(get_settings(), "APP_ENV", "production")
    r = upload(client, world["pm"].headers, world["url"], "LAND_RECORD", PDF)
    monkeypatch.setattr(get_settings(), "APP_ENV", "test")
    assert r.status_code == 503 and r.json()["error_code"] == "SCANNER_UNAVAILABLE"
    db.expire_all()
    assert db.scalar(select(func.count()).select_from(Document)) == before
    assert db.scalars(select(SecurityEvent).where(SecurityEvent.event_type == "ANTIVIRUS_UNAVAILABLE")).first()


def test_production_refuses_test_scanners(monkeypatch: pytest.MonkeyPatch, av: TestDoubleScanner) -> None:
    monkeypatch.setattr(get_settings(), "APP_ENV", "production")
    malware.get_scanner.cache_clear()
    try:
        with pytest.raises(RuntimeError):
            malware.get_scanner()
        monkeypatch.setattr(get_settings(), "MALWARE_SCANNER", "no-such-vendor")
        malware.get_scanner.cache_clear()
        with pytest.raises(RuntimeError, match="no registered adapter"):
            malware.get_scanner()
    finally:
        monkeypatch.setattr(get_settings(), "APP_ENV", "test")
        malware.get_scanner.cache_clear()


@pytest.mark.usefixtures("no_secret_env")
def test_production_configuration_guard_requires_storage_and_scanner(tmp_path: Path) -> None:
    from pydantic import ValidationError

    from app.core.config import Settings
    base = get_settings().model_dump()
    base.update(APP_ENV="production", REFRESH_COOKIE_SECURE=True, SECRET_KEY="k" * 40, JWT_SECRET="j" * 40, STORAGE_BACKEND="local")
    with pytest.raises(ValidationError, match="STORAGE_BACKEND=s3"):
        Settings(**base)
    base.update(STORAGE_BACKEND="s3", OBJECT_STORAGE_ENDPOINT="http://minio:9000", OBJECT_STORAGE_ACCESS_KEY="a", OBJECT_STORAGE_SECRET_KEY="b")
    with pytest.raises(ValidationError, match="https://"):
        Settings(**base)                                           # plain-http endpoint refused
    base.update(OBJECT_STORAGE_ENDPOINT="https://minio.internal:9000")
    with pytest.raises(ValidationError, match="real antivirus scanner"):
        Settings(**base)                                           # the signature scanner is not an antivirus engine
    base.update(MALWARE_SCANNER="vendor-x", ANTIVIRUS_ENDPOINT="https://av.internal", ANTIVIRUS_API_KEY="x",
                # Phase 12B-II production requirements (shared Redis limiter over TLS, secret-store mount, JSON logs, manual providers)
                RATE_LIMIT_BACKEND="redis", REDIS_URL="rediss://carbon-app:secret@redis.internal:6380/0", SECRETS_DIR=str(tmp_path),
                LOG_FORMAT="json", SATELLITE_PROVIDER="manual", LAB_PROVIDER="manual")
    assert Settings(**base).is_production                          # configuration accepted; the adapter itself is a deployment item


def test_scan_history_is_append_only_in_database() -> None:
    from app.core.database import get_engine
    for stmt in ("UPDATE dbo.document_scans SET result = 'CLEAN'", "DELETE FROM dbo.document_scans"):
        with get_engine().connect() as conn:
            trans = conn.begin()
            with pytest.raises(DBAPIError, match="append-only"):
                conn.execute(text(stmt))
            if trans.is_active:
                trans.rollback()


# ---------------------------------------------------------------- quarantine, rescan, release (security operations)
def test_quarantine_rescan_release_flow_and_rbac(client: TestClient, db: Session, world: dict, av: TestDoubleScanner) -> None:
    doc = _up(client, world)
    sec, padm, pm = world["sec"].headers, world["padm"].headers, world["pm"].headers
    reason = {"reason": "Suspicious upload reported by the field team"}
    assert client.post(f"{D}/{doc['id']}/quarantine", headers=pm, json=reason).status_code == 403
    assert client.post(f"{D}/{doc['id']}/quarantine", headers=padm, json=reason).status_code == 403    # read-only security
    q = client.post(f"{D}/{doc['id']}/quarantine", headers=sec, json=reason)
    assert q.status_code == 200 and q.json()["status"] == "QUARANTINED" and q.json()["scan_state"] == "QUARANTINED"
    assert client.get(f"{D}/{doc['id']}/download", headers=pm).json()["error_code"] == "DOCUMENT_QUARANTINED"
    listed = client.get(f"{D}/quarantined", headers=padm)
    assert listed.status_code == 200 and doc["id"] in {d["id"] for d in listed.json()}
    assert client.get(f"{D}/quarantined", headers=pm).status_code == 403
    assert client.post(f"{D}/{doc['id']}/quarantine", headers=sec, json={}).status_code == 422            # reason required
    rq = client.post(f"{D}/{doc['id']}/rescan", headers=sec)
    assert rq.status_code == 202
    job = db.get(BackgroundJob, uuid.UUID(rq.json()["job_id"]))
    assert job is not None and job.job_type == "DOCUMENT_RESCAN" and job.entity_id == doc["id"]
    assert client.post(f"{D}/{doc['id']}/rescan", headers=padm).status_code == 403
    av.mode = "unavailable"
    refused = client.post(f"{D}/{doc['id']}/release", headers=sec, json=reason)
    assert refused.status_code == 409 and refused.json()["error_code"] == "DOCUMENT_RELEASE_REFUSED"
    assert db.get(Document, uuid.UUID(doc["id"])).status == "QUARANTINED"  # type: ignore[union-attr]
    av.mode = "clean"
    ok = client.post(f"{D}/{doc['id']}/release", headers=sec, json=reason)
    assert ok.status_code == 200 and ok.json()["status"] == "ACTIVE" and ok.json()["scan_state"] == "CLEAN"
    assert client.get(f"{D}/{doc['id']}/download", headers=pm).status_code == 200
    hist = client.get(f"{D}/{doc['id']}/scans", headers=padm).json()
    assert [(h["trigger_type"], h["result"]) for h in hist] == [("UPLOAD", "CLEAN"), ("RELEASE", "ERROR"), ("RELEASE", "CLEAN")]
    actions = set(db.scalars(select(AuditLog.action).where(AuditLog.entity_id == world["farmer"]["id"])))
    assert {"DOCUMENT_QUARANTINED", "DOCUMENT_RELEASE_REFUSED", "DOCUMENT_RELEASED", "DOCUMENT_RESCANNED"} <= actions
    again = client.post(f"{D}/{doc['id']}/release", headers=sec, json=reason)
    assert again.status_code == 409 and again.json()["error_code"] == "DOCUMENT_NOT_QUARANTINED"


def test_infected_on_rescan_quarantines_and_cannot_be_released_without_clean_rescan(client: TestClient, db: Session, world: dict,
                                                                                     av: TestDoubleScanner) -> None:
    doc = _up(client, world)
    av.mode = "infect-all"                                          # new signatures now detect the stored file
    jid = client.post(f"{D}/{doc['id']}/rescan", headers=world["sec"].headers).json()["job_id"]
    job = db.get(BackgroundJob, uuid.UUID(jid))
    assert job is not None and job_service.execute(db, job.id, "test-worker:1", expected_task_name=job.task_name) == "SUCCEEDED"
    got = client.get(f"{D}/{doc['id']}", headers=world["pm"].headers).json()
    assert got["status"] == "QUARANTINED" and got["scan_state"] == "INFECTED"
    assert db.scalars(select(SecurityEvent).where(SecurityEvent.event_type == "DOCUMENT_RESCAN_INFECTED")).first()
    r = client.post(f"{D}/{doc['id']}/release", headers=world["sec"].headers, json={"reason": "Customer insists the file is fine"})
    assert r.status_code == 409 and r.json()["details"]["results"] == ["INFECTED"]
    av.mode = "clean"                                               # e.g. a false positive withdrawn by the vendor
    ok = client.post(f"{D}/{doc['id']}/release", headers=world["sec"].headers, json={"reason": "Vendor withdrew the signature"})
    assert ok.status_code == 200 and ok.json()["status"] == "ACTIVE"
    assert [s.result for s in _scans(db, doc["id"])] == ["CLEAN", "INFECTED", "INFECTED", "CLEAN"]     # history kept in full


def test_release_with_signature_scanner_is_refused(client: TestClient, db: Session, world: dict) -> None:
    doc = _up(client, world)
    client.post(f"{D}/{doc['id']}/quarantine", headers=world["sec"].headers, json={"reason": "Hold for review please"})
    r = client.post(f"{D}/{doc['id']}/release", headers=world["sec"].headers, json={"reason": "Release after review"})
    assert r.status_code == 409 and r.json()["details"]["results"] == ["NOT_SCANNED"]               # NOT_SCANNED is never clean


def test_security_operations_respect_environment(client: TestClient, db: Session, world: dict) -> None:
    doc = _up(client, world)
    demo_sec = make_user(db, roles=[("SECURITY_ADMIN", None)], environment="DEMO")
    h = login(client, demo_sec)
    assert client.get(f"{D}/{doc['id']}/scans", headers=h).status_code == 404
    assert client.post(f"{D}/{doc['id']}/quarantine", headers=h, json={"reason": "Cross environment attempt"}).status_code == 404
    assert doc["id"] not in {d["id"] for d in client.get(f"{D}/quarantined", headers=h).json()}


def test_batch_rescan_skips_without_a_real_engine_and_scans_with_one(client: TestClient, db: Session, world: dict,
                                                                    monkeypatch: pytest.MonkeyPatch) -> None:
    doc = _up(client, world)
    ctx = RequestContext(request_id="t", user_id=SYSTEM_ACTOR_IDS["LIVE"])
    job, _ = job_service.enqueue(db, ctx, "DOCUMENT_RESCAN", environment="LIVE", trigger_type="SERVICE", created_by=SYSTEM_ACTOR_IDS["LIVE"])
    db.commit()
    assert job_service.execute(db, job.id, "w:1", expected_task_name=job.task_name) == "SUCCEEDED"
    assert json.loads(db.get(BackgroundJob, job.id).result or "{}")["skipped"] is True  # type: ignore[union-attr]
    scanner = TestDoubleScanner()
    monkeypatch.setitem(malware._REGISTRY, "test-double", lambda _s: scanner)
    monkeypatch.setattr(get_settings(), "MALWARE_SCANNER", "test-double")
    malware.get_scanner.cache_clear()
    monkeypatch.setattr(get_settings(), "JOB_BATCH_SIZE", 3)
    try:
        job2, _ = job_service.enqueue(db, ctx, "DOCUMENT_RESCAN", environment="LIVE", trigger_type="SERVICE",
                                      created_by=SYSTEM_ACTOR_IDS["LIVE"])
        db.commit()
        assert job_service.execute(db, job2.id, "w:1", expected_task_name=job2.task_name) == "SUCCEEDED"
        res = json.loads(db.get(BackgroundJob, job2.id).result or "{}")  # type: ignore[union-attr]
        assert res["complete"] and res["documents"] >= 1 and res["infected"] == 0
        assert [s.result for s in _scans(db, doc["id"])][-1] == "CLEAN"
    finally:
        malware.get_scanner.cache_clear()


# ---------------------------------------------------------------- orphan cleanup (D10)
def _aged(st: Any, key: str, s3: S3Stub | None = None) -> None:
    if s3 is not None:
        s3.age("carbon-" + key.split("/")[0], key, datetime.utcnow() - timedelta(hours=get_settings().JOB_ORPHAN_GRACE_HOURS + 2))
    else:
        aged = _time.time() - (get_settings().JOB_ORPHAN_GRACE_HOURS + 2) * 3600
        os.utime(st._path(key), (aged, aged))


def _orphan_job(db: Session, env: str = "LIVE") -> dict:
    ctx = RequestContext(request_id="t", user_id=SYSTEM_ACTOR_IDS[env])
    job, _ = job_service.enqueue(db, ctx, "ORPHAN_FILE_SCAN", environment=env, trigger_type="SERVICE", created_by=SYSTEM_ACTOR_IDS[env])
    db.commit()
    assert job_service.execute(db, job.id, "w:1", expected_task_name=job.task_name) == "SUCCEEDED"
    return json.loads(db.get(BackgroundJob, job.id).result or "{}")  # type: ignore[union-attr]


@pytest.mark.parametrize("backend", ["local", "s3"])
def test_orphans_deleted_only_when_aged_unreferenced_and_server_generated(client: TestClient, db: Session, world: dict,
                                                                          request: pytest.FixtureRequest, backend: str) -> None:
    stub = request.getfixturevalue("s3") if backend == "s3" else None
    st: Any = storage.get_storage()
    doc = _up(client, world)
    referenced = db.scalars(select(DocumentVersion.storage_key).where(DocumentVersion.document_id == uuid.UUID(doc["id"]))).one()
    orphan, recent, demo_orphan = _key(), _key(), _key("demo")
    for k in (orphan, recent, demo_orphan):
        st.put(k, b"orphan bytes", "application/pdf")
    for k in (orphan, referenced, demo_orphan):
        _aged(st, k, stub)
    if stub is None:                                                 # a stray non-document file under live/ is never touched
        stray = Path(st.root) / "live" / "notes.txt"
        stray.parent.mkdir(parents=True, exist_ok=True)
        stray.write_bytes(b"keep me")
    res = _orphan_job(db)
    assert res["deletion"] == "ENABLED" and res["complete"] and res["deleted"] >= 1 and res["delete_failures"] == 0
    assert not st.exists(orphan) and st.exists(referenced) and st.exists(recent) and st.exists(demo_orphan)
    assert db.scalars(select(AuditLog).where(AuditLog.action == "STORAGE_ORPHAN_DELETED", AuditLog.entity_id == orphan)).one()
    if stub is None:
        assert stray.exists() and res["unrecognized_keys"] >= 1
        stray.unlink()
    else:
        assert stub.buckets["carbon-live"].objects[orphan][0].data == b"orphan bytes"                # still recoverable (versioning)
        assert any(m == "DELETE" and a == DELETE_KEY for m, _p, a in stub.requests)
        assert not any(m == "DELETE" and a == APP_KEY for m, _p, a in stub.requests)
    assert client.get(f"{D}/{doc['id']}/download", headers=world["pm"].headers).status_code == 200    # referenced object intact
    demo = _orphan_job(db, "DEMO")
    assert demo["deleted"] >= 1 and not st.exists(demo_orphan) and st.exists(referenced)          # the DEMO job owns demo/ only


def test_orphan_cleanup_without_deletion_identity_deletes_nothing(db: Session, s3: S3Stub, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "OBJECT_STORAGE_DELETE_ACCESS_KEY", None)
    st = storage.get_storage()
    k = _key()
    st.put(k, b"x", "application/pdf")
    _aged(st, k, s3)
    res = _orphan_job(db)
    assert res["deletion"].startswith("DISABLED") and k in res["sample_candidates"] and res["deleted"] == 0 and st.exists(k)


def test_reference_appearing_after_the_scan_is_never_deleted(db: Session, world: dict, monkeypatch: pytest.MonkeyPatch) -> None:
    """The candidate list is computed first; a version referencing the key is then committed (e.g. a slow upload transaction). The
    locked re-check inside the deletion transaction must see it. (Cross-connection locking is in test_storage_concurrency.py.)"""
    st: Any = storage.get_storage()
    k = _key()
    st.put(k, PDF, "application/pdf")
    _aged(st, k)
    doc = Document(entity_type="farmer", entity_id=uuid.UUID(world["farmer"]["id"]), organization_id=world["org"].id, category="OTHER",
                   title="late", environment="LIVE")
    db.add(doc)
    db.flush()
    real = handlers.KEY_PATTERN

    class LateReference:
        def match(self, key: str) -> Any:
            if key == k:
                db.add(DocumentVersion(document_id=doc.id, version=1, file_name="late.pdf", storage_key=k, mime_type="application/pdf",
                                       size_bytes=len(PDF), checksum_sha256=hashlib.sha256(PDF).hexdigest(), scan_status="NOT_SCANNED"))
                db.flush()
            return real.match(key)
    monkeypatch.setattr(handlers, "KEY_PATTERN", LateReference())
    res = _orphan_job(db)
    assert res["became_referenced"] == 1 and st.exists(k)


# ---------------------------------------------------------------- local -> MinIO migration (D9)
def test_local_to_s3_migration_copies_verifies_and_never_deletes(client: TestClient, db: Session, world: dict, s3: S3Stub) -> None:
    local = LocalFileStorage(storage.local_root())
    storage.get_storage.cache_clear()
    keys = []
    for i in range(3):
        key = _key()
        data = PDF + str(i).encode()
        local.put(key, data, "application/pdf")
        keys.append((key, data))
    doc = Document(entity_type="farmer", entity_id=uuid.UUID(world["farmer"]["id"]), organization_id=world["org"].id, category="OTHER",
                   title="migrate", environment="LIVE", current_version=5)
    db.add(doc)
    db.flush()
    for n, (key, data) in enumerate(keys, start=1):
        db.add(DocumentVersion(document_id=doc.id, version=n, file_name="m.pdf", storage_key=key, mime_type="application/pdf",
                               size_bytes=len(data), checksum_sha256=hashlib.sha256(data).hexdigest(), scan_status="NOT_SCANNED"))
    missing, mismatched = _key(), _key()
    local.put(mismatched, b"not what the record says", "application/pdf")
    db.add(DocumentVersion(document_id=doc.id, version=4, file_name="m.pdf", storage_key=missing, mime_type="application/pdf",
                           size_bytes=3, checksum_sha256="0" * 64, scan_status="NOT_SCANNED"))
    db.add(DocumentVersion(document_id=doc.id, version=5, file_name="m.pdf", storage_key=mismatched, mime_type="application/pdf",
                           size_bytes=3, checksum_sha256="1" * 64, scan_status="NOT_SCANNED"))
    db.flush()
    target = storage.get_storage()
    dry = migrate_local_to(db, local, target, dry_run=True)
    assert dry.copied >= 3 and not any(s3.buckets["carbon-live"].current(k) for k, _ in keys)       # dry run writes nothing
    rep = migrate_local_to(db, local, target)
    assert {k for k, _ in keys} <= set(s3.buckets["carbon-live"].objects)
    for key, data in keys:
        target.verify(key, hashlib.sha256(data).hexdigest(), len(data))
        assert local.get(key) == data                                                                  # original untouched
    assert missing in rep.missing_source and mismatched in rep.source_checksum_mismatch and not rep.ok
    assert local.exists(mismatched) and s3.buckets["carbon-live"].current(mismatched) is None
    again = migrate_local_to(db, local, target)
    assert again.copied == 0 and again.already_present >= 3                                            # idempotent re-run
    with pytest.raises(StorageError):
        migrate_local_to(db, local, local)


def test_s3_client_rejects_bad_endpoints() -> None:
    with pytest.raises(ValueError):
        S3Client("ftp://minio", REGION, "a", "b")
    with pytest.raises(S3Error):
        raise S3Error(500, "InternalError")
