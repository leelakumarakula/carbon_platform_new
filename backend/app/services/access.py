"""Record-level access for farmer-owned data (spec rule 8 / section 31).

Access = organization-scoped permission  OR  self-service (the farmer's own login, holding farmers.self).
Out-of-scope records raise NotFound so their existence is not revealed.
"""
import uuid

from app.core.errors import NotFound, PermissionDenied
from app.security.permissions import P
from app.security.principal import Principal

# What a farmer may do on their own records with farmers.self.
SELF_ALLOWED = frozenset({P.FARMERS_READ, P.FARMERS_MANAGE, P.FARMERS_BANK_MANAGE, P.FARMS_READ, P.FARMS_MANAGE})
READ_OF = {P.FARMERS_MANAGE: P.FARMERS_READ, P.FARMERS_KYC_VERIFY: P.FARMERS_READ, P.FARMERS_BANK_MANAGE: P.FARMERS_READ,
           P.FARMERS_BANK_VERIFY: P.FARMERS_READ, P.FARMS_MANAGE: P.FARMS_READ, P.FARMS_REVIEW: P.FARMS_READ,
           P.PROJECTS_MANAGE: P.PROJECTS_READ, P.PROJECTS_REVIEW: P.PROJECTS_READ}


def is_self(principal: Principal, owner_user_id: uuid.UUID | None) -> bool:
    return owner_user_id is not None and owner_user_id == principal.user_id and principal.has(P.FARMERS_SELF)


def can(principal: Principal, code: str, organization_id: uuid.UUID, owner_user_id: uuid.UUID | None) -> bool:
    if principal.can_in_org(code, organization_id):
        return True
    return code in SELF_ALLOWED and is_self(principal, owner_user_id)


def require(principal: Principal, code: str, organization_id: uuid.UUID, owner_user_id: uuid.UUID | None,
            not_found: NotFound) -> None:
    """Raise NotFound if the caller cannot even see the record, PermissionDenied if they can see but not act."""
    if can(principal, code, organization_id, owner_user_id):
        return
    read_code = READ_OF.get(code, code)
    if read_code != code and can(principal, read_code, organization_id, owner_user_id):
        raise PermissionDenied(details={"required_permission": code})
    raise not_found


def read_scope(principal: Principal, code: str) -> tuple[frozenset[uuid.UUID] | None, bool]:
    """For list queries: (organization scope or None for all, include own records via self-service)."""
    include_self = principal.has(P.FARMERS_SELF)
    if principal.has_platform(code):
        return None, include_self
    orgs = frozenset(g.organization_id for g in principal.grants if code in g.permissions and g.organization_id)
    if not orgs and not include_self:
        raise PermissionDenied(details={"required_permission": code})
    return orgs, include_self
