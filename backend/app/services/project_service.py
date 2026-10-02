"""Projects (spec section 4.4, 7.4, 8, 9): creation, team, standard/activity references, crediting period,
baseline metadata, documents and the early project workflow.

Rules enforced here:
- access is organization-scoped (projects.read / manage / review); out-of-scope projects are 404
- farms, carbon rights, crediting period, baseline and standard/activity selection change only while the project is
  DRAFT or DATA_COLLECTION (activity also in STANDARD_SELECTED); re-open a project to correct it
- every status change goes through PROJECT_MACHINE with readiness checks, and is written to workflow_events,
  audit_logs and the append-only project_status_history
- the person who submitted the project cannot approve its eligibility review
- no methodology is selected and nothing is calculated in Phase 3 (methodology_status stays NOT_SELECTED)
"""
import json
import uuid
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit.service import record, record_transition, snapshot
from app.core.context import RequestContext
from app.core.errors import Conflict, NotFound, PermissionDenied, ValidationFailed
from app.models import (
    Activity,
    Organization,
    OrganizationUser,
    Project,
    ProjectBaseline,
    ProjectCreditingPeriod,
    ProjectDocument,
    ProjectParticipant,
    ProjectStandard,
    ProjectStatusHistory,
    Role,
    Standard,
    User,
    UserRole,
)
from app.models.base import utcnow
from app.models.documents import DocumentCategory
from app.models.projects import ProjectActivity
from app.repositories import projects as repo
from app.repositories.sequences import next_code
from app.schemas.common import PageParams
from app.schemas.farmers import ChecklistItem, TransitionReadiness
from app.schemas.projects import (
    ActivitySelect,
    BaselineIn,
    CreditingPeriodIn,
    ParticipantIn,
    ParticipantUpdate,
    ProjectCreate,
    ProjectUpdate,
    StandardSelect,
)
from app.security.permissions import P
from app.security.principal import Principal
from app.services import access, catalog_service, document_service
from app.services.notification_service import notify
from app.services.workflows import PROJECT_MACHINE

ENTITY = "project"
OWNER_ORG_TYPES = {"PROJECT_DEVELOPER", "FIELD_PARTNER", "FARMER_GROUP"}
EDITABLE = ("DRAFT", "DATA_COLLECTION")
ACTIVITY_EDITABLE = ("DRAFT", "DATA_COLLECTION", "STANDARD_SELECTED")
TEAM_LOCKED = ("CLOSED",)
PROJECT_DOC_CATEGORIES = {DocumentCategory.PROJECT_DESIGN.value, DocumentCategory.CARBON_RIGHTS.value, DocumentCategory.BASELINE_DATA.value,
                          DocumentCategory.AGREEMENT.value, DocumentCategory.GEOSPATIAL_FILE.value, DocumentCategory.OTHER.value}
PROJECT_FIELDS = ("project_code", "name", "description", "project_type", "organization_id", "country", "region", "start_date", "status",
                  "environment")
# Which permission each target status needs (the endpoint enforces the same).
TRANSITION_PERMISSION = {"DATA_COLLECTION": P.PROJECTS_MANAGE, "ELIGIBILITY_REVIEW": P.PROJECTS_MANAGE,
                         "STANDARD_SELECTED": P.PROJECTS_REVIEW, "ACTIVITY_SELECTED": P.PROJECTS_MANAGE, "CLOSED": P.PROJECTS_MANAGE,
                         # Phase 4: entered through the methodology endpoints (evaluate / confirm / unlock)
                         "METHODOLOGY_REVIEW": P.PROJECTS_MANAGE, "METHODOLOGY_CONFIRMED": P.PROJECTS_MANAGE,
                         # Phase 5: entered through the MRV endpoints (plan approval / period start)
                         "MRV_PLANNED": P.MRV_MANAGE, "MONITORING": P.MRV_MANAGE}


def _not_found() -> NotFound:
    return NotFound("Project not found.", error_code="PROJECT_NOT_FOUND")


def get_project(db: Session, principal: Principal, project_id: uuid.UUID, code: str = P.PROJECTS_READ) -> Project:
    p = repo.get(db, project_id)
    if p is None:
        raise _not_found()
    access.require(principal, code, p.organization_id, None, _not_found())
    return p


