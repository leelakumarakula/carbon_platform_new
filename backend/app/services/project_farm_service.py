"""Project participation: farms, carbon-rights references and the derived project boundary (spec section 7.4,
12, 41).

Rules:
- only VERIFIED farms of ACTIVE farmers, in the project's organization and environment, can be added
- adding a farm records its participation period, the farm boundary version in use and at least one carbon-rights
  reference (agreement, document or reference) in the same transaction
- spatial overlaps and other active participations are *shown* and must be acknowledged with a note; they never
  reject the farm automatically (spec section 41) — the eligibility reviewer decides
- removing a farm ends its participation and its active carbon-rights records; nothing is deleted
- the project boundary is computed by SQL Server (geography::UnionAggregate of the farms' current boundaries);
  every recomputation is a new version, GIS review applies to the version reviewed
"""
import json
import uuid
from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit.service import record, record_transition
from app.core.config import get_settings
from app.core.context import RequestContext
from app.core.errors import Conflict, NotFound, PermissionDenied, ValidationFailed
from app.models import (
    Farm,
    Farmer,
    FarmerAgreement,
    FarmOverlapCheck,
    Organization,
    Project,
    ProjectBoundary,
    ProjectCarbonRight,
    ProjectFarm,
)
from app.models.base import utcnow
from app.models.documents import DocumentCategory
from app.repositories import farms as farm_repo
from app.repositories import gis
from app.repositories import projects as repo
from app.rules.geometry_io import wkt_to_geojson
from app.schemas.projects import CarbonRightIn, ConflictOut, ProjectCarbonRightIn, ProjectFarmIn
from app.security.permissions import P
from app.security.principal import Principal
from app.services import document_service, farm_service
from app.services.project_service import EDITABLE, ENTITY, get_project, require_status
from app.services.workflows import CARBON_RIGHT_MACHINE

RIGHTS_DOC_CATEGORIES = {DocumentCategory.CARBON_RIGHTS.value, DocumentCategory.AGREEMENT.value, DocumentCategory.OTHER.value}


# ---------------------------------------------------------------- conflicts (visible, never auto-reject)
def _overlaps_ranges(a_start: date, a_end: date | None, b_start: date, b_end: date | None) -> bool:
    return (b_end is None or a_start <= b_end) and (a_end is None or b_start <= a_end)


def conflicts_for(db: Session, principal: Principal, farm: Farm, project: Project, start: date, end: date | None) -> list[ConflictOut]:
    out: list[ConflictOut] = []
    for c in farm_repo.overlaps(db, farm.id, include_closed=False):
        if c.status not in ("OPEN", "CONFIRMED_CONFLICT"):
            continue
        other_id = c.other_farm_id if c.farm_id == farm.id else c.farm_id
        other = farm_repo.get(db, other_id)
        visible = bool(other and farm_service.can_see(db, principal, other))
        out.append(ConflictOut(kind="FARM_OVERLAP", status=c.status, overlap_area_m2=c.overlap_area_m2,
                               other_farm_code=other.farm_code if visible and other else None,
                               detail=f"{c.status.replace('_', ' ').lower()} boundary overlap of {float(c.overlap_area_m2):,.0f} m² with "
                                      + (other.farm_code if visible and other else "a farm in another organization")))
    for pf in repo.active_participations_of_farm(db, farm.id):
        if pf.project_id == project.id or not _overlaps_ranges(start, end, pf.participation_start, pf.participation_end):
            continue
        other_p = repo.get(db, pf.project_id)
        if other_p is None or other_p.status == "CLOSED":
            continue
        visible = principal.can_in_org(P.PROJECTS_READ, other_p.organization_id)
        out.append(ConflictOut(kind="OTHER_PROJECT_PARTICIPATION", status=other_p.status,
                               other_project_code=other_p.project_code if visible else None,
                               detail="Already participating in " + (other_p.project_code if visible else "another project")
                                      + f" from {pf.participation_start}" + (f" to {pf.participation_end}" if pf.participation_end else "")))
    return out


def farm_organization_allowed(project: Project, farm: Farm) -> bool:
    """Decision P3: which organizations' farms may join. Only SAME_ORGANIZATION is supported today; a partner-
    organization policy (field partners / farmer groups) plugs in here once the business rules are decided."""
    policy = get_settings().PROJECT_FARM_ORG_POLICY
    if policy != "SAME_ORGANIZATION":
        raise ValidationFailed(f"Project farm policy {policy} is not supported.", error_code="UNSUPPORTED_POLICY")
    return farm.organization_id == project.organization_id


