"""Stratification, sampling designs, sampling points, assignments, relocations and field collection
(spec section 13, 14, 7.7).

Rules enforced here:
- strata group participating farms; geometry/area = SQL Server union of the farms' current boundaries; a farm belongs
  to at most one current stratum; approved strata are never edited (a change creates a new version)
- methodology SAMPLING parameters (if the locked version configures them) are enforced on designs; otherwise the design
  is PROJECT_CONFIGURED with CONFIGURATION_REQUIRED gaps — no sample count is ever derived from area
- points are generated only from an APPROVED design version, once, with a recorded seed; every point is inside a
  stratum farm's current boundary (SQL Server STIntersects), inside the project boundary, and not a duplicate
- a point never moves silently: relocations record old/new location, reason, requester and an approver (≠ requester)
- field collectors work only on points assigned to them; reviewers never review their own collection; an accepted
  record is corrected by a new version that supersedes it
"""
import json
import math
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
    FarmBoundary,
    FieldCollectionRecord,
    MonitoringPeriod,
    MrvEvidence,
    MrvPlan,
    Project,
    ProjectFarm,
    ProjectStratum,
    SamplingAssignment,
    SamplingDesign,
    SamplingDesignStratum,
    SamplingDesignVersion,
    SamplingPoint,
    SamplingPointRelocation,
    StratumCharacteristic,
    StratumFarm,
    User,
)
from app.models.base import utcnow
from app.repositories import gis
from app.repositories import projects as project_repo
from app.repositories.sequences import next_code
from app.rules import sampling_points as gen
from app.rules.geometry_io import wkt_to_geojson
from app.schemas.mrv import CollectionUpdate, DesignIn, DesignParams, StratumIn, StratumUpdate
from app.security.permissions import P
from app.security.principal import Principal, load_grants
from app.services import field_rules as rules
from app.services import mrv_access, mrv_service
from app.services.mrv_requirements import requirements
from app.services.notification_service import notify
from app.services.workflows import FIELD_COLLECTION_MACHINE

ENTITY = "project"
# Platform operational checklist for a field collection (not a methodology protocol; configurable later).
POINT_OPEN_PERIOD = ("PLANNED", "ACTIVE", "DATA_COLLECTION")


def _audit(db: Session, ctx: RequestContext, p: Project, action: str, new: dict[str, Any], old: dict[str, Any] | None = None,
           reason: str | None = None) -> None:
    record(db, ctx, action, ENTITY, p.id, old, new, reason, organization_id=p.organization_id)


# ---------------------------------------------------------------- strata
def strata(db: Session, project_id: uuid.UUID, include_history: bool = False) -> list[ProjectStratum]:
    stmt = select(ProjectStratum).where(ProjectStratum.project_id == project_id)
    if not include_history:
        stmt = stmt.where(ProjectStratum.status.in_(["DRAFT", "APPROVED"]))
    return list(db.scalars(stmt.order_by(ProjectStratum.code, ProjectStratum.version)).all())


def stratum_farms(db: Session, stratum_id: uuid.UUID) -> list[StratumFarm]:
    return list(db.scalars(select(StratumFarm).where(StratumFarm.stratum_id == stratum_id)).all())


def characteristics(db: Session, stratum_id: uuid.UUID) -> list[StratumCharacteristic]:
    return list(db.scalars(select(StratumCharacteristic).where(StratumCharacteristic.stratum_id == stratum_id)).all())


def required_characteristics(db: Session, p: Project) -> list[str]:
    """Stratification variables the locked methodology version configures (SAMPLING rule `stratification_variables`)."""
    _, v = mrv_access.locked_methodology(db, p)
    val = requirements(db, v).value("stratification_variables")
    return [str(x).upper() for x in val] if isinstance(val, list) else []


def get_stratum(db: Session, principal: Principal, stratum_id: uuid.UUID, *codes: str) -> tuple[ProjectStratum, Project]:
    s = db.scalars(select(ProjectStratum).where(ProjectStratum.id == stratum_id).execution_options(populate_existing=True)).first()
    if s is None:
        raise NotFound("Stratum not found.", error_code="STRATUM_NOT_FOUND")
    return s, mrv_access.project(db, principal, s.project_id, *codes)


def _set_farms(db: Session, p: Project, s: ProjectStratum, farm_ids: list[uuid.UUID]) -> None:
    active = {pf.farm_id for pf in project_repo.project_farms(db, p.id, active_only=True)}
    unknown = [f for f in farm_ids if f not in active]
    if unknown:
        raise ValidationFailed("Only farms participating in the project can be stratified.", error_code="FARM_NOT_IN_PROJECT",
                               details={"farm_ids": [str(f) for f in unknown]})
    taken = {sf.farm_id: o.code for o in strata(db, p.id) if o.record_id != s.record_id and o.is_current for sf in stratum_farms(db, o.id)}
    clash = [f for f in farm_ids if f in taken]
    if clash:
        raise Conflict("A farm can belong to only one current stratum.", error_code="FARM_ALREADY_STRATIFIED",
                       details={"farms": {str(f): taken[f] for f in clash}})
    for sf in stratum_farms(db, s.id):
        db.delete(sf)
    db.flush()
    bids = []
    for fid in dict.fromkeys(farm_ids):
        farm = db.get(Farm, fid)
        if farm is None or farm.current_boundary_id is None:
            raise ValidationFailed("Every stratum farm needs a boundary.", error_code="FARM_HAS_NO_BOUNDARY")
        db.add(StratumFarm(stratum_id=s.id, farm_id=fid, farm_boundary_id=farm.current_boundary_id))
        bids.append(farm.current_boundary_id)
    wkt, area_m2, valid, _ = gis.union_of_boundaries(db, bids)
    if not wkt or not valid:
        raise ValidationFailed("SQL Server could not build a valid stratum geometry from these farms.", error_code="INVALID_STRATUM_GEOMETRY")
    s.geometry, s.area_hectares, s.farm_boundary_ids = wkt, Decimal(f"{area_m2 / 10_000:.4f}"), json.dumps(sorted(str(b) for b in bids))


def _set_characteristics(db: Session, s: ProjectStratum, items: list[Any], required: list[str]) -> None:
    for c in characteristics(db, s.id):
        db.delete(c)
    db.flush()
    for c in items:
        db.add(StratumCharacteristic(stratum_id=s.id, characteristic=c.characteristic, value=c.value, source=c.source,
                                     required_by_methodology=c.characteristic in required))


