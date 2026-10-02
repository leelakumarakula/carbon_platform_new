import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.api.deps import DB, Ctx, require
from app.repositories import identity as repo
from app.schemas.identity import PermissionOut, RoleCreate, RoleOut, RolePermissionsUpdate, RoleUpdate
from app.security.permissions import P
from app.security.principal import Principal
from app.services import role_service
from app.services.mappers import role_out

router = APIRouter(prefix="/admin", tags=["admin: roles & permissions"])

CanRead = Annotated[Principal, Depends(require(P.ROLES_READ))]
CanManage = Annotated[Principal, Depends(require(P.ROLES_MANAGE))]


@router.get("/permissions", response_model=list[PermissionOut])
def list_permissions(_: CanRead, db: DB) -> list[PermissionOut]:
    return [PermissionOut.model_validate(p) for p in repo.list_permissions(db)]


@router.get("/roles", response_model=list[RoleOut])
def list_roles(_: CanRead, db: DB) -> list[RoleOut]:
    counts = repo.role_assignment_counts(db)
    return [role_out(r, counts.get(r.id, 0)) for r in repo.list_roles(db)]


@router.get("/roles/{role_id}", response_model=RoleOut)
def get_role(role_id: uuid.UUID, _: CanRead, db: DB) -> RoleOut:
    return role_out(role_service.get_role(db, role_id), repo.role_assignment_counts(db).get(role_id, 0))


@router.post("/roles", response_model=RoleOut, status_code=status.HTTP_201_CREATED)
def create_role(body: RoleCreate, principal: CanManage, db: DB, ctx: Ctx) -> RoleOut:
    return role_out(role_service.create_role(db, ctx, principal, body))


@router.patch("/roles/{role_id}", response_model=RoleOut)
def update_role(role_id: uuid.UUID, body: RoleUpdate, principal: CanManage, db: DB, ctx: Ctx) -> RoleOut:
    return role_out(role_service.update_role(db, ctx, principal, role_id, body))


@router.put("/roles/{role_id}/permissions", response_model=RoleOut)
def set_permissions(role_id: uuid.UUID, body: RolePermissionsUpdate, principal: CanManage, db: DB, ctx: Ctx) -> RoleOut:
    return role_out(role_service.set_permissions(db, ctx, principal, role_id, body.permissions))
