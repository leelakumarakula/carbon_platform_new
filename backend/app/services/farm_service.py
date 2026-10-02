"""Farms: registration, versioned boundaries (SQL Server geography), ownership, evidence, overlap checks and
the verification workflow (spec §7.3, §11, §12, §41).

Rules:
- authoritative area and validity come from SQL Server; every boundary save creates a new version
- boundary and ownership edits only while DRAFT (re-open a verified/rejected farm to correct it)
- overlaps with any other current boundary (any organization, same environment) are flagged OPEN for
  review — never auto-rejected. Details of farms the caller cannot see are withheld.
- verification needs: GIS review, no OPEN/CONFIRMED_CONFLICT overlap, a verified ownership/tenure record,
  farmer KYC-verified; the person who submitted the farm cannot verify it
"""
import json
import uuid
from datetime import date
from decimal import Decimal
from typing import Any

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit.service import record, record_transition
from app.core.context import RequestContext
from app.core.errors import Conflict, NotFound, PermissionDenied, ValidationFailed
from app.models import Farm, FarmBoundary, Farmer, FarmEvidence, FarmOverlapCheck, FarmOwnership
from app.models.base import utcnow
from app.models.documents import DocumentCategory
from app.repositories import farms as repo
from app.repositories import gis
from app.repositories.sequences import next_code
from app.rules.geometry_io import wkt_to_geojson
from app.schemas.common import PageParams
from app.schemas.farmers import ChecklistItem, TransitionReadiness
from app.schemas.farms import EvidenceIn, FarmCreate, FarmUpdate, OwnershipIn
from app.security.permissions import P
from app.security.principal import Principal
from app.services import access, document_service, farm_history_service, gis_service
from app.services.notification_service import notify
from app.services.workflows import FARM_MACHINE, OVERLAP_MACHINE

ENTITY = "farm"
FARM_DOC_CATEGORIES = {DocumentCategory.LAND_TITLE.value, DocumentCategory.LEASE_AGREEMENT.value, DocumentCategory.LAND_RECORD.value,
                       DocumentCategory.FIELD_PHOTO.value, DocumentCategory.INPUT_RECORD.value, DocumentCategory.GEOSPATIAL_FILE.value,
                       DocumentCategory.OTHER.value}
BLOCKING_OVERLAPS = ("OPEN", "CONFIRMED_CONFLICT")


def _not_found() -> NotFound:
    return NotFound("Farm not found.", error_code="FARM_NOT_FOUND")


def _owner(db: Session, farm: Farm) -> uuid.UUID | None:
    return repo.owner_user(db, farm.farmer_id)


def get_farm(db: Session, principal: Principal, farm_id: uuid.UUID, code: str = P.FARMS_READ) -> Farm:
    farm = repo.get(db, farm_id)
    if farm is None:
        raise _not_found()
    access.require(principal, code, farm.organization_id, _owner(db, farm), _not_found())
    return farm


def can_see(db: Session, principal: Principal, farm: Farm) -> bool:
    return access.can(principal, P.FARMS_READ, farm.organization_id, _owner(db, farm))


def _document_resolver(db: Session, principal: Principal, farm_id: uuid.UUID, kind: str) -> None:
    farm = repo.get(db, farm_id)
    nf = NotFound("Document not found.", error_code="DOCUMENT_NOT_FOUND")
    if farm is None:
        raise nf
    access.require(principal, P.FARMS_MANAGE if kind == "manage" else P.FARMS_READ, farm.organization_id, _owner(db, farm), nf)


document_service.register_resolver(ENTITY, _document_resolver)


def list_farms(db: Session, principal: Principal, params: PageParams, **filters: object) -> tuple[list[Farm], int]:
    scope, include_self = access.read_scope(principal, P.FARMS_READ)
    org = filters.get("organization_id")
    if scope is not None and org is not None and org not in scope:
        raise PermissionDenied(details={"organization_id": str(org)})
    return repo.list_farms(db, params, scope=scope, include_self=include_self, user_id=principal.user_id, **filters)  # type: ignore[arg-type]