def _eligibility_reasons(db: Session, farm: Farm, project: Project) -> list[str]:
    reasons = []
    farmer = db.get(Farmer, farm.farmer_id)
    if not farm_organization_allowed(project, farm):
        reasons.append("The farm belongs to another organization.")
    if farm.environment != project.environment:
        reasons.append("Demo and live records cannot be mixed.")
    if farm.status != "VERIFIED":
        reasons.append(f"The farm is {farm.status}, not VERIFIED.")
    if farm.current_boundary_id is None:
        reasons.append("The farm has no boundary.")
    if farmer is None or farmer.status != "ACTIVE":
        reasons.append(f"The farmer is {farmer.status if farmer else 'missing'}, not ACTIVE.")
    return reasons


def eligible_farms(db: Session, principal: Principal, project_id: uuid.UUID) -> list[dict[str, Any]]:
    p = get_project(db, principal, project_id, P.PROJECTS_MANAGE)
    active = {pf.farm_id for pf in repo.project_farms(db, p.id, active_only=True)}
    farms = db.scalars(select(Farm).where(Farm.organization_id == p.organization_id, Farm.environment == p.environment,
                                          Farm.status != "INACTIVE").order_by(Farm.farm_code)).all()
    out = []
    today = date.today()
    for f in farms:
        if f.id in active:
            continue
        farmer = db.get(Farmer, f.farmer_id)
        reasons = _eligibility_reasons(db, f, p)
        conflicts = conflicts_for(db, principal, f, p, today, None)
        out.append({"farm_id": f.id, "farm_code": f.farm_code, "farm_name": f.name, "farmer_id": f.farmer_id,
                    "farmer_name": farmer.full_name if farmer else "", "farmer_status": farmer.status if farmer else "",
                    "farm_status": f.status, "area_hectares": f.area_hectares, "eligible": not reasons, "reasons": reasons,
                    "conflicts": conflicts,
                    "in_other_projects": [c.other_project_code or "another project" for c in conflicts if c.kind == "OTHER_PROJECT_PARTICIPATION"]})
    return out


# ---------------------------------------------------------------- farms
def add_farm(db: Session, ctx: RequestContext, principal: Principal, project_id: uuid.UUID, data: ProjectFarmIn) -> ProjectFarm:
    p = get_project(db, principal, project_id, P.PROJECTS_MANAGE)
    require_status(p, EDITABLE, "Adding farms")
    farm = farm_repo.get(db, data.farm_id)
    if farm is None or not farm_service.can_see(db, principal, farm):
        raise NotFound("Farm not found.", error_code="FARM_NOT_FOUND")
    if not farm_organization_allowed(p, farm):
        raise ValidationFailed("Only farms of the project's organization can join this project.", error_code="FARM_NOT_IN_PROJECT_ORGANIZATION")
    if farm.environment != p.environment:
        raise Conflict("Demo and live records cannot be mixed.", error_code="ENVIRONMENT_MISMATCH")
    if farm.status != "VERIFIED":
        raise Conflict(f"Only verified farms can join a project (this farm is {farm.status}).", error_code="FARM_NOT_VERIFIED")
    farmer = db.get(Farmer, farm.farmer_id)
    if farmer is None or farmer.status != "ACTIVE":
        raise Conflict("The farmer must be ACTIVE (KYC verified, required consents granted) before the farm can join.",
                       error_code="FARMER_NOT_ACTIVE")
    if any(pf.farm_id == farm.id for pf in repo.project_farms(db, p.id, active_only=True)):
        raise Conflict("This farm is already in the project.", error_code="FARM_ALREADY_IN_PROJECT")
    boundary = farm_repo.current_boundary(db, farm.id)
    if boundary is None:
        raise Conflict("The farm has no boundary.", error_code="FARM_HAS_NO_BOUNDARY")
    conflicts = conflicts_for(db, principal, farm, p, data.participation_start, data.participation_end)
    if conflicts and not (data.acknowledge_conflicts and data.conflict_notes):
        raise Conflict("This farm has conflicts that must be acknowledged with a note before it is added; they will be "
                       "reviewed during the eligibility review.", error_code="CONFLICTS_REQUIRE_ACKNOWLEDGEMENT",
                       details={"conflicts": [c.model_dump(mode="json") for c in conflicts]})
    pf = ProjectFarm(project_id=p.id, farm_id=farm.id, farmer_id=farm.farmer_id, participation_start=data.participation_start,
                     participation_end=data.participation_end, farm_boundary_id=boundary.id, farm_area_hectares=boundary.area_hectares,
                     conflicts_acknowledged=bool(conflicts), conflict_notes=data.conflict_notes if conflicts else None,
                     conflicts_snapshot=json.dumps([c.model_dump(mode="json") for c in conflicts]) if conflicts else None,
                     added_by=principal.user_id)
    db.add(pf)
    db.flush()
    record(db, ctx, "PROJECT_FARM_ADDED", ENTITY, p.id, None,
           {"project_farm_id": pf.id, "farm_id": farm.id, "farm_code": farm.farm_code, "farm_boundary_id": boundary.id,
            "farm_area_hectares": boundary.area_hectares, "participation_start": pf.participation_start,
            "participation_end": pf.participation_end, "conflicts": len(conflicts)}, data.conflict_notes, organization_id=p.organization_id)
    _create_carbon_right(db, ctx, principal, p, pf, data.carbon_rights)
    recompute_boundary(db, ctx, p)
    db.commit()
    return pf


