"""Bootstrap admin and clearly-marked DEMO data (spec section 43).

Passwords always come from environment variables; nothing is hard-coded (rule 17).
"""
import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit.service import record
from app.core.context import RequestContext
from app.core.errors import AppError
from app.models import Organization, OrganizationUser, Role, User, UserRole
from app.models.base import Environment, utcnow
from app.security.passwords import hash_password, validate_password_policy
from app.seed.reference import PLATFORM_ORG_CODE

log = logging.getLogger("app.seed")


def _role(db: Session, code: str) -> Role:
    r = db.scalars(select(Role).where(Role.code == code)).first()
    if r is None:
        raise AppError(f"Role {code} missing; run seed-reference first.", error_code="SEED_ORDER")
    return r


def _grant(db: Session, user: User, role_code: str, org: Organization | None) -> None:
    role = _role(db, role_code)
    org_id = org.id if org else None
    org_clause = UserRole.organization_id == org_id if org_id else UserRole.organization_id.is_(None)
    exists = db.scalars(select(UserRole).where(UserRole.user_id == user.id, UserRole.role_id == role.id, org_clause)).first()
    if not exists:
        db.add(UserRole(user_id=user.id, role_id=role.id, organization_id=org_id))


def _member(db: Session, user: User, org: Organization, title: str | None = None) -> None:
    if not db.scalars(select(OrganizationUser).where(OrganizationUser.user_id == user.id,
                                                     OrganizationUser.organization_id == org.id)).first():
        db.add(OrganizationUser(user_id=user.id, organization_id=org.id, title=title, is_primary=True))


def bootstrap_admin(db: Session, email: str, password: str, full_name: str) -> tuple[User, bool]:
    """Create the first Platform Admin if no user with that email exists. Returns (user, created)."""
    validate_password_policy(password)
    email = email.strip().lower()
    user = db.scalars(select(User).where(User.email == email)).first()
    if user:
        return user, False
    platform = db.scalars(select(Organization).where(Organization.code == PLATFORM_ORG_CODE)).one()
    user = User(email=email, full_name=full_name, password_hash=hash_password(password), must_change_password=True,
                password_changed_at=utcnow())
    db.add(user)
    db.flush()
    _member(db, user, platform, "Platform Administrator")
    _grant(db, user, "PLATFORM_ADMIN", None)
    record(db, RequestContext.system(), "USER_CREATED", "user", user.id, None,
           {"email": email, "role": "PLATFORM_ADMIN", "source": "bootstrap"})
    db.commit()
    return user, True


DEMO_ORGS = [
    ("DEMO-DEV-A", "Project Developer A (DEMO)", "PROJECT_DEVELOPER"),
    ("DEMO-FPO-E", "Farmer Producer Group E (DEMO)", "FARMER_GROUP"),
    ("DEMO-LAB-B", "Soil Laboratory B (DEMO)", "LABORATORY"),
    ("DEMO-VVB-C", "Verification Body C (DEMO)", "VVB"),
    ("DEMO-BUYER-D", "Buyer D (DEMO)", "BUYER"),
]

# (email local part, full name, org code or None for platform-wide, role code)
DEMO_USERS = [
    ("admin", "Demo Platform Admin", None, "PLATFORM_ADMIN"),
    ("security", "Demo Security Admin", None, "SECURITY_ADMIN"),
    ("support", "Demo Support Agent", None, "SUPPORT"),
    ("methodology", "Demo Methodology Specialist", None, "METHODOLOGY_SPECIALIST"),
    ("platformgis", "Demo Platform GIS Specialist", None, "PLATFORM_GIS_SPECIALIST"),
    ("pm", "Demo Project Manager", "DEMO-DEV-A", "PROJECT_MANAGER"),
    ("supervisor", "Demo Field Supervisor", "DEMO-DEV-A", "FIELD_SUPERVISOR"),
    ("collector", "Demo Field Collector", "DEMO-DEV-A", "FIELD_AGENT"),
    ("gis", "Demo GIS Specialist", "DEMO-DEV-A", "GIS_SPECIALIST"),
    ("mrv", "Demo MRV Manager", "DEMO-DEV-A", "MRV_MANAGER"),
    ("analyst", "Demo Calculation Analyst", "DEMO-DEV-A", "CALCULATION_ANALYST"),
    ("qa", "Demo QA Officer", "DEMO-DEV-A", "QA_OFFICER"),
    ("registry", "Demo Registry Manager", "DEMO-DEV-A", "REGISTRY_MANAGER"),
    ("credits", "Demo Credit Manager", "DEMO-DEV-A", "CREDIT_MANAGER"),
    ("finance", "Demo Finance Manager", "DEMO-DEV-A", "FINANCE_MANAGER"),
    ("farmer", "Demo Farmer", "DEMO-FPO-E", "FARMER"),
    ("labtech", "Demo Lab Technician", "DEMO-LAB-B", "LAB_TECHNICIAN"),
    ("labmanager", "Demo Lab Manager", "DEMO-LAB-B", "LAB_MANAGER"),
    ("vvb", "Demo VVB Reviewer", "DEMO-VVB-C", "VVB_REVIEWER"),
    ("buyer", "Demo Buyer", "DEMO-BUYER-D", "BUYER"),
]
DEMO_DOMAIN = "demo.carbon.example"


def seed_demo(db: Session, password: str) -> dict[str, int]:
    validate_password_policy(password)
    stats = {"organizations": 0, "users": 0}
    orgs: dict[str, Organization] = {}
    for code, name, org_type in DEMO_ORGS:
        o = db.scalars(select(Organization).where(Organization.code == code)).first()
        if o is None:
            o = Organization(code=code, name=name, org_type=org_type, country="IN", environment=Environment.DEMO.value)
            db.add(o)
            stats["organizations"] += 1
        elif o.environment != Environment.DEMO.value:
            raise AppError(f"Organization {code} exists but is not DEMO; refusing to mix data.", error_code="DEMO_CONFLICT")
        orgs[code] = o
    db.flush()
    pw_hash = hash_password(password)
    for local, name, org_code, role in DEMO_USERS:
        email = f"{local}@{DEMO_DOMAIN}"
        u = db.scalars(select(User).where(User.email == email)).first()
        if u is None:
            u = User(email=email, full_name=name, password_hash=pw_hash, environment=Environment.DEMO.value,
                     password_changed_at=utcnow())
            db.add(u)
            db.flush()
            stats["users"] += 1
        elif u.environment != Environment.DEMO.value:
            raise AppError(f"User {email} exists but is not DEMO; refusing to mix data.", error_code="DEMO_CONFLICT")
        org = orgs[org_code] if org_code else None
        if org:
            _member(db, u, org)
        _grant(db, u, role, org)
    if any(stats.values()):
        record(db, RequestContext.system(), "DEMO_DATA_SEEDED", "demo", None, None, stats)
    db.commit()
    return stats