def _require_status(farm: Farm, *allowed: str, what: str) -> None:
    if farm.status not in allowed:
        raise Conflict(f"{what} is only possible while the farm is {' or '.join(allowed)} (it is {farm.status}).",
                       error_code="FARM_NOT_EDITABLE")


# ---------------------------------------------------------------- create / update
def create_farm(db: Session, ctx: RequestContext, principal: Principal, data: FarmCreate) -> Farm:
    farmer = db.get(Farmer, data.farmer_id)
    if farmer is None:
        raise NotFound("Farmer not found.", error_code="FARMER_NOT_FOUND")
    access.require(principal, P.FARMS_MANAGE, farmer.organization_id, farmer.user_id,
                   NotFound("Farmer not found.", error_code="FARMER_NOT_FOUND"))
    if farmer.status in ("DRAFT", "SUSPENDED"):
        raise Conflict("Register the farmer (and lift any suspension) before adding farms.", error_code="FARMER_NOT_READY")
    farm = Farm(farm_code=next_code(db, "farm", date.today().year), organization_id=farmer.organization_id,
                environment=farmer.environment, created_by=ctx.user_id, **data.model_dump())
    db.add(farm)
    db.flush()
    record(db, ctx, "FARM_CREATED", ENTITY, farm.id, None,
           {"farm_code": farm.farm_code, "farmer_id": farmer.id, **json.loads(data.model_dump_json())}, organization_id=farm.organization_id)
    db.commit()
    return repo.get(db, farm.id)  # type: ignore[return-value]


def update_farm(db: Session, ctx: RequestContext, principal: Principal, farm_id: uuid.UUID, data: FarmUpdate) -> Farm:
    farm = get_farm(db, principal, farm_id, P.FARMS_MANAGE)
    _require_status(farm, "DRAFT", what="Editing farm details")
    changes = data.model_dump(exclude_unset=True)
    old = {k: getattr(farm, k) for k in changes}
    for k, v in changes.items():
        setattr(farm, k, v)
    if old != changes:
        record(db, ctx, "FARM_UPDATED", ENTITY, farm.id, old, changes, organization_id=farm.organization_id)
    db.commit()
    return repo.get(db, farm.id)  # type: ignore[return-value]


# ---------------------------------------------------------------- boundary
def save_boundary(db: Session, ctx: RequestContext, principal: Principal, farm_id: uuid.UUID, geojson: dict[str, Any] | None,
                  kml: str | None, source: str, source_document_id: uuid.UUID | None = None) -> tuple[Farm, list[str]]:
    farm = get_farm(db, principal, farm_id, P.FARMS_MANAGE)
    _require_status(farm, "DRAFT", what="Changing the boundary")
    check = gis_service.check_boundary(db, gis_service.parse_input(geojson, kml), farm.declared_area_hectares)
    previous = repo.current_boundary(db, farm.id)
    version = (max((b.version for b in repo.boundaries(db, farm.id)), default=0)) + 1
    if previous:
        previous.status, previous.superseded_at = "SUPERSEDED", utcnow()
        db.flush()
    b = FarmBoundary(farm_id=farm.id, version=version, boundary=check.wkt, source=source, source_document_id=source_document_id,
                     area_m2=Decimal(f"{check.area_m2:.2f}"), area_hectares=Decimal(f"{check.area_hectares:.4f}"),
                     perimeter_m=Decimal(f"{check.perimeter_m:.2f}"), centroid_lat=Decimal(f"{check.centroid_lat:.7f}"),
                     centroid_lon=Decimal(f"{check.centroid_lon:.7f}"), vertex_count=check.vertex_count,
                     validation_notes="\n".join(check.notes + check.warnings) or None, created_by=ctx.user_id)
    db.add(b)
    db.flush()
    farm.current_boundary_id, farm.area_hectares = b.id, b.area_hectares
    record(db, ctx, "FARM_BOUNDARY_SAVED", ENTITY, farm.id,
           {"boundary_id": previous.id, "version": previous.version, "area_hectares": previous.area_hectares} if previous else None,
           {"boundary_id": b.id, "version": version, "area_hectares": b.area_hectares, "source": source,
            "warnings": check.warnings}, organization_id=farm.organization_id)
    detect_overlaps(db, ctx, farm, b)
    db.commit()
    return repo.get(db, farm.id), check.warnings  # type: ignore[return-value]