def _document_resolver(db: Session, principal: Principal, project_id: uuid.UUID, kind: str) -> None:
    p = repo.get(db, project_id)
    nf = NotFound("Document not found.", error_code="DOCUMENT_NOT_FOUND")
    if p is None:
        raise nf
    access.require(principal, P.PROJECTS_MANAGE if kind == "manage" else P.PROJECTS_READ, p.organization_id, None, nf)


document_service.register_resolver(ENTITY, _document_resolver)


def require_status(p: Project, allowed: tuple[str, ...], what: str) -> None:
    if p.status not in allowed:
        raise Conflict(f"{what} is only possible while the project is {' or '.join(allowed)} (it is {p.status}). "
                       "Re-open the project to correct it.", error_code="PROJECT_NOT_EDITABLE")


def list_projects(db: Session, principal: Principal, params: PageParams, **filters: object) -> tuple[list[Project], int]:
    scope = principal.scope_for(P.PROJECTS_READ)
    org = filters.get("organization_id")
    if scope is not None and org is not None and org not in scope:
        raise PermissionDenied(details={"organization_id": str(org)})
    return repo.list_projects(db, params, scope=scope, **filters)  # type: ignore[arg-type]


# ---------------------------------------------------------------- create / update
def create_project(db: Session, ctx: RequestContext, principal: Principal, data: ProjectCreate) -> Project:
    org = db.get(Organization, data.organization_id)
    if org is None:
        raise NotFound("Organization not found.", error_code="ORGANIZATION_NOT_FOUND")
    principal.require_in_org(P.PROJECTS_MANAGE, org.id)
    if org.status != "ACTIVE":
        raise ValidationFailed("Choose an active organization.", error_code="ORGANIZATION_INACTIVE")
    if org.org_type not in OWNER_ORG_TYPES:
        raise ValidationFailed("Projects are run by a project developer, field partner or farmer group.",
                               error_code="ORGANIZATION_TYPE_NOT_ALLOWED")
    p = Project(project_code=next_code(db, "project", date.today().year), environment=org.environment, created_by=ctx.user_id,
                **data.model_dump())
    db.add(p)
    db.flush()
    record(db, ctx, "PROJECT_CREATED", ENTITY, p.id, None, snapshot(p, PROJECT_FIELDS), organization_id=p.organization_id)
    _history(db, ctx, p, None, "DRAFT", "PROJECT_CREATED", None)
    if _holds_role(db, principal.user_id, "PROJECT_MANAGER", p.organization_id):  # the creating PM joins the team
        _add_participant(db, ctx, p, principal.user_id, "PROJECT_MANAGER", None, None, "Project creator")
    db.commit()
    return repo.get(db, p.id)  # type: ignore[return-value]


def update_project(db: Session, ctx: RequestContext, principal: Principal, project_id: uuid.UUID, data: ProjectUpdate) -> Project:
    p = get_project(db, principal, project_id, P.PROJECTS_MANAGE)
    require_status(p, EDITABLE, "Editing project details")
    changes = data.model_dump(exclude_unset=True)
    old = {k: getattr(p, k) for k in changes}
    for k, v in changes.items():
        setattr(p, k, v)
    if old != changes:
        record(db, ctx, "PROJECT_UPDATED", ENTITY, p.id, old, changes, organization_id=p.organization_id)
    db.commit()
    return repo.get(db, p.id)  # type: ignore[return-value]


# ---------------------------------------------------------------- participants (team)
def _holds_role(db: Session, user_id: uuid.UUID, role_code: str, organization_id: uuid.UUID) -> bool:
    return db.scalars(select(UserRole.id).join(Role, Role.id == UserRole.role_id).where(
        UserRole.user_id == user_id, Role.code == role_code,
        (UserRole.organization_id == organization_id) | (UserRole.organization_id.is_(None)))).first() is not None


def candidate_users(db: Session, principal: Principal, project_id: uuid.UUID) -> list[tuple[User, list[str]]]:
    """Users who could join the team: members of the project organization or platform-wide role holders, with the
    project-relevant roles they actually hold."""
    from app.models.projects import PROJECT_ROLES
    p = get_project(db, principal, project_id, P.PROJECTS_MANAGE)
    rows = db.execute(select(User, Role.code).join(UserRole, UserRole.user_id == User.id).join(Role, Role.id == UserRole.role_id).where(
        Role.code.in_(PROJECT_ROLES), User.status == "ACTIVE", User.environment == p.environment,
        (UserRole.organization_id == p.organization_id) | (UserRole.organization_id.is_(None)))).all()
    out: dict[uuid.UUID, tuple[User, list[str]]] = {}
    for user, code in rows:
        out.setdefault(user.id, (user, []))[1].append(code)
    return sorted(out.values(), key=lambda x: x[0].full_name)