def create_stratum(db: Session, ctx: RequestContext, principal: Principal, project_id: uuid.UUID, data: StratumIn) -> ProjectStratum:
    p = mrv_access.project(db, principal, project_id, P.SAMPLING_MANAGE)
    mrv_access.locked_methodology(db, p)
    if any(o.code == data.code and o.status in ("DRAFT", "APPROVED") for o in strata(db, p.id)):
        raise Conflict(f"Stratum {data.code} already exists.", error_code="STRATUM_EXISTS")
    s = ProjectStratum(project_id=p.id, record_id=uuid.uuid4(), version=1, is_current=True, code=data.code, name=data.name,
                       description=data.description, criteria=json.dumps(data.criteria) if data.criteria else None, created_by=principal.user_id)
    db.add(s)
    db.flush()
    _set_farms(db, p, s, data.farm_ids)
    _set_characteristics(db, s, data.characteristics, required_characteristics(db, p))
    db.flush()
    _audit(db, ctx, p, "STRATUM_CREATED", {"stratum_id": s.id, "code": s.code, "version": 1, "farm_ids": data.farm_ids,
                                          "area_hectares": s.area_hectares,
                                          "characteristics": {c.characteristic: c.value for c in data.characteristics}})
    db.commit()
    return s


def update_stratum(db: Session, ctx: RequestContext, principal: Principal, stratum_id: uuid.UUID, data: StratumUpdate) -> ProjectStratum:
    """DRAFT: edited in place. APPROVED: a new DRAFT version is created (the approved one stays in force until replaced)."""
    s, p = get_stratum(db, principal, stratum_id, P.SAMPLING_MANAGE)
    if s.status not in ("DRAFT", "APPROVED"):
        raise Conflict(f"A {s.status} stratum cannot be changed.", error_code="STRATUM_NOT_EDITABLE")
    target = s
    if s.status == "APPROVED":
        if not data.reason:
            raise ValidationFailed("Give a reason for revising an approved stratum.", error_code="REASON_REQUIRED")
        if any(o.record_id == s.record_id and o.status == "DRAFT" for o in strata(db, p.id)):
            raise Conflict("A revision of this stratum is already in draft; edit that version.", error_code="REVISION_EXISTS")
        target = ProjectStratum(project_id=p.id, record_id=s.record_id, version=s.version + 1, is_current=False, code=s.code, name=s.name,
                                description=s.description, criteria=s.criteria, created_by=principal.user_id, change_reason=data.reason)
        db.add(target)
        db.flush()
        _set_farms(db, p, target, data.farm_ids or [sf.farm_id for sf in stratum_farms(db, s.id)])
        _set_characteristics(db, target, data.characteristics if data.characteristics is not None else characteristics(db, s.id),
                             required_characteristics(db, p))
    else:
        if data.farm_ids is not None:
            _set_farms(db, p, target, data.farm_ids)
        if data.characteristics is not None:
            _set_characteristics(db, target, data.characteristics, required_characteristics(db, p))
    for k in ("name", "description"):
        if getattr(data, k) is not None:
            setattr(target, k, getattr(data, k))
    if data.criteria is not None:
        target.criteria = json.dumps(data.criteria)
    db.flush()
    _audit(db, ctx, p, "STRATUM_UPDATED", {"stratum_id": target.id, "record_id": target.record_id, "version": target.version,
                                          "new_version": target is not s, "area_hectares": target.area_hectares}, None, data.reason)
    db.commit()
    return target


def approve_stratum(db: Session, ctx: RequestContext, principal: Principal, stratum_id: uuid.UUID, notes: str) -> ProjectStratum:
    s, p = get_stratum(db, principal, stratum_id, P.SAMPLING_REVIEW)
    if s.status != "DRAFT":
        raise Conflict("Only a DRAFT stratum can be approved.", error_code="STRATUM_NOT_DRAFT")
    if s.created_by == principal.user_id:
        raise PermissionDenied("You created this stratum version, so someone else must approve it.", error_code="SEPARATION_OF_DUTIES")
    have = {c.characteristic for c in characteristics(db, s.id)}
    missing = [c for c in required_characteristics(db, p) if c not in have]
    if missing:
        raise Conflict("The methodology requires these stratification variables: " + ", ".join(missing) + ".",
                       error_code="CHARACTERISTICS_REQUIRED", details={"missing": missing})
    for old in strata(db, p.id):
        if old.record_id == s.record_id and old.id != s.id and old.status == "APPROVED":
            old.status, old.is_current = "SUPERSEDED", False
            db.flush()
    s.status, s.is_current, s.approved_by, s.approved_at = "APPROVED", True, principal.user_id, utcnow()
    _audit(db, ctx, p, "STRATUM_APPROVED", {"stratum_id": s.id, "code": s.code, "version": s.version}, None, notes)
    db.commit()
    return s


# ---------------------------------------------------------------- sampling designs
def get_design(db: Session, principal: Principal, design_id: uuid.UUID, *codes: str) -> tuple[SamplingDesign, Project]:
    d = db.get(SamplingDesign, design_id)
    if d is None:
        raise NotFound("Sampling design not found.", error_code="SAMPLING_DESIGN_NOT_FOUND")
    return d, mrv_access.project(db, principal, d.project_id, *codes)


def design_versions(db: Session, design_id: uuid.UUID) -> list[SamplingDesignVersion]:
    return list(db.scalars(select(SamplingDesignVersion).where(SamplingDesignVersion.design_id == design_id)
                           .order_by(SamplingDesignVersion.version.desc()).execution_options(populate_existing=True)).all())


def allocations(db: Session, version_id: uuid.UUID) -> list[SamplingDesignStratum]:
    return list(db.scalars(select(SamplingDesignStratum).where(SamplingDesignStratum.design_version_id == version_id)).all())