def detect_overlaps(db: Session, ctx: RequestContext, farm: Farm, boundary: FarmBoundary) -> list[FarmOverlapCheck]:
    """Flag every intersection with another current boundary. Checks against superseded boundaries become OBSOLETE."""
    from app.core.config import get_settings
    known: set[frozenset[uuid.UUID]] = set()
    for old in db.scalars(select(FarmOverlapCheck).where(
            ((FarmOverlapCheck.farm_id == farm.id) | (FarmOverlapCheck.other_farm_id == farm.id)),
            FarmOverlapCheck.status != "OBSOLETE")).all():
        if old.boundary_id != boundary.id and old.other_boundary_id != boundary.id:
            old.status = "OBSOLETE"  # refers to a superseded boundary of this farm
        else:
            known.add(frozenset({old.boundary_id, old.other_boundary_id}))  # keep existing decision for this pair
    hits = gis.find_overlaps(db, boundary.id, farm.id, farm.environment)
    min_area = get_settings().FARM_OVERLAP_MIN_AREA_M2
    created = []
    for h in hits:
        if h.overlap_m2 < min_area or frozenset({boundary.id, h.other_boundary_id}) in known:
            continue  # shared edge / numeric sliver, or already flagged for this pair of boundaries
        chk = FarmOverlapCheck(farm_id=farm.id, boundary_id=boundary.id, other_farm_id=h.other_farm_id,
                               other_boundary_id=h.other_boundary_id, relation=h.relation,
                               overlap_area_m2=Decimal(f"{h.overlap_m2:.2f}"),
                               overlap_pct_of_farm=Decimal(f"{min(100.0, h.overlap_m2 / h.area_m2 * 100):.3f}"),
                               overlap_pct_of_other=Decimal(f"{min(100.0, h.overlap_m2 / h.other_area_m2 * 100):.3f}"),
                               same_farmer=h.other_farmer_id == farm.farmer_id,
                               same_organization=h.other_organization_id == farm.organization_id)
        db.add(chk)
        created.append(chk)
    db.flush()
    for chk in created:
        record(db, ctx, "FARM_OVERLAP_DETECTED", ENTITY, farm.id, None,
               {"overlap_check_id": chk.id, "other_farm_id": chk.other_farm_id, "relation": chk.relation,
                "overlap_area_m2": chk.overlap_area_m2, "same_organization": chk.same_organization}, organization_id=farm.organization_id)
    return created


def boundary_out_geojson(b: FarmBoundary) -> dict[str, Any]:
    return wkt_to_geojson(b.boundary)


def resolve_overlap(db: Session, ctx: RequestContext, principal: Principal, farm_id: uuid.UUID, check_id: uuid.UUID,
                    resolution: str, notes: str) -> FarmOverlapCheck:
    farm = get_farm(db, principal, farm_id, P.FARMS_READ)
    principal.require_in_org(P.FARMS_REVIEW, farm.organization_id)
    chk = db.get(FarmOverlapCheck, check_id)
    if chk is None or farm.id not in (chk.farm_id, chk.other_farm_id):
        raise NotFound("Overlap check not found.", error_code="OVERLAP_NOT_FOUND")
    other_id = chk.other_farm_id if chk.farm_id == farm.id else chk.farm_id
    other = repo.get(db, other_id)
    cross_org = bool(other and other.organization_id != farm.organization_id)
    # A cross-organization overlap affects another developer's farm: only platform-level reviewers may clear it.
    if cross_org and resolution == "CLEARED" and not principal.has_platform(P.FARMS_REVIEW):
        raise PermissionDenied("Overlaps with another organization's farm can only be cleared by a platform-level reviewer.",
                               error_code="CROSS_ORG_OVERLAP")
    record_transition(db, ctx, OVERLAP_MACHINE, chk.id, chk.status, resolution, "FARM_OVERLAP_RESOLVED", notes, farm.organization_id)
    chk.status, chk.resolved_by, chk.resolved_at, chk.resolution_notes = resolution, principal.user_id, utcnow(), notes
    db.commit()
    return chk