def _add_participant(db: Session, ctx: RequestContext, p: Project, user_id: uuid.UUID, role: str, start: date | None, end: date | None,
                     notes: str | None) -> ProjectParticipant:
    if any(x.user_id == user_id and x.project_role == role and x.status == "ACTIVE" for x in repo.participants(db, p.id)):
        raise Conflict("This person already has that role on the project.", error_code="PARTICIPANT_EXISTS")
    pp = ProjectParticipant(project_id=p.id, user_id=user_id, project_role=role, start_date=start, end_date=end, notes=notes,
                            added_by=ctx.user_id)
    db.add(pp)
    db.flush()
    record(db, ctx, "PROJECT_PARTICIPANT_ADDED", ENTITY, p.id, None,
           {"participant_id": pp.id, "user_id": user_id, "project_role": role, "start_date": start, "end_date": end},
           organization_id=p.organization_id)
    return pp


def add_participant(db: Session, ctx: RequestContext, principal: Principal, project_id: uuid.UUID, data: ParticipantIn) -> ProjectParticipant:
    p = get_project(db, principal, project_id, P.PROJECTS_MANAGE)
    require_status(p, tuple(s for s in PROJECT_MACHINE.states if s not in TEAM_LOCKED), "Changing the project team")
    user = db.get(User, data.user_id)
    if user is None:
        raise NotFound("User not found.", error_code="USER_NOT_FOUND")
    member = db.scalars(select(OrganizationUser).where(OrganizationUser.user_id == user.id,
                                                       OrganizationUser.organization_id == p.organization_id)).first()
    platform_grant = db.scalars(select(UserRole.id).join(Role, Role.id == UserRole.role_id).where(
        UserRole.user_id == user.id, Role.code == data.project_role, UserRole.organization_id.is_(None))).first()
    if member is None and platform_grant is None:
        raise NotFound("User not found.", error_code="USER_NOT_FOUND")  # not visible from this project's organization
    if user.environment != p.environment:
        raise Conflict("Demo and live records cannot be mixed.", error_code="ENVIRONMENT_MISMATCH")
    if user.status != "ACTIVE":
        raise Conflict("Only active users can join a project team.", error_code="USER_NOT_ACTIVE")
    if not _holds_role(db, user.id, data.project_role, p.organization_id):
        raise ValidationFailed(f"{user.full_name} does not hold the {data.project_role} role for this organization. "
                               "Grant the role first (project roles never add permissions).", error_code="ROLE_NOT_HELD")
    if data.start_date and data.end_date and data.end_date < data.start_date:
        raise ValidationFailed("The end date is before the start date.", error_code="INVALID_DATES")
    pp = _add_participant(db, ctx, p, user.id, data.project_role, data.start_date, data.end_date, data.notes)
    notify(db, [user.id], "PROJECT_TEAM_ADDED", f"Added to project {p.project_code} {p.name}", f"Role: {data.project_role}",
           ENTITY, p.id, f"/projects/{p.id}")
    db.commit()
    return pp


def update_participant(db: Session, ctx: RequestContext, principal: Principal, project_id: uuid.UUID, participant_id: uuid.UUID,
                       data: ParticipantUpdate) -> ProjectParticipant:
    p = get_project(db, principal, project_id, P.PROJECTS_MANAGE)
    require_status(p, tuple(s for s in PROJECT_MACHINE.states if s not in TEAM_LOCKED), "Changing the project team")
    pp = db.get(ProjectParticipant, participant_id)
    if pp is None or pp.project_id != p.id:
        raise NotFound("Participant not found.", error_code="PARTICIPANT_NOT_FOUND")
    if pp.status != "ACTIVE":
        raise Conflict("This participant has already been removed.", error_code="PARTICIPANT_REMOVED")
    if data.status == "REMOVED":
        if not data.reason:
            raise ValidationFailed("Give a reason for removing this participant.", error_code="REASON_REQUIRED")
        pp.status, pp.removed_by, pp.removed_at, pp.removal_reason = "REMOVED", principal.user_id, utcnow(), data.reason
        pp.end_date = pp.end_date or date.today()
        record(db, ctx, "PROJECT_PARTICIPANT_REMOVED", ENTITY, p.id, {"participant_id": pp.id, "status": "ACTIVE"},
               {"status": "REMOVED", "user_id": pp.user_id, "project_role": pp.project_role}, data.reason, organization_id=p.organization_id)
    else:
        changes = data.model_dump(exclude_unset=True, exclude={"status", "reason"})
        start = changes.get("start_date", pp.start_date)
        end = changes.get("end_date", pp.end_date)
        if start and end and end < start:
            raise ValidationFailed("The end date is before the start date.", error_code="INVALID_DATES")
        old = {k: getattr(pp, k) for k in changes}
        for k, v in changes.items():
            setattr(pp, k, v)
        pp.updated_at = utcnow()
        record(db, ctx, "PROJECT_PARTICIPANT_UPDATED", ENTITY, p.id, {"participant_id": pp.id, **old}, changes, data.reason,
               organization_id=p.organization_id)
    db.commit()
    return pp


