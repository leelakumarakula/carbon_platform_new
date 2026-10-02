import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel

from app.api.deps import DB, Ctx, Paging, require
from app.repositories import identity as repo
from app.schemas.common import Message, Page, Reason
from app.schemas.identity import MemberAdd, MemberOut, OrganizationCreate, OrganizationOut, OrganizationUpdate, OrgStatusChange
from app.security.permissions import P
from app.security.principal import Principal
from app.services import organization_service as svc
from app.services.mappers import organization_out

router = APIRouter(prefix="/admin/organizations", tags=["admin: organizations"])

CanRead = Annotated[Principal, Depends(require(P.ORGANIZATIONS_READ))]
CanManage = Annotated[Principal, Depends(require(P.ORGANIZATIONS_MANAGE))]
CanMembers = Annotated[Principal, Depends(require(P.ORGANIZATIONS_MANAGE_MEMBERS))]


class ReasonBody(BaseModel):
    reason: Reason


def _out(db: DB, org: object) -> OrganizationOut:
    return organization_out(org, repo.member_counts(db, [org.id]).get(org.id, 0))  # type: ignore[attr-defined, arg-type]


@router.get("", response_model=Page[OrganizationOut])
def list_orgs(principal: CanRead, db: DB, paging: Paging,
              search: Annotated[str | None, Query(max_length=100)] = None,
              org_type: str | None = None,
              status_: Annotated[Literal["ACTIVE", "SUSPENDED", "ARCHIVED"] | None, Query(alias="status")] = None,
              environment: Literal["LIVE", "DEMO"] | None = None) -> Page[OrganizationOut]:
    rows, total = svc.list_orgs(db, principal, paging, search=search, org_type=org_type, status=status_,
                                environment=environment)
    counts = repo.member_counts(db, [o.id for o in rows])
    return Page(items=[organization_out(o, counts.get(o.id, 0)) for o in rows], total=total,
                page=paging.page, page_size=paging.page_size)


@router.post("", response_model=OrganizationOut, status_code=status.HTTP_201_CREATED)
def create_org(body: OrganizationCreate, principal: CanManage, db: DB, ctx: Ctx) -> OrganizationOut:
    return _out(db, svc.create(db, ctx, principal, body))


@router.get("/{org_id}", response_model=OrganizationOut)
def get_org(org_id: uuid.UUID, principal: CanRead, db: DB) -> OrganizationOut:
    return _out(db, svc.get_visible(db, principal, org_id))


@router.patch("/{org_id}", response_model=OrganizationOut)
def update_org(org_id: uuid.UUID, body: OrganizationUpdate, principal: CanManage, db: DB, ctx: Ctx) -> OrganizationOut:
    return _out(db, svc.update(db, ctx, principal, org_id, body))


@router.post("/{org_id}/status", response_model=OrganizationOut)
def change_status(org_id: uuid.UUID, body: OrgStatusChange, principal: CanManage, db: DB, ctx: Ctx) -> OrganizationOut:
    return _out(db, svc.change_status(db, ctx, principal, org_id, body.status, body.reason))


@router.get("/{org_id}/members", response_model=list[MemberOut])
def list_members(org_id: uuid.UUID, principal: CanRead, db: DB) -> list[MemberOut]:
    return [MemberOut(id=m.id, user_id=m.user_id, email=m.user.email, full_name=m.user.full_name,
                      user_status=m.user.status, title=m.title, is_primary=m.is_primary, joined_at=m.joined_at)
            for m in svc.list_members(db, principal, org_id)]


@router.post("/{org_id}/members", response_model=Message, status_code=status.HTTP_201_CREATED)
def add_member(org_id: uuid.UUID, body: MemberAdd, principal: CanMembers, db: DB, ctx: Ctx) -> Message:
    svc.add_member(db, ctx, principal, org_id, body)
    return Message(message="Member added.")


@router.post("/{org_id}/members/{user_id}/remove", response_model=Message)
def remove_member(org_id: uuid.UUID, user_id: uuid.UUID, body: ReasonBody, principal: CanMembers, db: DB,
                  ctx: Ctx) -> Message:
    svc.remove_member(db, ctx, principal, org_id, user_id, body.reason)
    return Message(message="Member removed and their roles in this organization revoked.")
