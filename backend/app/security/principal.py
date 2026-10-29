"""The authenticated principal and organisation-scoped permission resolution (spec section 31).

A permission can be held platform-wide (role granted with organization_id NULL) or only
inside specific organisations. Services ask `principal.scope_for(code)`:
  None              -> may act on every organisation (only a principal built without environment data)
  frozenset({...})  -> may act only on records belonging to these organisations
A platform-wide grant reaches only the organisations of the caller's own environment (DEMO never reads or acts on
LIVE records, and the reverse), and grants inside an organisation that is not ACTIVE are ignored.
"""
import uuid
from collections.abc import Iterable, Iterator, Set
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.errors import PermissionDenied
from app.models import Organization, OrganizationStatus, OrganizationUser, Permission, Role, RolePermission, User, UserRole


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
    # Every organisation of the caller's environment (any status): the reach of a platform-wide grant. A request principal gets
    # an `EnvironmentOrganizations` (read on demand, not per request); None only for synthetic principals built in code without
    # environment data (no environment restriction).
    environment_organization_ids: Set[uuid.UUID] | None = None

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

    def in_environment(self, organization_id: uuid.UUID) -> bool:
        """True if the organisation belongs to the caller's environment (the reach of a platform-wide grant)."""
        return self.environment_organization_ids is None or organization_id in self.environment_organization_ids

    def scope_for(self, code: str) -> Set[uuid.UUID] | None:
        if self.has_platform(code):
            return self.environment_organization_ids  # the caller's environment only, never "every organisation"
        orgs = frozenset(g.organization_id for g in self.grants if code in g.permissions and g.organization_id)
        if not orgs:
            raise PermissionDenied(details={"required_permission": code})
        return orgs

    def can_in_org(self, code: str, organization_id: uuid.UUID | None) -> bool:
        if self.has_platform(code) and (organization_id is None or self.in_environment(organization_id)):
            return True
        return organization_id is not None and any(
            g.organization_id == organization_id and code in g.permissions for g in self.grants)

    def require_in_org(self, code: str, organization_id: uuid.UUID | None) -> None:
        if not self.can_in_org(code, organization_id):
            raise PermissionDenied(details={"required_permission": code,
                                            "organization_id": str(organization_id) if organization_id else None})


class EnvironmentOrganizations(Set[uuid.UUID]):
    """The ids of every organisation of one environment, read only when needed: a membership test is one primary-key lookup
    (cached), and the full id list is loaded on first iteration only. Semantically the same set `load_principal` used to load on
    every request. SQL listings should not iterate it (an IN list of every organisation breaks SQL Server's 2100-parameter limit):
    they use `security.scoping.org_predicate`, which filters with a subquery on the environment instead."""

    def __init__(self, db: Session, environment: str) -> None:
        self._db, self.environment = db, environment
        self._ids: frozenset[uuid.UUID] | None = None
        self._known: dict[Any, bool] = {}

    def _all(self) -> frozenset[uuid.UUID]:
        if self._ids is None:
            with self._db.no_autoflush:
                self._ids = frozenset(self._db.scalars(select(Organization.id).where(Organization.environment == self.environment)))
        return self._ids

    def __contains__(self, organization_id: object) -> bool:
        if self._ids is not None:
            return organization_id in self._ids
        if organization_id not in self._known:
            if not isinstance(organization_id, uuid.UUID):
                return False
            with self._db.no_autoflush:
                env = self._db.scalar(select(Organization.environment).where(Organization.id == organization_id))
            self._known[organization_id] = env == self.environment
        return self._known[organization_id]

    def __iter__(self) -> Iterator[uuid.UUID]:
        return iter(self._all())

    def __len__(self) -> int:
        return len(self._all())

    @classmethod
    def _from_iterable(cls, it: Iterable[uuid.UUID]) -> frozenset[uuid.UUID]:   # set operators (&, |, -) return a plain frozenset
        return frozenset(it)

    __hash__ = object.__hash__   # keeps Principal (a frozen dataclass) hashable


def load_grants(db: Session, user_id: uuid.UUID) -> tuple[Grant, ...]:
    rows = db.execute(
        select(UserRole.id, Role.code, Role.scope, UserRole.organization_id, Permission.code)
        .join(Role, Role.id == UserRole.role_id)
        .outerjoin(RolePermission, RolePermission.role_id == Role.id)
        .outerjoin(Permission, Permission.id == RolePermission.permission_id)
        .outerjoin(Organization, Organization.id == UserRole.organization_id)
        # A suspended or archived organisation gives its members no access (platform-wide grants are unaffected).
        .where(UserRole.user_id == user_id,
               or_(UserRole.organization_id.is_(None), Organization.status == OrganizationStatus.ACTIVE.value))
    ).all()
    grouped: dict[uuid.UUID, tuple[str, str, uuid.UUID | None, set[str]]] = {}
    for ur_id, role_code, scope, org_id, perm in rows:
        entry = grouped.setdefault(ur_id, (role_code, scope, org_id, set()))
        if perm:
            entry[3].add(perm)
    return tuple(Grant(k, v[0], v[1], v[2], frozenset(v[3])) for k, v in grouped.items())


def load_principal(db: Session, user: User, session_id: uuid.UUID | None) -> Principal:
    orgs = db.scalars(select(OrganizationUser.organization_id).where(OrganizationUser.user_id == user.id)).all()
    return Principal(user=user, session_id=session_id, grants=load_grants(db, user.id), member_organization_ids=frozenset(orgs),
                     environment_organization_ids=EnvironmentOrganizations(db, user.environment))