# ---------------------------------------------------------------- standard / activity references
def _catalog_entry_usable(entry: Standard | Activity | None, p: Project, what: str) -> None:
    if entry is None:
        raise NotFound(f"{what} not found.", error_code=f"{what.upper()}_NOT_FOUND")
    if entry.environment != p.environment:
        raise Conflict("Demo and live records cannot be mixed.", error_code="ENVIRONMENT_MISMATCH")
    if entry.status != "ACTIVE":
        raise ValidationFailed(f"This {what.lower()} is inactive.", error_code=f"{what.upper()}_INACTIVE")


def select_standard(db: Session, ctx: RequestContext, principal: Principal, project_id: uuid.UUID, data: StandardSelect) -> Project:
    p = get_project(db, principal, project_id, P.PROJECTS_MANAGE)
    require_status(p, EDITABLE, "Selecting the standard / route")
    s = db.get(Standard, data.standard_id)
    _catalog_entry_usable(s, p, "Standard")
    assert s is not None
    if p.standard_id == s.id:
        raise Conflict("This standard is already selected.", error_code="ALREADY_SELECTED")
    now = utcnow()
    prev = repo.current_standard(db, p.id)
    if prev:
        prev.is_current, prev.superseded_at = False, now
        db.flush()
    db.add(ProjectStandard(project_id=p.id, standard_id=s.id, reason=data.reason, selected_by=principal.user_id, selected_at=now))
    record(db, ctx, "PROJECT_STANDARD_SELECTED", ENTITY, p.id, {"standard_id": p.standard_id},
           {"standard_id": s.id, "standard_code": s.code}, data.reason, organization_id=p.organization_id)
    p.standard_id = s.id
    act = repo.current_activity(db, p.id)
    if act and not catalog_service.is_linked(db, s.id, act.activity_id):  # activity not offered under the new standard
        act.is_current, act.superseded_at, act.superseded_reason = False, now, "Standard changed; activity not offered under the new standard"
        record(db, ctx, "PROJECT_ACTIVITY_CLEARED", ENTITY, p.id, {"activity_id": act.activity_id}, {"activity_id": None},
               "Standard changed", organization_id=p.organization_id)
        p.activity_id = None
    db.commit()
    return repo.get(db, p.id)  # type: ignore[return-value]


def select_activity(db: Session, ctx: RequestContext, principal: Principal, project_id: uuid.UUID, data: ActivitySelect) -> Project:
    p = get_project(db, principal, project_id, P.PROJECTS_MANAGE)
    require_status(p, ACTIVITY_EDITABLE, "Selecting the activity")
    if p.standard_id is None:
        raise Conflict("Select a standard / route first.", error_code="STANDARD_REQUIRED")
    a = db.get(Activity, data.activity_id)
    _catalog_entry_usable(a, p, "Activity")
    assert a is not None
    if not catalog_service.is_linked(db, p.standard_id, a.id):
        raise ValidationFailed("This activity is not offered under the selected standard.", error_code="ACTIVITY_NOT_IN_STANDARD")
    if p.activity_id == a.id:
        raise Conflict("This activity is already selected.", error_code="ALREADY_SELECTED")
    now = utcnow()
    prev = repo.current_activity(db, p.id)
    if prev:
        prev.is_current, prev.superseded_at, prev.superseded_reason = False, now, data.reason or "Replaced"
        db.flush()
    db.add(ProjectActivity(project_id=p.id, activity_id=a.id, standard_id=p.standard_id, reason=data.reason,
                           selected_by=principal.user_id, selected_at=now))
    record(db, ctx, "PROJECT_ACTIVITY_SELECTED", ENTITY, p.id, {"activity_id": p.activity_id},
           {"activity_id": a.id, "activity_code": a.code, "standard_id": p.standard_id}, data.reason, organization_id=p.organization_id)
    p.activity_id = a.id
    db.commit()
    return repo.get(db, p.id)  # type: ignore[return-value]


