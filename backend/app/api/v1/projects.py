import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile, status

from app.api.deps import DB, Ctx, Paging, read_upload, require
from app.models import Farm
from app.repositories import projects as repo
from app.schemas.common import IdRef, Page
from app.schemas.documents import document_out
from app.schemas.projects import (
    ActivitySelect,
    BaselineIn,
    BaselinesOut,
    BoundaryReview,
    CandidateUserOut,
    CarbonRightEnd,
    CarbonRightOut,
    CarbonRightReview,
    CreditingPeriodIn,
    CreditingPeriodOut,
    EligibleFarmOut,
    MyParticipationOut,
    ParticipantIn,
    ParticipantOut,
    ParticipantUpdate,
    ProjectActivitiesOut,
    ProjectBoundaryView,
    ProjectCarbonRightIn,
    ProjectCreate,
    ProjectDocumentsOut,
    ProjectFarmIn,
    ProjectFarmOut,
    ProjectOut,
    ProjectStandardsOut,
    ProjectSummary,
    ProjectTransition,
    ProjectUpdate,
    ReasonBody,
    SelectionOut,
    StandardSelect,
    StatusHistoryOut,
)
from app.security.permissions import P
from app.security.principal import Principal
from app.services import catalog_service, document_service
from app.services import project_farm_service as pfs
from app.services import project_service as svc
from app.services.project_mappers import (
    baseline_out,
    boundary_view,
    carbon_right_out,
    crediting_out,
    participant_out,
    project_farm_out,
    project_out,
    project_summaries,
)

router = APIRouter(prefix="/projects", tags=["projects"])
Reader = Annotated[Principal, Depends(require(P.PROJECTS_READ))]
Manager = Annotated[Principal, Depends(require(P.PROJECTS_MANAGE))]
Reviewer = Annotated[Principal, Depends(require(P.PROJECTS_REVIEW))]
GisReviewer = Annotated[Principal, Depends(require(P.FARMS_REVIEW))]
Farmer = Annotated[Principal, Depends(require(P.FARMERS_SELF))]


@router.get("", response_model=Page[ProjectSummary])
def list_projects(principal: Reader, db: DB, paging: Paging, search: Annotated[str | None, Query(max_length=100)] = None,
                  status_: Annotated[str | None, Query(alias="status", max_length=25)] = None, organization_id: uuid.UUID | None = None,
                  environment: Literal["LIVE", "DEMO"] | None = None) -> Page[ProjectSummary]:
    rows, total = svc.list_projects(db, principal, paging, search=search, status=status_, organization_id=organization_id,
                                    environment=environment)
    return Page(items=project_summaries(db, rows), total=total, page=paging.page, page_size=paging.page_size)


@router.post("", response_model=ProjectOut, status_code=status.HTTP_201_CREATED)
def create_project(body: ProjectCreate, principal: Manager, db: DB, ctx: Ctx) -> ProjectOut:
    return project_out(db, principal, svc.create_project(db, ctx, principal, body))


@router.get("/my-participation", response_model=list[MyParticipationOut], summary="The signed-in farmer's project participation")
def my_participation(principal: Farmer, db: DB) -> list[MyParticipationOut]:
    return [MyParticipationOut(project_id=p.id, project_code=p.project_code, project_name=p.name, project_status=p.status, farm_id=farm.id,
                               farm_code=farm.farm_code, farm_name=farm.name, participation_status=pf.status,
                               participation_start=pf.participation_start, participation_end=pf.participation_end,
                               carbon_rights=[carbon_right_out(db, r, farm.farm_code) for r in rights])
            for p, pf, farm, rights in pfs.my_participation(db, principal)]


@router.get("/{project_id}", response_model=ProjectOut)
def get_project(project_id: uuid.UUID, principal: Reader, db: DB) -> ProjectOut:
    return project_out(db, principal, svc.get_project(db, principal, project_id))


@router.patch("/{project_id}", response_model=ProjectOut)
def update_project(project_id: uuid.UUID, body: ProjectUpdate, principal: Manager, db: DB, ctx: Ctx) -> ProjectOut:
    return project_out(db, principal, svc.update_project(db, ctx, principal, project_id, body))


# ---------- farms
@router.get("/{project_id}/farms", response_model=list[ProjectFarmOut])
def list_farms(project_id: uuid.UUID, principal: Reader, db: DB, include_removed: bool = False, geometry: bool = False) -> list[ProjectFarmOut]:
    p = svc.get_project(db, principal, project_id)
    return [project_farm_out(db, principal, p, pf, geometry) for pf in repo.project_farms(db, p.id, active_only=not include_removed)]