# ---------------------------------------------------------------- ownership
def add_ownership(db: Session, ctx: RequestContext, principal: Principal, farm_id: uuid.UUID, data: OwnershipIn) -> FarmOwnership:
    farm = get_farm(db, principal, farm_id, P.FARMS_MANAGE)
    _require_status(farm, "DRAFT", what="Recording ownership")
    owner_name = data.owner_name
    if data.owner_type == "FARMER":
        if data.owner_farmer_id is None:
            raise ValidationFailed("Choose the farmer who owns the land.", error_code="OWNER_FARMER_REQUIRED")
        owner = db.get(Farmer, data.owner_farmer_id)
        if owner is None or owner.environment != farm.environment:
            raise ValidationFailed("The owning farmer was not found.", error_code="OWNER_FARMER_NOT_FOUND")
        owner_name = owner_name or owner.full_name
    elif data.owner_farmer_id is not None:
        raise ValidationFailed("owner_farmer_id is only used when the owner is a farmer.", error_code="INVALID_OWNER")
    if not owner_name:
        raise ValidationFailed("Enter the owner's name.", error_code="OWNER_NAME_REQUIRED")
    document_service.require_attached(db, data.evidence_document_id, ENTITY, farm.id,
                                      {DocumentCategory.LAND_TITLE.value, DocumentCategory.LEASE_AGREEMENT.value,
                                       DocumentCategory.LAND_RECORD.value, DocumentCategory.OTHER.value})
    o = FarmOwnership(farm_id=farm.id, recorded_by=ctx.user_id, **(data.model_dump() | {"owner_name": owner_name}))
    db.add(o)
    db.flush()
    record(db, ctx, "FARM_OWNERSHIP_RECORDED", ENTITY, farm.id, None,
           {"ownership_id": o.id, **json.loads(data.model_dump_json()), "owner_name": owner_name}, organization_id=farm.organization_id)
    db.commit()
    return o


def _ownership(db: Session, farm: Farm, ownership_id: uuid.UUID) -> FarmOwnership:
    o = db.get(FarmOwnership, ownership_id)
    if o is None or o.farm_id != farm.id:
        raise NotFound("Ownership record not found.", error_code="OWNERSHIP_NOT_FOUND")
    return o


def end_ownership(db: Session, ctx: RequestContext, principal: Principal, farm_id: uuid.UUID, ownership_id: uuid.UUID,
                  valid_to: date, reason: str) -> FarmOwnership:
    farm = get_farm(db, principal, farm_id, P.FARMS_MANAGE)
    _require_status(farm, "DRAFT", what="Ending an ownership record")
    o = _ownership(db, farm, ownership_id)
    if o.valid_to is not None:
        raise Conflict("This ownership record has already ended.", error_code="OWNERSHIP_ENDED")
    if o.valid_from and valid_to < o.valid_from:
        raise ValidationFailed("The end date is before the start date.", error_code="INVALID_DATES")
    o.valid_to, o.end_reason = valid_to, reason
    record(db, ctx, "FARM_OWNERSHIP_ENDED", ENTITY, farm.id, {"ownership_id": o.id, "valid_to": None},
           {"valid_to": valid_to}, reason, organization_id=farm.organization_id)
    db.commit()
    return o


