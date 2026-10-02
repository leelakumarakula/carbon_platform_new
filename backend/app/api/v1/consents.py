"""Versioned consent definitions (decision D3)."""
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel

from app.api.deps import DB, Ctx, require, require_any
from app.schemas.common import Reason
from app.schemas.farmers import ConsentDefinitionIn, ConsentDefinitionOut
from app.security.permissions import P
from app.security.principal import Principal
from app.services import consent_service as svc

router = APIRouter(tags=["consent definitions"])
Reader = Annotated[Principal, Depends(require_any(P.FARMERS_READ, P.FARMERS_SELF, P.CONSENTS_CONFIGURE))]
Configurer = Annotated[Principal, Depends(require(P.CONSENTS_CONFIGURE))]


class ReasonBody(BaseModel):
    reason: Reason


@router.get("/consent-definitions", response_model=list[ConsentDefinitionOut], summary="Active consent definitions")
def list_active(_: Reader, db: DB) -> list[ConsentDefinitionOut]:
    return [ConsentDefinitionOut.model_validate(d, from_attributes=True) for d in svc.list_definitions(db)]


@router.get("/admin/consent-definitions", response_model=list[ConsentDefinitionOut], summary="All consent definitions incl. retired")
def list_all(_: Configurer, db: DB) -> list[ConsentDefinitionOut]:
    return [ConsentDefinitionOut.model_validate(d, from_attributes=True) for d in svc.list_definitions(db, include_retired=True)]


@router.post("/admin/consent-definitions", response_model=ConsentDefinitionOut, status_code=status.HTTP_201_CREATED,
             summary="Publish a consent type or a new version of one (the previous version is retired)")
def publish(body: ConsentDefinitionIn, principal: Configurer, db: DB, ctx: Ctx) -> ConsentDefinitionOut:
    return ConsentDefinitionOut.model_validate(svc.publish(db, ctx, principal, body), from_attributes=True)


@router.post("/admin/consent-definitions/{definition_id}/retire", response_model=ConsentDefinitionOut)
def retire(definition_id: uuid.UUID, body: ReasonBody, principal: Configurer, db: DB, ctx: Ctx) -> ConsentDefinitionOut:
    return ConsentDefinitionOut.model_validate(svc.retire(db, ctx, principal, definition_id, body.reason), from_attributes=True)
