"""ORM → response mapping for projects (permissions and visibility are decided here, never in the client)."""
import json
import uuid

from sqlalchemy.orm import Session

from app.models import Farm, Farmer, FarmerAgreement, Organization, Project, ProjectBoundary, ProjectCarbonRight, ProjectFarm, User
from app.models.projects import ProjectCreditingPeriod, ProjectParticipant
from app.repositories import farms as farm_repo
from app.repositories import projects as repo
from app.schemas.projects import (
    BaselineOut,
    BoundaryFarmOut,
    CarbonRightOut,
    CreditingPeriodOut,
    ParticipantOut,
    ProjectBoundaryOut,
    ProjectBoundaryView,
    ProjectFarmOut,
    ProjectOut,
    ProjectOverlapOut,
    ProjectSummary,
)
from app.security.permissions import P
from app.security.principal import Principal
from app.services import document_service, farm_service
from app.services import project_farm_service as pfs
from app.services import project_service as svc


def project_summaries(db: Session, projects: list[Project]) -> list[ProjectSummary]:
    counts = repo.farm_counts(db, [p.id for p in projects])
    orgs = {o.id: o.name for o in (db.get(Organization, oid) for oid in {p.organization_id for p in projects}) if o}
    stds = repo.standards_by_id(db, {p.standard_id for p in projects if p.standard_id})
    acts = repo.activities_by_id(db, {p.activity_id for p in projects if p.activity_id})
    out = []
    for p in projects:
        b = db.get(ProjectBoundary, p.current_boundary_id) if p.current_boundary_id else None
        out.append(ProjectSummary(
            id=p.id, project_code=p.project_code, name=p.name, project_type=p.project_type, organization_id=p.organization_id,
            organization_name=orgs.get(p.organization_id), country=p.country, region=p.region, status=p.status, start_date=p.start_date,
            standard_name=stds[p.standard_id].name if p.standard_id in stds else None,
            activity_name=acts[p.activity_id].name if p.activity_id in acts else None, methodology_status=p.methodology_status,
            farm_count=counts.get(p.id, 0), area_hectares=b.area_hectares if b else None, environment=p.environment,
            created_at=p.created_at))
    return out


def project_out(db: Session, principal: Principal, p: Project) -> ProjectOut:
    base = project_summaries(db, [p])[0]
    transitions = svc.allowed_for(principal, p)
    counts = {"farms": base.farm_count,
              "participants": sum(1 for x in repo.participants(db, p.id) if x.status == "ACTIVE"),
              "carbon_rights": sum(1 for x in repo.carbon_rights(db, p.id) if x.status == "ACTIVE"),
              "crediting_periods": sum(1 for x in repo.crediting_periods(db, p.id) if x.status == "PROPOSED"),
              "baseline_versions": len(repo.baselines(db, p.id)),
              "documents": len(document_service.list_for(db, svc.ENTITY, p.id))}
    return ProjectOut(**base.model_dump(), description=p.description, standard_id=p.standard_id, activity_id=p.activity_id,
                      current_boundary_id=p.current_boundary_id, submitted_at=p.submitted_at, submitted_by=p.submitted_by,
                      eligibility_reviewed_at=p.eligibility_reviewed_at, eligibility_reviewed_by=p.eligibility_reviewed_by,
                      review_notes=p.review_notes, updated_at=p.updated_at, allowed_transitions=transitions,
                      readiness=[r for r in svc.readiness(db, p) if r.target in transitions],
                      can_manage=principal.can_in_org(P.PROJECTS_MANAGE, p.organization_id),
                      can_review=principal.can_in_org(P.PROJECTS_REVIEW, p.organization_id),
                      can_review_boundary=principal.can_in_org(P.FARMS_REVIEW, p.organization_id),
                      is_editable=p.status in svc.EDITABLE, counts=counts)


def carbon_right_out(db: Session, cr: ProjectCarbonRight, farm_code: str | None = None) -> CarbonRightOut:
    ag = db.get(FarmerAgreement, cr.agreement_id) if cr.agreement_id else None
    return CarbonRightOut.model_validate({**{k: getattr(cr, k) for k in CarbonRightOut.model_fields if hasattr(cr, k)},
                                          "farm_code": farm_code, "agreement_number": ag.agreement_number if ag else None})


