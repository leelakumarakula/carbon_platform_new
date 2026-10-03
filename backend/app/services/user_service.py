"""User administration with organisation scoping and privilege-escalation guards."""
import uuid

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.audit.service import AuditAction, record, record_transition, snapshot
from app.core.context import RequestContext
from app.core.errors import Conflict, NotFound, PermissionDenied, ValidationFailed
from app.models import OrganizationStatus, OrganizationUser, Role, RoleScope, User, UserRole, UserStatus
from app.models.base import Environment, utcnow
from app.repositories import identity as repo
from app.schemas.common import PageParams
from app.schemas.identity import RoleGrantIn, UserCreate, UserUpdate
from app.security.passwords import hash_password, validate_password_policy
from app.security.permissions import PRIVILEGED_CODES, P
from app.security.principal import Principal
from app.services.auth_service import revoke_user_sessions
from app.services.workflows import USER_MACHINE

PROFILE_FIELDS = ("email", "full_name", "phone", "status", "environment")


def _visible(principal: Principal, user: User, code: str) -> bool:
    scope = principal.scope_for(code)
    return scope is None or any(m.organization_id in scope for m in user.memberships)


def get_visible_user(db: Session, principal: Principal, user_id: uuid.UUID, code: str = P.USERS_READ) -> User:
    user = repo.get_user(db, user_id)
    if user is None or user.status == "SYSTEM" or not _visible(principal, user, code):   # Phase 12A: the job actor is not a user
        # Same response for "missing" and "outside your organisations" to avoid leaking existence.
        raise NotFound("User not found.", error_code="USER_NOT_FOUND")
    return user


def _require_manage(principal: Principal, user: User, code: str = P.USERS_MANAGE) -> None:
    scope = principal.scope_for(code)
    if scope is not None and not any(m.organization_id in scope for m in user.memberships):
        raise PermissionDenied(details={"required_permission": code})


def list_users(db: Session, principal: Principal, params: PageParams, **filters: object) -> tuple[list[User], int]:
    scope = principal.scope_for(P.USERS_READ)
    org_id = filters.get("organization_id")
    if scope is not None and org_id is not None and org_id not in scope:
        raise PermissionDenied(details={"organization_id": str(org_id)})
    return repo.list_users(db, params, scope=scope, **filters)  # type: ignore[arg-type]


def create_user(db: Session, ctx: RequestContext, principal: Principal, data: UserCreate) -> User:
    if data.organization_id is None:
        if not principal.has_platform(P.USERS_MANAGE):
            raise ValidationFailed("An organization is required.", error_code="ORGANIZATION_REQUIRED")
    else:
        principal.require_in_org(P.USERS_MANAGE, data.organization_id)
        org = repo.get_organization(db, data.organization_id)
        if org is None:
            raise NotFound("Organization not found.", error_code="ORGANIZATION_NOT_FOUND")
        if org.status != OrganizationStatus.ACTIVE.value:
            raise Conflict("Users can only be added to active organizations.", error_code="ORGANIZATION_INACTIVE")
    if repo.get_user_by_email(db, data.email):
        raise Conflict("A user with this email already exists.", error_code="EMAIL_EXISTS")
    validate_password_policy(data.temporary_password)

    environment = Environment.LIVE.value
    if data.organization_id:
        environment = repo.get_organization(db, data.organization_id).environment  # type: ignore[union-attr]
    user = User(email=data.email, full_name=data.full_name, phone=data.phone,
                password_hash=hash_password(data.temporary_password), status=UserStatus.ACTIVE.value,
                must_change_password=True, environment=environment)
    db.add(user)
    try:
        db.flush()
    except IntegrityError as e:
        db.rollback()
        raise Conflict("A user with this email already exists.", error_code="EMAIL_EXISTS") from e
    if data.organization_id:
        user.memberships.append(OrganizationUser(organization_id=data.organization_id, title=data.title, is_primary=True))
        db.flush()
    record(db, ctx, AuditAction.USER_CREATED, "user", user.id, None,
           {**snapshot(user, PROFILE_FIELDS), "organization_id": data.organization_id}, organization_id=data.organization_id)
    for grant in data.roles:
        _assign(db, ctx, principal, user, grant)
    db.commit()
    return repo.get_user(db, user.id)  # type: ignore[return-value]