# ---------------------------------------------------------------- crediting period / baseline
def add_crediting_period(db: Session, ctx: RequestContext, principal: Principal, project_id: uuid.UUID,
                         data: CreditingPeriodIn) -> ProjectCreditingPeriod:
    """Store a proposed crediting period. No methodology-specific length rules here (Phase 4 validates them)."""
    p = get_project(db, principal, project_id, P.PROJECTS_MANAGE)
    require_status(p, EDITABLE, "Recording the crediting period")
    periods = repo.crediting_periods(db, p.id)
    replaced = None
    if data.replaces_id:
        replaced = next((x for x in periods if x.id == data.replaces_id), None)
        if replaced is None or replaced.status != "PROPOSED":
            raise ValidationFailed("Only a proposed crediting period of this project can be replaced.", error_code="INVALID_REPLACEMENT")
        if not data.reason:
            raise ValidationFailed("Give a reason for replacing the crediting period.", error_code="REASON_REQUIRED")
    clash = [x for x in periods if x.status == "PROPOSED" and x is not replaced
             and x.start_date < data.end_date and data.start_date < x.end_date]
    if clash:
        raise Conflict("This period overlaps another proposed crediting period. Replace that period instead.",
                       error_code="CREDITING_PERIOD_OVERLAP", details={"period_numbers": [x.period_number for x in clash]})
    now = utcnow()
    if replaced:
        replaced.status, replaced.status_changed_at, replaced.status_changed_by, replaced.status_reason = (
            "SUPERSEDED", now, principal.user_id, data.reason)
        record(db, ctx, "PROJECT_CREDITING_PERIOD_SUPERSEDED", ENTITY, p.id,
               {"crediting_period_id": replaced.id, "status": "PROPOSED"}, {"status": "SUPERSEDED"}, data.reason,
               organization_id=p.organization_id)
    cp = ProjectCreditingPeriod(project_id=p.id, period_number=max((x.period_number for x in periods), default=0) + 1,
                                start_date=data.start_date, end_date=data.end_date, notes=data.notes,
                                replaces_id=replaced.id if replaced else None, created_by=principal.user_id)
    db.add(cp)
    db.flush()
    record(db, ctx, "PROJECT_CREDITING_PERIOD_CREATED", ENTITY, p.id, None,
           {"crediting_period_id": cp.id, "period_number": cp.period_number, "start_date": cp.start_date, "end_date": cp.end_date,
            "replaces_id": cp.replaces_id}, data.reason, organization_id=p.organization_id)
    db.commit()
    return cp


def update_baseline(db: Session, ctx: RequestContext, principal: Principal, project_id: uuid.UUID, data: BaselineIn) -> ProjectBaseline:
    """Baseline metadata only — a new version each time; nothing is calculated."""
    p = get_project(db, principal, project_id, P.PROJECTS_MANAGE)
    require_status(p, EDITABLE, "Recording baseline metadata")
    versions = repo.baselines(db, p.id)
    prev = next((b for b in versions if b.is_current), None)
    if prev:
        if not data.reason:
            raise ValidationFailed("Give a reason for changing the baseline metadata.", error_code="REASON_REQUIRED")
        prev.is_current = False
        db.flush()
    b = ProjectBaseline(project_id=p.id, version=max((v.version for v in versions), default=0) + 1, period_start=data.period_start,
                        period_end=data.period_end, description=data.description, data_sources=data.data_sources, notes=data.notes,
                        change_reason=data.reason, created_by=principal.user_id)
    db.add(b)
    db.flush()
    fields = ("period_start", "period_end", "description", "data_sources", "notes")
    record(db, ctx, "PROJECT_BASELINE_UPDATED", ENTITY, p.id,
           {"baseline_id": prev.id, "version": prev.version, **snapshot(prev, fields)} if prev else None,
           {"baseline_id": b.id, "version": b.version, **snapshot(b, fields)}, data.reason, organization_id=p.organization_id)
    db.commit()
    return b


