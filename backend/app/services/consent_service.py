"""Versioned consent definitions (decision D3).

A consent definition names a consent type, its version and whether it is required before a farmer can become
ACTIVE. Definitions are never edited after publication: publishing a new version of a type retires the previous
version. No consent type is invented here; the platform ships with DATA_PROCESSING v1 (required) only.
"""
import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.audit.service import record
from app.core.context import RequestContext
from app.core.errors import Conflict, NotFound, ValidationFailed
from app.models import ConsentDefinition
from app.models.base import utcnow
from app.schemas.farmers import ConsentDefinitionIn
from app.security.permissions import P
from app.security.principal import Principal

ENTITY = "consent_definition"
BASELINE = {"consent_type": "DATA_PROCESSING", "title": "Personal data processing",
            "description": "Consent to collect and process the farmer's personal data for platform operations.",
            "required_for_activation": True}


def list_definitions(db: Session, include_retired: bool = False) -> list[ConsentDefinition]:
    stmt = select(ConsentDefinition)
    if not include_retired:
        stmt = stmt.where(ConsentDefinition.status == "ACTIVE")
    return list(db.scalars(stmt.order_by(ConsentDefinition.consent_type, ConsentDefinition.version.desc())).all())


def active(db: Session, consent_type: str) -> ConsentDefinition | None:
    return db.scalars(select(ConsentDefinition).where(ConsentDefinition.consent_type == consent_type,
                                                      ConsentDefinition.status == "ACTIVE")).first()


def required_for_activation(db: Session) -> list[ConsentDefinition]:
    return list(db.scalars(select(ConsentDefinition).where(ConsentDefinition.status == "ACTIVE",
                                                           ConsentDefinition.required_for_activation == True)  # noqa: E712
                           .order_by(ConsentDefinition.consent_type)).all())


def publish(db: Session, ctx: RequestContext, principal: Principal, data: ConsentDefinitionIn) -> ConsentDefinition:
    """Create a new consent type, or a new version of an existing type (the previous version is retired)."""
    principal.require_in_org(P.CONSENTS_CONFIGURE, None)
    previous = active(db, data.consent_type)
    latest = db.scalar(select(func.max(ConsentDefinition.version)).where(ConsentDefinition.consent_type == data.consent_type)) or 0
    if previous is not None:
        previous.status, previous.retired_at, previous.retired_by = "RETIRED", utcnow(), principal.user_id
        db.flush()
    d = ConsentDefinition(version=latest + 1, created_by=principal.user_id, **data.model_dump())
    db.add(d)
    db.flush()
    record(db, ctx, "CONSENT_DEFINITION_PUBLISHED", ENTITY, d.id,
           {"previous_definition_id": previous.id, "previous_version": previous.version} if previous else None,
           {"consent_type": d.consent_type, "version": d.version, "required_for_activation": d.required_for_activation,
            "text_version": d.text_version})
    db.commit()
    return d


def retire(db: Session, ctx: RequestContext, principal: Principal, definition_id: uuid.UUID, reason: str) -> ConsentDefinition:
    principal.require_in_org(P.CONSENTS_CONFIGURE, None)
    d = db.get(ConsentDefinition, definition_id)
    if d is None:
        raise NotFound("Consent definition not found.", error_code="CONSENT_DEFINITION_NOT_FOUND")
    if d.status != "ACTIVE":
        raise Conflict("This consent definition is already retired.", error_code="CONSENT_DEFINITION_RETIRED")
    d.status, d.retired_at, d.retired_by = "RETIRED", utcnow(), principal.user_id
    record(db, ctx, "CONSENT_DEFINITION_RETIRED", ENTITY, d.id, {"status": "ACTIVE"}, {"status": "RETIRED"}, reason)
    db.commit()
    return d


def resolve_for_grant(db: Session, consent_type: str) -> ConsentDefinition:
    d = active(db, consent_type)
    if d is None:
        raise ValidationFailed(f"{consent_type} is not an active consent type. Ask an administrator to publish it first.",
                               error_code="UNKNOWN_CONSENT_TYPE")
    return d


def ensure_baseline(db: Session) -> bool:
    """Reference-data sync: make sure the baseline DATA_PROCESSING definition exists (never alters existing ones)."""
    if db.scalars(select(ConsentDefinition).where(ConsentDefinition.consent_type == BASELINE["consent_type"])).first():
        return False
    db.add(ConsentDefinition(version=1, **BASELINE))
    db.flush()
    return True
