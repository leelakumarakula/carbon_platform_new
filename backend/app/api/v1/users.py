import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel

from app.api.deps import DB, Ctx, Paging, require
from app.schemas.common import Page, Reason
from app.schemas.identity import PasswordReset, RoleGrantIn, UserCreate, UserOut, UserStatusChange, UserUpdate
from app.security.permissions import P
from app.security.principal import Principal
from app.services import user_service
from app.services.mappers import user_out

router = APIRouter(prefix="/admin/users", tags=["admin: users"])

CanRead = Annotated[Principal, Depends(require(P.USERS_READ))]
CanManage = Annotated[Principal, Depends(require(P.USERS_MANAGE))]
CanAssign = Annotated[Principal, Depends(require(P.USERS_ASSIGN_ROLES))]
CanSecure = Annotated[Principal, Depends(require(P.SECURITY_MANAGE))]


class ReasonBody(BaseModel):
    reason: Reason


@router.get("", response_model=Page[UserOut])
def list_users(principal: CanRead, db: DB, paging: Paging,
               search: Annotated[str | None, Query(max_length=100)] = None,
               status_: Annotated[Literal["ACTIVE", "SUSPENDED", "DEACTIVATED"] | None, Query(alias="status")] = None,
               organization_id: uuid.UUID | None = None,
               role: Annotated[str | None, Query(max_length=60)] = None,
               environment: Literal["LIVE", "DEMO"] | None = None) -> Page[UserOut]:
    rows, total = user_service.list_users(db, principal, paging, search=search, status=status_,
                                          organization_id=organization_id, role_code=role, environment=environment)
    return Page(items=[user_out(u) for u in rows], total=total, page=paging.page, page_size=paging.page_size)


@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(body: UserCreate, principal: CanManage, db: DB, ctx: Ctx) -> UserOut:
    return user_out(user_service.create_user(db, ctx, principal, body))


@router.get("/{user_id}", response_model=UserOut)
def get_user(user_id: uuid.UUID, principal: CanRead, db: DB) -> UserOut:
    return user_out(user_service.get_visible_user(db, principal, user_id))


@router.patch("/{user_id}", response_model=UserOut)
def update_user(user_id: uuid.UUID, body: UserUpdate, principal: CanManage, db: DB, ctx: Ctx) -> UserOut:
    return user_out(user_service.update_user(db, ctx, principal, user_id, body))


@router.post("/{user_id}/status", response_model=UserOut, summary="Change status via the user state machine")
def change_status(user_id: uuid.UUID, body: UserStatusChange, principal: CanManage, db: DB, ctx: Ctx) -> UserOut:
    return user_out(user_service.change_status(db, ctx, principal, user_id, body.status, body.reason))


@router.post("/{user_id}/reset-password", response_model=UserOut)
def reset_password(user_id: uuid.UUID, body: PasswordReset, principal: CanManage, db: DB, ctx: Ctx) -> UserOut:
    return user_out(user_service.reset_password(db, ctx, principal, user_id, body.temporary_password, body.reason))


@router.post("/{user_id}/unlock", response_model=UserOut)
def unlock(user_id: uuid.UUID, body: ReasonBody, principal: CanSecure, db: DB, ctx: Ctx) -> UserOut:
    return user_out(user_service.unlock(db, ctx, principal, user_id, body.reason))


@router.post("/{user_id}/roles", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def assign_role(user_id: uuid.UUID, body: RoleGrantIn, principal: CanAssign, db: DB, ctx: Ctx) -> UserOut:
    return user_out(user_service.assign_role(db, ctx, principal, user_id, body))


@router.delete("/{user_id}/roles/{user_role_id}", response_model=UserOut)
def revoke_role(user_id: uuid.UUID, user_role_id: uuid.UUID, principal: CanAssign, db: DB, ctx: Ctx,
                reason: Annotated[str | None, Query(max_length=1000)] = None) -> UserOut:
    return user_out(user_service.revoke_role(db, ctx, principal, user_id, user_role_id, reason))
