"""Who may see / act on a project's MRV data (organization-scoped RBAC; no second permission system).

- staff with the needed MRV / sampling permission in the project's organization (or platform-wide)
- field collectors (sampling.collect) only for sampling points assigned to them and their own collection records
Out-of-scope projects return 404 so their existence is not revealed.
"""
import uuid

from sqlalchemy.orm import Session

from app.core.errors import Conflict, NotFound, PermissionDenied
from app.models import MethodologyVersion, Project, ProjectMethodology
from app.repositories import projects as project_repo
from app.security.permissions import P
from app.security.principal import Principal

VISIBLE = (P.MRV_READ, P.MRV_MANAGE, P.MRV_COLLECT, P.MRV_REVIEW, P.MRV_APPROVE, P.SAMPLING_MANAGE, P.SAMPLING_ASSIGN, P.SAMPLING_COLLECT,
           P.SAMPLING_REVIEW)
# MRV continues after calculation starts (Phase 7): later periods and data corrections (which lead to a recalculation) stay possible.
MRV_STATES = ("METHODOLOGY_CONFIRMED", "MRV_PLANNED", "MONITORING", "CALCULATION_READY", "CALCULATED")


def not_found() -> NotFound:
    return NotFound("Project not found.", error_code="PROJECT_NOT_FOUND")


def project(db: Session, principal: Principal, project_id: uuid.UUID, *codes: str) -> Project:
    """Project if the caller holds any of `codes` in its organization; 403 if the project is visible but the action is
    not allowed; 404 otherwise."""
    p = project_repo.get(db, project_id)
    if p is None:
        raise not_found()
    if any(principal.can_in_org(c, p.organization_id) for c in codes or (P.MRV_READ,)):
        return p
    if any(principal.can_in_org(c, p.organization_id) for c in (*VISIBLE, P.PROJECTS_READ)):
        raise PermissionDenied(details={"required_permission": " or ".join(codes or (P.MRV_READ,))})
    raise not_found()


def can(principal: Principal, p: Project, code: str) -> bool:
    return principal.can_in_org(code, p.organization_id)


def locked_methodology(db: Session, p: Project) -> tuple[ProjectMethodology, MethodologyVersion]:
    """MRV runs only against a LOCKED methodology version that is still valid (APPROVED, or SUPERSEDED but locked)."""
    from sqlalchemy import select
    pm = db.scalars(select(ProjectMethodology).where(ProjectMethodology.project_id == p.id, ProjectMethodology.status == "LOCKED")).first()
    if pm is None or p.methodology_status != "CONFIRMED":
        raise Conflict("The project's methodology and version must be confirmed (locked) before MRV.", error_code="METHODOLOGY_NOT_LOCKED")
    v = db.get(MethodologyVersion, pm.methodology_version_id)
    if v is None or v.status not in ("APPROVED", "SUPERSEDED"):
        raise Conflict(f"The locked methodology version is {v.status if v else 'missing'}; MRV cannot use it.",
                       error_code="METHODOLOGY_VERSION_INVALID")
    if p.status not in MRV_STATES:
        raise Conflict(f"MRV is not possible while the project is {p.status}.", error_code="PROJECT_NOT_IN_MRV")
    return pm, v