def remove_farm(db: Session, ctx: RequestContext, principal: Principal, project_id: uuid.UUID, farm_id: uuid.UUID, reason: str) -> ProjectFarm:
    p = get_project(db, principal, project_id, P.PROJECTS_MANAGE)
    require_status(p, EDITABLE, "Removing farms")
    pf = next((x for x in repo.project_farms(db, p.id, active_only=True) if x.farm_id == farm_id), None)
    if pf is None:
        raise NotFound("This farm is not in the project.", error_code="PROJECT_FARM_NOT_FOUND")
    today = date.today()
    pf.status, pf.removed_by, pf.removed_at, pf.removal_reason = "REMOVED", principal.user_id, utcnow(), reason
    if pf.participation_end is None or pf.participation_end > today:
        pf.participation_end = max(today, pf.participation_start)
    for cr in repo.carbon_rights(db, p.id, pf.id):
        if cr.status == "ACTIVE":
            _end_right(db, ctx, p, cr, "ENDED", pf.participation_end, f"Farm removed from project: {reason}")
    record(db, ctx, "PROJECT_FARM_REMOVED", ENTITY, p.id, {"project_farm_id": pf.id, "farm_id": farm_id, "status": "ACTIVE"},
           {"status": "REMOVED", "participation_end": pf.participation_end}, reason, organization_id=p.organization_id)
    recompute_boundary(db, ctx, p)
    db.commit()
    return pf


