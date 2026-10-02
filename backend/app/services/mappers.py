"""ORM -> response schema mapping."""
from app.models import Organization, Role, User
from app.models.base import utcnow
from app.schemas.identity import MembershipOut, OrganizationOut, RoleGrantOut, RoleOut, UserOut


def user_out(u: User) -> UserOut:
    return UserOut(
        id=u.id, email=u.email, full_name=u.full_name, phone=u.phone, status=u.status,
        must_change_password=u.must_change_password, mfa_enabled=u.mfa_enabled, is_locked=u.is_locked(utcnow()),
        locked_until=u.locked_until, last_login_at=u.last_login_at, environment=u.environment,
        created_at=u.created_at, updated_at=u.updated_at,
        roles=sorted((RoleGrantOut(id=r.id, role_code=r.role.code, role_name=r.role.name, scope=r.role.scope,
                                   organization_id=r.organization_id,
                                   organization_name=r.organization.name if r.organization else None,
                                   assigned_at=r.assigned_at) for r in u.roles),
                     key=lambda g: (g.organization_name or "", g.role_name)),
        organizations=sorted((MembershipOut(organization_id=m.organization_id, organization_code=m.organization.code,
                                            organization_name=m.organization.name, org_type=m.organization.org_type,
                                            title=m.title, is_primary=m.is_primary) for m in u.memberships),
                             key=lambda m: (not m.is_primary, m.organization_name)),
    )


def role_out(r: Role, assignment_count: int = 0) -> RoleOut:
    return RoleOut(id=r.id, code=r.code, name=r.name, description=r.description, scope=r.scope,
                   is_system=r.is_system, permissions=sorted(rp.permission.code for rp in r.permissions),
                   assignment_count=assignment_count)


def organization_out(o: Organization, member_count: int = 0) -> OrganizationOut:
    out = OrganizationOut.model_validate(o)
    out.member_count = member_count
    return out