def _check_against_methodology(db: Session, p: Project, data: DesignParams) -> tuple[str, list[str]]:
    """Enforce configured methodology SAMPLING parameters; report the rest as CONFIGURATION_REQUIRED gaps."""
    _, v = mrv_access.locked_methodology(db, p)
    req = requirements(db, v)
    errors: list[str] = []
    gaps: list[str] = []

    def configured(key: str) -> Any:
        val = req.value(key)
        if val is None:
            gaps.append(f"{key} (not configured by the methodology version; project-configured value used)")
        return val

    top, bottom = configured("depth_top_cm"), configured("depth_bottom_cm")
    if (top is not None and Decimal(str(top)) != data.depth_top_cm) or (bottom is not None and Decimal(str(bottom)) != data.depth_bottom_cm):
        errors.append(f"sampling depth must be {top}-{bottom} cm")
    design = configured("statistical_design")
    if design is not None and str(design).upper() != data.statistical_design:
        errors.append(f"statistical design must be {design}")
    min_n = configured("min_samples_per_stratum")
    if min_n is not None and any(a.sample_count < int(min_n) for a in data.allocations):
        errors.append(f"each stratum needs at least {min_n} samples")
    prec = configured("target_precision_pct")
    if prec is not None and (data.target_precision_pct is None or data.target_precision_pct > Decimal(str(prec))):
        errors.append(f"target precision must be {prec}% or better")
    conf = configured("confidence_level_pct")
    if conf is not None and (data.confidence_level_pct is None or data.confidence_level_pct < Decimal(str(conf))):
        errors.append(f"confidence level must be at least {conf}%")
    if errors:
        raise ValidationFailed("The design does not meet the methodology version's sampling requirements: " + "; ".join(errors) + ".",
                               error_code="METHODOLOGY_REQUIREMENT", details={"errors": errors})
    return ("METHODOLOGY" if not gaps else "PROJECT_CONFIGURED"), gaps


def _new_version(db: Session, p: Project, design: SamplingDesign, version: int, data: DesignParams, principal: Principal) -> SamplingDesignVersion:
    source, gaps = _check_against_methodology(db, p, data)
    approved = {s.id: s for s in strata(db, p.id) if s.status == "APPROVED"}
    for a in data.allocations:
        if a.stratum_id not in approved:
            raise ValidationFailed("Sampling designs use APPROVED strata of this project only.", error_code="STRATUM_NOT_APPROVED",
                                   details={"stratum_id": str(a.stratum_id)})
    if len({a.stratum_id for a in data.allocations}) != len(data.allocations):
        raise ValidationFailed("Each stratum appears once in the allocation.", error_code="DUPLICATE_ALLOCATION")
    seed = data.random_seed if data.random_seed is not None else uuid.uuid4().int % 2_147_483_647
    _, mv = mrv_access.locked_methodology(db, p)
    dv = SamplingDesignVersion(design_id=design.id, version=version, statistical_design=data.statistical_design,
                               target_precision_pct=data.target_precision_pct, confidence_level_pct=data.confidence_level_pct,
                               variability_cv_pct=data.variability_cv_pct, min_detectable_difference=data.min_detectable_difference,
                               sampling_method=data.sampling_method, depth_top_cm=data.depth_top_cm, depth_bottom_cm=data.depth_bottom_cm,
                               min_distance_m=data.min_distance_m, repeat_sampling=data.repeat_sampling, random_seed=seed,
                               requirement_source=source, configuration_status="CONFIGURED" if not gaps else "CONFIGURATION_REQUIRED",
                               configuration_gaps=json.dumps(gaps) if gaps else None, field_rules=json.dumps(rules.resolve(db, mv)),
                               notes=data.notes, created_by=principal.user_id)
    db.add(dv)
    db.flush()
    for a in data.allocations:
        db.add(SamplingDesignStratum(design_version_id=dv.id, stratum_id=a.stratum_id, sample_count=a.sample_count,
                                     allocation_basis=a.allocation_basis))
    db.flush()
    return dv


def create_design(db: Session, ctx: RequestContext, principal: Principal, data: DesignIn) -> SamplingDesign:
    mp, p = mrv_service.get_period(db, principal, data.monitoring_period_id, P.SAMPLING_MANAGE)
    if mp.status not in POINT_OPEN_PERIOD:
        raise Conflict(f"Sampling designs are prepared while the period is planned or running (it is {mp.status}).", error_code="PERIOD_NOT_OPEN")
    plan = db.get(MrvPlan, mp.mrv_plan_id)
    assert plan is not None
    if db.scalars(select(SamplingDesign).where(SamplingDesign.monitoring_period_id == mp.id, SamplingDesign.code == data.code)).first():
        raise Conflict(f"Design {data.code} already exists for this period.", error_code="DESIGN_EXISTS")
    _check_against_methodology(db, p, data)  # validate before anything is written
    d = SamplingDesign(project_id=p.id, mrv_plan_id=plan.id, monitoring_period_id=mp.id, methodology_id=plan.methodology_id,
                       methodology_version_id=plan.methodology_version_id, code=data.code, name=data.name, created_by=principal.user_id)
    db.add(d)
    db.flush()
    dv = _new_version(db, p, d, 1, data, principal)
    _audit(db, ctx, p, "SAMPLING_DESIGN_CREATED", {"design_id": d.id, "code": d.code, "monitoring_period_id": mp.id, "version_id": dv.id,
                                                  "statistical_design": dv.statistical_design, "requirement_source": dv.requirement_source,
                                                  "allocations": {str(a.stratum_id): a.sample_count for a in data.allocations}})
    db.commit()
    return d


def add_design_version(db: Session, ctx: RequestContext, principal: Principal, design_id: uuid.UUID, data: DesignParams) -> SamplingDesignVersion:
    d, p = get_design(db, principal, design_id, P.SAMPLING_MANAGE)
    vs = design_versions(db, d.id)
    if any(v.status == "DRAFT" for v in vs):
        raise Conflict("A draft version already exists.", error_code="DRAFT_EXISTS")
    dv = _new_version(db, p, d, (vs[0].version if vs else 0) + 1, data, principal)
    _audit(db, ctx, p, "SAMPLING_DESIGN_VERSION_CREATED", {"design_id": d.id, "version_id": dv.id, "version": dv.version})
    db.commit()
    return dv