@router.get("/{project_id}/farms/eligible", response_model=list[EligibleFarmOut], summary="Farms of the organization and whether they can join")
def eligible_farms(project_id: uuid.UUID, principal: Manager, db: DB) -> list[EligibleFarmOut]:
    return [EligibleFarmOut.model_validate(x) for x in pfs.eligible_farms(db, principal, project_id)]


@router.post("/{project_id}/farms", response_model=ProjectFarmOut, status_code=status.HTTP_201_CREATED)
def add_farm(project_id: uuid.UUID, body: ProjectFarmIn, principal: Manager, db: DB, ctx: Ctx) -> ProjectFarmOut:
    pf = pfs.add_farm(db, ctx, principal, project_id, body)
    return project_farm_out(db, principal, svc.get_project(db, principal, project_id), pf)


@router.delete("/{project_id}/farms/{farm_id}", response_model=ProjectFarmOut, summary="End a farm's participation (the record is kept)")
def remove_farm(project_id: uuid.UUID, farm_id: uuid.UUID, body: ReasonBody, principal: Manager, db: DB, ctx: Ctx) -> ProjectFarmOut:
    pf = pfs.remove_farm(db, ctx, principal, project_id, farm_id, body.reason)
    return project_farm_out(db, principal, svc.get_project(db, principal, project_id), pf)


# ---------- participants
@router.get("/{project_id}/participants", response_model=list[ParticipantOut])
def list_participants(project_id: uuid.UUID, principal: Reader, db: DB) -> list[ParticipantOut]:
    p = svc.get_project(db, principal, project_id)
    return [participant_out(db, x) for x in repo.participants(db, p.id)]


@router.get("/{project_id}/participants/candidates", response_model=list[CandidateUserOut])
def participant_candidates(project_id: uuid.UUID, principal: Manager, db: DB) -> list[CandidateUserOut]:
    return [CandidateUserOut(user_id=u.id, full_name=u.full_name, email=u.email, roles=sorted(set(r)))
            for u, r in svc.candidate_users(db, principal, project_id)]


@router.post("/{project_id}/participants", response_model=ParticipantOut, status_code=status.HTTP_201_CREATED)
def add_participant(project_id: uuid.UUID, body: ParticipantIn, principal: Manager, db: DB, ctx: Ctx) -> ParticipantOut:
    return participant_out(db, svc.add_participant(db, ctx, principal, project_id, body))


@router.patch("/{project_id}/participants/{participant_id}", response_model=ParticipantOut)
def update_participant(project_id: uuid.UUID, participant_id: uuid.UUID, body: ParticipantUpdate, principal: Manager, db: DB,
                       ctx: Ctx) -> ParticipantOut:
    return participant_out(db, svc.update_participant(db, ctx, principal, project_id, participant_id, body))


# ---------- boundary
@router.get("/{project_id}/boundary", response_model=ProjectBoundaryView)
def get_boundary(project_id: uuid.UUID, principal: Reader, db: DB) -> ProjectBoundaryView:
    return boundary_view(db, principal, svc.get_project(db, principal, project_id))


@router.post("/{project_id}/boundary/recompute", response_model=ProjectBoundaryView)
def recompute_boundary(project_id: uuid.UUID, principal: Manager, db: DB, ctx: Ctx) -> ProjectBoundaryView:
    pfs.recompute(db, ctx, principal, project_id)
    return boundary_view(db, principal, svc.get_project(db, principal, project_id))


@router.post("/{project_id}/boundary/review", response_model=ProjectBoundaryView, summary="GIS review of the current boundary version")
def review_boundary(project_id: uuid.UUID, body: BoundaryReview, principal: GisReviewer, db: DB, ctx: Ctx) -> ProjectBoundaryView:
    pfs.review_boundary(db, ctx, principal, project_id, body.decision, body.notes)
    return boundary_view(db, principal, svc.get_project(db, principal, project_id))


# ---------- standard / activity
def _selections(rows: list, names: dict, key: str) -> list[SelectionOut]:  # type: ignore[type-arg]
    out = []
    for r in rows:
        ref = getattr(r, key)
        entry = names.get(ref)
        out.append(SelectionOut(id=r.id, ref_id=ref, code=entry.code if entry else "", name=entry.name if entry else "", is_current=r.is_current,
                                reason=r.reason, selected_by=r.selected_by, selected_at=r.selected_at, superseded_at=r.superseded_at))
    return out