def review_ownership(db: Session, ctx: RequestContext, principal: Principal, farm_id: uuid.UUID, ownership_id: uuid.UUID,
                     status: str, notes: str) -> FarmOwnership:
    farm = get_farm(db, principal, farm_id, P.FARMS_READ)
    principal.require_in_org(P.FARMS_REVIEW, farm.organization_id)
    o = _ownership(db, farm, ownership_id)
    old = o.verification_status
    o.verification_status, o.reviewed_by, o.reviewed_at, o.review_notes = status, principal.user_id, utcnow(), notes
    record(db, ctx, "FARM_OWNERSHIP_REVIEWED", ENTITY, farm.id, {"ownership_id": o.id, "verification_status": old},
           {"verification_status": status}, notes, organization_id=farm.organization_id)
    db.commit()
    return o


def ownership_is_current(o: FarmOwnership, today: date | None = None) -> bool:
    return o.valid_to is None or o.valid_to >= (today or date.today())


# ---------------------------------------------------------------- history (delegates)
def history_action(db: Session, ctx: RequestContext, principal: Principal, farm_id: uuid.UUID, kind: str, action: str,
                   record_id: uuid.UUID | None = None, data: BaseModel | None = None, changes: dict[str, Any] | None = None,
                   reason: str | None = None, status: str | None = None) -> Any:
    if action == "review":
        farm = get_farm(db, principal, farm_id, P.FARMS_READ)
        principal.require_in_org(P.FARMS_REVIEW, farm.organization_id)
    else:
        farm = get_farm(db, principal, farm_id, P.FARMS_MANAGE)
    if data is not None and getattr(data, "evidence_document_id", None):
        document_service.require_attached(db, data.evidence_document_id, ENTITY, farm.id)  # type: ignore[attr-defined]
    if action == "add":
        out = farm_history_service.add(db, ctx, farm, kind, data)  # type: ignore[arg-type]
    elif action == "amend":
        out = farm_history_service.amend(db, ctx, farm, kind, record_id, changes or {}, reason or "")  # type: ignore[arg-type]
    elif action == "retract":
        out = farm_history_service.retract(db, ctx, farm, kind, record_id, reason or "")  # type: ignore[arg-type]
    else:
        out = farm_history_service.review(db, ctx, farm, kind, record_id, status or "", reason or "")  # type: ignore[arg-type]
    db.commit()
    return out


# ---------------------------------------------------------------- evidence
def add_evidence(db: Session, ctx: RequestContext, principal: Principal, farm_id: uuid.UUID, data: EvidenceIn) -> FarmEvidence:
    farm = get_farm(db, principal, farm_id, P.FARMS_MANAGE)
    if farm.status == "INACTIVE":
        raise Conflict("Evidence cannot be added to an inactive farm.", error_code="FARM_NOT_EDITABLE")
    is_self = access.is_self(principal, _owner(db, farm)) and not principal.can_in_org(P.FARMS_MANAGE, farm.organization_id)
    if is_self and data.source_type != "FARMER_CLAIM":
        raise ValidationFailed("Farmers record evidence as a farmer claim; other sources are recorded by staff.",
                               error_code="EVIDENCE_SOURCE_NOT_ALLOWED")
    document_service.require_attached(db, data.document_id, ENTITY, farm.id)
    e = FarmEvidence(farm_id=farm.id, captured_by=ctx.user_id, **data.model_dump())
    db.add(e)
    db.flush()
    record(db, ctx, "FARM_EVIDENCE_ADDED", ENTITY, farm.id, None, {"evidence_id": e.id, **json.loads(data.model_dump_json())},
           organization_id=farm.organization_id)
    db.commit()
    return e