def approve_design_version(db: Session, ctx: RequestContext, principal: Principal, design_id: uuid.UUID, version_id: uuid.UUID,
                           notes: str) -> SamplingDesignVersion:
    d, p = get_design(db, principal, design_id, P.SAMPLING_REVIEW)
    vs = design_versions(db, d.id)
    dv = next((v for v in vs if v.id == version_id), None)
    if dv is None or dv.status != "DRAFT":
        raise Conflict("Only a DRAFT version of this design can be approved.", error_code="VERSION_NOT_DRAFT")
    if dv.created_by == principal.user_id:
        raise PermissionDenied("You created this design version, so someone else must approve it.", error_code="SEPARATION_OF_DUTIES")
    for old in vs:
        if old.status == "APPROVED":
            old.status = "SUPERSEDED"
            db.flush()
    dv.status, dv.approved_by, dv.approved_at = "APPROVED", principal.user_id, utcnow()
    _audit(db, ctx, p, "SAMPLING_DESIGN_APPROVED", {"design_id": d.id, "version_id": dv.id, "version": dv.version,
                                                   "configuration_status": dv.configuration_status}, None, notes)
    db.commit()
    return dv


# ---------------------------------------------------------------- point generation
def _coords_of(db: Session, boundary_ids: list[uuid.UUID]) -> list[tuple[float, float]]:
    out: list[tuple[float, float]] = []
    for bid in boundary_ids:
        b = db.get(FarmBoundary, bid)
        if b is None:
            continue
        geo = wkt_to_geojson(b.boundary)
        polys = [geo["coordinates"]] if geo["type"] == "Polygon" else geo["coordinates"]
        out += [(c[0], c[1]) for poly in polys for ring in poly for c in ring]
    return out


def _take(db: Session, cands: list[tuple[float, float]], bids: list[uuid.UUID], accepted: list[tuple[float, float, uuid.UUID, uuid.UUID]],
          limit: int, period_id: uuid.UUID, min_dist: float, project_boundary_id: uuid.UUID | None) -> None:
    """Keep candidates that SQL Server places inside a stratum farm (and the project boundary), that are not duplicates of
    existing points, and that keep the minimum spacing. Appends (lat, lon, boundary_id, farm_id) to `accepted`."""
    inside = gis.points_in_boundaries(db, cands, bids)
    ordered = [(cands[k], inside[k]) for k in sorted(inside)]
    if not ordered:
        return
    near = gis.nearest_existing_point_m(db, period_id, [c for c, _ in ordered])
    fresh = [(c, b) for k, (c, b) in enumerate(ordered) if near.get(k, math.inf) >= min_dist]
    keep = gen.accept_spaced([c for c, _ in fresh], [(a[0], a[1]) for a in accepted], min_dist, limit)
    lookup = dict(fresh)
    for c in keep:
        if project_boundary_id is None or gis.point_inside_project(db, project_boundary_id, c[0], c[1]):
            accepted.append((c[0], c[1], *lookup[c]))


def generate_points(db: Session, ctx: RequestContext, principal: Principal, design_id: uuid.UUID) -> list[SamplingPoint]:
    d, p = get_design(db, principal, design_id, P.SAMPLING_MANAGE)
    mp = db.get(MonitoringPeriod, d.monitoring_period_id)
    assert mp is not None
    if mp.status not in POINT_OPEN_PERIOD:
        raise Conflict(f"Points are generated while the period is planned or running (it is {mp.status}).", error_code="PERIOD_NOT_OPEN")
    dv = next((v for v in design_versions(db, d.id) if v.status == "APPROVED"), None)
    if dv is None:
        raise Conflict("Approve a design version before generating points.", error_code="DESIGN_NOT_APPROVED")
    if dv.points_generated_at is not None:
        raise Conflict("Points were already generated for this design version. Create a new version to change them.",
                       error_code="POINTS_ALREADY_GENERATED")
    s = get_settings()
    project_boundary = project_repo.current_boundary(db, p.id)
    min_dist = max(float(dv.min_distance_m or 0), rules.of_design(dv)["duplicate_distance_m"])
    created: list[SamplingPoint] = []
    placed: list[tuple[ProjectStratum, list[tuple[float, float, uuid.UUID, uuid.UUID]]]] = []
    for i, alloc in enumerate(sorted(allocations(db, dv.id), key=lambda a: str(a.stratum_id))):
        st = db.get(ProjectStratum, alloc.stratum_id)
        assert st is not None
        bids = [uuid.UUID(x) for x in json.loads(st.farm_boundary_ids or "[]")]
        box = gen.bbox_of(_coords_of(db, bids))
        seed = dv.random_seed + i * 7919
        accepted: list[tuple[float, float, uuid.UUID, uuid.UUID]] = []
        attempts = 0
        limit = alloc.sample_count * s.SAMPLING_MAX_ATTEMPTS_PER_POINT

        if dv.statistical_design == "SYSTEMATIC_GRID":
            shrink = 1.0
            for _ in range(12):
                _take(db, gen.grid_candidates(box, float(st.area_hectares or 0) * 10_000, alloc.sample_count, seed, shrink), bids, accepted,
                      alloc.sample_count, mp.id, min_dist, project_boundary.id if project_boundary else None)
                if len(accepted) >= alloc.sample_count:
                    break
                accepted.clear()
                shrink *= 0.85
            accepted = accepted[:alloc.sample_count]
        else:
            for batch in gen.random_candidates(box, seed, max(20, alloc.sample_count * 10)):
                attempts += len(batch)
                _take(db, batch, bids, accepted, alloc.sample_count, mp.id, min_dist, project_boundary.id if project_boundary else None)
                if len(accepted) >= alloc.sample_count or attempts >= limit:
                    break
        if len(accepted) < alloc.sample_count:
            raise Conflict(f"Could only place {len(accepted)} of {alloc.sample_count} points in stratum {st.code} with the configured spacing.",
                           error_code="INSUFFICIENT_AREA")
        placed.append((st, list(accepted)))
    for st, accepted in placed:  # rows are created only once every stratum could be placed
        for n, (lat, lon, bid, fid) in enumerate(accepted, start=1):
            sp = SamplingPoint(point_code=next_code(db, "sampling_point", mp.start_date.year), project_id=p.id, monitoring_period_id=mp.id,
                               design_version_id=dv.id, stratum_id=st.id, farm_id=fid, farm_boundary_id=bid, sequence=n,
                               location=f"POINT ({lon:.7f} {lat:.7f})", latitude=Decimal(f"{lat:.7f}"), longitude=Decimal(f"{lon:.7f}"),
                               planned_depth_top_cm=dv.depth_top_cm, planned_depth_bottom_cm=dv.depth_bottom_cm)
            db.add(sp)
            created.append(sp)
    # points of earlier (superseded) versions that were never collected are cancelled — not deleted
    for old in db.scalars(select(SamplingPoint).where(SamplingPoint.monitoring_period_id == mp.id, SamplingPoint.design_version_id != dv.id,
                                                      SamplingPoint.status.in_(["PLANNED", "ASSIGNED"]))).all():
        old.status, old.status_reason = "CANCELLED", f"Replaced by design {d.code} v{dv.version}"
    dv.points_generated_at = utcnow()
    db.flush()
    _audit(db, ctx, p, "SAMPLING_POINT_CREATED", {"design_id": d.id, "version_id": dv.id, "count": len(created), "seed": dv.random_seed,
                                                 "point_codes": [x.point_code for x in created]})
    db.commit()
    return created