@router.get("/{project_id}/standards", response_model=ProjectStandardsOut)
def get_standards(project_id: uuid.UUID, principal: Reader, db: DB) -> ProjectStandardsOut:
    p = svc.get_project(db, principal, project_id)
    hist = repo.standard_history(db, p.id)
    names = repo.standards_by_id(db, {h.standard_id for h in hist})
    available = catalog_service.list_standards(db, environment=p.environment, active_only=True)
    current = next((s for s in catalog_service.list_standards(db, environment=p.environment) if s.id == p.standard_id), None)
    return ProjectStandardsOut(current=current, history=_selections(hist, names, "standard_id"), available=available)


@router.post("/{project_id}/standard", response_model=ProjectOut, summary="Select the standard / crediting route (reference only)")
def select_standard(project_id: uuid.UUID, body: StandardSelect, principal: Manager, db: DB, ctx: Ctx) -> ProjectOut:
    return project_out(db, principal, svc.select_standard(db, ctx, principal, project_id, body))


@router.get("/{project_id}/activities", response_model=ProjectActivitiesOut)
def get_activities(project_id: uuid.UUID, principal: Reader, db: DB) -> ProjectActivitiesOut:
    p = svc.get_project(db, principal, project_id)
    hist = repo.activity_history(db, p.id)
    names = repo.activities_by_id(db, {h.activity_id for h in hist})
    available = catalog_service.list_activities(db, environment=p.environment, standard_id=p.standard_id, active_only=True) if p.standard_id else []
    current = next((a for a in catalog_service.list_activities(db, environment=p.environment) if a.id == p.activity_id), None)
    return ProjectActivitiesOut(current=current, history=_selections(hist, names, "activity_id"), available=available,
                                methodology_status=p.methodology_status)


@router.post("/{project_id}/activity", response_model=ProjectOut, summary="Select the activity (must be offered under the standard)")
def select_activity(project_id: uuid.UUID, body: ActivitySelect, principal: Manager, db: DB, ctx: Ctx) -> ProjectOut:
    return project_out(db, principal, svc.select_activity(db, ctx, principal, project_id, body))


# ---------- crediting period / baseline
@router.get("/{project_id}/crediting-period", response_model=list[CreditingPeriodOut])
def list_crediting(project_id: uuid.UUID, principal: Reader, db: DB) -> list[CreditingPeriodOut]:
    p = svc.get_project(db, principal, project_id)
    return [crediting_out(x) for x in repo.crediting_periods(db, p.id)]


@router.post("/{project_id}/crediting-period", response_model=CreditingPeriodOut, status_code=status.HTTP_201_CREATED)
def add_crediting(project_id: uuid.UUID, body: CreditingPeriodIn, principal: Manager, db: DB, ctx: Ctx) -> CreditingPeriodOut:
    return crediting_out(svc.add_crediting_period(db, ctx, principal, project_id, body))


@router.get("/{project_id}/baseline", response_model=BaselinesOut)
def get_baseline(project_id: uuid.UUID, principal: Reader, db: DB) -> BaselinesOut:
    p = svc.get_project(db, principal, project_id)
    versions = [baseline_out(b) for b in repo.baselines(db, p.id)]
    return BaselinesOut(current=next((b for b in versions if b.is_current), None), versions=versions)


@router.patch("/{project_id}/baseline", response_model=BaselinesOut, summary="Record baseline metadata (new version; nothing is calculated)")
def update_baseline(project_id: uuid.UUID, body: BaselineIn, principal: Manager, db: DB, ctx: Ctx) -> BaselinesOut:
    svc.update_baseline(db, ctx, principal, project_id, body)
    return get_baseline(project_id, principal, db)


# ---------- carbon rights
@router.get("/{project_id}/carbon-rights", response_model=list[CarbonRightOut])
def list_carbon_rights(project_id: uuid.UUID, principal: Reader, db: DB) -> list[CarbonRightOut]:
    p = svc.get_project(db, principal, project_id)
    rights = repo.carbon_rights(db, p.id)
    codes = {f.id: f.farm_code for f in (db.get(Farm, fid) for fid in {r.farm_id for r in rights}) if f}
    return [carbon_right_out(db, r, codes.get(r.farm_id)) for r in rights]


@router.post("/{project_id}/carbon-rights", response_model=CarbonRightOut, status_code=status.HTTP_201_CREATED)
def add_carbon_right(project_id: uuid.UUID, body: ProjectCarbonRightIn, principal: Manager, db: DB, ctx: Ctx) -> CarbonRightOut:
    return carbon_right_out(db, pfs.add_carbon_right(db, ctx, principal, project_id, body))


