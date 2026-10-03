"""Test fixtures.

Tests run against a real SQL Server database (`<SQL_SERVER_DATABASE>_test`) so constraints, triggers and
(later) geography behave exactly as in production. Each test runs inside a transaction that is rolled back.
"""
import os
import shutil
import tempfile
import uuid
from collections.abc import Iterator
from dataclasses import dataclass, field

import pytest

os.environ["APP_ENV"] = "test"
os.environ["SQL_SERVER_DATABASE"] = os.environ.get("TEST_SQL_SERVER_DATABASE", "carbon_platform_test")
os.environ["DATABASE_URL"] = ""
os.environ["LOGIN_RATE_LIMIT_PER_MINUTE"] = "1000"
_STORAGE = tempfile.mkdtemp(prefix="cp-test-storage-")
os.environ["LOCAL_STORAGE_ROOT"] = _STORAGE

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db, get_engine
from app.core.rate_limit import limiter
from app.main import create_app
from app.models import Organization, OrganizationUser, Role, User, UserRole
from app.models.base import Environment
from app.security.passwords import hash_password
from tests.av_fixture import av  # noqa: F401 - TEST-only antivirus double fixture (Phase 12B D17)

PASSWORD = "Correct-Horse-42"
_HASH = hash_password(PASSWORD)


def pytest_sessionstart(session: pytest.Session) -> None:
    """Phase 12B-III disk safety: the suite creates database snapshots and files; refuse to start below 1 GB free (a full disk once
    truncated a source file during a write)."""
    free = shutil.disk_usage(tempfile.gettempdir()).free // (1024 * 1024)
    if free < 1024:
        pytest.exit(f"Refusing to run the test suite: only {free} MB free on the temp volume (need >= 1024 MB).", returncode=3)


@pytest.fixture(scope="session", autouse=True)
def _database() -> Iterator[None]:
    from alembic import command
    from alembic.config import Config

    import manage

    assert get_settings().SQL_SERVER_DATABASE.endswith("_test"), "refusing to run tests against a non-test database"
    manage.create_db()
    cfg = Config(os.path.join(os.path.dirname(__file__), "..", "alembic.ini"))
    cfg.attributes["configure_logger"] = False
    command.upgrade(cfg, "head")
    from app.core.database import get_session_factory
    from app.seed.reference import sync_reference
    with get_session_factory()() as db:
        sync_reference(db)
    yield
    get_engine().dispose()
    shutil.rmtree(_STORAGE, ignore_errors=True)


@pytest.fixture()
def db() -> Iterator[Session]:
    conn = get_engine().connect()
    trans = conn.begin()
    session = Session(bind=conn, join_transaction_mode="create_savepoint", expire_on_commit=False, autoflush=False)
    try:
        yield session
    finally:
        session.close()
        trans.rollback()
        conn.close()


@pytest.fixture()
def access_log() -> list[dict]:
    return []


@pytest.fixture()
def client(db: Session, access_log: list[dict]) -> Iterator[TestClient]:
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db
    app.state.access_log_writer = access_log.append
    limiter.reset()
    with TestClient(app, base_url="http://testserver") as c:
        yield c
    limiter.reset()


# ---------------------------------------------------------------- factories
def role(db: Session, code: str) -> Role:
    from sqlalchemy import select
    return db.scalars(select(Role).where(Role.code == code)).one()


def make_org(db: Session, code: str | None = None, org_type: str = "PROJECT_DEVELOPER",
             environment: str = Environment.LIVE.value) -> Organization:
    o = Organization(code=code or f"T-{uuid.uuid4().hex[:8].upper()}", name=f"Org {code or 'test'}",
                     org_type=org_type, environment=environment)
    db.add(o)
    db.flush()
    return o


def make_user(db: Session, *, roles: list[tuple[str, Organization | None]] = (), orgs: list[Organization] = (),
              email: str | None = None, must_change: bool = False, status: str = "ACTIVE",
              environment: str = Environment.LIVE.value) -> User:
    u = User(email=email or f"u{uuid.uuid4().hex[:10]}@test.example", full_name="Test User", password_hash=_HASH,
             must_change_password=must_change, status=status, environment=environment)
    db.add(u)
    db.flush()
    member_of = {o.id: o for o in orgs}
    for _, o in roles:
        if o is not None:
            member_of[o.id] = o
    for o in member_of.values():
        db.add(OrganizationUser(organization_id=o.id, user_id=u.id))
    for code, o in roles:
        db.add(UserRole(user_id=u.id, role_id=role(db, code).id, organization_id=o.id if o else None))
    db.flush()
    db.refresh(u)
    return u


def login(client: TestClient, user: User, password: str = PASSWORD) -> dict[str, str]:
    r = client.post("/api/v1/auth/login", json={"email": user.email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@dataclass
class Actor:
    user: User
    headers: dict[str, str] = field(default_factory=dict)


@pytest.fixture()
def admin(db: Session, client: TestClient) -> Actor:
    u = make_user(db, roles=[("PLATFORM_ADMIN", None)])
    return Actor(u, login(client, u))