# ---------------------------------------------------------------- carbon rights
def _create_carbon_right(db: Session, ctx: RequestContext, principal: Principal, p: Project, pf: ProjectFarm,
                         data: CarbonRightIn) -> ProjectCarbonRight:
    holder_name = data.holder_name
    holder_farmer_id = data.holder_farmer_id
    holder_org_id = data.holder_organization_id
    if data.holder_type == "FARMER":
        holder_farmer_id = holder_farmer_id or pf.farmer_id
        hf = db.get(Farmer, holder_farmer_id)
        if hf is None or hf.environment != p.environment or hf.organization_id != p.organization_id:
            raise ValidationFailed("The holding farmer was not found.", error_code="HOLDER_NOT_FOUND")
        holder_name = holder_name or hf.full_name
    elif holder_farmer_id is not None:
        raise ValidationFailed("holder_farmer_id is only used when the holder is a farmer.", error_code="INVALID_HOLDER")
    if data.holder_type in ("ORGANIZATION", "FARMER_GROUP"):
        if holder_org_id is not None:
            org = db.get(Organization, holder_org_id)
            if org is None or org.environment != p.environment:
                raise ValidationFailed("The holding organization was not found.", error_code="HOLDER_NOT_FOUND")
            if data.holder_type == "FARMER_GROUP" and org.org_type != "FARMER_GROUP":
                raise ValidationFailed("Choose a farmer-group organization.", error_code="INVALID_HOLDER")
            holder_name = holder_name or org.name
    elif holder_org_id is not None:
        raise ValidationFailed("holder_organization_id is only used for organization / farmer-group holders.", error_code="INVALID_HOLDER")
    if not holder_name:
        raise ValidationFailed("Enter the name of the carbon-rights holder.", error_code="HOLDER_NAME_REQUIRED")
    agreement_number = None
    if data.agreement_id:
        ag = db.get(FarmerAgreement, data.agreement_id)
        if ag is None or ag.farmer_id not in {pf.farmer_id, holder_farmer_id}:
            raise ValidationFailed("The agreement must belong to the farm's farmer or the holding farmer.", error_code="AGREEMENT_NOT_FOUND")
        if ag.status != "SIGNED":
            raise ValidationFailed(f"Only signed agreements can evidence carbon rights (this one is {ag.status}).",
                                   error_code="AGREEMENT_NOT_SIGNED")
        agreement_number = ag.agreement_number
    document_service.require_attached(db, data.document_id, ENTITY, p.id, RIGHTS_DOC_CATEGORIES)
    active = [x for x in repo.carbon_rights(db, p.id, pf.id) if x.status == "ACTIVE"]
    if data.share_pct is not None:
        total = sum((x.share_pct or Decimal(0)) for x in active) + data.share_pct
        if total > 100:
            raise ValidationFailed(f"Active carbon-rights shares for this farm would total {total}% (> 100%).", error_code="SHARE_EXCEEDS_100")
    cr = ProjectCarbonRight(project_id=p.id, project_farm_id=pf.id, farm_id=pf.farm_id, farmer_id=pf.farmer_id, holder_type=data.holder_type,
                            holder_farmer_id=holder_farmer_id, holder_organization_id=holder_org_id, holder_name=holder_name,
                            share_pct=data.share_pct, agreement_id=data.agreement_id, document_id=data.document_id,
                            reference=data.reference, effective_from=data.effective_from, effective_to=data.effective_to,
                            created_by=principal.user_id)
    db.add(cr)
    db.flush()
    record(db, ctx, "PROJECT_CARBON_RIGHT_CREATED", ENTITY, p.id, None,
           {"carbon_right_id": cr.id, "project_farm_id": pf.id, "farm_id": pf.farm_id, "holder_type": cr.holder_type,
            "holder_name": holder_name, "share_pct": cr.share_pct, "agreement_id": cr.agreement_id, "agreement_number": agreement_number,
            "document_id": cr.document_id, "reference": cr.reference, "effective_from": cr.effective_from, "effective_to": cr.effective_to},
           organization_id=p.organization_id)
    return cr


def add_carbon_right(db: Session, ctx: RequestContext, principal: Principal, project_id: uuid.UUID,
                     data: ProjectCarbonRightIn) -> ProjectCarbonRight:
    p = get_project(db, principal, project_id, P.PROJECTS_MANAGE)
    require_status(p, EDITABLE, "Recording carbon rights")
    pf = db.get(ProjectFarm, data.project_farm_id)
    if pf is None or pf.project_id != p.id:
        raise NotFound("This farm is not in the project.", error_code="PROJECT_FARM_NOT_FOUND")
    if pf.status != "ACTIVE":
        raise Conflict("The farm's participation has ended.", error_code="PARTICIPATION_ENDED")
    cr = _create_carbon_right(db, ctx, principal, p, pf, CarbonRightIn(**data.model_dump(exclude={"project_farm_id"})))
    db.commit()
    return cr


def _right(db: Session, p: Project, right_id: uuid.UUID) -> ProjectCarbonRight:
    cr = db.get(ProjectCarbonRight, right_id)
    if cr is None or cr.project_id != p.id:
        raise NotFound("Carbon-rights record not found.", error_code="CARBON_RIGHT_NOT_FOUND")
    return cr


def review_carbon_right(db: Session, ctx: RequestContext, principal: Principal, project_id: uuid.UUID, right_id: uuid.UUID,
                        status: str, notes: str) -> ProjectCarbonRight:
    p = get_project(db, principal, project_id, P.PROJECTS_REVIEW)
    cr = _right(db, p, right_id)
    if cr.status != "ACTIVE":
        raise Conflict("Only active carbon-rights records can be reviewed.", error_code="CARBON_RIGHT_NOT_ACTIVE")
    if cr.created_by == principal.user_id:
        raise PermissionDenied("You recorded these carbon rights, so someone else must review them.", error_code="SEPARATION_OF_DUTIES")
    old = cr.verification_status
    cr.verification_status, cr.reviewed_by, cr.reviewed_at, cr.review_notes, cr.updated_at = status, principal.user_id, utcnow(), notes, utcnow()
    record(db, ctx, "PROJECT_CARBON_RIGHT_REVIEWED", ENTITY, p.id, {"carbon_right_id": cr.id, "verification_status": old},
           {"verification_status": status}, notes, organization_id=p.organization_id)
    db.commit()
    return cr