@router.post("/{project_id}/carbon-rights/{right_id}/review", response_model=CarbonRightOut)
def review_carbon_right(project_id: uuid.UUID, right_id: uuid.UUID, body: CarbonRightReview, principal: Reviewer, db: DB,
                        ctx: Ctx) -> CarbonRightOut:
    return carbon_right_out(db, pfs.review_carbon_right(db, ctx, principal, project_id, right_id, body.status, body.notes))


@router.post("/{project_id}/carbon-rights/{right_id}/end", response_model=CarbonRightOut)
def end_carbon_right(project_id: uuid.UUID, right_id: uuid.UUID, body: CarbonRightEnd, principal: Manager, db: DB, ctx: Ctx) -> CarbonRightOut:
    return carbon_right_out(db, pfs.end_carbon_right(db, ctx, principal, project_id, right_id, body.status, body.effective_to, body.reason))


# ---------- documents
@router.get("/{project_id}/documents", response_model=ProjectDocumentsOut)
def list_documents(project_id: uuid.UUID, principal: Reader, db: DB) -> ProjectDocumentsOut:
    p = svc.get_project(db, principal, project_id)
    return ProjectDocumentsOut(documents=[document_out(d) for d in document_service.list_for(db, svc.ENTITY, p.id)],
                               categories=sorted(svc.PROJECT_DOC_CATEGORIES))


@router.post("/{project_id}/documents", response_model=IdRef, status_code=status.HTTP_201_CREATED)
def upload_document(project_id: uuid.UUID, principal: Manager, db: DB, ctx: Ctx, file: Annotated[UploadFile, File()],
                    category: Annotated[str, Form(max_length=30)], title: Annotated[str, Form(max_length=200)] = "") -> IdRef:
    return IdRef(id=svc.upload_document(db, ctx, principal, project_id, category, title, file.filename, read_upload(file)))


# ---------- workflow
@router.post("/{project_id}/start-data-collection", response_model=ProjectOut)
def start_data_collection(project_id: uuid.UUID, body: ProjectTransition, principal: Manager, db: DB, ctx: Ctx) -> ProjectOut:
    return project_out(db, principal, svc.start_data_collection(db, ctx, principal, project_id, body.reason))


@router.post("/{project_id}/submit", response_model=ProjectOut, summary="Submit for eligibility review")
def submit(project_id: uuid.UUID, body: ProjectTransition, principal: Manager, db: DB, ctx: Ctx) -> ProjectOut:
    return project_out(db, principal, svc.submit(db, ctx, principal, project_id, body.reason))


@router.post("/{project_id}/approve-eligibility", response_model=ProjectOut)
def approve_eligibility(project_id: uuid.UUID, body: ProjectTransition, principal: Reviewer, db: DB, ctx: Ctx) -> ProjectOut:
    return project_out(db, principal, svc.approve_eligibility(db, ctx, principal, project_id, body.reason))


@router.post("/{project_id}/return", response_model=ProjectOut, summary="Return to data collection for correction")
def return_project(project_id: uuid.UUID, body: ProjectTransition, principal: Reviewer, db: DB, ctx: Ctx) -> ProjectOut:
    return project_out(db, principal, svc.return_for_correction(db, ctx, principal, project_id, body.reason))


@router.post("/{project_id}/confirm-activity", response_model=ProjectOut)
def confirm_activity(project_id: uuid.UUID, body: ProjectTransition, principal: Manager, db: DB, ctx: Ctx) -> ProjectOut:
    return project_out(db, principal, svc.confirm_activity(db, ctx, principal, project_id, body.reason))


@router.post("/{project_id}/reopen", response_model=ProjectOut)
def reopen(project_id: uuid.UUID, body: ProjectTransition, principal: Manager, db: DB, ctx: Ctx) -> ProjectOut:
    return project_out(db, principal, svc.reopen(db, ctx, principal, project_id, body.reason))


@router.post("/{project_id}/close", response_model=ProjectOut)
def close(project_id: uuid.UUID, body: ProjectTransition, principal: Manager, db: DB, ctx: Ctx) -> ProjectOut:
    return project_out(db, principal, svc.close(db, ctx, principal, project_id, body.reason))


@router.get("/{project_id}/status-history", response_model=list[StatusHistoryOut])
def status_history(project_id: uuid.UUID, principal: Reader, db: DB) -> list[StatusHistoryOut]:
    return [StatusHistoryOut(id=r.id, from_status=r.from_status, to_status=r.to_status, action=r.action, reason=r.reason,
                             changed_by=r.changed_by, changed_by_name=name, changed_at=r.changed_at, request_id=r.request_id)
            for r, name in svc.status_history(db, principal, project_id)]