def review_evidence(db: Session, ctx: RequestContext, principal: Principal, farm_id: uuid.UUID, evidence_id: uuid.UUID,
                    status: str, notes: str) -> FarmEvidence:
    farm = get_farm(db, principal, farm_id, P.FARMS_READ)
    principal.require_in_org(P.FARMS_REVIEW, farm.organization_id)
    e = db.get(FarmEvidence, evidence_id)
    if e is None or e.farm_id != farm.id:
        raise NotFound("Evidence not found.", error_code="EVIDENCE_NOT_FOUND")
    if e.captured_by == principal.user_id:
        raise PermissionDenied("You captured this evidence, so someone else must review it.", error_code="SEPARATION_OF_DUTIES")
    old = e.verification_status
    e.verification_status, e.reviewed_by, e.reviewed_at, e.review_notes = status, principal.user_id, utcnow(), notes
    record(db, ctx, "FARM_EVIDENCE_REVIEWED", ENTITY, farm.id, {"evidence_id": e.id, "verification_status": old},
           {"verification_status": status}, notes, organization_id=farm.organization_id)
    db.commit()
    return e


def evidence_distance(db: Session, farm: Farm, e: FarmEvidence) -> float | None:
    if e.latitude is None or e.longitude is None or farm.current_boundary_id is None:
        return None
    return round(gis.point_distance_to_boundary_m(db, farm.current_boundary_id, float(e.latitude), float(e.longitude)), 1)


# ---------------------------------------------------------------- documents
def upload_document(db: Session, ctx: RequestContext, principal: Principal, farm_id: uuid.UUID, category: str, title: str,
                    filename: str | None, data: bytes) -> uuid.UUID:
    from app.models import FarmDocument
    farm = get_farm(db, principal, farm_id, P.FARMS_MANAGE)
    if category not in FARM_DOC_CATEGORIES:
        raise ValidationFailed("This document category is not used for farms.", error_code="INVALID_CATEGORY")
    doc = document_service.create_document(db, ctx, entity_type=ENTITY, entity_id=farm.id, organization_id=farm.organization_id,
                                           environment=farm.environment, category=category, title=title, filename=filename, data=data)
    db.add(FarmDocument(farm_id=farm.id, document_id=doc.id))
    db.commit()
    return doc.id


def save_boundary_from_file(db: Session, ctx: RequestContext, principal: Principal, farm_id: uuid.UUID, filename: str | None,
                            data: bytes) -> tuple[Farm, list[str]]:
    from app.rules.file_types import sniff
    farm = get_farm(db, principal, farm_id, P.FARMS_MANAGE)
    _require_status(farm, "DRAFT", what="Changing the boundary")
    mime = sniff(data)
    if mime not in ("application/geo+json", "application/vnd.google-earth.kml+xml"):
        raise ValidationFailed("Upload a GeoJSON or KML file.", error_code="UNSUPPORTED_FILE_TYPE")
    text = data.decode("utf-8-sig")
    parsed = gis_service.parse_input(geojson=None if mime.endswith("kml+xml") else text, kml=text if mime.endswith("kml+xml") else None)
    gis_service.check_boundary(db, parsed)  # validate before keeping the file
    doc = document_service.create_document(db, ctx, entity_type=ENTITY, entity_id=farm.id, organization_id=farm.organization_id,
                                           environment=farm.environment, category=DocumentCategory.GEOSPATIAL_FILE.value,
                                           title=f"Boundary file {filename or ''}".strip(), filename=filename, data=data)
    from app.models import FarmDocument
    db.add(FarmDocument(farm_id=farm.id, document_id=doc.id))
    db.flush()
    gj = json.loads(text) if not mime.endswith("kml+xml") else None
    return save_boundary(db, ctx, principal, farm_id, gj, text if gj is None else None,
                         "KML_UPLOAD" if gj is None else "GEOJSON_UPLOAD", doc.id)