# ---------------------------------------------------------------- documents
def upload_document(db: Session, ctx: RequestContext, principal: Principal, project_id: uuid.UUID, category: str, title: str,
                    filename: str | None, data: bytes) -> uuid.UUID:
    p = get_project(db, principal, project_id, P.PROJECTS_MANAGE)
    require_status(p, tuple(s for s in PROJECT_MACHINE.states if s != "CLOSED"), "Adding documents")
    if category not in PROJECT_DOC_CATEGORIES:
        raise ValidationFailed("This document category is not used for projects.", error_code="INVALID_CATEGORY",
                               details={"allowed": sorted(PROJECT_DOC_CATEGORIES)})
    doc = document_service.create_document(db, ctx, entity_type=ENTITY, entity_id=p.id, organization_id=p.organization_id,
                                           environment=p.environment, category=category, title=title, filename=filename, data=data)
    db.add(ProjectDocument(project_id=p.id, document_id=doc.id))
    record(db, ctx, "PROJECT_DOCUMENT_ADDED", ENTITY, p.id, None, {"document_id": doc.id, "category": category, "title": doc.title},
           organization_id=p.organization_id)
    db.commit()
    return doc.id


# ---------------------------------------------------------------- workflow
def _history(db: Session, ctx: RequestContext, p: Project, from_status: str | None, to_status: str, action: str, reason: str | None) -> None:
    db.add(ProjectStatusHistory(project_id=p.id, from_status=from_status, to_status=to_status, action=action, reason=reason,
                                changed_by=ctx.user_id, request_id=ctx.request_id))


def readiness(db: Session, p: Project) -> list[TransitionReadiness]:
    from app.services import project_farm_service as pfs
    out: list[TransitionReadiness] = []
    team = [x for x in repo.participants(db, p.id) if x.status == "ACTIVE"]
    has_pm = any(x.project_role == "PROJECT_MANAGER" for x in team)
    for target in sorted(PROJECT_MACHINE.allowed_from(p.status)):
        items: list[ChecklistItem] = []
        if target == "DATA_COLLECTION" and p.status == "DRAFT":
            items = [ChecklistItem(key="pm", label="A Project Manager is on the project team", done=has_pm)]
        elif target == "ELIGIBILITY_REVIEW":
            farms = repo.project_farms(db, p.id, active_only=True)
            facts = pfs.farm_facts(db, p, farms)
            periods = [x for x in repo.crediting_periods(db, p.id) if x.status == "PROPOSED"]
            docs = document_service.list_for(db, ENTITY, p.id)
            items = [
                ChecklistItem(key="farms", label="At least one participating farm", done=bool(farms)),
                ChecklistItem(key="farms_verified", label="All participating farms are verified and their farmers active",
                              done=bool(farms) and facts["all_verified"]),
                ChecklistItem(key="carbon_rights", label="Every participating farm has an active carbon-rights record",
                              done=bool(farms) and facts["all_have_rights"]),
                ChecklistItem(key="boundary", label="Project boundary computed (SQL Server) from the current farm boundaries",
                              done=bool(farms) and facts["boundary_ok"]),
                ChecklistItem(key="standard", label="A standard / crediting route is selected", done=p.standard_id is not None),
                ChecklistItem(key="activity", label="An activity is selected", done=p.activity_id is not None),
                ChecklistItem(key="crediting_period", label="A proposed crediting period is recorded", done=bool(periods)),
                ChecklistItem(key="baseline", label="Baseline period metadata is recorded", done=bool(repo.baselines(db, p.id))),
                ChecklistItem(key="pm", label="A Project Manager is on the project team", done=has_pm),
                ChecklistItem(key="design_doc", label="Project design document attached",
                              done=any(d.category == DocumentCategory.PROJECT_DESIGN.value for d in docs), required=False),
            ]
        elif target == "STANDARD_SELECTED":
            farms = repo.project_farms(db, p.id, active_only=True)
            facts = pfs.farm_facts(db, p, farms)
            b = repo.current_boundary(db, p.id)
            items = [
                ChecklistItem(key="boundary_review", label="GIS review accepted the current project boundary",
                              done=bool(b and b.review_status == "ACCEPTED" and facts["boundary_ok"])),
                ChecklistItem(key="carbon_rights_verified", label="All active carbon-rights records are verified",
                              done=facts["all_rights_verified"]),
                ChecklistItem(key="overlaps_reviewed", label="No unresolved (OPEN) overlap flags on participating farms",
                              done=facts["open_overlaps"] == 0),
                ChecklistItem(key="standard", label="A standard / crediting route is selected", done=p.standard_id is not None),
            ]
        elif target == "METHODOLOGY_REVIEW" and p.status == "ACTIVITY_SELECTED":
            items = [ChecklistItem(key="standard_activity", label="Standard and activity selected",
                                   done=bool(p.standard_id and p.activity_id))]
        elif target == "METHODOLOGY_CONFIRMED":
            from app.services import project_methodology_service as pms
            latest = pms.latest_evaluation(db, p.id)
            res = pms.results(db, latest.id) if latest else []
            recommended = [rv for rv in pms.reviews(db, [r.id for r in res]) if rv.recommendation == "RECOMMENDED"]
            items = [ChecklistItem(key="evaluation", label="Methodology candidates evaluated", done=latest is not None),
                     ChecklistItem(key="specialist_review", label="A candidate recommended by a methodology specialist",
                                   done=bool(recommended))]
        elif target == "ACTIVITY_SELECTED":
            items = [ChecklistItem(key="activity", label="An activity offered under the selected standard is selected",
                                   done=bool(p.activity_id and p.standard_id and catalog_service.is_linked(db, p.standard_id, p.activity_id)))]
        out.append(TransitionReadiness(target=target, ready=all(i.done for i in items if i.required), items=items))
    return out


