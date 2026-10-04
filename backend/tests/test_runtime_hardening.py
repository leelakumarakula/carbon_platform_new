"""Phase 12B-II — runtime hardening.

Rate limiting behind the existing abstraction (D18) with the locked D19 values, FAIL-OPEN on a Redis outage (D20, logged + metric +
readiness), trusted-proxy client IPs (D21), production Redis / secret-store / mock-provider / logging guards (D22, D23, D30, D38, D44),
MultiFernet + JWT `kid` rotation (D30), health live / ready (D46), F1 / F5 / F6 / F9, structured logs and metrics (D43 / D44), the
deferred external-notification boundary (D39 / D41 / D42) and Phase 12A D24 (Redis down: jobs stay QUEUED in SQL Server).
No real Redis, secret store, SMTP or monitoring platform is used: fakeredis (dev dependency) and closed ports stand in for Redis.
"""
import json
import logging
import uuid
from datetime import datetime, time, timedelta
from typing import Any

import fakeredis
import jwt
import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette.requests import Request

from app.api.v1 import health
from app.core import metrics
from app.core.config import Settings, get_settings
from app.core.context import set_request_id
from app.core.errors import AuthenticationFailed
from app.core.logs import JsonFormatter, scrub, scrub_text
from app.core.middleware import client_ip
from app.core.rate_limit import RedisRateLimiter, limiter, redis_client
from app.integrations import notify, payment, payout, registry
from app.integrations.lims import NoLimsAdapter, get_lims_adapter
from app.main import create_app
from app.models import BackgroundJob, FarmerBankAccount, SecurityEvent
from app.models.jobs import SYSTEM_ACTOR_IDS
from app.security import crypto, tokens
from app.services.key_rotation import reencrypt_bank_accounts
from tests.conftest import PASSWORD, Actor, login, make_user
from tests.phase2 import PDF, create_farmer, dev_org, staff, upload
from tests.test_storage_av import s3  # noqa: F401 - pytest fixture (TEST-only S3 stub)

API = "/api/v1"


@pytest.fixture(autouse=True)
def _fresh_metrics() -> None:
    metrics.reset()


# ---------------------------------------------------------------- D18 / D20 Redis limiter (fail open, never silent)
def test_redis_limiter_counts_in_shared_windows_with_hashed_keys() -> None:
    r = fakeredis.FakeRedis()
    rl = RedisRateLimiter(r, prefix="rl:test")
    assert all(rl.hit("login:10.0.0.1:alice@example.com", 3, 60) for _ in range(3))
    assert not rl.hit("login:10.0.0.1:alice@example.com", 3, 60)
    other = RedisRateLimiter(r, prefix="rl:test")                          # a second API process shares the same counters
    assert not other.hit("login:10.0.0.1:alice@example.com", 3, 60)
    keys = [k.decode() for k in r.keys("*")]
    assert keys and all("alice" not in k and "example.com" not in k and k.startswith("rl:test:") for k in keys)   # D18: hashed
    assert all(0 < r.ttl(k) <= 120 for k in keys)                          # counters only, they expire
    rl.reset()
    assert r.keys("*") == []


class _DownRedis:
    def __init__(self) -> None:
        self.calls = 0

    def pipeline(self, transaction: bool = True) -> Any:
        self.calls += 1
        raise ConnectionError("redis down")


def test_redis_outage_fails_open_with_log_metric_and_retry_pause(caplog: pytest.LogCaptureFixture) -> None:
    down = _DownRedis()
    rl = RedisRateLimiter(down, retry_seconds=30)
    with caplog.at_level(logging.WARNING, logger="app.ratelimit"):
        assert all(rl.hit("global:1.2.3.4", 1, 60) for _ in range(5))       # D20: allowed even far above the limit
    assert down.calls == 1                                                  # retry pause: no further Redis calls (no added latency)
    assert rl.degraded() and rl.fail_open_count == 5
    assert any("DEGRADED" in r.getMessage() and "fail-open" in r.getMessage() for r in caplog.records)
    snap = {(c["name"], tuple(sorted(c["labels"].items()))): c["value"] for c in metrics.snapshot()["counters"]}
    assert snap[("rate_limiter_degraded_total", (("backend", "redis"),))] == 5
    assert snap[("redis_errors_total", (("component", "rate_limiter"),))] == 1


