"""Roles: system roles are reference data (read-only via API); custom roles are admin-managed."""
import uuid

from sqlalchemy.orm import Session

from app.audit.service import AuditAction, record
from app.core.context import RequestContext
from app.core.errors import Conflict, NotFound, PermissionDenied, ValidationFailed
from app.models import Role, RolePermission
from app.repositories import identity as repo
from app.schemas.identity import RoleCreate, RoleUpdate
from app.security.permissions import PRIVILEGED_CODES, SYSTEM_ROLE_CODES, P
from app.security.principal import Principal


def get_role(db: Session, role_id: uuid.UUID) -> Role:
    role = repo.get_role(db, role_id)
    if role is None:
        raise NotFound("Role not found.", error_code="ROLE_NOT_FOUND")
    return role


def _check_permissions(db: Session, principal: Principal, codes: list[str]) -> dict[str, object]:
    found = repo.permissions_by_code(db, codes)
    unknown = sorted(set(codes) - set(found))
    if unknown:
        raise ValidationFailed("Unknown permissions.", error_code="UNKNOWN_PERMISSION", details={"unknown": unknown})
    not_held = sorted(c for c in set(codes) & PRIVILEGED_CODES if not principal.has_platform(c))
    if not_held:
        raise PermissionDenied("You cannot add permissions you do not hold platform-wide.",
                               error_code="ROLE_ESCALATION_BLOCKED", details={"missing_permissions": not_held})
    return found  # type: ignore[return-value]


def _require_manage(principal: Principal) -> None:
    if not principal.has_platform(P.ROLES_MANAGE):
        raise PermissionDenied(details={"required_permission": P.ROLES_MANAGE})


def create_role(db: Session, ctx: RequestContext, principal: Principal, data: RoleCreate) -> Role:
    _require_manage(principal)
    if data.code in SYSTEM_ROLE_CODES or repo.get_role_by_code(db, data.code):
        raise Conflict("A role with this code already exists.", error_code="ROLE_EXISTS")
    perms = _check_permissions(db, principal, data.permissions)
    role = Role(code=data.code, name=data.name, description=data.description, scope=data.scope, is_system=False)
    role.permissions = [RolePermission(permission=p) for p in perms.values()]  # type: ignore[misc]
    db.add(role)
    db.flush()
    record(db, ctx, AuditAction.ROLE_CREATED, "role", role.id, None,
           {"code": role.code, "scope": role.scope, "permissions": sorted(perms)})
    db.commit()
    return get_role(db, role.id)


def update_role(db: Session, ctx: RequestContext, principal: Principal, role_id: uuid.UUID, data: RoleUpdate) -> Role:
    _require_manage(principal)
    role = get_role(db, role_id)
    if role.is_system:
        raise Conflict("System roles are reference data and cannot be edited here.", error_code="SYSTEM_ROLE_READONLY")
    changes = data.model_dump(exclude_unset=True)
    old = {k: getattr(role, k) for k in changes}
    for k, v in changes.items():
        setattr(role, k, v)
    record(db, ctx, AuditAction.ROLE_UPDATED, "role", role.id, old, changes)
    db.commit()
    return get_role(db, role.id)


def set_permissions(db: Session, ctx: RequestContext, principal: Principal, role_id: uuid.UUID,
                    codes: list[str]) -> Role:
    _require_manage(principal)
    role = get_role(db, role_id)
    if role.is_system:
        raise Conflict("System role permissions are defined as reference data (app/security/permissions.py).",
                       error_code="SYSTEM_ROLE_READONLY")
    old = sorted(rp.permission.code for rp in role.permissions)
    perms = _check_permissions(db, principal, codes)
    role.permissions = [RolePermission(permission=p) for p in perms.values()]  # type: ignore[misc]
    record(db, ctx, AuditAction.ROLE_PERMISSIONS_CHANGED, "role", role.id, {"permissions": old},
           {"permissions": sorted(perms)})
    db.commit()
    return get_role(db, role.id)