# ---------------------------------------------------------------- points
def points_of_period(db: Session, period_id: uuid.UUID) -> list[SamplingPoint]:
    return list(db.scalars(select(SamplingPoint).where(SamplingPoint.monitoring_period_id == period_id).order_by(SamplingPoint.point_code)).all())


def list_points(db: Session, principal: Principal, project_id: uuid.UUID | None, period_id: uuid.UUID | None, mine: bool) -> list[SamplingPoint]:
    stmt = select(SamplingPoint)
    if mine or not principal.has(P.MRV_READ):
        stmt = stmt.where(SamplingPoint.assigned_collector_id == principal.user_id, SamplingPoint.status.in_(["ASSIGNED", "COLLECTED"]))
    else:
        scope = principal.scope_for(P.MRV_READ)
        if scope is not None:
            stmt = stmt.join(Project, Project.id == SamplingPoint.project_id).where(Project.organization_id.in_(list(scope)))
    if project_id:
        stmt = stmt.where(SamplingPoint.project_id == project_id)
    if period_id:
        stmt = stmt.where(SamplingPoint.monitoring_period_id == period_id)
    return list(db.scalars(stmt.order_by(SamplingPoint.point_code).limit(2000)).all())


def get_point(db: Session, principal: Principal, point_id: uuid.UUID, *codes: str) -> tuple[SamplingPoint, Project]:
    sp = db.scalars(select(SamplingPoint).where(SamplingPoint.id == point_id).execution_options(populate_existing=True)).first()
    if sp is None:
        raise NotFound("Sampling point not found.", error_code="SAMPLING_POINT_NOT_FOUND")
    p = db.get(Project, sp.project_id)
    assert p is not None
    if sp.assigned_collector_id == principal.user_id and principal.can_in_org(P.SAMPLING_COLLECT, p.organization_id) \
            and (not codes or P.SAMPLING_COLLECT in codes):
        return sp, p
    staff = tuple(c for c in codes if c != P.SAMPLING_COLLECT) or (P.MRV_READ,)
    return sp, mrv_access.project(db, principal, sp.project_id, *staff)


def _holds(db: Session, user_id: uuid.UUID, code: str, organization_id: uuid.UUID) -> bool:
    return any(code in g.permissions and g.organization_id in (None, organization_id) for g in load_grants(db, user_id))


def collectors(db: Session, principal: Principal, project_id: uuid.UUID) -> list[tuple[uuid.UUID, str, str]]:
    """Active users of the project's organization who may collect samples: (id, full name, email)."""
    from app.models import User, UserRole
    p = mrv_access.project(db, principal, project_id, P.SAMPLING_ASSIGN)
    ids = set(db.scalars(select(UserRole.user_id).where((UserRole.organization_id == p.organization_id) | UserRole.organization_id.is_(None)
                                                          )).all())
    users = db.scalars(select(User).where(User.id.in_(ids), User.status == "ACTIVE").order_by(User.full_name)).all() if ids else []
    return [(u.id, u.full_name, u.email) for u in users if _holds(db, u.id, P.SAMPLING_COLLECT, p.organization_id)]


def assign(db: Session, ctx: RequestContext, principal: Principal, point_id: uuid.UUID, collector_id: uuid.UUID, planned_date: date | None,
           instructions: str | None, commit: bool = True) -> SamplingPoint:
    sp, p = get_point(db, principal, point_id, P.SAMPLING_ASSIGN)
    mp = db.get(MonitoringPeriod, sp.monitoring_period_id)
    assert mp is not None
    if mp.status not in POINT_OPEN_PERIOD:
        raise Conflict("Points can be assigned while the period is planned or running.", error_code="PERIOD_NOT_OPEN")
    if sp.status not in ("PLANNED", "ASSIGNED"):
        raise Conflict(f"A {sp.status} point cannot be (re)assigned.", error_code="POINT_NOT_ASSIGNABLE")
    user = db.get(User, collector_id)
    if user is None or user.status != "ACTIVE" or user.environment != p.environment or not _holds(db, collector_id, P.SAMPLING_COLLECT,
                                                                                                  p.organization_id):
        raise ValidationFailed("The collector must be an active user with field-collection rights in this organization.",
                               error_code="NOT_A_COLLECTOR")
    if planned_date and not (mp.start_date <= planned_date <= mp.end_date):
        raise ValidationFailed("The planned date must fall within the monitoring period.", error_code="OUTSIDE_PERIOD")
    old = sp.assigned_collector_id
    for a in db.scalars(select(SamplingAssignment).where(SamplingAssignment.sampling_point_id == sp.id, SamplingAssignment.status == "ACTIVE")).all():
        a.status, a.ended_at = "REASSIGNED", utcnow()
    db.flush()
    db.add(SamplingAssignment(sampling_point_id=sp.id, collector_id=collector_id, planned_date=planned_date, instructions=instructions,
                              assigned_by=principal.user_id))
    sp.assigned_collector_id, sp.planned_date, sp.status = collector_id, planned_date, "ASSIGNED"
    _audit(db, ctx, p, "SAMPLING_POINT_ASSIGNED", {"point_id": sp.id, "point_code": sp.point_code, "collector_id": collector_id,
                                                  "planned_date": planned_date}, {"collector_id": old} if old else None)
    if commit:
        notify(db, [collector_id], "SAMPLE_ASSIGNED", f"Sampling point assigned: {sp.point_code}", instructions, ENTITY, p.id, "/field")
        db.commit()
    return sp


