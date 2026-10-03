"""Queries for users, roles and organizations."""
import uuid
from collections.abc import Iterable
from typing import Any

from sqlalchemy import ColumnElement, Select, exists, func, or_, select
from sqlalchemy.orm import Session, selectinload
from sqlalchemy.orm.interfaces import LoaderOption

from app.models import Organization, OrganizationUser, Permission, Role, RolePermission, User, UserRole
from app.repositories.common import paginate
from app.schemas.common import PageParams

USER_SORTS = {"email": User.email, "full_name": User.full_name, "created_at": User.created_at,
              "status": User.status, "last_login_at": User.last_login_at}
ORG_SORTS = {"code": Organization.code, "name": Organization.name, "org_type": Organization.org_type,
             "created_at": Organization.created_at, "status": Organization.status}


def _user_loader() -> tuple[LoaderOption, ...]:
    return (selectinload(User.roles).selectinload(UserRole.role),
            selectinload(User.roles).selectinload(UserRole.organization),
            selectinload(User.memberships).selectinload(OrganizationUser.organization))


def get_user(db: Session, user_id: uuid.UUID) -> User | None:
    return db.scalars(select(User).where(User.id == user_id).options(*_user_loader())
                      .execution_options(populate_existing=True)).first()


def get_user_by_email(db: Session, email: str) -> User | None:
    return db.scalars(select(User).where(User.email == email.lower())).first()


def user_in_orgs(user_id_col: Any, org_ids: Iterable[uuid.UUID]) -> ColumnElement[bool]:
    return exists().where(OrganizationUser.user_id == user_id_col, OrganizationUser.organization_id.in_(list(org_ids)))


def list_users(db: Session, params: PageParams, *, scope: frozenset[uuid.UUID] | None, search: str | None,
               status: str | None, organization_id: uuid.UUID | None, role_code: str | None,
               environment: str | None) -> tuple[list[User], int]:
    stmt: Select[tuple[User]] = select(User).options(*_user_loader()).where(User.status != "SYSTEM")   # Phase 12A: never listed
    if scope is not None:
        stmt = stmt.where(user_in_orgs(User.id, scope))
    if search:
        like = f"%{search.strip()}%"
        stmt = stmt.where(or_(User.email.ilike(like), User.full_name.ilike(like), User.phone.ilike(like)))
    if status:
        stmt = stmt.where(User.status == status)
    if environment:
        stmt = stmt.where(User.environment == environment)
    if organization_id:
        stmt = stmt.where(user_in_orgs(User.id, [organization_id]))
    if role_code:
        stmt = stmt.where(exists().where(UserRole.user_id == User.id, UserRole.role_id == Role.id,
                                         Role.code == role_code.upper()))
    return paginate(db, stmt, params, USER_SORTS, "email", User.id)


def get_role_by_code(db: Session, code: str) -> Role | None:
    return db.scalars(select(Role).where(Role.code == code.upper())
                      .options(selectinload(Role.permissions).selectinload(RolePermission.permission))).first()


def get_role(db: Session, role_id: uuid.UUID) -> Role | None:
    return db.scalars(select(Role).where(Role.id == role_id)
                      .options(selectinload(Role.permissions).selectinload(RolePermission.permission))).first()


def list_roles(db: Session) -> list[Role]:
    return list(db.scalars(select(Role).options(selectinload(Role.permissions).selectinload(RolePermission.permission))
                           .order_by(Role.is_system.desc(), Role.name)).all())


def role_assignment_counts(db: Session) -> dict[uuid.UUID, int]:
    return dict(db.execute(select(UserRole.role_id, func.count()).group_by(UserRole.role_id)).tuples().all())


def permissions_by_code(db: Session, codes: Iterable[str]) -> dict[str, Permission]:
    codes = list(set(codes))
    if not codes:
        return {}
    return {p.code: p for p in db.scalars(select(Permission).where(Permission.code.in_(codes))).all()}


def list_permissions(db: Session) -> list[Permission]:
    return list(db.scalars(select(Permission).order_by(Permission.module, Permission.code)).all())


def get_organization(db: Session, org_id: uuid.UUID) -> Organization | None:
    return db.get(Organization, org_id)


def get_organization_by_code(db: Session, code: str) -> Organization | None:
    return db.scalars(select(Organization).where(Organization.code == code.upper())).first()


def list_organizations(db: Session, params: PageParams, *, scope: frozenset[uuid.UUID] | None, search: str | None,
                       org_type: str | None, status: str | None, environment: str | None
                       ) -> tuple[list[Organization], int]:
    stmt: Select[tuple[Organization]] = select(Organization)
    if scope is not None:
        stmt = stmt.where(Organization.id.in_(list(scope)))
    if search:
        like = f"%{search.strip()}%"
        stmt = stmt.where(or_(Organization.code.ilike(like), Organization.name.ilike(like)))
    if org_type:
        stmt = stmt.where(Organization.org_type == org_type)
    if status:
        stmt = stmt.where(Organization.status == status)
    if environment:
        stmt = stmt.where(Organization.environment == environment)
    return paginate(db, stmt, params, ORG_SORTS, "name", Organization.id)


def member_counts(db: Session, org_ids: Iterable[uuid.UUID]) -> dict[uuid.UUID, int]:
    ids = list(org_ids)
    if not ids:
        return {}
    return dict(db.execute(select(OrganizationUser.organization_id, func.count())
                           .where(OrganizationUser.organization_id.in_(ids))
                           .group_by(OrganizationUser.organization_id)).tuples().all())


def list_members(db: Session, org_id: uuid.UUID) -> list[OrganizationUser]:
    return list(db.scalars(select(OrganizationUser).where(OrganizationUser.organization_id == org_id)
                           .options(selectinload(OrganizationUser.user))
                           .order_by(OrganizationUser.joined_at)).all())


def get_membership(db: Session, org_id: uuid.UUID, user_id: uuid.UUID) -> OrganizationUser | None:
    return db.scalars(select(OrganizationUser).where(OrganizationUser.organization_id == org_id,
                                                     OrganizationUser.user_id == user_id)).first()


def count_platform_admin_grants(db: Session) -> int:
    return db.scalar(select(func.count()).select_from(UserRole).join(Role, Role.id == UserRole.role_id)
                     .join(User, User.id == UserRole.user_id)
                     .where(Role.code == "PLATFORM_ADMIN", UserRole.organization_id.is_(None),
                            User.status == "ACTIVE")) or 0