def _end_right(db: Session, ctx: RequestContext, p: Project, cr: ProjectCarbonRight, status: str, effective_to: date | None,
               reason: str) -> None:
    old = cr.status
    record_transition(db, ctx, CARBON_RIGHT_MACHINE, cr.id, old, status, "CARBON_RIGHT_STATUS_CHANGED", reason, p.organization_id)
    cr.status, cr.end_reason, cr.updated_at = status, reason, utcnow()
    if status == "ENDED":
        cr.effective_to = effective_to or cr.effective_to or max(date.today(), cr.effective_from)
        if cr.effective_to < cr.effective_from:
            raise ValidationFailed("The end date is before the start date.", error_code="INVALID_DATES")
    record(db, ctx, "PROJECT_CARBON_RIGHT_ENDED", ENTITY, p.id, {"carbon_right_id": cr.id, "status": old},
           {"status": status, "effective_to": cr.effective_to}, reason, organization_id=p.organization_id)


def end_carbon_right(db: Session, ctx: RequestContext, principal: Principal, project_id: uuid.UUID, right_id: uuid.UUID, status: str,
                     effective_to: date | None, reason: str) -> ProjectCarbonRight:
    p = get_project(db, principal, project_id, P.PROJECTS_MANAGE)
    require_status(p, EDITABLE, "Ending carbon rights")
    cr = _right(db, p, right_id)
    _end_right(db, ctx, p, cr, status, effective_to, reason)
    db.commit()
    return cr


# ---------------------------------------------------------------- boundary
def _current_farm_boundary_ids(db: Session, p: Project) -> list[str]:
    ids = []
    for pf in repo.project_farms(db, p.id, active_only=True):
        farm = farm_repo.get(db, pf.farm_id)
        if farm and farm.current_boundary_id:
            ids.append(str(farm.current_boundary_id))
    return sorted(ids)


def boundary_is_stale(db: Session, p: Project) -> bool:
    current = repo.current_boundary(db, p.id)
    ids = _current_farm_boundary_ids(db, p)
    if current is None:
        return bool(ids)
    return sorted(json.loads(current.farm_boundary_ids)) != ids


def recompute_boundary(db: Session, ctx: RequestContext, p: Project) -> ProjectBoundary | None:
    """Recompute the project boundary from the current farm boundaries (new version; the old one is superseded)."""
    db.flush()
    previous = repo.current_boundary(db, p.id)
    ids = _current_farm_boundary_ids(db, p)
    if previous is not None:
        previous.status, previous.superseded_at = "SUPERSEDED", utcnow()
        db.flush()
    if not ids:
        p.current_boundary_id = None
        if previous is not None:
            record(db, ctx, "PROJECT_BOUNDARY_COMPUTED", ENTITY, p.id, {"boundary_id": previous.id, "version": previous.version},
                   {"boundary_id": None, "farm_count": 0}, organization_id=p.organization_id)
        return None
    u = gis.project_union(db, p.id)
    notes = []
    valid = u.valid and u.wkt is not None and (u.geometry_type in ("Polygon", "MultiPolygon"))
    if not valid:
        notes.append(f"SQL Server reported an invalid or unsupported project geometry ({u.geometry_type}).")
    internal = max(0.0, u.sum_m2 - u.area_m2)
    if internal > get_settings().FARM_OVERLAP_MIN_AREA_M2:
        notes.append(f"Participating farms overlap each other by {internal / 10_000:,.4f} ha; the overlap is counted once in the project area.")
    version = max((b.version for b in repo.boundaries(db, p.id)), default=0) + 1
    b = ProjectBoundary(project_id=p.id, version=version, boundary=u.wkt, area_m2=Decimal(f"{u.area_m2:.2f}"),
                        area_hectares=Decimal(f"{u.area_m2 / 10_000:.4f}"), sum_farm_area_hectares=Decimal(f"{u.sum_m2 / 10_000:.4f}"),
                        internal_overlap_hectares=Decimal(f"{internal / 10_000:.4f}"), farm_count=len(ids),
                        farm_boundary_ids=json.dumps(ids), is_valid=valid, validation_notes="\n".join(notes) or None,
                        computed_by=ctx.user_id)
    db.add(b)
    db.flush()
    hits = [h for h in gis.project_overlaps(db, b.id, p.id, p.environment) if h[2] > get_settings().FARM_OVERLAP_MIN_AREA_M2]
    b.project_overlaps = json.dumps([{"project_id": str(pid), "organization_id": str(oid), "overlap_m2": round(m2, 2)} for pid, oid, m2 in hits])
    p.current_boundary_id = b.id
    record(db, ctx, "PROJECT_BOUNDARY_COMPUTED", ENTITY, p.id,
           {"boundary_id": previous.id, "version": previous.version, "area_hectares": previous.area_hectares} if previous else None,
           {"boundary_id": b.id, "version": version, "area_hectares": b.area_hectares, "farm_count": b.farm_count,
            "internal_overlap_hectares": b.internal_overlap_hectares, "other_project_overlaps": len(hits), "is_valid": valid},
           organization_id=p.organization_id)
    return b


