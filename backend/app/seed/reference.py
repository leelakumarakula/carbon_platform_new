"""Sync reference data (permissions, system roles, platform organization) from code to the database.

Idempotent. Run after every migration:  python manage.py seed-reference
"""
import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit.service import record
from app.core.context import RequestContext
from app.models import Organization, OrganizationType, Permission, Role, RolePermission
from app.security.permissions import ALL_PERMISSION_CODES, PERMISSIONS, SYSTEM_ROLES

log = logging.getLogger("app.seed")
PLATFORM_ORG_CODE = "PLATFORM"


def sync_reference(db: Session) -> dict[str, int]:
    stats = {"permissions_added": 0, "roles_added": 0, "role_permission_changes": 0}
    perms = {p.code: p for p in db.scalars(select(Permission)).all()}
    for d in PERMISSIONS:
        p = perms.get(d.code)
        if p is None:
            p = Permission(code=d.code, module=d.module, name=d.name, description=d.description)
            db.add(p)
            perms[d.code] = p
            stats["permissions_added"] += 1
        else:
            p.module, p.name, p.description = d.module, d.name, d.description
    stale = sorted(set(perms) - ALL_PERMISSION_CODES)
    if stale:
        log.warning("Permissions in DB but not in code (left untouched, review manually): %s", stale)
    db.flush()

    roles = {r.code: r for r in db.scalars(select(Role)).all()}
    for rd in SYSTEM_ROLES:
        r = roles.get(rd.code)
        if r is None:
            r = Role(code=rd.code, name=rd.name, description=rd.description, scope=rd.scope, is_system=True)
            db.add(r)
            db.flush()
            stats["roles_added"] += 1
        else:
            r.name, r.description, r.scope, r.is_system = rd.name, rd.description, rd.scope, True
        current = {rp.permission.code: rp for rp in r.permissions}
        for code in rd.permissions - set(current):
            r.permissions.append(RolePermission(permission=perms[code]))
            stats["role_permission_changes"] += 1
        for code in set(current) - rd.permissions:
            r.permissions.remove(current[code])
            stats["role_permission_changes"] += 1

    from app.services import consent_service
    stats["consent_definitions_added"] = int(consent_service.ensure_baseline(db))

    if db.scalars(select(Organization).where(Organization.code == PLATFORM_ORG_CODE)).first() is None:
        db.add(Organization(code=PLATFORM_ORG_CODE, name="Carbon Platform Operator", org_type=OrganizationType.PLATFORM.value))
    db.flush()
    if any(stats.values()):
        record(db, RequestContext.system(), "REFERENCE_DATA_SYNCED", "reference_data", None, None, stats)
    db.commit()
    return stats
