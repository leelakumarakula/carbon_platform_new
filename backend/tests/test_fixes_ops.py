"""Deployment / operations fixes (2026-10-14).

E1 secrets and local files kept out of the Docker build context (.dockerignore); E2 SQL parameters never logged, DB_ECHO refused in
production (D44); E3 production refuses an unvalidated SQL Server TLS certificate; E4 compose trusts X-Forwarded-For only from its
container range (D21) and keeps SQL Server local; E5 readiness fails only when the schema is BEHIND the code (rolling deploys);
E6 container health checks probe liveness, and the worker / beat containers do not run the API check.
"""
import ipaddress
import re
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
import yaml
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from app.api.v1 import health
from app.core.config import Settings, get_settings
from app.core.database import get_engine
from tests.test_runtime_hardening import _prod

API = "/api/v1"
REPO = Path(__file__).resolve().parents[2]
DB_URL = "mssql+pyodbc://carbon_app:pw@sql.internal:1433/carbon?driver=ODBC+Driver+18+for+SQL+Server"


# ---------------------------------------------------------------- E2 personal data never reaches logs through SQL parameters
def test_engine_hides_sql_parameters_in_errors() -> None:
    engine = get_engine()
    assert engine.hide_parameters is True
    with engine.connect() as conn, pytest.raises(DBAPIError) as e:
        conn.execute(text("SELECT 1 FROM dbo.no_such_table_e2 WHERE phone = :phone"), {"phone": "PII-9876543210"})
    assert "PII-9876543210" not in str(e.value) and "hidden" in str(e.value)


@pytest.mark.usefixtures("no_secret_env")
def test_db_echo_is_refused_in_production(tmp_path: Any) -> None:
    with pytest.raises(ValidationError, match="DB_ECHO"):
        Settings(**_prod(tmp_path, DB_ECHO=True))
    base = get_settings().model_dump()
    assert Settings(**{**base, "DB_ECHO": True}).DB_ECHO is True                      # development / test unaffected


# ---------------------------------------------------------------- E3 SQL Server certificate validated in production
@pytest.mark.parametrize("over", [
    {"SQL_SERVER_TRUST_SERVER_CERTIFICATE": True},
    {"DATABASE_URL": DB_URL},                                                         # no option in the URL = trusted
    {"DATABASE_URL": f"{DB_URL}&TrustServerCertificate=yes"},
])
@pytest.mark.usefixtures("no_secret_env")
def test_unvalidated_sql_server_certificate_is_refused_in_production(tmp_path: Any, over: dict[str, Any]) -> None:
    with pytest.raises(ValidationError, match="validated SQL Server TLS certificate"):
        Settings(**_prod(tmp_path, **over))


@pytest.mark.usefixtures("no_secret_env")
def test_production_connects_with_tls_and_certificate_validation(tmp_path: Any) -> None:
    s = Settings(**_prod(tmp_path, DATABASE_URL=f"{DB_URL}&TrustServerCertificate=no"))
    assert s.SQL_SERVER_TRUST_SERVER_CERTIFICATE is False
    query = s.database_url().query
    assert query.get("Encrypt") == "yes" and "TrustServerCertificate" not in query
    assert Settings(**_prod(tmp_path)).database_url().query.get("Encrypt") == "yes"


def test_development_certificate_defaults_are_unchanged() -> None:
    base = get_settings().model_dump()
    s = Settings(**{**base, "DATABASE_URL": DB_URL})
    assert s.SQL_SERVER_TRUST_SERVER_CERTIFICATE is True
    query = s.database_url().query
    assert query.get("TrustServerCertificate") == "yes" and "Encrypt" not in query
    assert Settings.model_fields["SQL_SERVER_TRUST_SERVER_CERTIFICATE"].default is True


# ---------------------------------------------------------------- E5 readiness: only a schema BEHIND the code is not ready
class _VersionDb:
    def __init__(self, version: str | None) -> None:
        self.version = version

    def execute(self, _stmt: Any) -> Any:
        return SimpleNamespace(scalar=lambda: self.version)


def test_database_readiness_by_migration_position() -> None:
    head, known = health._migration_head(), health._known_revisions()
    assert head in known and len(known) > 1
    older = next(r for r in known if r != head)
    assert health._database(_VersionDb(head))[0] == "ok"
    state, detail = health._database(_VersionDb(older))
    assert state == "failed" and "run migrate" in detail                              # behind: an ancestor of the code head
    assert health._database(_VersionDb(None))[0] == "failed"                          # no migration recorded
    state, detail = health._database(_VersionDb("20991231_9999_future"))
    assert state == "ok" and "newer" in detail                                        # migrated ahead of this code: still ready