def bulk_assign(db: Session, ctx: RequestContext, principal: Principal, point_ids: list[uuid.UUID], collector_id: uuid.UUID,
                planned_date: date | None, instructions: str | None) -> list[SamplingPoint]:
    out = [assign(db, ctx, principal, pid, collector_id, planned_date, instructions, commit=False) for pid in dict.fromkeys(point_ids)]
    if out:
        p = db.get(Project, out[0].project_id)
        notify(db, [collector_id], "SAMPLE_ASSIGNED", f"{len(out)} sampling point(s) assigned", instructions, ENTITY, out[0].project_id, "/field")
        assert p is not None
    db.commit()
    return out


def skip_point(db: Session, ctx: RequestContext, principal: Principal, point_id: uuid.UUID, reason: str) -> SamplingPoint:
    sp, p = get_point(db, principal, point_id, P.SAMPLING_REVIEW)
    if sp.status not in ("PLANNED", "ASSIGNED"):
        raise Conflict(f"A {sp.status} point cannot be skipped.", error_code="POINT_NOT_SKIPPABLE")
    old = sp.status
    sp.status, sp.status_reason = "SKIPPED", reason
    _audit(db, ctx, p, "SAMPLING_POINT_UPDATED", {"point_id": sp.id, "point_code": sp.point_code, "status": "SKIPPED"}, {"status": old}, reason)
    db.commit()
    return sp


def request_relocation(db: Session, ctx: RequestContext, principal: Principal, point_id: uuid.UUID, lat: float, lon: float,
                       reason: str) -> SamplingPointRelocation:
    sp, p = get_point(db, principal, point_id, P.SAMPLING_COLLECT, P.SAMPLING_MANAGE)
    if sp.status not in ("PLANNED", "ASSIGNED"):
        raise Conflict("Only points not yet collected can be relocated.", error_code="POINT_NOT_RELOCATABLE")
    if db.scalars(select(SamplingPointRelocation).where(SamplingPointRelocation.sampling_point_id == sp.id,
                                                        SamplingPointRelocation.status == "PENDING")).first():
        raise Conflict("A relocation request is already pending.", error_code="RELOCATION_PENDING")
    if not gis.point_inside_boundary(db, sp.farm_boundary_id, lat, lon):
        raise ValidationFailed("The new location is outside the point's farm boundary.", error_code="OUTSIDE_FARM")
    near = gis.nearest_existing_point_m(db, sp.monitoring_period_id, [(lat, lon)], exclude_id=sp.id)
    dv = db.get(SamplingDesignVersion, sp.design_version_id)
    assert dv is not None
    if near.get(0, math.inf) < rules.of_design(dv)["duplicate_distance_m"]:
        raise Conflict("Another sampling point is already at that location.", error_code="DUPLICATE_POINT")
    dist = gis.distance_to_point_m(db, sp.id, lat, lon)
    r = SamplingPointRelocation(sampling_point_id=sp.id, old_latitude=sp.latitude, old_longitude=sp.longitude, new_latitude=Decimal(f"{lat:.7f}"),
                                new_longitude=Decimal(f"{lon:.7f}"), distance_m=Decimal(f"{dist:.1f}"), reason=reason, requested_by=principal.user_id)
    db.add(r)
    db.flush()
    _audit(db, ctx, p, "SAMPLING_POINT_RELOCATION_REQUESTED", {"point_id": sp.id, "relocation_id": r.id, "from": [str(sp.latitude),
                                                                                                                  str(sp.longitude)],
                                                              "to": [str(r.new_latitude),
                                                                     str(r.new_longitude)], "distance_m": r.distance_m}, None, reason)
    db.commit()
    return r


def decide_relocation(db: Session, ctx: RequestContext, principal: Principal, relocation_id: uuid.UUID, decision: str,
                      notes: str) -> SamplingPointRelocation:
    r = db.get(SamplingPointRelocation, relocation_id)
    if r is None:
        raise NotFound("Relocation request not found.", error_code="RELOCATION_NOT_FOUND")
    sp, p = get_point(db, principal, r.sampling_point_id, P.SAMPLING_REVIEW)
    if r.status != "PENDING":
        raise Conflict("This request was already decided.", error_code="RELOCATION_DECIDED")
    if r.requested_by == principal.user_id:
        raise PermissionDenied("You requested this relocation, so someone else must decide it.", error_code="SEPARATION_OF_DUTIES")
    r.status, r.reviewed_by, r.reviewed_at, r.review_notes = decision, principal.user_id, utcnow(), notes
    if decision == "APPROVED":
        old = {"latitude": sp.latitude, "longitude": sp.longitude}
        sp.latitude, sp.longitude = r.new_latitude, r.new_longitude
        sp.location = f"POINT ({r.new_longitude} {r.new_latitude})"
        _audit(db, ctx, p, "SAMPLING_POINT_UPDATED", {"point_id": sp.id, "point_code": sp.point_code, "latitude": sp.latitude,
                                                     "longitude": sp.longitude, "relocation_id": r.id}, old, f"{r.reason} / approved: {notes}")
    else:
        _audit(db, ctx, p, "SAMPLING_POINT_RELOCATION_REJECTED", {"point_id": sp.id, "relocation_id": r.id}, None, notes)
    db.commit()
    return r


def relocations(db: Session, point_id: uuid.UUID) -> list[SamplingPointRelocation]:
    return list(db.scalars(select(SamplingPointRelocation).where(SamplingPointRelocation.sampling_point_id == point_id)
                           .order_by(SamplingPointRelocation.requested_at.desc())).all())


# ---------------------------------------------------------------- field collection
def collections_of_period(db: Session, period_id: uuid.UUID) -> list[FieldCollectionRecord]:
    return list(db.scalars(select(FieldCollectionRecord).where(FieldCollectionRecord.monitoring_period_id == period_id)
                           .order_by(FieldCollectionRecord.collection_code)).all())


def get_collection(db: Session, principal: Principal, collection_id: uuid.UUID, *codes: str) -> tuple[FieldCollectionRecord, Project]:
    fc = db.scalars(select(FieldCollectionRecord).where(FieldCollectionRecord.id == collection_id).execution_options(populate_existing=True)).first()
    if fc is None:
        raise NotFound("Field collection not found.", error_code="FIELD_COLLECTION_NOT_FOUND")
    p = db.get(Project, fc.project_id)
    assert p is not None
    if fc.collector_id == principal.user_id and principal.can_in_org(P.SAMPLING_COLLECT,
                                                                     p.organization_id) and (not codes or P.SAMPLING_COLLECT in codes):
        return fc, p
    staff = tuple(c for c in codes if c != P.SAMPLING_COLLECT) or (P.MRV_READ,)
    return fc, mrv_access.project(db, principal, fc.project_id, *staff)