def allowed_for(principal: Principal, p: Project) -> list[str]:
    out = []
    for t in sorted(PROJECT_MACHINE.allowed_from(p.status)):
        code = P.PROJECTS_REVIEW if (t == "DATA_COLLECTION" and p.status == "ELIGIBILITY_REVIEW") else TRANSITION_PERMISSION[t]
        if principal.can_in_org(code, p.organization_id):
            out.append(t)
    return out


def _transition(db: Session, ctx: RequestContext, p: Project, target: str, audit_action: str, history_action: str, reason: str) -> None:
    PROJECT_MACHINE.assert_transition(p.status, target)
    ready = next((r for r in readiness(db, p) if r.target == target), None)
    if ready and not ready.ready:
        missing = [i.label for i in ready.items if i.required and not i.done]
        raise Conflict(f"Cannot move to {target} yet: " + "; ".join(missing) + ".", error_code="REQUIREMENTS_NOT_MET",
                       details={"missing": missing})
    record_transition(db, ctx, PROJECT_MACHINE, p.id, p.status, target, audit_action, reason, p.organization_id)
    _history(db, ctx, p, p.status, target, history_action, reason)
    p.status = target


def transition_to(db: Session, ctx: RequestContext, p: Project, target: str, audit_action: str, history_action: str, reason: str) -> None:
    """Public entry for other project modules (methodology): same checks, audit and status history."""
    _transition(db, ctx, p, target, audit_action, history_action, reason)


def _team(db: Session, p: Project, *roles: str) -> list[uuid.UUID]:
    return [x.user_id for x in repo.participants(db, p.id) if x.status == "ACTIVE" and (not roles or x.project_role in roles)]


def start_data_collection(db: Session, ctx: RequestContext, principal: Principal, project_id: uuid.UUID, reason: str) -> Project:
    p = get_project(db, principal, project_id, P.PROJECTS_MANAGE)
    require_status(p, ("DRAFT",), "Starting data collection")
    _transition(db, ctx, p, "DATA_COLLECTION", "PROJECT_STATUS_CHANGED", "DATA_COLLECTION_STARTED", reason)
    db.commit()
    return repo.get(db, p.id)  # type: ignore[return-value]


def submit(db: Session, ctx: RequestContext, principal: Principal, project_id: uuid.UUID, reason: str) -> Project:
    from app.services import project_farm_service as pfs
    p = get_project(db, principal, project_id, P.PROJECTS_MANAGE)
    require_status(p, ("DATA_COLLECTION",), "Submitting for eligibility review")
    if pfs.boundary_is_stale(db, p):
        pfs.recompute_boundary(db, ctx, p)  # make sure the reviewed boundary reflects the current farm boundaries
    _transition(db, ctx, p, "ELIGIBILITY_REVIEW", "PROJECT_SUBMITTED", "SUBMITTED_FOR_ELIGIBILITY_REVIEW", reason)
    p.submitted_at, p.submitted_by = utcnow(), principal.user_id
    p.eligibility_reviewed_at = p.eligibility_reviewed_by = None
    notify(db, _team(db, p, "QA_OFFICER", "GIS_SPECIALIST", "PLATFORM_GIS_SPECIALIST"), "PROJECT_SUBMITTED",
           f"Project ready for eligibility review: {p.project_code} {p.name}", reason, ENTITY, p.id, f"/projects/{p.id}")
    db.commit()
    return repo.get(db, p.id)  # type: ignore[return-value]


