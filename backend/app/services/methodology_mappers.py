"""ORM → response mapping for methodologies and project methodology selection."""
import json
import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.models import Methodology, MethodologyEvaluation, MethodologyVersion, Project, ProjectMethodology, Standard, User
from app.schemas.methodologies import (
    CandidateOut,
    ChangeOut,
    EvaluationOut,
    MethodologyOut,
    ProjectMethodologyOut,
    ProjectMethodologyView,
    ReviewOut,
    RuleOut,
    RuleResultOut,
    VersionDetail,
    VersionOut,
)
from app.security.permissions import P
from app.security.principal import Principal
from app.services import methodology_service as msvc
from app.services import project_methodology_service as pms

VERSION_FIELDS = [f for f in VersionOut.model_fields if f != "rule_counts"]
RULE_COMMON = ("rule_code", "title", "description", "source_reference", "sort_order")


def version_out(db: Session, v: MethodologyVersion) -> VersionOut:
    rs = msvc.rules(db, v.id)
    return VersionOut.model_validate({**{f: getattr(v, f) for f in VERSION_FIELDS}, "rule_counts": {k: len(x) for k, x in rs.items()}})


def rule_out(kind: str, r: Any) -> RuleOut:
    data = {c.key: getattr(r, c.key) for c in r.__table__.columns
            if c.key not in ("id", "methodology_version_id", "created_at", *RULE_COMMON)}
    if kind == "applicability":
        data["expected_value"] = msvc.expected_value(data["expected_value"])
    if kind == "general" and data.get("parameters"):
        data["parameters"] = json.loads(data["parameters"])
    return RuleOut(id=r.id, kind=kind, data=data, **{k: getattr(r, k) for k in RULE_COMMON})  # type: ignore[arg-type]


def version_detail(db: Session, principal: Principal, m: Methodology, v: MethodologyVersion) -> VersionDetail:
    rs = msvc.rules(db, v.id)
    base = version_out(db, v)
    return VersionDetail(**base.model_dump(), methodology_code=m.code, methodology_name=m.name,
                         rules=[rule_out(k, r) for k, items in rs.items() for r in items],
                         can_edit=principal.has(P.METHODOLOGIES_MANAGE) and v.status == "DRAFT",
                         can_submit=principal.has(P.METHODOLOGIES_MANAGE) and v.status == "DRAFT",
                         can_approve=principal.has(P.METHODOLOGIES_APPROVE) and v.status == "IN_REVIEW" and v.submitted_by != principal.user_id)


def methodology_out(db: Session, m: Methodology) -> MethodologyOut:
    std = db.get(Standard, m.standard_id)
    return MethodologyOut(id=m.id, code=m.code, name=m.name, standard_id=m.standard_id, standard_name=std.name if std else None,
                          activity_ids=msvc.activity_ids(db, m.id), owner_name=m.owner_name, description=m.description,
                          source_url=m.source_url, status=m.status, environment=m.environment,
                          versions=[version_out(db, v) for v in msvc.versions(db, m.id)])


def change_out(c: Any) -> ChangeOut:
    return ChangeOut(id=c.id, methodology_version_id=c.methodology_version_id, change_type=c.change_type, summary=c.summary, reason=c.reason,
                     changed_by=c.changed_by, changed_at=c.changed_at, request_id=c.request_id)


def _names(db: Session, ids: set[uuid.UUID | None]) -> dict[uuid.UUID, str]:
    return {i: u.full_name for i in ids if i for u in [db.get(User, i)] if u}


def evaluation_out(db: Session, ev: MethodologyEvaluation) -> EvaluationOut:
    res = pms.results(db, ev.id)
    rvs = pms.reviews(db, [r.id for r in res])
    names = _names(db, {x.reviewed_by for x in rvs})
    cands = []
    for r in res:
        m = db.get(Methodology, r.methodology_id)
        v = db.get(MethodologyVersion, r.methodology_version_id)
        assert m is not None and v is not None
        rules = [RuleResultOut.model_validate(x) for x in json.loads(r.rule_results)]
        cands.append(CandidateOut(
            id=r.id, methodology_id=m.id, methodology_code=m.code, methodology_name=m.name, methodology_version_id=v.id,
            version_label=v.version_label, version_status=v.status, calculation_readiness=v.calculation_readiness,
            is_demo_illustrative=v.is_demo_illustrative, outcome=r.outcome, rules_version=r.rules_version, rules=rules,  # type: ignore[arg-type]
            evidence_requirements=sorted({x.evidence_requirement for x in rules if x.evidence_requirement and x.check in ("PASS", "FAIL")}),
            reviews=[ReviewOut(id=x.id, evaluation_result_id=x.evaluation_result_id, recommendation=x.recommendation, notes=x.notes,
                               evidence_acknowledged=x.evidence_acknowledged, reviewed_by=x.reviewed_by,
                               reviewer_name=names.get(x.reviewed_by) if x.reviewed_by else None, reviewed_at=x.reviewed_at)
                     for x in rvs if x.evaluation_result_id == r.id]))
    order = {"APPLICABLE": 0, "EVIDENCE_REQUIRED": 1, "NEEDS_INFORMATION": 2, "NOT_APPLICABLE": 3}
    cands.sort(key=lambda c: (order[c.outcome], c.methodology_code, c.version_label))
    return EvaluationOut(id=ev.id, project_id=ev.project_id, engine_version=ev.engine_version, facts=json.loads(ev.facts),
                         candidate_count=ev.candidate_count, evaluated_by=ev.evaluated_by, evaluated_at=ev.evaluated_at, candidates=cands)


def project_methodology_out(db: Session, pm: ProjectMethodology) -> ProjectMethodologyOut:
    m = db.get(Methodology, pm.methodology_id)
    v = db.get(MethodologyVersion, pm.methodology_version_id)
    assert m is not None and v is not None
    newer = any(x.status == "APPROVED" and x.version_number > v.version_number for x in msvc.versions(db, m.id))
    return ProjectMethodologyOut(id=pm.id, methodology_id=m.id, methodology_code=m.code, methodology_name=m.name, methodology_version_id=v.id,
                                 version_label=v.version_label, version_status=v.status, rules_version=pm.rules_version,
                                 monitoring_rules_version=pm.monitoring_rules_version, calculation_rules_version=pm.calculation_rules_version,
                                 calculation_readiness=v.calculation_readiness, status=pm.status, confirmation_notes=pm.confirmation_notes,
                                 confirmed_by=pm.confirmed_by, locked_at=pm.locked_at, unlocked_at=pm.unlocked_at,
                                 unlock_reason=pm.unlock_reason, newer_version_available=newer)


def project_view(db: Session, principal: Principal, p: Project) -> ProjectMethodologyView:
    latest = pms.latest_evaluation(db, p.id)
    cur = pms.current(db, p.id)
    evs = pms.evaluations(db, principal, p.id)
    findings: list[str] = []
    if cur is not None:
        v = db.get(MethodologyVersion, cur.methodology_version_id)
        if v is not None:
            findings = pms.crediting_period_findings(db, p, v)
    return ProjectMethodologyView(methodology_status=p.methodology_status, project_status=p.status,
                                  current=project_methodology_out(db, cur) if cur else None,
                                  history=[project_methodology_out(db, x) for x in pms.history(db, p.id)],
                                  latest_evaluation=evaluation_out(db, latest) if latest else None, evaluation_count=len(evs),
                                  findings=findings, **pms.permissions(principal, p))