def test_real_connection_refused_fails_open_and_recovers() -> None:
    rl = RedisRateLimiter(redis_client("redis://127.0.0.1:1/0", timeout=0.2), retry_seconds=0)
    assert rl.hit("k", 1, 60) and rl.hit("k", 1, 60) and rl.degraded() is False   # retry_seconds=0: probes again each time
    rl.client = fakeredis.FakeRedis()                                           # Redis back: limits enforced again
    assert rl.hit("k", 1, 60) and not rl.hit("k", 1, 60)


def test_database_lockout_still_applies_while_redis_is_down(client: TestClient, db: Session) -> None:
    limiter.use(RedisRateLimiter(_DownRedis(), retry_seconds=60))
    try:
        u = make_user(db)
        for _ in range(get_settings().MAX_FAILED_LOGINS):
            client.post(f"{API}/auth/login", json={"email": u.email, "password": "wrong-password-1"})
        r = client.post(f"{API}/auth/login", json={"email": u.email, "password": PASSWORD})
        assert r.status_code in (401, 423) and r.json()["error_code"] in ("ACCOUNT_LOCKED", "INVALID_CREDENTIALS")
        db.refresh(u)
        assert u.is_locked()                                                     # DB lockout is independent of Redis
    finally:
        limiter.use(None)


def test_production_requires_the_shared_redis_limiter(tmp_path: Any) -> None:
    with pytest.raises(ValidationError, match="RATE_LIMIT_BACKEND=redis"):
        Settings(**_prod(tmp_path, RATE_LIMIT_BACKEND="memory"))


# ---------------------------------------------------------------- D19 / F5 limits through the API (configured values)
def _limits(monkeypatch: pytest.MonkeyPatch, **values: int) -> None:
    for k, v in values.items():
        monkeypatch.setattr(get_settings(), k, v)
    limiter.reset()


def test_d19_defaults_are_the_locked_values() -> None:
    s = get_settings()
    assert (s.REFRESH_RATE_LIMIT_PER_MINUTE, s.UPLOAD_RATE_LIMIT_PER_MINUTE, s.USER_RATE_LIMIT_PER_MINUTE,
            s.ORGANIZATION_RATE_LIMIT_PER_MINUTE, s.API_BURST_RATE_LIMIT_PER_MINUTE) == (100, 100, 1000, 5000, 10000)
    assert (s.LOGIN_RATE_LIMIT_PER_MINUTE, s.GLOBAL_RATE_LIMIT_PER_MINUTE, s.MAX_FAILED_LOGINS) == (1000, 600, 5)  # tests: login 1000