def update_user(db: Session, ctx: RequestContext, principal: Principal, user_id: uuid.UUID, data: UserUpdate) -> User:
    user = get_visible_user(db, principal, user_id)
    _require_manage(principal, user)
    changes = data.model_dump(exclude_unset=True)
    old = {k: getattr(user, k) for k in changes}
    for k, v in changes.items():
        setattr(user, k, v)
    if old != changes:
        record(db, ctx, AuditAction.USER_UPDATED, "user", user.id, old, changes)
    db.commit()
    return repo.get_user(db, user.id)  # type: ignore[return-value]


def change_status(db: Session, ctx: RequestContext, principal: Principal, user_id: uuid.UUID,
                  status: str, reason: str) -> User:
    user = get_visible_user(db, principal, user_id)
    _require_manage(principal, user)
    if user.id == principal.user_id:
        raise Conflict("You cannot change the status of your own account.", error_code="SELF_STATUS_CHANGE")
    if status != UserStatus.ACTIVE.value and _is_last_platform_admin(db, user):
        raise Conflict("This is the last active Platform Admin and cannot be suspended or deactivated.",
                       error_code="LAST_PLATFORM_ADMIN")
    record_transition(db, ctx, USER_MACHINE, user.id, user.status, status, AuditAction.USER_STATUS_CHANGED, reason)
    user.status = status
    if status != UserStatus.ACTIVE.value:
        revoke_user_sessions(db, user.id, f"USER_{status}")
    db.commit()
    return repo.get_user(db, user.id)  # type: ignore[return-value]


def reset_password(db: Session, ctx: RequestContext, principal: Principal, user_id: uuid.UUID,
                   temporary_password: str, reason: str) -> User:
    user = get_visible_user(db, principal, user_id)
    _require_manage(principal, user)
    if user.id == principal.user_id:
        raise Conflict("Use change-password for your own account.", error_code="SELF_PASSWORD_RESET")
    validate_password_policy(temporary_password)
    user.password_hash = hash_password(temporary_password)
    user.must_change_password = True
    user.password_changed_at = utcnow()
    revoked = revoke_user_sessions(db, user.id, "PASSWORD_RESET")
    record(db, ctx, AuditAction.PASSWORD_RESET, "user", user.id, new={"sessions_revoked": revoked}, reason=reason)
    db.commit()
    return repo.get_user(db, user.id)  # type: ignore[return-value]


def unlock(db: Session, ctx: RequestContext, principal: Principal, user_id: uuid.UUID, reason: str) -> User:
    if not principal.has_platform(P.SECURITY_MANAGE):
        raise PermissionDenied(details={"required_permission": P.SECURITY_MANAGE})
    user = get_visible_user(db, principal, user_id, P.USERS_READ)
    old = {"locked_until": user.locked_until, "failed_login_count": user.failed_login_count}
    user.locked_until = None
    user.failed_login_count = 0
    record(db, ctx, AuditAction.USER_UNLOCKED, "user", user.id, old, {"locked_until": None}, reason)
    db.commit()
    return repo.get_user(db, user.id)  # type: ignore[return-value]