def approve_eligibility(db: Session, ctx: RequestContext, principal: Principal, project_id: uuid.UUID, notes: str) -> Project:
    p = get_project(db, principal, project_id, P.PROJECTS_REVIEW)
    require_status(p, ("ELIGIBILITY_REVIEW",), "Approving eligibility")
    if p.submitted_by == principal.user_id:
        raise PermissionDenied("You submitted this project, so someone else must review it.", error_code="SEPARATION_OF_DUTIES")
    _transition(db, ctx, p, "STANDARD_SELECTED", "PROJECT_STATUS_CHANGED", "ELIGIBILITY_APPROVED", notes)
    p.eligibility_reviewed_at, p.eligibility_reviewed_by, p.review_notes = utcnow(), principal.user_id, notes
    notify(db, [p.submitted_by, *_team(db, p, "PROJECT_MANAGER")], "PROJECT_ELIGIBILITY_APPROVED",
           f"Eligibility review approved: {p.project_code} {p.name}", notes, ENTITY, p.id, f"/projects/{p.id}")
    db.commit()
    return repo.get(db, p.id)  # type: ignore[return-value]


def return_for_correction(db: Session, ctx: RequestContext, principal: Principal, project_id: uuid.UUID, reason: str) -> Project:
    p = get_project(db, principal, project_id, P.PROJECTS_REVIEW)
    require_status(p, ("ELIGIBILITY_REVIEW",), "Returning the project")
    _transition(db, ctx, p, "DATA_COLLECTION", "PROJECT_STATUS_CHANGED", "ELIGIBILITY_RETURNED", reason)
    p.review_notes = reason
    notify(db, [p.submitted_by, *_team(db, p, "PROJECT_MANAGER")], "PROJECT_RETURNED",
           f"Project returned for correction: {p.project_code} {p.name}", reason, ENTITY, p.id, f"/projects/{p.id}")
    db.commit()
    return repo.get(db, p.id)  # type: ignore[return-value]


def confirm_activity(db: Session, ctx: RequestContext, principal: Principal, project_id: uuid.UUID, reason: str) -> Project:
    p = get_project(db, principal, project_id, P.PROJECTS_MANAGE)
    require_status(p, ("STANDARD_SELECTED",), "Confirming the activity")
    _transition(db, ctx, p, "ACTIVITY_SELECTED", "PROJECT_STATUS_CHANGED", "ACTIVITY_CONFIRMED", reason)
    db.commit()
    return repo.get(db, p.id)  # type: ignore[return-value]


def reopen(db: Session, ctx: RequestContext, principal: Principal, project_id: uuid.UUID, reason: str) -> Project:
    p = get_project(db, principal, project_id, P.PROJECTS_MANAGE)
    require_status(p, ("STANDARD_SELECTED", "ACTIVITY_SELECTED", "METHODOLOGY_REVIEW"), "Re-opening the project")
    _transition(db, ctx, p, "DATA_COLLECTION", "PROJECT_STATUS_CHANGED", "REOPENED_FOR_CORRECTION", reason)
    p.eligibility_reviewed_at = p.eligibility_reviewed_by = None  # eligibility must be reviewed again
    p.methodology_status = "NOT_SELECTED"  # candidates must be evaluated again (earlier evaluations stay as history)
    db.commit()
    return repo.get(db, p.id)  # type: ignore[return-value]


def close(db: Session, ctx: RequestContext, principal: Principal, project_id: uuid.UUID, reason: str) -> Project:
    p = get_project(db, principal, project_id, P.PROJECTS_MANAGE)
    _transition(db, ctx, p, "CLOSED", "PROJECT_STATUS_CHANGED", "PROJECT_CLOSED", reason)
    db.commit()
    return repo.get(db, p.id)  # type: ignore[return-value]


def status_history(db: Session, principal: Principal, project_id: uuid.UUID) -> list[tuple[ProjectStatusHistory, str | None]]:
    p = get_project(db, principal, project_id)
    rows = repo.status_history(db, p.id)
    names = {u.id: u.full_name for u in db.scalars(select(User).where(User.id.in_({r.changed_by for r in rows if r.changed_by}))).all()} \
        if rows else {}
    return [(r, names.get(r.changed_by) if r.changed_by else None) for r in rows]


def to_json(data: object) -> str:
    return json.dumps(data, default=str, sort_keys=True)