def list_collections(db: Session, principal: Principal, project_id: uuid.UUID | None, period_id: uuid.UUID | None, mine: bool
                     ) -> list[FieldCollectionRecord]:
    stmt = select(FieldCollectionRecord)
    if mine or not principal.has(P.MRV_READ):
        stmt = stmt.where(FieldCollectionRecord.collector_id == principal.user_id)
    else:
        scope = principal.scope_for(P.MRV_READ)
        if scope is not None:
            stmt = stmt.join(Project, Project.id == FieldCollectionRecord.project_id).where(Project.organization_id.in_(list(scope)))
    if project_id:
        stmt = stmt.where(FieldCollectionRecord.project_id == project_id)
    if period_id:
        stmt = stmt.where(FieldCollectionRecord.monitoring_period_id == period_id)
    return list(db.scalars(stmt.order_by(FieldCollectionRecord.created_at.desc()).limit(2000)).all())


def start_collection(db: Session, ctx: RequestContext, principal: Principal, point_id: uuid.UUID) -> FieldCollectionRecord:
    sp, p = get_point(db, principal, point_id, P.SAMPLING_COLLECT)
    if sp.assigned_collector_id != principal.user_id:
        raise PermissionDenied("This sampling point is not assigned to you.", error_code="NOT_ASSIGNED")
    mp = db.get(MonitoringPeriod, sp.monitoring_period_id)
    assert mp is not None
    if mp.status != "DATA_COLLECTION":
        raise Conflict("Field collection is open only while the period is in DATA_COLLECTION.", error_code="PERIOD_NOT_COLLECTING")
    existing = [c for c in collections_of_period(db, mp.id) if c.sampling_point_id == sp.id and c.status != "SUPERSEDED"]
    if existing:
        raise Conflict(f"A collection record already exists for {sp.point_code} ({existing[0].collection_code}).", error_code="COLLECTION_EXISTS")
    a = db.scalars(select(SamplingAssignment).where(SamplingAssignment.sampling_point_id == sp.id, SamplingAssignment.status == "ACTIVE")).first()
    dv = db.get(SamplingDesignVersion, sp.design_version_id)
    assert dv is not None
    fr = rules.of_design(dv)   # frozen: later changes to the defaults never alter this record
    fc = FieldCollectionRecord(collection_code=next_code(db, "field_collection", mp.start_date.year), sampling_point_id=sp.id,
                               assignment_id=a.id if a else None, monitoring_period_id=mp.id, project_id=p.id, farm_id=sp.farm_id,
                               collector_id=principal.user_id, field_rules=json.dumps(fr), checklist_version=fr["checklist_version"],
                               gps_tolerance_m=Decimal(f"{fr['gps_tolerance_m']:.1f}"))
    db.add(fc)
    db.flush()
    record_transition(db, ctx, FIELD_COLLECTION_MACHINE, fc.id, None, "IN_PROGRESS", "FIELD_COLLECTION_STARTED", None, p.organization_id)
    _audit(db, ctx, p, "FIELD_COLLECTION_STARTED", {"collection_id": fc.id, "collection_code": fc.collection_code, "point_code": sp.point_code})
    db.commit()
    return fc


def update_collection(db: Session, ctx: RequestContext, principal: Principal, collection_id: uuid.UUID,
                      data: CollectionUpdate) -> FieldCollectionRecord:
    fc, p = get_collection(db, principal, collection_id, P.SAMPLING_COLLECT)
    if fc.collector_id != principal.user_id:
        raise PermissionDenied("Only the collector edits a field record.", error_code="NOT_COLLECTOR")
    if fc.status not in ("IN_PROGRESS", "RETURNED"):
        raise Conflict(f"A {fc.status} field record cannot be edited; request a correction instead.", error_code="COLLECTION_NOT_EDITABLE")
    changes = data.model_dump(exclude_unset=True)
    if "checklist" in changes and changes["checklist"] is not None:
        changes["checklist"] = json.dumps(changes["checklist"])
    for k, v in changes.items():
        setattr(fc, k, v)
    if fc.gps_latitude is not None and fc.gps_longitude is not None and ("gps_latitude" in changes or "gps_longitude" in changes):
        sp = db.get(SamplingPoint, fc.sampling_point_id)
        assert sp is not None
        lat, lon = float(fc.gps_latitude), float(fc.gps_longitude)
        fc.gps_location = f"POINT ({lon:.7f} {lat:.7f})"
        fc.distance_from_point_m = Decimal(f"{gis.distance_to_point_m(db, sp.id, lat, lon):.1f}")
        fc.gps_inside_farm = gis.point_inside_boundary(db, sp.farm_boundary_id, lat, lon)
    _audit(db, ctx, p, "FIELD_COLLECTION_UPDATED", {"collection_id": fc.id, **{k: v for k, v in changes.items() if k != "checklist"}})
    db.commit()
    return fc


def checklist_of(fc: FieldCollectionRecord) -> dict[str, bool]:
    return json.loads(fc.checklist) if fc.checklist else {}