def test_ready_during_a_rolling_deploy(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    head, known = health._migration_head(), health._known_revisions()
    previous = health._scripts().get_revision(head).down_revision
    # the previous release: its code ends one migration earlier, so the migrated database is newer than it knows
    monkeypatch.setattr(health, "_migration_head", lambda: previous)
    monkeypatch.setattr(health, "_known_revisions", lambda: known - {head})
    r = client.get(f"{API}/health/ready")
    assert r.status_code == 200 and r.json()["checks"]["database"] == "ok"
    # the next release before `migrate`: the database is behind the code
    monkeypatch.setattr(health, "_migration_head", lambda: "next")
    monkeypatch.setattr(health, "_known_revisions", lambda: known | {"next"})
    r = client.get(f"{API}/health/ready")
    assert r.status_code == 503 and r.json()["checks"]["database"] == "failed"


# ---------------------------------------------------------------- E1 Docker build context (emulates the .dockerignore matcher)
def _dockerignore_rules() -> list[tuple[bool, re.Pattern[str]]]:
    rules = []
    for raw in (REPO / ".dockerignore").read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        keep = line.startswith("!")
        pattern = line.lstrip("!").strip().strip("/")
        rx = re.escape(pattern).replace(r"\*\*/", "(.*/)?").replace(r"\*\*", ".*").replace(r"\*", "[^/]*").replace(r"\?", "[^/]")
        rx = re.sub(r"\\\[(.*?)\\\]", r"[\1]", rx)                                    # character classes, e.g. *.py[cod]
        rules.append((keep, re.compile(f"^{rx}$")))
    return rules


def _in_build_context(path: str) -> bool:
    parts = path.split("/")
    candidates = ["/".join(parts[:i]) for i in range(1, len(parts) + 1)]          # a matched parent directory excludes its content
    excluded = False
    for keep, rx in _dockerignore_rules():
        if any(rx.match(c) for c in candidates):
            excluded = not keep
    return not excluded


@pytest.mark.parametrize("path", ["backend/.env", ".env", "backend/.env.local", "backend/prod.env", "backend/.venv/Lib/site.py",
                                  "backend/app/__pycache__/main.cpython-312.pyc", "backend/.mypy_cache/x.json", "backend/.ruff_cache/x",
                                  "backend/.pytest_cache/v", "storage/local-dev/LIVE/doc.pdf", "backend/storage/x.pdf", ".git/config",
                                  "backend/tests/conftest.py", "docs/deployment.md"])
def test_secrets_and_local_files_stay_out_of_the_image(path: str) -> None:
    assert not _in_build_context(path)


@pytest.mark.parametrize("path", ["backend/app/main.py", "backend/app/ops/schema_manifest.json", "backend/alembic/env.py",
                                  "backend/alembic/script.py.mako", "backend/alembic/versions/20261005_0023_x.py", "backend/alembic.ini",
                                  "backend/manage.py", "backend/requirements/base.txt", ".env.example"])
def test_runtime_files_are_in_the_build_context(path: str) -> None:
    assert _in_build_context(path)


def test_dockerfile_copies_only_what_the_context_keeps() -> None:
    dockerfile = (REPO / "docker" / "backend.Dockerfile").read_text(encoding="utf-8")
    sources = re.findall(r"^COPY\s+(\S+)\s", dockerfile, flags=re.MULTILINE)
    assert sources
    for src in sources:
        assert (REPO / src).exists() and _in_build_context(src.rstrip("/"))
    for f in ("app/main.py", "alembic.ini", "manage.py", "requirements/base.txt"):
        assert (REPO / "backend" / f).is_file() and _in_build_context(f"backend/{f}")


# ---------------------------------------------------------------- E4 / E6 compose and health checks
def test_container_healthcheck_probes_liveness() -> None:
    dockerfile = (REPO / "docker" / "backend.Dockerfile").read_text(encoding="utf-8")
    probe = next(line for line in dockerfile.splitlines() if line.startswith("HEALTHCHECK"))
    assert "/api/v1/health/live" in probe
    compose = yaml.safe_load((REPO / "docker-compose.yml").read_text(encoding="utf-8"))
    for name in ("worker", "beat"):                                                  # same image, no HTTP API
        assert compose["services"][name]["healthcheck"] == {"disable": True}
    assert "healthcheck" not in compose["services"]["backend"]


def test_compose_trusts_only_its_container_range_and_keeps_sql_server_local() -> None:
    compose = yaml.safe_load((REPO / "docker-compose.yml").read_text(encoding="utf-8"))
    ipam = compose["networks"]["default"]["ipam"]["config"][0]
    subnet, containers = ipaddress.ip_network(ipam["subnet"]), ipaddress.ip_network(ipam["ip_range"])
    trusted = [ipaddress.ip_network(c.strip()) for c in compose["services"]["backend"]["environment"]["TRUSTED_PROXIES"].split(",")]
    assert trusted and all(t.subnet_of(containers) for t in trusted) and containers.subnet_of(subnet)
    assert not any(ipaddress.ip_address(ipam["gateway"]) in t for t in trusted)     # published-port traffic arrives via the gateway
    base = get_settings().model_dump()
    assert Settings(**{**base, "TRUSTED_PROXIES": compose["services"]["backend"]["environment"]["TRUSTED_PROXIES"]}).TRUSTED_PROXIES
    assert compose["services"]["sqlserver"]["ports"] == ["127.0.0.1:1433:1433"]
    for name in ("redis", "minio"):
        assert all(str(p).startswith("127.0.0.1:") for p in compose["services"][name]["ports"])