# ----- role grants -----
def _assign(db: Session, ctx: RequestContext, principal: Principal, user: User, grant: RoleGrantIn) -> UserRole:
    role = repo.get_role_by_code(db, grant.role_code)
    if role is None:
        raise NotFound(f"Role {grant.role_code} not found.", error_code="ROLE_NOT_FOUND")
    org_id = grant.organization_id
    if role.scope == RoleScope.PLATFORM.value and org_id is not None:
        raise ValidationFailed(f"{role.code} is a platform-wide role and cannot be scoped to an organization.",
                               error_code="ROLE_SCOPE_MISMATCH")
    if role.scope == RoleScope.ORGANIZATION.value:
        if org_id is None:
            raise ValidationFailed(f"{role.code} must be granted within an organization.", error_code="ROLE_SCOPE_MISMATCH")
        if not any(m.organization_id == org_id for m in user.memberships):
            raise Conflict("The user must be a member of the organization before receiving a role in it.",
                           error_code="USER_NOT_MEMBER")
    if user.id == principal.user_id:
        raise PermissionDenied("You cannot change your own roles.", error_code="SELF_ROLE_CHANGE")
    principal.require_in_org(P.USERS_ASSIGN_ROLES, org_id)
    _guard_escalation(principal, role, org_id)
    if any(r.role_id == role.id and r.organization_id == org_id for r in user.roles):
        raise Conflict("The user already holds this role.", error_code="ROLE_ALREADY_ASSIGNED")
    ur = UserRole(user_id=user.id, role_id=role.id, organization_id=org_id, assigned_by=principal.user_id, role=role)
    user.roles.append(ur)
    try:
        with db.begin_nested():
            db.flush()
    except IntegrityError as e:  # concurrent duplicate grant
        raise Conflict("The user already holds this role.", error_code="ROLE_ALREADY_ASSIGNED") from e
    record(db, ctx, AuditAction.ROLE_ASSIGNED, "user", user.id, None,
           {"role": role.code, "organization_id": org_id, "user_role_id": ur.id}, organization_id=org_id)
    return ur


def _guard_escalation(principal: Principal, role: Role, org_id: uuid.UUID | None) -> None:
    """Nobody may grant privileged (admin/audit/security) permissions they do not themselves hold in that scope."""
    perms = {rp.permission.code for rp in role.permissions} & PRIVILEGED_CODES
    missing = sorted(p for p in perms if not principal.can_in_org(p, org_id))
    if missing:
        raise PermissionDenied("You cannot grant a role with permissions you do not hold.",
                               error_code="ROLE_ESCALATION_BLOCKED", details={"missing_permissions": missing})


def assign_role(db: Session, ctx: RequestContext, principal: Principal, user_id: uuid.UUID, grant: RoleGrantIn) -> User:
    user = get_visible_user(db, principal, user_id)
    if user.status == UserStatus.DEACTIVATED.value:
        raise Conflict("Roles cannot be granted to a deactivated user.", error_code="USER_DEACTIVATED")
    _assign(db, ctx, principal, user, grant)
    db.commit()
    return repo.get_user(db, user.id)  # type: ignore[return-value]


def revoke_role(db: Session, ctx: RequestContext, principal: Principal, user_id: uuid.UUID,
                user_role_id: uuid.UUID, reason: str | None = None) -> User:
    user = get_visible_user(db, principal, user_id)
    ur = next((r for r in user.roles if r.id == user_role_id), None)
    if ur is None:
        raise NotFound("Role assignment not found.", error_code="ROLE_ASSIGNMENT_NOT_FOUND")
    if user.id == principal.user_id:
        raise PermissionDenied("You cannot change your own roles.", error_code="SELF_ROLE_CHANGE")
    principal.require_in_org(P.USERS_ASSIGN_ROLES, ur.organization_id)
    _guard_escalation(principal, ur.role, ur.organization_id)
    if ur.role.code == "PLATFORM_ADMIN" and ur.organization_id is None and _is_last_platform_admin(db, user):
        raise Conflict("The last active Platform Admin grant cannot be removed.", error_code="LAST_PLATFORM_ADMIN")
    record(db, ctx, AuditAction.ROLE_REVOKED, "user", user.id,
           {"role": ur.role.code, "organization_id": ur.organization_id, "user_role_id": ur.id}, None, reason,
           organization_id=ur.organization_id)
    user.roles.remove(ur)
    db.commit()
    return repo.get_user(db, user.id)  # type: ignore[return-value]


def _is_last_platform_admin(db: Session, user: User) -> bool:
    holds = any(r.role.code == "PLATFORM_ADMIN" and r.organization_id is None for r in user.roles)
    return holds and user.status == UserStatus.ACTIVE.value and repo.count_platform_admin_grants(db) <= 1
