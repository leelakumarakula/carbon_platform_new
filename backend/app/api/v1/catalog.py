"""Standard / route and activity catalog (reference data, Phase 3). Methodologies are Phase 4."""
import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, status

from app.api.deps import DB, Ctx, require, require_any
from app.schemas.projects import ActivityIn, ActivityOut, ActivityUpdate, StandardIn, StandardLink, StandardOut, StandardUpdate
from app.security.permissions import P
from app.security.principal import Principal
from app.services import catalog_service as svc

router = APIRouter(tags=["standards & activities"])
Reader = Annotated[Principal, Depends(require_any(P.PROJECTS_READ, P.STANDARDS_MANAGE))]
Manager = Annotated[Principal, Depends(require(P.STANDARDS_MANAGE))]


@router.get("/standards", response_model=list[StandardOut])
def list_standards(_: Reader, db: DB, environment: Literal["LIVE", "DEMO"] | None = None, active_only: bool = False) -> list[StandardOut]:
    return svc.list_standards(db, environment, active_only)


@router.post("/standards", response_model=StandardOut, status_code=status.HTTP_201_CREATED)
def create_standard(body: StandardIn, principal: Manager, db: DB, ctx: Ctx) -> StandardOut:
    return svc.create_standard(db, ctx, principal, body)


@router.patch("/standards/{standard_id}", response_model=StandardOut)
def update_standard(standard_id: uuid.UUID, body: StandardUpdate, principal: Manager, db: DB, ctx: Ctx) -> StandardOut:
    return svc.update_standard(db, ctx, principal, standard_id, body)


@router.get("/activities", response_model=list[ActivityOut])
def list_activities(_: Reader, db: DB, environment: Literal["LIVE", "DEMO"] | None = None, standard_id: uuid.UUID | None = None,
                    active_only: bool = False) -> list[ActivityOut]:
    return svc.list_activities(db, environment, standard_id, active_only)


@router.post("/activities", response_model=ActivityOut, status_code=status.HTTP_201_CREATED)
def create_activity(body: ActivityIn, principal: Manager, db: DB, ctx: Ctx) -> ActivityOut:
    return svc.create_activity(db, ctx, principal, body)


@router.patch("/activities/{activity_id}", response_model=ActivityOut)
def update_activity(activity_id: uuid.UUID, body: ActivityUpdate, principal: Manager, db: DB, ctx: Ctx) -> ActivityOut:
    return svc.update_activity(db, ctx, principal, activity_id, body)


@router.post("/activities/{activity_id}/standards", response_model=ActivityOut, summary="Offer this activity under a standard")
def link_activity(activity_id: uuid.UUID, body: StandardLink, principal: Manager, db: DB, ctx: Ctx) -> ActivityOut:
    return svc.link_activity(db, ctx, principal, activity_id, body.standard_id)