# ---------------------------------------------------------------- workflow
def readiness(db: Session, farm: Farm) -> list[TransitionReadiness]:
    farmer = db.get(Farmer, farm.farmer_id)
    owns = repo.ownerships(db, farm.id)
    current_owns = [o for o in owns if ownership_is_current(o)]
    blocking = [c for c in repo.overlaps(db, farm.id) if c.status in BLOCKING_OVERLAPS]
    hist = farm_history_service.counts(db, farm.id)
    out: list[TransitionReadiness] = []
    for target in sorted(FARM_MACHINE.allowed_from(farm.status)):
        items: list[ChecklistItem] = []
        if target == "SUBMITTED":
            items = [ChecklistItem(key="boundary", label="A valid boundary is saved", done=farm.current_boundary_id is not None),
                     ChecklistItem(key="ownership", label="At least one current ownership / tenure record", done=bool(current_owns)),
                     ChecklistItem(key="farmer", label="Farmer is registered and not suspended",
                                   done=bool(farmer and farmer.status not in ("DRAFT", "SUSPENDED"))),
                     ChecklistItem(key="land_history", label="Land-use history recorded", done=hist["land"] > 0, required=False),
                     ChecklistItem(key="crop_history", label="Crop history recorded", done=hist["crop"] > 0, required=False),
                     ChecklistItem(key="practice_history", label="Practice history recorded", done=hist["practice"] > 0, required=False)]
        elif target == "VERIFIED":
            items = [ChecklistItem(key="overlaps", label="No open or confirmed boundary overlaps", done=not blocking),
                     ChecklistItem(key="ownership_verified", label="A current ownership / tenure record is verified",
                                   done=any(o.verification_status == "VERIFIED" for o in current_owns)),
                     ChecklistItem(key="farmer_kyc", label="Farmer KYC is verified",
                                   done=bool(farmer and farmer.status in ("KYC_VERIFIED", "ACTIVE")))]
        out.append(TransitionReadiness(target=target, ready=all(i.done for i in items if i.required), items=items))
    return out


def _transition(db: Session, ctx: RequestContext, farm: Farm, target: str, action: str, reason: str) -> None:
    FARM_MACHINE.assert_transition(farm.status, target)
    ready = next((r for r in readiness(db, farm) if r.target == target), None)
    if ready and not ready.ready:
        missing = [i.label for i in ready.items if i.required and not i.done]
        raise Conflict(f"Cannot move to {target} yet: " + "; ".join(missing) + ".", error_code="REQUIREMENTS_NOT_MET",
                       details={"missing": missing})
    record_transition(db, ctx, FARM_MACHINE, farm.id, farm.status, target, action, reason, farm.organization_id)
    farm.status = target


def submit(db: Session, ctx: RequestContext, principal: Principal, farm_id: uuid.UUID, reason: str) -> Farm:
    farm = get_farm(db, principal, farm_id, P.FARMS_MANAGE)
    b = repo.current_boundary(db, farm.id)
    if b is not None:
        detect_overlaps(db, ctx, farm, b)  # re-check against farms added since the boundary was saved
    _transition(db, ctx, farm, "SUBMITTED", "FARM_SUBMITTED", reason)
    farm.submitted_at, farm.submitted_by = utcnow(), principal.user_id
    db.commit()
    return repo.get(db, farm.id)  # type: ignore[return-value]


def withdraw(db: Session, ctx: RequestContext, principal: Principal, farm_id: uuid.UUID, reason: str) -> Farm:
    farm = get_farm(db, principal, farm_id, P.FARMS_MANAGE)
    _require_status(farm, "SUBMITTED", what="Withdrawing a submission")
    _transition(db, ctx, farm, "DRAFT", "FARM_SUBMISSION_WITHDRAWN", reason)
    db.commit()
    return repo.get(db, farm.id)  # type: ignore[return-value]


def _reviewer(db: Session, principal: Principal, farm_id: uuid.UUID) -> Farm:
    farm = get_farm(db, principal, farm_id, P.FARMS_READ)
    principal.require_in_org(P.FARMS_REVIEW, farm.organization_id)
    return farm


def start_review(db: Session, ctx: RequestContext, principal: Principal, farm_id: uuid.UUID, reason: str) -> Farm:
    farm = _reviewer(db, principal, farm_id)
    _transition(db, ctx, farm, "GIS_REVIEW", "FARM_REVIEW_STARTED", reason)
    farm.reviewed_by = principal.user_id
    db.commit()
    return repo.get(db, farm.id)  # type: ignore[return-value]