def recompute(db: Session, ctx: RequestContext, principal: Principal, project_id: uuid.UUID) -> ProjectBoundary | None:
    p = get_project(db, principal, project_id, P.PROJECTS_MANAGE)
    require_status(p, EDITABLE, "Recomputing the project boundary")
    b = recompute_boundary(db, ctx, p)
    db.commit()
    return b


def review_boundary(db: Session, ctx: RequestContext, principal: Principal, project_id: uuid.UUID, decision: str, notes: str) -> ProjectBoundary:
    """GIS review of the current project boundary version (farms.review in the project's organization)."""
    p = get_project(db, principal, project_id, P.PROJECTS_READ)
    principal.require_in_org(P.FARMS_REVIEW, p.organization_id)
    b = repo.current_boundary(db, p.id)
    if b is None:
        raise Conflict("The project has no boundary yet.", error_code="NO_PROJECT_BOUNDARY")
    if boundary_is_stale(db, p):
        raise Conflict("Farm boundaries changed since this version was computed; recompute it before reviewing.", error_code="BOUNDARY_STALE")
    old = b.review_status
    b.review_status, b.reviewed_by, b.reviewed_at, b.review_notes = decision, principal.user_id, utcnow(), notes
    record(db, ctx, "PROJECT_BOUNDARY_REVIEWED", ENTITY, p.id, {"boundary_id": b.id, "version": b.version, "review_status": old},
           {"review_status": decision}, notes, organization_id=p.organization_id)
    db.commit()
    return b


def boundary_geojson(b: ProjectBoundary) -> dict[str, Any]:
    return wkt_to_geojson(b.boundary)


# ---------------------------------------------------------------- readiness facts
def farm_facts(db: Session, p: Project, farms: list[ProjectFarm]) -> dict[str, Any]:
    rights = [r for r in repo.carbon_rights(db, p.id) if r.status == "ACTIVE"]
    by_pf = {r.project_farm_id for r in rights}
    all_verified = True
    open_overlaps = 0
    for pf in farms:
        farm = farm_repo.get(db, pf.farm_id)
        farmer = db.get(Farmer, pf.farmer_id)
        if farm is None or farm.status != "VERIFIED" or farmer is None or farmer.status != "ACTIVE":
            all_verified = False
        open_overlaps += db.query(FarmOverlapCheck).filter(
            ((FarmOverlapCheck.farm_id == pf.farm_id) | (FarmOverlapCheck.other_farm_id == pf.farm_id)),
            FarmOverlapCheck.status == "OPEN").count()
    b = repo.current_boundary(db, p.id)
    return {"all_verified": all_verified, "all_have_rights": all(pf.id in by_pf for pf in farms),
            "all_rights_verified": bool(rights) and all(r.verification_status == "VERIFIED" for r in rights),
            "boundary_ok": bool(b and b.is_valid) and not boundary_is_stale(db, p), "open_overlaps": open_overlaps}


# ---------------------------------------------------------------- farmer self-service
def my_participation(db: Session, principal: Principal) -> list[tuple[Project, ProjectFarm, Farm, list[ProjectCarbonRight]]]:
    """Projects the signed-in farmer's farms take part in (farmers.self). Only their own records are returned."""
    if not principal.has(P.FARMERS_SELF):
        raise PermissionDenied(details={"required_permission": P.FARMERS_SELF})
    farmer = db.scalars(select(Farmer).where(Farmer.user_id == principal.user_id)).first()
    if farmer is None:
        return []
    out = []
    for pf in db.scalars(select(ProjectFarm).where(ProjectFarm.farmer_id == farmer.id).order_by(ProjectFarm.added_at)).all():
        p = repo.get(db, pf.project_id)
        farm = farm_repo.get(db, pf.farm_id)
        if p and farm:
            out.append((p, pf, farm, repo.carbon_rights(db, p.id, pf.id)))
    return out