def submit_collection(db: Session, ctx: RequestContext, principal: Principal, collection_id: uuid.UUID) -> FieldCollectionRecord:
    fc, p = get_collection(db, principal, collection_id, P.SAMPLING_COLLECT)
    if fc.collector_id != principal.user_id:
        raise PermissionDenied("Only the collector submits a field record.", error_code="NOT_COLLECTOR")
    mp = db.get(MonitoringPeriod, fc.monitoring_period_id)
    sp = db.get(SamplingPoint, fc.sampling_point_id)
    assert mp is not None and sp is not None
    fr = rules.of_collection(fc)
    keys = rules.checklist_keys(fr)
    photos = sum(1 for e in mrv_service.evidence_for(db, p.id, entity_id=fc.id) if e.evidence_type == "FIELD_PHOTO" and e.status != "REJECTED")
    missing = [label for ok, label in (
        (fc.collected_at is not None, "collection date/time"), (fc.gps_latitude is not None, "GPS position"),
        (fc.actual_depth_top_cm is not None and fc.actual_depth_bottom_cm is not None, "actual sampling depth"),
        (all(checklist_of(fc).get(k) for k in keys), f"completed checklist {fr['checklist_version']} (" + ", ".join(keys) + ")"),
        (photos >= fr["min_photos"], f"at least {fr['min_photos']} field photo(s)"),
    ) if not ok]
    if fc.collected_at is not None and not (mp.start_date <= fc.collected_at.date() <= mp.end_date):
        missing.append("a collection date within the monitoring period")
    if fc.collected_at is not None and fc.collected_at > utcnow():
        missing.append("a collection time that is not in the future")
    far = fc.distance_from_point_m is not None and float(fc.distance_from_point_m) > fr["gps_tolerance_m"]
    if (far or fc.gps_inside_farm is False) and not fc.deviation_note:
        missing.append(f"a note explaining why the GPS position is {fc.distance_from_point_m} m from the point"
                       + (" and outside the farm" if fc.gps_inside_farm is False else ""))
    if missing:
        raise Conflict("Cannot submit yet: " + "; ".join(missing) + ".", error_code="REQUIREMENTS_NOT_MET", details={"missing": missing})
    record_transition(db, ctx, FIELD_COLLECTION_MACHINE, fc.id, fc.status, "SUBMITTED", "FIELD_COLLECTION_SUBMITTED", None, p.organization_id)
    fc.status, fc.submitted_at = "SUBMITTED", utcnow()
    sp.status = "COLLECTED"
    for a in db.scalars(select(SamplingAssignment).where(SamplingAssignment.sampling_point_id == sp.id, SamplingAssignment.status == "ACTIVE")).all():
        a.status, a.ended_at = "COMPLETED", utcnow()
    _audit(db, ctx, p, "FIELD_COLLECTION_SUBMITTED", {"collection_id": fc.id, "collection_code": fc.collection_code, "point_code": sp.point_code,
                                                     "gps": [str(fc.gps_latitude),
                                                             str(fc.gps_longitude)], "distance_from_point_m": fc.distance_from_point_m})
    db.commit()
    return fc


def review_collection(db: Session, ctx: RequestContext, principal: Principal, collection_id: uuid.UUID, decision: str,
                      notes: str) -> FieldCollectionRecord:
    fc, p = get_collection(db, principal, collection_id, P.SAMPLING_REVIEW)
    if fc.collector_id == principal.user_id:
        raise PermissionDenied("You collected this record, so someone else must review it.", error_code="SEPARATION_OF_DUTIES")
    action = "FIELD_COLLECTION_ACCEPTED" if decision == "ACCEPTED" else "FIELD_COLLECTION_RETURNED"
    record_transition(db, ctx, FIELD_COLLECTION_MACHINE, fc.id, fc.status, decision, action, notes, p.organization_id)
    fc.status, fc.reviewed_by, fc.reviewed_at, fc.review_notes = decision, principal.user_id, utcnow(), notes
    sp = db.get(SamplingPoint, fc.sampling_point_id)
    assert sp is not None
    if decision == "ACCEPTED" and fc.supersedes_id:
        old = db.get(FieldCollectionRecord, fc.supersedes_id)
        if old is not None and old.status == "ACCEPTED":
            record_transition(db, ctx, FIELD_COLLECTION_MACHINE, old.id, "ACCEPTED", "SUPERSEDED", "FIELD_COLLECTION_SUPERSEDED",
                              f"Corrected by {fc.collection_code}", p.organization_id)
            old.status = "SUPERSEDED"
    if decision == "RETURNED":
        sp.status = "ASSIGNED"
        notify(db, [fc.collector_id], "FIELD_COLLECTION_RETURNED", f"Field record returned: {fc.collection_code}", notes, ENTITY, p.id, "/field")
    _audit(db, ctx, p, action, {"collection_id": fc.id, "collection_code": fc.collection_code}, None, notes)
    db.commit()
    return fc


def correct_collection(db: Session, ctx: RequestContext, principal: Principal, collection_id: uuid.UUID, reason: str) -> FieldCollectionRecord:
    """An accepted record is never edited: a correction is a new version (the original stays until the new one is accepted)."""
    fc, p = get_collection(db, principal, collection_id, P.SAMPLING_COLLECT, P.SAMPLING_REVIEW)
    if fc.status != "ACCEPTED":
        raise Conflict("Only accepted records are corrected by a new version; edit or resubmit the others.", error_code="NOT_ACCEPTED")
    if any(c.supersedes_id == fc.id and c.status != "SUPERSEDED" for c in collections_of_period(db, fc.monitoring_period_id)):
        raise Conflict("A correction of this record is already open.", error_code="CORRECTION_EXISTS")
    mp = db.get(MonitoringPeriod, fc.monitoring_period_id)
    assert mp is not None
    keep = ("sampling_point_id", "assignment_id", "monitoring_period_id", "project_id", "farm_id", "collector_id", "collected_at", "gps_location",
            "gps_latitude", "gps_longitude", "gps_accuracy_m", "distance_from_point_m", "gps_inside_farm", "deviation_note", "actual_depth_top_cm",
            "actual_depth_bottom_cm", "sample_quantity", "sample_unit", "observations", "notes", "checklist", "field_rules", "checklist_version",
            "gps_tolerance_m")
    new = FieldCollectionRecord(collection_code=next_code(db, "field_collection", mp.start_date.year), version=fc.version + 1,
                                supersedes_id=fc.id, correction_reason=reason, **{k: getattr(fc, k) for k in keep})
    db.add(new)
    db.flush()
    record_transition(db, ctx, FIELD_COLLECTION_MACHINE, new.id, None, "IN_PROGRESS", "FIELD_COLLECTION_CORRECTED", reason, p.organization_id)
    _audit(db, ctx, p, "FIELD_COLLECTION_CORRECTED", {"collection_id": new.id, "collection_code": new.collection_code,
                                                      "supersedes": fc.collection_code,
                                                     "version": new.version}, None, reason)
    db.commit()
    return new


def evidence_count(db: Session, collection_id: uuid.UUID) -> int:
    return len(db.scalars(select(MrvEvidence.id).where(MrvEvidence.entity_id == collection_id)).all())


def project_farm_ids(db: Session, project_id: uuid.UUID) -> list[uuid.UUID]:
    return [pf.farm_id for pf in db.scalars(select(ProjectFarm).where(ProjectFarm.project_id == project_id, ProjectFarm.status == "ACTIVE")).all()]
