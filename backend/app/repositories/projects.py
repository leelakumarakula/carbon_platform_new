"""Project queries."""
import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models import (
    Activity,
    Project,
    ProjectBaseline,
    ProjectBoundary,
    ProjectCarbonRight,
    ProjectCreditingPeriod,
    ProjectFarm,
    ProjectParticipant,
    ProjectStandard,
    ProjectStatusHistory,
    Standard,
)
from app.models.projects import ProjectActivity
from app.repositories.common import paginate
from app.schemas.common import PageParams

SORTS = {"project_code": Project.project_code, "name": Project.name, "status": Project.status, "created_at": Project.created_at,
         "start_date": Project.start_date}


def get(db: Session, project_id: uuid.UUID) -> Project | None:
    return db.scalars(select(Project).where(Project.id == project_id).execution_options(populate_existing=True)).first()


def list_projects(db: Session, params: PageParams, *, scope: frozenset[uuid.UUID] | None, search: str | None, status: str | None,
                  organization_id: uuid.UUID | None, environment: str | None) -> tuple[list[Project], int]:
    stmt = select(Project)
    if scope is not None:
        stmt = stmt.where(Project.organization_id.in_(list(scope)))
    if search:
        like = f"%{search.strip()}%"
        stmt = stmt.where(or_(Project.project_code.ilike(like), Project.name.ilike(like), Project.region.ilike(like)))
    if status:
        stmt = stmt.where(Project.status == status)
    if organization_id:
        stmt = stmt.where(Project.organization_id == organization_id)
    if environment:
        stmt = stmt.where(Project.environment == environment)
    return paginate(db, stmt, params, SORTS, "-created_at", Project.id)


def project_farms(db: Session, project_id: uuid.UUID, active_only: bool = False) -> list[ProjectFarm]:
    stmt = select(ProjectFarm).where(ProjectFarm.project_id == project_id)
    if active_only:
        stmt = stmt.where(ProjectFarm.status == "ACTIVE")
    return list(db.scalars(stmt.order_by(ProjectFarm.added_at)).all())


def active_participations_of_farm(db: Session, farm_id: uuid.UUID) -> list[ProjectFarm]:
    return list(db.scalars(select(ProjectFarm).where(ProjectFarm.farm_id == farm_id, ProjectFarm.status == "ACTIVE")).all())


def farm_counts(db: Session, project_ids: list[uuid.UUID]) -> dict[uuid.UUID, int]:
    if not project_ids:
        return {}
    rows = db.execute(select(ProjectFarm.project_id, func.count()).where(ProjectFarm.project_id.in_(project_ids),
                                                                         ProjectFarm.status == "ACTIVE")
                      .group_by(ProjectFarm.project_id)).all()
    return {r[0]: int(r[1]) for r in rows}


def carbon_rights(db: Session, project_id: uuid.UUID, project_farm_id: uuid.UUID | None = None) -> list[ProjectCarbonRight]:
    stmt = select(ProjectCarbonRight).where(ProjectCarbonRight.project_id == project_id)
    if project_farm_id:
        stmt = stmt.where(ProjectCarbonRight.project_farm_id == project_farm_id)
    return list(db.scalars(stmt.order_by(ProjectCarbonRight.created_at)).all())


def participants(db: Session, project_id: uuid.UUID) -> list[ProjectParticipant]:
    return list(db.scalars(select(ProjectParticipant).where(ProjectParticipant.project_id == project_id)
                           .order_by(ProjectParticipant.added_at)).all())


def standard_history(db: Session, project_id: uuid.UUID) -> list[ProjectStandard]:
    return list(db.scalars(select(ProjectStandard).where(ProjectStandard.project_id == project_id)
                           .order_by(ProjectStandard.selected_at.desc())).all())


def activity_history(db: Session, project_id: uuid.UUID) -> list[ProjectActivity]:
    return list(db.scalars(select(ProjectActivity).where(ProjectActivity.project_id == project_id)
                           .order_by(ProjectActivity.selected_at.desc())).all())


def current_standard(db: Session, project_id: uuid.UUID) -> ProjectStandard | None:
    return db.scalars(select(ProjectStandard).where(ProjectStandard.project_id == project_id, ProjectStandard.is_current == True)  # noqa: E712
                      ).first()


def current_activity(db: Session, project_id: uuid.UUID) -> ProjectActivity | None:
    return db.scalars(select(ProjectActivity).where(ProjectActivity.project_id == project_id, ProjectActivity.is_current == True)  # noqa: E712
                      ).first()


def crediting_periods(db: Session, project_id: uuid.UUID) -> list[ProjectCreditingPeriod]:
    return list(db.scalars(select(ProjectCreditingPeriod).where(ProjectCreditingPeriod.project_id == project_id)
                           .order_by(ProjectCreditingPeriod.period_number)).all())


def baselines(db: Session, project_id: uuid.UUID) -> list[ProjectBaseline]:
    return list(db.scalars(select(ProjectBaseline).where(ProjectBaseline.project_id == project_id)
                           .order_by(ProjectBaseline.version.desc())).all())


def boundaries(db: Session, project_id: uuid.UUID) -> list[ProjectBoundary]:
    return list(db.scalars(select(ProjectBoundary).where(ProjectBoundary.project_id == project_id)
                           .order_by(ProjectBoundary.version.desc())).all())


def current_boundary(db: Session, project_id: uuid.UUID) -> ProjectBoundary | None:
    return db.scalars(select(ProjectBoundary).where(ProjectBoundary.project_id == project_id, ProjectBoundary.status == "CURRENT")
                      .execution_options(populate_existing=True)).first()


def status_history(db: Session, project_id: uuid.UUID) -> list[ProjectStatusHistory]:
    return list(db.scalars(select(ProjectStatusHistory).where(ProjectStatusHistory.project_id == project_id)
                           .order_by(ProjectStatusHistory.id)).all())


def standards_by_id(db: Session, ids: set[uuid.UUID]) -> dict[uuid.UUID, Standard]:
    return {s.id: s for s in db.scalars(select(Standard).where(Standard.id.in_(ids))).all()} if ids else {}


def activities_by_id(db: Session, ids: set[uuid.UUID]) -> dict[uuid.UUID, Activity]:
    return {a.id: a for a in db.scalars(select(Activity).where(Activity.id.in_(ids))).all()} if ids else {}
