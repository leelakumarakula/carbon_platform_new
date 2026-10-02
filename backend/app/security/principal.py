"""The authenticated principal and organisation-scoped permission resolution (spec section 31).

A permission can be held platform-wide (role granted with organization_id NULL) or only
inside specific organisations. Services ask `principal.scope_for(code)`:
  None              -> may act on every organisation
  frozenset({...})  -> may act only on records belonging to these organisations
"""
import uuid
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import PermissionDenied
from app.models import OrganizationUser, Permission, Role, RolePermission, User, UserRole


@dataclass(frozen=True)
class Grant:
    user_role_id: uuid.UUID
    role_code: str
    role_scope: str
    organization_id: uuid.UUID | None
    permissions: frozenset[str]


@dataclass(frozen=True)
class Principal:
    user: User
    session_id: uuid.UUID | None
    grants: tuple[Grant, ...]
    member_organization_ids: frozenset[uuid.UUID] = field(default_factory=frozenset)

    @property
    def user_id(self) -> uuid.UUID:
        return self.user.id

    @property
    def permissions(self) -> frozenset[str]:
        return frozenset(p for g in self.grants for p in g.permissions)

    @property
    def role_codes(self) -> frozenset[str]:
        return frozenset(g.role_code for g in self.grants)

    def has(self, code: str) -> bool:
        return code in self.permissions

    def has_platform(self, code: str) -> bool:
        return any(g.organization_id is None and code in g.permissions for g in self.grants)

    def scope_for(self, code: str) -> frozenset[uuid.UUID] | None:
        if self.has_platform(code):
            return None
        orgs = frozenset(g.organization_id for g in self.grants if code in g.permissions and g.organization_id)
        if not orgs:
            raise PermissionDenied(details={"required_permission": code})
        return orgs

    def can_in_org(self, code: str, organization_id: uuid.UUID | None) -> bool:
        if self.has_platform(code):
            return True
        return organization_id is not None and any(
            g.organization_id == organization_id and code in g.permissions for g in self.grants)

    def require_in_org(self, code: str, organization_id: uuid.UUID | None) -> None:
        if not self.can_in_org(code, organization_id):
            raise PermissionDenied(details={"required_permission": code,
                                            "organization_id": str(organization_id) if organization_id else None})


def load_grants(db: Session, user_id: uuid.UUID) -> tuple[Grant, ...]:
    rows = db.execute(
        select(UserRole.id, Role.code, Role.scope, UserRole.organization_id, Permission.code)
        .join(Role, Role.id == UserRole.role_id)
        .outerjoin(RolePermission, RolePermission.role_id == Role.id)
        .outerjoin(Permission, Permission.id == RolePermission.permission_id)
        .where(UserRole.user_id == user_id)
    ).all()
    grouped: dict[uuid.UUID, tuple[str, str, uuid.UUID | None, set[str]]] = {}
    for ur_id, role_code, scope, org_id, perm in rows:
        entry = grouped.setdefault(ur_id, (role_code, scope, org_id, set()))
        if perm:
            entry[3].add(perm)
    return tuple(Grant(k, v[0], v[1], v[2], frozenset(v[3])) for k, v in grouped.items())


def load_principal(db: Session, user: User, session_id: uuid.UUID | None) -> Principal:
    orgs = db.scalars(select(OrganizationUser.organization_id).where(OrganizationUser.user_id == user.id)).all()
    return Principal(user=user, session_id=session_id, grants=load_grants(db, user.id),
                     member_organization_ids=frozenset(orgs))
