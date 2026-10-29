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
MRV_STATES = ("METHODOLOGY_CONFIRMED", "MRV_PLANNED", "MONITORING", "CALCULATION_READY", "CALCULATED", "VERIFICATION", "VERIFIED", "ISSUED")
# A CLOSED project keeps its MRV / laboratory / calculation history READABLE (it may have been credited); every write is refused.
# A request is a read when one of the codes it asks for is a read permission (`project(..)` without codes reads with mrv.read).
READ_CODES = frozenset({P.MRV_READ, P.LAB_READ, P.LAB_LAB_READ, P.CALCULATION_READ, P.PROJECTS_READ})


def is_write(codes: tuple[str, ...]) -> bool:
    return bool(codes) and not any(c in READ_CODES for c in codes)


def require_open(p: Project, what: str = "MRV, laboratory and calculation records") -> None:
    """Refuse a write on a CLOSED project (its history stays readable)."""
    if p.status == "CLOSED":
        raise Conflict(f"The project is CLOSED: its {what} are read-only.", error_code="PROJECT_CLOSED",
                       details={"project_code": p.project_code})


def not_found() -> NotFound:
    return NotFound("Project not found.", error_code="PROJECT_NOT_FOUND")


def project(db: Session, principal: Principal, project_id: uuid.UUID, *codes: str) -> Project:
    """Project if the caller holds any of `codes` in its organization; 403 if the project is visible but the action is
    not allowed; 404 otherwise."""
    p = project_repo.get(db, project_id)
    if p is None:
        raise not_found()
    if any(principal.can_in_org(c, p.organization_id) for c in codes or (P.MRV_READ,)):
        if is_write(codes):
            require_open(p)
        return p
    if any(principal.can_in_org(c, p.organization_id) for c in (*VISIBLE, P.PROJECTS_READ)):
        raise PermissionDenied(details={"required_permission": " or ".join(codes or (P.MRV_READ,))})
    raise not_found()


def can(principal: Principal, p: Project, code: str) -> bool:
    return principal.can_in_org(code, p.organization_id)


def locked_methodology(db: Session, p: Project, *, read_only: bool = False) -> tuple[ProjectMethodology, MethodologyVersion]:
    """MRV runs only against a LOCKED methodology version that is still valid (APPROVED, or SUPERSEDED but locked).
    `read_only` (views such as the requirements or a stratum's required characteristics): a CLOSED project's locked version is
    still shown, whatever its status since (a version may be retired once no open project is locked to it)."""
    from sqlalchemy import select
    pm = db.scalars(select(ProjectMethodology).where(ProjectMethodology.project_id == p.id, ProjectMethodology.status == "LOCKED")).first()
    if pm is None or p.methodology_status != "CONFIRMED":
        raise Conflict("The project's methodology and version must be confirmed (locked) before MRV.", error_code="METHODOLOGY_NOT_LOCKED")
    v = db.get(MethodologyVersion, pm.methodology_version_id)
    if read_only and v is not None and p.status in (*MRV_STATES, "CLOSED"):
        return pm, v
    require_open(p)
    if v is None or v.status not in ("APPROVED", "SUPERSEDED"):
        raise Conflict(f"The locked methodology version is {v.status if v else 'missing'}; MRV cannot use it.",
                       error_code="METHODOLOGY_VERSION_INVALID")
    if p.status not in MRV_STATES:
        raise Conflict(f"MRV is not possible while the project is {p.status}.", error_code="PROJECT_NOT_IN_MRV")
    return pm, v