def verify(db: Session, ctx: RequestContext, principal: Principal, farm_id: uuid.UUID, notes: str) -> Farm:
    farm = _reviewer(db, principal, farm_id)
    if farm.submitted_by == principal.user_id:
        raise PermissionDenied("You submitted this farm, so someone else must verify it.", error_code="SEPARATION_OF_DUTIES")
    _transition(db, ctx, farm, "VERIFIED", "FARM_VERIFIED", notes)
    farm.verified_at, farm.verified_by, farm.review_notes = utcnow(), principal.user_id, notes
    notify(db, [farm.submitted_by, _owner(db, farm)], "FARM_VERIFIED", f"Farm verified: {farm.farm_code} {farm.name}", notes,
           ENTITY, farm.id, f"/farms/{farm.id}")
    db.commit()
    return repo.get(db, farm.id)  # type: ignore[return-value]


def reject(db: Session, ctx: RequestContext, principal: Principal, farm_id: uuid.UUID, reason: str) -> Farm:
    farm = _reviewer(db, principal, farm_id)
    _transition(db, ctx, farm, "REJECTED", "FARM_REJECTED", reason)
    farm.review_notes = reason
    notify(db, [farm.submitted_by, _owner(db, farm)], "FARM_REJECTED", f"Farm needs correction: {farm.farm_code} {farm.name}",
           reason, ENTITY, farm.id, f"/farms/{farm.id}")
    db.commit()
    return repo.get(db, farm.id)  # type: ignore[return-value]


def reopen(db: Session, ctx: RequestContext, principal: Principal, farm_id: uuid.UUID, reason: str) -> Farm:
    farm = get_farm(db, principal, farm_id, P.FARMS_MANAGE)
    if farm.status in ("VERIFIED", "INACTIVE"):
        principal.require_in_org(P.FARMS_MANAGE, farm.organization_id)  # not self-service once verified
    _transition(db, ctx, farm, "DRAFT", "FARM_REOPENED", reason)
    farm.verified_at = farm.verified_by = None
    db.commit()
    return repo.get(db, farm.id)  # type: ignore[return-value]


def inactivate(db: Session, ctx: RequestContext, principal: Principal, farm_id: uuid.UUID, reason: str) -> Farm:
    farm = get_farm(db, principal, farm_id, P.FARMS_READ)
    principal.require_in_org(P.FARMS_MANAGE, farm.organization_id)
    _transition(db, ctx, farm, "INACTIVE", "FARM_INACTIVATED", reason)
    for chk in repo.overlaps(db, farm.id):
        if chk.status == "OPEN":
            chk.status = "OBSOLETE"
    db.commit()
    return repo.get(db, farm.id)  # type: ignore[return-value]


# ---------------------------------------------------------------- spatial search
def farms_near(db: Session, principal: Principal, lat: float, lon: float, radius_m: float, environment: str) -> list[tuple[Farm, Decimal]]:
    if not (-90 <= lat <= 90 and -180 <= lon <= 180) or not (0 < radius_m <= 50_000):
        raise ValidationFailed("Latitude/longitude out of range or radius not within 0–50 km.", error_code="INVALID_SPATIAL_QUERY")
    out = []
    for fid, dist in gis.farms_near(db, lat, lon, radius_m, environment):
        farm = repo.get(db, fid)
        if farm and can_see(db, principal, farm):
            out.append((farm, dist))
    return out


def farms_at_point(db: Session, principal: Principal, lat: float, lon: float, environment: str) -> list[Farm]:
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        raise ValidationFailed("Latitude/longitude out of range.", error_code="INVALID_SPATIAL_QUERY")
    farms = [repo.get(db, fid) for fid in gis.farms_at_point(db, lat, lon, environment)]
    return [f for f in farms if f and can_see(db, principal, f)]