def test_per_user_and_per_organization_limits(client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    org = dev_org(db)
    a, b = staff(db, client, org, "PROJECT_MANAGER"), staff(db, client, org, "PROJECT_MANAGER")
    _limits(monkeypatch, USER_RATE_LIMIT_PER_MINUTE=3)
    codes = [client.get(f"{API}/farmers", headers=a.headers).status_code for _ in range(4)]
    assert codes == [200, 200, 200, 429]
    assert client.get(f"{API}/farmers", headers=b.headers).status_code == 200          # another user is unaffected
    _limits(monkeypatch, USER_RATE_LIMIT_PER_MINUTE=1000, ORGANIZATION_RATE_LIMIT_PER_MINUTE=3)
    seq = [client.get(f"{API}/farmers", headers=h).status_code for h in (a.headers, b.headers, a.headers, b.headers)]
    assert seq == [200, 200, 200, 429]                                                 # the organization's total, across users
    r = client.get(f"{API}/farmers", headers=a.headers)
    assert r.json()["error_code"] == "ORGANIZATION_RATE_LIMITED" and r.headers["retry-after"] == "60"


def test_upload_limit(client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    org = dev_org(db)
    pm = staff(db, client, org, "PROJECT_MANAGER")
    farmer = create_farmer(client, pm.headers, org)
    _limits(monkeypatch, UPLOAD_RATE_LIMIT_PER_MINUTE=2)
    url = f"{API}/farmers/{farmer['id']}/documents"
    codes = [upload(client, pm.headers, url, "LAND_RECORD", PDF).status_code for _ in range(3)]
    assert codes == [201, 201, 429]
    assert upload(client, pm.headers, url, "LAND_RECORD", PDF).json()["error_code"] == "UPLOAD_RATE_LIMITED"
    assert client.get(f"{API}/farmers", headers=pm.headers).status_code == 200           # non-upload requests unaffected


def test_refresh_limit_keeps_rotation_and_reuse_detection(client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    u = make_user(db)
    r = client.post(f"{API}/auth/login", json={"email": u.email, "password": PASSWORD})
    assert r.status_code == 200
    _limits(monkeypatch, REFRESH_RATE_LIMIT_PER_MINUTE=2)
    first = client.post(f"{API}/auth/refresh")
    assert first.status_code == 200                                                    # rotation as before
    assert client.post(f"{API}/auth/refresh").status_code == 200
    blocked = client.post(f"{API}/auth/refresh")
    assert blocked.status_code == 429 and blocked.json()["error_code"] == "RATE_LIMITED"


def test_burst_ceiling_and_probes_are_exempt(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    _limits(monkeypatch, API_BURST_RATE_LIMIT_PER_MINUTE=3)
    codes = [client.get(f"{API}/health").status_code for _ in range(4)]
    assert codes == [200, 200, 200, 429]
    assert client.get(f"{API}/health/live").status_code == 200                           # load-balancer probes never limited
    assert client.get(f"{API}/health/ready").status_code in (200, 503)


# ---------------------------------------------------------------- D21 trusted proxies
def _req(peer: str, xff: str | None = None) -> Request:
    headers = [(b"x-forwarded-for", xff.encode())] if xff is not None else []
    return Request({"type": "http", "method": "GET", "path": "/", "headers": headers, "client": (peer, 1234), "query_string": b""})


def test_forwarded_for_is_trusted_only_from_configured_proxies(monkeypatch: pytest.MonkeyPatch) -> None:
    s = get_settings()
    monkeypatch.setattr(s, "TRUSTED_PROXIES", [])
    assert client_ip(_req("203.0.113.9", "1.1.1.1")) == "203.0.113.9"                  # nothing trusted: header ignored
    monkeypatch.setattr(s, "TRUSTED_PROXIES", ["10.0.0.0/8"])
    assert client_ip(_req("198.51.100.7", "1.1.1.1")) == "198.51.100.7"               # spoofed header from an untrusted peer
    assert client_ip(_req("10.1.2.3", "203.0.113.50")) == "203.0.113.50"              # via our proxy
    assert client_ip(_req("10.1.2.3", "6.6.6.6, 203.0.113.50, 10.9.9.9")) == "203.0.113.50"   # client-supplied left part ignored
    assert client_ip(_req("10.1.2.3", "not-an-ip")) == "10.1.2.3"
    assert client_ip(_req("10.1.2.3")) == "10.1.2.3"
    for bad in (["0.0.0.0/0"], ["::/0"], ["proxy.internal"]):
        base = get_settings().model_dump()
        base["TRUSTED_PROXIES"] = bad
        with pytest.raises(ValidationError):
            Settings(**base)


# ---------------------------------------------------------------- F6 body size (declared and streamed)
def test_body_size_limit_declared_and_chunked(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "MAX_REQUEST_BYTES", 2048)
    big = json.dumps({"email": "x@test.example", "password": "y" * 5000})
    r = client.post(f"{API}/auth/login", content=big, headers={"content-type": "application/json"})
    assert r.status_code == 413 and r.json()["error_code"] == "PAYLOAD_TOO_LARGE"

    def chunks() -> Any:
        for _ in range(10):
            yield b"x" * 600
    r2 = client.post(f"{API}/auth/login", content=chunks(), headers={"content-type": "application/json"})
    assert r2.status_code == 413 and r2.json()["error_code"] == "PAYLOAD_TOO_LARGE"
    ok = client.post(f"{API}/auth/login", json={"email": "nobody@test.example", "password": "short-but-valid-1"})
    assert ok.status_code != 413


# ---------------------------------------------------------------- D46 / F9 health
def test_health_live_ready_and_compatibility(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    assert client.get(f"{API}/health/live").json() == {"status": "alive"}
    h = client.get(f"{API}/health").json()
    assert h["status"] == "ok" and h["environment"] == "test"                         # unchanged outside production
    r = client.get(f"{API}/health/ready")
    assert r.status_code == 200 and r.json()["checks"]["database"] == "ok" and "details" in r.json()
    monkeypatch.setattr(get_settings(), "APP_ENV", "production")
    h = client.get(f"{API}/health").json()
    assert "environment" not in h                                                       # F9
    rp = client.get(f"{API}/health/ready").json()
    assert set(rp) == {"status", "checks"} and "test" not in json.dumps(rp)             # no details / environment in production
    monkeypatch.setattr(get_settings(), "APP_ENV", "test")


def test_ready_fails_on_schema_mismatch(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(health, "_migration_head", lambda: "9999")
    r = client.get(f"{API}/health/ready")
    assert r.status_code == 503 and r.json()["status"] == "not_ready" and r.json()["checks"]["database"] == "failed"


class _FakeRedis:
    def __init__(self, policy: str = "noeviction", aof: int = 1, down: bool = False) -> None:
        self.policy, self.aof, self.down = policy, aof, down

    def ping(self) -> bool:
        if self.down:
            raise ConnectionError("down")
        return True

    def info(self, section: str) -> dict[str, Any]:
        return {"maxmemory_policy": self.policy} if section == "memory" else {"aof_enabled": self.aof}


def test_redis_readiness_outage_is_degraded_misconfiguration_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(health, "redis_client", lambda *a, **k: _FakeRedis(down=True))
    assert health.redis_status("rediss://u:p@redis:6380/0", production=True)[0] == "degraded"
    monkeypatch.setattr(health, "redis_client", lambda *a, **k: _FakeRedis(policy="allkeys-lru"))
    state, detail = health.redis_status("rediss://u:p@redis:6380/0", production=True)
    assert state == "failed" and "noeviction" in detail
    monkeypatch.setattr(health, "redis_client", lambda *a, **k: _FakeRedis(aof=0))
    assert health.redis_status("rediss://u:p@redis:6380/0", production=True)[0] == "failed"
    monkeypatch.setattr(health, "redis_client", lambda *a, **k: _FakeRedis())
    assert health.redis_status("rediss://u:p@redis:6380/0", production=True)[0] == "ok"
    assert health.redis_status(None, production=True)[0] == "not_configured"


def test_ready_with_redis_down_stays_ready_but_degraded(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "REDIS_URL", "redis://127.0.0.1:1/0")
    r = client.get(f"{API}/health/ready")
    assert r.status_code == 200 and r.json()["status"] == "degraded" and r.json()["checks"]["broker"] == "degraded"


def test_ready_fails_on_public_bucket(client: TestClient, s3: Any) -> None:  # noqa: F811
    s3.buckets["carbon-live"].policy = json.dumps({"Statement": [{"Effect": "Allow", "Principal": "*", "Action": "s3:GetObject"}]})
    r = client.get(f"{API}/health/ready")
    assert r.status_code == 503 and r.json()["checks"]["storage"] == "failed"
    s3.buckets["carbon-live"].policy = None
    assert client.get(f"{API}/health/ready").json()["checks"]["storage"] == "ok"


# ---------------------------------------------------------------- F1 OpenAPI off in production
def test_openapi_and_swagger_disabled_in_production(monkeypatch: pytest.MonkeyPatch) -> None:
    dev = TestClient(create_app())
    assert dev.get("/docs").status_code == 200 and dev.get(f"{API}/openapi.json").status_code == 200
    monkeypatch.setattr(get_settings(), "APP_ENV", "production")
    app = create_app()
    app.state.access_log_writer = lambda _r: None
    prod = TestClient(app)
    assert prod.get("/docs").status_code == 404 and prod.get(f"{API}/openapi.json").status_code == 404
    monkeypatch.setattr(get_settings(), "APP_ENV", "test")


# ---------------------------------------------------------------- production configuration guards (D22/D23, D30, D38, D44)
def _prod(tmp_path: Any, **over: Any) -> dict[str, Any]:
    base = get_settings().model_dump()
    base.update(APP_ENV="production", REFRESH_COOKIE_SECURE=True, SECRET_KEY="k" * 40, JWT_SECRET="j" * 40, STORAGE_BACKEND="s3",
                OBJECT_STORAGE_ENDPOINT="https://minio.internal:9000", OBJECT_STORAGE_ACCESS_KEY="a", OBJECT_STORAGE_SECRET_KEY="b",
                MALWARE_SCANNER="vendor-x", ANTIVIRUS_ENDPOINT="https://av.internal", ANTIVIRUS_API_KEY="x", RATE_LIMIT_BACKEND="redis",
                REDIS_URL="rediss://carbon-app:secret@redis.internal:6380/0", SECRETS_DIR=str(tmp_path), LOG_FORMAT="json",
                SATELLITE_PROVIDER="manual", LAB_PROVIDER="manual")
    base.update(over)
    return base


@pytest.mark.usefixtures("no_secret_env")
def test_valid_production_configuration_is_accepted(tmp_path: Any) -> None:
    assert Settings(**_prod(tmp_path)).is_production


@pytest.mark.parametrize("over,match", [
    ({"REDIS_URL": "redis://carbon-app:secret@redis.internal:6379/0"}, "TLS"),
    ({"REDIS_URL": "rediss://redis.internal:6380/0"}, "ACL user and password"),
    ({"REDIS_URL": "rediss://:secret@redis.internal:6380/0"}, "ACL user and password"),
    ({"REDIS_URL": "rediss://default:secret@redis.internal:6380/0"}, "dedicated Redis ACL user"),
    ({"RATE_LIMIT_REDIS_URL": "redis://limiter:pw@redis.internal:6379/1"}, "TLS"),
    ({"SATELLITE_PROVIDER": "mock"}, "simulated providers"),
    ({"LAB_PROVIDER": "Mock"}, "simulated providers"),
    ({"PAYMENT_PROVIDER": "fake"}, "simulated providers"),
    ({"REGISTRY_PROVIDER": "test"}, "simulated providers"),
    ({"SECRETS_DIR": None}, "SECRETS_DIR"),
    ({"LOG_FORMAT": "text"}, "structured JSON"),
    ({"METRICS_TOKEN": "short"}, "METRICS_TOKEN"),
])
@pytest.mark.usefixtures("no_secret_env")
def test_unsafe_production_configuration_is_refused(tmp_path: Any, over: dict[str, Any], match: str) -> None:
    with pytest.raises(ValidationError, match=match):
        Settings(**_prod(tmp_path, **over))


def test_mock_provider_names_allowed_only_outside_production() -> None:
    base = get_settings().model_dump()
    base.update(SATELLITE_PROVIDER="mock", LAB_PROVIDER="mock")
    assert Settings(**base).SATELLITE_PROVIDER == "mock"                                  # development / TEST unaffected
    assert get_settings().SATELLITE_PROVIDER in ("manual", "mock")


def test_runtime_adapters_are_manual_only() -> None:
    """D38: no simulated provider is registered at runtime (TEST adapters live in the test suite only)."""
    assert set(payment.ADAPTERS) == {"MANUAL"} and set(payout.ADAPTERS) == {"MANUAL"} and set(registry.ADAPTERS) == {"MANUAL"}
    assert isinstance(get_lims_adapter(), NoLimsAdapter)


def test_secrets_as_plain_environment_variables_are_refused_in_production(tmp_path: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JWT_SECRET", "j" * 40)
    with pytest.raises(ValidationError, match="plain environment variables"):
        Settings(**_prod(tmp_path))


def test_secret_store_mount_is_read_and_dotenv_is_ignored_in_production(tmp_path: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "METRICS_TOKEN").write_text("m" * 40, encoding="utf-8")
    s = get_settings()                                              # no .env here: a developer's METRICS_TOKEN= line would win
    required = {"SECRET_KEY": s.SECRET_KEY, "JWT_SECRET": s.JWT_SECRET, "DATA_ENCRYPTION_KEY": s.DATA_ENCRYPTION_KEY}
    monkeypatch.delenv("METRICS_TOKEN", raising=False)
    assert Settings(_env_file=None, _secrets_dir=str(tmp_path), **required).METRICS_TOKEN == "m" * 40  # type: ignore[call-arg]
    sources = ("init", "env", "dotenv", "secrets")
    monkeypatch.setenv("APP_ENV", "production")
    assert Settings.settings_customise_sources(Settings, *sources) == ("init", "env", "secrets")  # type: ignore[arg-type]
    monkeypatch.setenv("APP_ENV", "development")
    assert Settings.settings_customise_sources(Settings, *sources) == sources  # type: ignore[arg-type]


def test_external_notification_delivery_cannot_be_enabled() -> None:
    base = get_settings().model_dump()
    base["NOTIFICATION_EXTERNAL_DELIVERY"] = "enabled"
    with pytest.raises(ValidationError, match="deferred"):
        Settings(**base)


def test_celery_broker_tls_verifies_certificates() -> None:
    import ssl

    from app.workers.celery_app import _broker_ssl
    assert _broker_ssl("redis://localhost:6379/0", None) is None
    opts = _broker_ssl("rediss://u:p@redis:6380/0", "/etc/ssl/ca.pem")
    assert opts == {"ssl_cert_reqs": ssl.CERT_REQUIRED, "ssl_ca_certs": "/etc/ssl/ca.pem"}


# ---------------------------------------------------------------- D24 Redis down: jobs stay QUEUED in SQL Server
def test_broker_outage_keeps_jobs_queued_and_counts_the_failure(db: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.core.context import RequestContext
    from app.workers import job_service
    monkeypatch.setattr(get_settings(), "REDIS_URL", "redis://127.0.0.1:1/0")
    actor = SYSTEM_ACTOR_IDS["LIVE"]
    job, _ = job_service.enqueue(db, RequestContext(user_id=actor), "RETENTION_PURGE", environment="LIVE", trigger_type="SERVICE",
                                 created_by=actor)
    db.commit()
    assert job_service.publish(db, job.id) is False
    row = db.get(BackgroundJob, job.id)
    assert row is not None and row.status == "QUEUED" and row.published_at is None and row.last_publish_error
    names = {c["name"]: c for c in metrics.snapshot()["counters"]}
    assert names["redis_errors_total"]["labels"] == {"component": "broker"}


# ---------------------------------------------------------------- D30 key rotation
def _rekey(monkeypatch: pytest.MonkeyPatch, primary: str, previous: list[str]) -> None:
    monkeypatch.setattr(get_settings(), "DATA_ENCRYPTION_KEY", primary)
    monkeypatch.setattr(get_settings(), "DATA_ENCRYPTION_PREVIOUS_KEYS", previous)
    crypto._fernet.cache_clear()
    crypto._primary.cache_clear()


def test_multifernet_rotation_and_reencryption(client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    old, new = get_settings().DATA_ENCRYPTION_KEY, Fernet.generate_key().decode()
    try:
        org = dev_org(db)
        pm = staff(db, client, org, "PROJECT_MANAGER")
        farmer = create_farmer(client, pm.headers, org)
        token = crypto.encrypt("123456789012")
        acct = FarmerBankAccount(farmer_id=uuid.UUID(farmer["id"]), account_holder_name="TEST", bank_name="TEST BANK", routing_code="TEST0000001",
                                 account_number_enc=token, account_last4="9012", account_number_hash="0" * 64)
        db.add(acct)
        db.commit()
        stamp = acct.updated_at
        _rekey(monkeypatch, new, [old])
        assert crypto.decrypt(token) == "123456789012" and crypto.needs_rotation(token)   # old values still readable
        assert not crypto.needs_rotation(crypto.encrypt("x"))                               # new values use the new key
        dry = reencrypt_bank_accounts(db, dry_run=True)
        assert dry["rotated"] >= 1 and db.get(FarmerBankAccount, acct.id).account_number_enc == token  # type: ignore[union-attr]
        rep = reencrypt_bank_accounts(db)
        assert rep["rotated"] >= 1 and rep["undecryptable"] == 0
        db.expire_all()
        row = db.get(FarmerBankAccount, acct.id)
        assert row is not None and row.account_number_enc != token and row.updated_at == stamp
        _rekey(monkeypatch, new, [])                                                         # old key removed after rotation
        assert crypto.decrypt(row.account_number_enc) == "123456789012"
        with pytest.raises(ValueError):
            crypto.decrypt(token)
        assert reencrypt_bank_accounts(db)["already_current"] >= 1
        ev = db.scalars(select(SecurityEvent).where(SecurityEvent.event_type == "DATA_ENCRYPTION_KEY_ROTATED")).all()
        assert ev and "123456789012" not in (ev[-1].details or "")
    finally:
        _rekey(monkeypatch, old, [])


def test_jwt_kid_rotation(monkeypatch: pytest.MonkeyPatch) -> None:
    s = get_settings()
    uid, sid = uuid.uuid4(), uuid.uuid4()
    old_token, _ = tokens.create_access_token(uid, sid)
    assert jwt.get_unverified_header(old_token)["kid"] == s.JWT_KEY_ID
    old_kid, old_secret = s.JWT_KEY_ID, s.JWT_SECRET
    monkeypatch.setattr(s, "JWT_KEY_ID", "k2")
    monkeypatch.setattr(s, "JWT_SECRET", "n" * 48)
    monkeypatch.setattr(s, "JWT_PREVIOUS_KEYS", [f"{old_kid}:{old_secret}"])
    assert tokens.decode_access_token(old_token).user_id == uid                          # rotation window: old kid still verifies
    new_token, _ = tokens.create_access_token(uid, sid)
    assert jwt.get_unverified_header(new_token)["kid"] == "k2" and tokens.decode_access_token(new_token).session_id == sid
    monkeypatch.setattr(s, "JWT_PREVIOUS_KEYS", [])
    with pytest.raises(AuthenticationFailed):
        tokens.decode_access_token(old_token)                                            # window closed
    forged = jwt.encode({"sub": str(uid), "sid": str(sid), "typ": "access", "iss": s.JWT_ISSUER, "iat": 0, "exp": 2 ** 31},
                        "n" * 48, algorithm="HS256", headers={"kid": "unknown"})
    with pytest.raises(AuthenticationFailed):
        tokens.decode_access_token(forged)
    none_alg = jwt.encode({"sub": str(uid)}, None, algorithm="none") if hasattr(jwt, "encode") else ""  # type: ignore[arg-type]
    with pytest.raises(AuthenticationFailed):
        tokens.decode_access_token(none_alg)


def test_rotation_key_configuration_is_validated() -> None:
    base = get_settings().model_dump()
    for over in ({"DATA_ENCRYPTION_PREVIOUS_KEYS": ["not-a-fernet-key"]}, {"JWT_PREVIOUS_KEYS": ["k0-without-secret"]},
                 {"JWT_PREVIOUS_KEYS": [f"{base['JWT_KEY_ID']}:{'s' * 40}"]}, {"JWT_KEY_ID": "a:b"}):
        with pytest.raises(ValidationError):
            Settings(**{**base, **over})


# ---------------------------------------------------------------- D44 structured logs, D43 metrics
def test_json_log_lines_carry_correlation_and_never_secrets() -> None:
    set_request_id("req-12345678")
    rec = logging.LogRecord("app.test", logging.INFO, __file__, 1, "login with Bearer abc.def.ghi password=hunter2 token: zzz", None, None)
    rec.fields = {"route": "/api/v1/farmers/{farmer_id}", "status": 200, "password": "p", "refresh_token": "t",  # type: ignore[attr-defined]
                  "account_number": "123", "nested": {"api_key": "k", "ok": 1},
                  "url": "rediss://user:supersecret@redis:6380/0"}
    out = json.loads(JsonFormatter().format(rec))
    assert out["request_id"] == "req-12345678" and out["level"] == "INFO" and out["ts"].endswith("Z")
    assert out["route"] == "/api/v1/farmers/{farmer_id}" and out["status"] == 200
    text = json.dumps(out)
    for secret in ("hunter2", "abc.def.ghi", "zzz", "supersecret", '"p"', '"t"', '"123"', '"k"'):
        assert secret not in text, secret
    assert scrub({"email": "a@b.c"}) == {"email": "[REDACTED]"}
    assert "[REDACTED-JWT]" in scrub_text("eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U")


def test_request_log_and_metrics_use_route_templates(client: TestClient, db: Session, caplog: pytest.LogCaptureFixture) -> None:
    org = dev_org(db)
    pm = staff(db, client, org, "PROJECT_MANAGER")
    farmer = create_farmer(client, pm.headers, org)
    with caplog.at_level(logging.INFO, logger="app.http"):
        assert client.get(f"{API}/farmers/{farmer['id']}", headers=pm.headers).status_code == 200
    rec = [r for r in caplog.records if r.name == "app.http" and r.getMessage() == "request"][-1]
    assert rec.fields["route"] == f"{API}/farmers/{{farmer_id}}" and farmer["id"] not in json.dumps(rec.fields)  # type: ignore[attr-defined]
    assert rec.fields["status"] == 200 and rec.fields["user_id"] == str(pm.user.id)  # type: ignore[attr-defined]
    names = {(c["name"], c["labels"].get("route")) for c in metrics.snapshot()["counters"]}
    assert ("api_requests_total", f"{API}/farmers/{{farmer_id}}") in names


def test_metrics_endpoint_requires_token(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    assert client.get("/metrics").status_code == 404                                     # disabled without METRICS_TOKEN
    monkeypatch.setattr(get_settings(), "METRICS_TOKEN", "t" * 40)
    assert client.get("/metrics").status_code == 401
    assert client.get("/metrics", headers={"Authorization": "Bearer wrong"}).status_code == 401
    client.get(f"{API}/health")
    r = client.get("/metrics", headers={"Authorization": f"Bearer {'t' * 40}"})
    assert r.status_code == 200 and r.headers["content-type"].startswith("application/openmetrics-text")
    body = r.text
    for name in ("api_requests_total", "jobs_queued", "jobs_failed", "jobs_oldest_queued_age_seconds", "rate_limiter_degraded",
                 "documents_quarantined", "database_up"):
        assert name in body, name
    assert body.rstrip().endswith("# EOF")
    j = client.get("/metrics?format=json", headers={"Authorization": f"Bearer {'t' * 40}"}).json()
    assert set(j) == {"counters", "timings", "gauges"} and j["gauges"]["database_up"] == 1.0


# ---------------------------------------------------------------- D39 / D41 / D42 notifications (nothing is sent)
NOW = datetime(2026, 10, 3, 12, 0)


def _prefs(**over: Any) -> notify.ExternalPreferences:
    base: dict[str, Any] = {"channel": "EMAIL", "opted_in_at": NOW - timedelta(days=1), "opted_out_at": None, "language": "hi"}
    base.update(over)
    return notify.ExternalPreferences(**base)


@pytest.mark.parametrize("prefs,reason", [
    (None, "NO_PREFERENCES"),
    (_prefs(channel="SMS"), "UNSUPPORTED_CHANNEL"),
    (_prefs(opted_in_at=None), "NOT_OPTED_IN"),
    (_prefs(opted_out_at=NOW - timedelta(hours=1)), "OPTED_OUT"),
    (_prefs(opted_in_at=None, opted_out_at=NOW), "OPTED_OUT"),
    (_prefs(language=" "), "LANGUAGE_REQUIRED"),
    (_prefs(quiet_start=time(17, 0), quiet_end=time(23, 0), utc_offset_minutes=330), "QUIET_HOURS"),   # 17:30 IST
    (_prefs(quiet_start=time(22, 0), quiet_end=time(7, 0), utc_offset_minutes=0), "DELIVERY_DEFERRED"),  # outside quiet hours
    (_prefs(), "DELIVERY_DEFERRED"),
])
def test_delivery_gate(prefs: notify.ExternalPreferences | None, reason: str) -> None:
    d = notify.delivery_decision(prefs, NOW)
    assert not d.allowed and d.reason == reason


def test_quiet_hours_defer_to_their_end_and_opt_in_after_opt_out_counts() -> None:
    d = notify.delivery_decision(_prefs(quiet_start=time(17, 0), quiet_end=time(23, 0), utc_offset_minutes=330), NOW)
    assert d.retry_at == datetime(2026, 10, 3, 17, 30)                                    # 23:00 IST
    renewed = _prefs(opted_out_at=NOW - timedelta(days=5), opted_in_at=NOW - timedelta(days=1))
    assert notify.delivery_decision(renewed, NOW).reason == "DELIVERY_DEFERRED"            # explicit re-opt-in after an opt-out


def test_smtp_channel_never_sends() -> None:
    ch = notify.SmtpChannel()
    with pytest.raises(notify.ExternalDeliveryDisabled):
        ch.send("x@test.example", "s", "b", "en")
    assert notify.deliver_external(ch, _prefs(), NOW, "x@test.example", "s", "b").reason == "DELIVERY_DEFERRED"


def test_existing_auth_protections_unchanged(client: TestClient, db: Session) -> None:
    """Refresh rotation + reuse detection (replaying a rotated refresh token revokes the session)."""
    u = make_user(db)
    a = Actor(u, login(client, u))
    old = client.cookies.get(get_settings().REFRESH_COOKIE_NAME)
    assert client.post(f"{API}/auth/refresh").status_code == 200                           # rotation (new refresh token)
    client.cookies.clear()
    replay = client.post(f"{API}/auth/refresh", json={"refresh_token": old})
    assert replay.status_code == 401 and replay.json()["error_code"] == "REFRESH_REUSED"
    assert client.get(f"{API}/auth/me", headers=a.headers).status_code == 401              # session revoked by reuse detection