def project_farm_out(db: Session, principal: Principal, p: Project, pf: ProjectFarm, with_geometry: bool = False) -> ProjectFarmOut:
    farm = farm_repo.get(db, pf.farm_id)
    farmer = db.get(Farmer, pf.farmer_id)
    assert farm is not None and farmer is not None
    conflicts = pfs.conflicts_for(db, principal, farm, p, pf.participation_start, pf.participation_end) if pf.status == "ACTIVE" else []
    geo = None
    if with_geometry and farm.current_boundary_id:
        b = farm_repo.current_boundary(db, farm.id)
        geo = farm_service.boundary_out_geojson(b) if b else None
    return ProjectFarmOut(id=pf.id, farm_id=farm.id, farm_code=farm.farm_code, farm_name=farm.name, farm_status=farm.status,
                          farmer_id=farmer.id, farmer_code=farmer.farmer_code, farmer_name=farmer.full_name, status=pf.status,
                          participation_start=pf.participation_start, participation_end=pf.participation_end,
                          farm_boundary_id=pf.farm_boundary_id, farm_area_hectares=pf.farm_area_hectares,
                          boundary_changed=farm.current_boundary_id != pf.farm_boundary_id, conflicts_acknowledged=pf.conflicts_acknowledged,
                          conflict_notes=pf.conflict_notes, conflicts=conflicts,
                          carbon_rights=[carbon_right_out(db, r, farm.farm_code) for r in repo.carbon_rights(db, p.id, pf.id)],
                          added_by=pf.added_by, added_at=pf.added_at, removed_at=pf.removed_at, removal_reason=pf.removal_reason, geojson=geo)


def participant_out(db: Session, pp: ProjectParticipant) -> ParticipantOut:
    u = db.get(User, pp.user_id)
    return ParticipantOut(id=pp.id, user_id=pp.user_id, user_name=u.full_name if u else "", user_email=u.email if u else "",
                          project_role=pp.project_role, status=pp.status, start_date=pp.start_date, end_date=pp.end_date, notes=pp.notes,
                          added_by=pp.added_by, added_at=pp.added_at, updated_at=pp.updated_at, removed_at=pp.removed_at,
                          removal_reason=pp.removal_reason)


def crediting_out(cp: ProjectCreditingPeriod) -> CreditingPeriodOut:
    return CreditingPeriodOut(id=cp.id, period_number=cp.period_number, start_date=cp.start_date, end_date=cp.end_date, status=cp.status,
                              notes=cp.notes, replaces_id=cp.replaces_id, created_by=cp.created_by, created_at=cp.created_at,
                              status_changed_at=cp.status_changed_at, status_reason=cp.status_reason,
                              length_days=(cp.end_date - cp.start_date).days)


def baseline_out(b: object) -> BaselineOut:
    return BaselineOut.model_validate(b, from_attributes=True)


def boundary_out(b: ProjectBoundary) -> ProjectBoundaryOut:
    return ProjectBoundaryOut(id=b.id, version=b.version, status=b.status, geojson=pfs.boundary_geojson(b), area_m2=b.area_m2,
                              area_hectares=b.area_hectares, sum_farm_area_hectares=b.sum_farm_area_hectares,
                              internal_overlap_hectares=b.internal_overlap_hectares, farm_count=b.farm_count, is_valid=b.is_valid,
                              validation_notes=b.validation_notes, computed_by=b.computed_by, computed_at=b.computed_at,
                              review_status=b.review_status, reviewed_by=b.reviewed_by, reviewed_at=b.reviewed_at, review_notes=b.review_notes)


def boundary_view(db: Session, principal: Principal, p: Project) -> ProjectBoundaryView:
    current = repo.current_boundary(db, p.id)
    farms: list[BoundaryFarmOut] = []
    pfs_active = repo.project_farms(db, p.id, active_only=True)
    open_counts = farm_repo.open_overlap_counts(db, [x.farm_id for x in pfs_active])
    for pf in pfs_active:
        farm: Farm | None = farm_repo.get(db, pf.farm_id)
        b = farm_repo.current_boundary(db, pf.farm_id) if farm else None
        if farm and b:
            farms.append(BoundaryFarmOut(farm_id=farm.id, farm_code=farm.farm_code, farm_name=farm.name, area_hectares=b.area_hectares,
                                         geojson=farm_service.boundary_out_geojson(b), open_overlaps=open_counts.get(farm.id, 0)))
    overlaps: list[ProjectOverlapOut] = []
    if current and current.project_overlaps:
        for h in json.loads(current.project_overlaps):
            other = repo.get(db, uuid.UUID(h["project_id"]))
            visible = bool(other and principal.can_in_org(P.PROJECTS_READ, other.organization_id))
            overlaps.append(ProjectOverlapOut(other_project_id=other.id if visible and other else None,
                                              other_project_code=other.project_code if visible and other else None,
                                              other_project_visible=visible, same_organization=uuid.UUID(h["organization_id"]) == p.organization_id,
                                              overlap_area_m2=h["overlap_m2"]))
    return ProjectBoundaryView(current=boundary_out(current) if current else None, stale=pfs.boundary_is_stale(db, p), farms=farms,
                               project_overlaps=overlaps, versions=[boundary_out(b) for b in repo.boundaries(db, p.id)],
                               can_recompute=principal.can_in_org(P.PROJECTS_MANAGE, p.organization_id) and p.status in svc.EDITABLE,
                               can_review=principal.can_in_org(P.FARMS_REVIEW, p.organization_id))
