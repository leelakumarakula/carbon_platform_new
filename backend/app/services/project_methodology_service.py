"""Project methodology selection (spec section 9): facts → candidate evaluation → specialist review → confirm → lock.

- Facts are derived from the project's own records (project, participating farms, farm history, baseline, crediting
  period). Users may *declare* extra facts (e.g. an additionality assessment); declared facts are labelled DECLARED,
  cannot override derived facts, and make evidence-bearing rules return EVIDENCE_REQUIRED.
- Candidates: APPROVED, effective versions of ACTIVE methodologies of the project's standard covering its activity.
  Drafts and versions under review are never candidates.
- The engine proposes; a methodology specialist records a recommendation; the project developer (projects.manage)
  confirms a recommended candidate, which locks methodology + version (+ rule-set revisions). Unlocking is explicit,
  needs a reason and is audited — a locked version never changes silently.
"""
import json
import uuid
from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit.service import record
from app.core.context import RequestContext
from app.core.errors import Conflict, NotFound, PermissionDenied, ValidationFailed
from app.models import (
    Activity,
    Farm,
    FarmEvidence,
    Methodology,
    MethodologyActivity,
    MethodologyEvaluation,
    MethodologyEvaluationResult,
    MethodologyVersion,
    Project,
    ProjectMethodology,
    ProjectMethodologyReview,
    Standard,
    User,
)
from app.models.base import utcnow
from app.models.farms import FarmCropHistory, FarmLandHistory, FarmPracticeHistory
from app.repositories import projects as repo
from app.rules.methodology_engine import ENGINE_VERSION, Fact, RuleSpec, evaluate
from app.schemas.methodologies import ConfirmIn, ReviewIn
from app.security.permissions import P
from app.security.principal import Principal
from app.services import methodology_service as msvc
from app.services import project_service as psvc
from app.services.notification_service import notify

ENTITY = "project"
EVALUABLE = ("ACTIVITY_SELECTED", "METHODOLOGY_REVIEW")


# ---------------------------------------------------------------- facts
def _current(db: Session, model: Any, farm_ids: list[uuid.UUID]) -> list[Any]:
    if not farm_ids:
        return []
    return list(db.scalars(select(model).where(model.farm_id.in_(farm_ids), model.is_current == True,  # noqa: E712
                                               model.is_retracted == False)).all())  # noqa: E712


def build_facts(db: Session, p: Project) -> dict[str, Fact]:
    """System-derived facts. Keys are documented in docs/methodology-engine.md."""
    facts: dict[str, Fact] = {}

    def put(key: str, value: Any, source: str, detail: str = "") -> None:
        facts[key] = Fact(value, source, detail)

    std = db.get(Standard, p.standard_id) if p.standard_id else None
    act = db.get(Activity, p.activity_id) if p.activity_id else None
    put("standard_code", std.code if std else None, "PROJECT")
    put("activity_code", act.code if act else None, "PROJECT")
    put("country", p.country, "PROJECT")
    put("project_type", p.project_type, "PROJECT")
    put("project_start_date", p.start_date.isoformat() if p.start_date else None, "PROJECT")
    pfs = repo.project_farms(db, p.id, active_only=True)
    farms = [f for f in (db.get(Farm, x.farm_id) for x in pfs) if f]
    ids = [f.id for f in farms]
    put("farm_count", len(farms), "PROJECT")
    put("farm_countries", sorted({f.country for f in farms}), "FARM_DATA")
    put("farm_states", sorted({f.state for f in farms if f.state}), "FARM_DATA")
    put("farm_districts", sorted({f.district for f in farms if f.district}), "FARM_DATA")
    put("farms_all_verified", bool(farms) and all(f.status == "VERIFIED" for f in farms), "FARM_DATA")
    b = repo.current_boundary(db, p.id)
    put("project_area_ha", float(b.area_hectares) if b else None, "PROJECT", "SQL Server project boundary")
    land = _current(db, FarmLandHistory, ids)
    if land:
        latest: dict[uuid.UUID, FarmLandHistory] = {}
        for r in land:
            if r.farm_id not in latest or r.year > latest[r.farm_id].year:
                latest[r.farm_id] = r
        put("land_use_current", sorted({r.land_use for r in latest.values()}), "FARM_DATA", "latest land-use record per farm")
        put("land_use_all_years", sorted({r.land_use for r in land}), "FARM_DATA")
        years = [len({r.year for r in land if r.farm_id == fid}) for fid in ids]
        put("land_use_history_years_min", min(years) if years else 0, "FARM_DATA", "fewest years of land-use history of any farm")
    # "No records" is missing information, not a negative fact: these facts are only set when data exists.
    crop = _current(db, FarmCropHistory, ids)
    if crop:
        cyears = [len({r.year for r in crop if r.farm_id == fid}) for fid in ids]
        put("crop_history_years_min", min(cyears), "FARM_DATA")
        put("crops", sorted({r.crop_name for r in crop}), "FARM_DATA")
    practice = _current(db, FarmPracticeHistory, ids)
    for phase in ("HISTORICAL", "CURRENT", "PROPOSED"):
        rows = [r for r in practice if r.practice_phase == phase]
        if rows:
            put(f"{phase.lower()}_practice_categories", sorted({r.practice_category for r in rows}), "FARM_DATA")
            put(f"{phase.lower()}_practice_types", sorted({r.practice_type for r in rows}), "FARM_DATA")
    baseline = next((x for x in repo.baselines(db, p.id) if x.is_current), None)
    put("baseline_recorded", baseline is not None, "PROJECT")
    put("baseline_period_years", round((baseline.period_end - baseline.period_start).days / 365.25, 2) if baseline else None, "PROJECT")
    periods = [c for c in repo.crediting_periods(db, p.id) if c.status == "PROPOSED"]
    put("crediting_period_years", round((periods[0].end_date - periods[0].start_date).days / 365.25, 2) if periods else None, "PROJECT")
    rights = [r for r in repo.carbon_rights(db, p.id) if r.status == "ACTIVE"]
    put("carbon_rights_all_verified", bool(rights) and all(r.verification_status == "VERIFIED" for r in rights), "PROJECT")
    ev = db.scalars(select(FarmEvidence).where(FarmEvidence.farm_id.in_(ids))).all() if ids else []
    put("verified_evidence_count", sum(1 for e in ev if e.verification_status == "VERIFIED"), "FARM_DATA")
    return facts


def _facts_json(facts: dict[str, Fact]) -> dict[str, Any]:
    return {k: {"value": f.value, "source": f.source, "detail": f.detail} for k, f in sorted(facts.items())}


def candidate_versions(db: Session, p: Project) -> list[tuple[Methodology, MethodologyVersion]]:
    if not (p.standard_id and p.activity_id):
        return []
    ref = p.start_date or date.today()
    ms = db.scalars(select(Methodology).join(MethodologyActivity, MethodologyActivity.methodology_id == Methodology.id).where(
        Methodology.standard_id == p.standard_id, MethodologyActivity.activity_id == p.activity_id, Methodology.status == "ACTIVE",
        Methodology.environment == p.environment).order_by(Methodology.code)).all()
    out = []
    for m in ms:
        for v in msvc.versions(db, m.id):
            if v.status == "APPROVED" and (v.effective_from is None or v.effective_from <= ref) and (v.effective_to is None or v.effective_to >= ref):
                out.append((m, v))
    return out


def _specs(db: Session, v: MethodologyVersion) -> list[RuleSpec]:
    return [RuleSpec(rule_code=r.rule_code, title=r.title, category=r.category, fact_key=r.fact_key, operator=r.operator,
                     expected=msvc.expected_value(r.expected_value), on_fail=r.on_fail,
                     evidence_requirement=r.evidence_requirement, mandatory=r.mandatory, source_reference=r.source_reference)
            for r in msvc.rules(db, v.id)["applicability"]]


# ---------------------------------------------------------------- permissions
def _can_evaluate(principal: Principal, p: Project) -> bool:
    return principal.can_in_org(P.PROJECTS_MANAGE, p.organization_id) or principal.can_in_org(P.METHODOLOGIES_REVIEW_PROJECT, p.organization_id)


# ---------------------------------------------------------------- evaluate
def run_evaluation(db: Session, ctx: RequestContext, principal: Principal, project_id: uuid.UUID,
                   declared: dict[str, Any]) -> MethodologyEvaluation:
    p = psvc.get_project(db, principal, project_id)
    if not _can_evaluate(principal, p):
        raise PermissionDenied(details={"required_permission": f"{P.PROJECTS_MANAGE} or {P.METHODOLOGIES_REVIEW_PROJECT}"})
    psvc.require_status(p, EVALUABLE, "Evaluating methodology candidates")
    facts = build_facts(db, p)
    clash = sorted(k for k in declared if k in facts)
    if clash:
        raise ValidationFailed("These facts come from project data and cannot be declared: " + ", ".join(clash) + ".",
                               error_code="DECLARED_FACT_CONFLICT", details={"keys": clash})
    who = db.get(User, principal.user_id)
    for k, val in declared.items():
        facts[k] = Fact(val, "DECLARED", f"declared by {who.full_name if who else principal.user_id}")
    cands = candidate_versions(db, p)
    ev = MethodologyEvaluation(project_id=p.id, standard_id=p.standard_id, activity_id=p.activity_id, engine_version=ENGINE_VERSION,
                               facts=json.dumps(_facts_json(facts), default=str), candidate_count=len(cands), evaluated_by=principal.user_id,
                               request_id=ctx.request_id)
    db.add(ev)
    db.flush()
    summary = []
    for m, v in cands:
        out = evaluate(_specs(db, v), facts)
        db.add(MethodologyEvaluationResult(evaluation_id=ev.id, methodology_id=m.id, methodology_version_id=v.id, outcome=out.outcome,
                                           rules_version=v.rules_version,
                                           rule_results=json.dumps([r.as_dict() for r in out.rules], default=str)))
        summary.append({"methodology": m.code, "version": v.version_label, "outcome": out.outcome})
    record(db, ctx, "PROJECT_METHODOLOGY_CANDIDATES_EVALUATED", ENTITY, p.id, None,
           {"evaluation_id": ev.id, "engine_version": ENGINE_VERSION, "candidates": summary,
            "declared_facts": sorted(declared)}, organization_id=p.organization_id)
    if p.status == "ACTIVITY_SELECTED":
        psvc.transition_to(db, ctx, p, "METHODOLOGY_REVIEW", "PROJECT_STATUS_CHANGED", "METHODOLOGY_REVIEW_STARTED",
                           "Methodology candidates evaluated")
        p.methodology_status = "UNDER_REVIEW"
    db.commit()
    return ev


def latest_evaluation(db: Session, project_id: uuid.UUID) -> MethodologyEvaluation | None:
    return db.scalars(select(MethodologyEvaluation).where(MethodologyEvaluation.project_id == project_id)
                      .order_by(MethodologyEvaluation.evaluated_at.desc())).first()


def evaluations(db: Session, principal: Principal, project_id: uuid.UUID) -> list[MethodologyEvaluation]:
    p = psvc.get_project(db, principal, project_id)
    return list(db.scalars(select(MethodologyEvaluation).where(MethodologyEvaluation.project_id == p.id)
                           .order_by(MethodologyEvaluation.evaluated_at.desc())).all())


def results(db: Session, evaluation_id: uuid.UUID) -> list[MethodologyEvaluationResult]:
    return list(db.scalars(select(MethodologyEvaluationResult).where(MethodologyEvaluationResult.evaluation_id == evaluation_id)).all())


def reviews(db: Session, result_ids: list[uuid.UUID]) -> list[ProjectMethodologyReview]:
    if not result_ids:
        return []
    return list(db.scalars(select(ProjectMethodologyReview).where(ProjectMethodologyReview.evaluation_result_id.in_(result_ids))
                           .order_by(ProjectMethodologyReview.reviewed_at)).all())


def _result_of_project(db: Session, p: Project, result_id: uuid.UUID) -> MethodologyEvaluationResult:
    r = db.get(MethodologyEvaluationResult, result_id)
    ev = db.get(MethodologyEvaluation, r.evaluation_id) if r else None
    if r is None or ev is None or ev.project_id != p.id:
        raise NotFound("Candidate not found.", error_code="CANDIDATE_NOT_FOUND")
    return r


# ---------------------------------------------------------------- specialist review
def review_candidate(db: Session, ctx: RequestContext, principal: Principal, project_id: uuid.UUID, data: ReviewIn) -> ProjectMethodologyReview:
    p = psvc.get_project(db, principal, project_id)
    principal.require_in_org(P.METHODOLOGIES_REVIEW_PROJECT, p.organization_id)
    psvc.require_status(p, ("METHODOLOGY_REVIEW",), "Reviewing methodology candidates")
    r = _result_of_project(db, p, data.evaluation_result_id)
    if data.recommendation == "RECOMMENDED":
        if r.outcome in ("NOT_APPLICABLE", "NEEDS_INFORMATION"):
            raise Conflict(f"A {r.outcome} candidate cannot be recommended. Complete the information or choose another candidate.",
                           error_code="CANDIDATE_NOT_ELIGIBLE")
        if r.outcome == "EVIDENCE_REQUIRED" and not data.evidence_acknowledged:
            raise ValidationFailed("Confirm that the required evidence has been checked or is planned.", error_code="EVIDENCE_NOT_ACKNOWLEDGED")
    rv = ProjectMethodologyReview(project_id=p.id, evaluation_result_id=r.id, recommendation=data.recommendation, notes=data.notes,
                                  evidence_acknowledged=data.evidence_acknowledged, reviewed_by=principal.user_id)
    db.add(rv)
    db.flush()
    v = db.get(MethodologyVersion, r.methodology_version_id)
    record(db, ctx, "PROJECT_METHODOLOGY_REVIEWED", ENTITY, p.id, None,
           {"review_id": rv.id, "evaluation_result_id": r.id, "methodology_version_id": r.methodology_version_id,
            "version_label": v.version_label if v else None, "outcome": r.outcome, "recommendation": data.recommendation},
           data.notes, organization_id=p.organization_id)
    notify(db, psvc._team(db, p, "PROJECT_MANAGER"), "PROJECT_METHODOLOGY_REVIEWED",
           f"Methodology candidate {data.recommendation.lower().replace('_', ' ')}: {p.project_code}", data.notes, ENTITY, p.id,
           f"/projects/{p.id}?tab=methodology")
    db.commit()
    return rv


# ---------------------------------------------------------------- confirm / lock / unlock
def crediting_period_findings(db: Session, p: Project, v: MethodologyVersion) -> list[str]:
    """Apply crediting-period parameters only if the specialist configured them on the version (min_years/max_years)."""
    out = []
    periods = [c for c in repo.crediting_periods(db, p.id) if c.status == "PROPOSED"]
    for rule in msvc.rules(db, v.id)["general"]:
        if rule.rule_type != "CREDITING_PERIOD" or not rule.parameters:
            continue
        params = json.loads(rule.parameters)
        for c in periods:
            years = (c.end_date - c.start_date).days / 365.25
            if "min_years" in params and years + 1e-9 < float(params["min_years"]):
                out.append(f"Crediting period #{c.period_number} is {years:.2f} years; {rule.rule_code} requires at least {params['min_years']}.")
            if "max_years" in params and years - 1e-9 > float(params["max_years"]):
                out.append(f"Crediting period #{c.period_number} is {years:.2f} years; {rule.rule_code} allows at most {params['max_years']}.")
    return out


def confirm(db: Session, ctx: RequestContext, principal: Principal, project_id: uuid.UUID, data: ConfirmIn) -> ProjectMethodology:
    p = psvc.get_project(db, principal, project_id, P.PROJECTS_MANAGE)
    psvc.require_status(p, ("METHODOLOGY_REVIEW",), "Confirming the methodology")
    r = _result_of_project(db, p, data.evaluation_result_id)
    latest = latest_evaluation(db, p.id)
    if latest is None or r.evaluation_id != latest.id:
        raise Conflict("This candidate comes from an older evaluation. Confirm a candidate of the latest evaluation.",
                       error_code="EVALUATION_OUTDATED")
    if r.outcome not in ("APPLICABLE", "EVIDENCE_REQUIRED"):
        raise Conflict(f"A {r.outcome} candidate cannot be confirmed.", error_code="CANDIDATE_NOT_ELIGIBLE")
    rvs = reviews(db, [r.id])
    last = rvs[-1] if rvs else None
    if last is None or last.recommendation != "RECOMMENDED":
        raise Conflict("A methodology specialist must recommend this candidate before it can be confirmed.", error_code="SPECIALIST_REVIEW_REQUIRED")
    if last.reviewed_by == principal.user_id:
        raise PermissionDenied("You recommended this candidate, so someone else must confirm it.", error_code="SEPARATION_OF_DUTIES")
    v = db.get(MethodologyVersion, r.methodology_version_id)
    m = db.get(Methodology, r.methodology_id)
    assert v is not None and m is not None
    if v.status != "APPROVED":
        raise Conflict(f"Version {v.version_label} is now {v.status}; evaluate again.", error_code="VERSION_NOT_APPROVED")
    findings = crediting_period_findings(db, p, v)
    if findings:
        raise Conflict("The proposed crediting period does not meet the version's configured rules: " + " ".join(findings),
                       error_code="CREDITING_PERIOD_NOT_COMPLIANT", details={"findings": findings})
    pm = ProjectMethodology(project_id=p.id, methodology_id=m.id, methodology_version_id=v.id, evaluation_result_id=r.id, review_id=last.id,
                            rules_version=v.rules_version, monitoring_rules_version=v.monitoring_rules_version,
                            calculation_rules_version=v.calculation_rules_version, confirmation_notes=data.notes, confirmed_by=principal.user_id)
    db.add(pm)
    db.flush()
    psvc.transition_to(db, ctx, p, "METHODOLOGY_CONFIRMED", "PROJECT_STATUS_CHANGED", "METHODOLOGY_CONFIRMED", data.notes)
    p.methodology_id, p.methodology_version_id, p.methodology_status = m.id, v.id, "CONFIRMED"
    record(db, ctx, "PROJECT_METHODOLOGY_CONFIRMED", ENTITY, p.id, None,
           {"project_methodology_id": pm.id, "methodology_id": m.id, "methodology_code": m.code, "methodology_version_id": v.id,
            "version_label": v.version_label, "rules_version": v.rules_version, "monitoring_rules_version": v.monitoring_rules_version,
            "calculation_rules_version": v.calculation_rules_version, "evaluation_result_id": r.id, "review_id": last.id,
            "outcome": r.outcome, "locked": True}, data.notes, organization_id=p.organization_id)
    db.commit()
    return pm


def unlock(db: Session, ctx: RequestContext, principal: Principal, project_id: uuid.UUID, reason: str) -> ProjectMethodology:
    p = psvc.get_project(db, principal, project_id, P.PROJECTS_MANAGE)
    psvc.require_status(p, ("METHODOLOGY_CONFIRMED",), "Unlocking the methodology")
    pm = current(db, p.id)
    if pm is None:
        raise Conflict("No locked methodology.", error_code="NOT_LOCKED")
    pm.status, pm.unlocked_by, pm.unlocked_at, pm.unlock_reason = "UNLOCKED", principal.user_id, utcnow(), reason
    psvc.transition_to(db, ctx, p, "METHODOLOGY_REVIEW", "PROJECT_STATUS_CHANGED", "METHODOLOGY_UNLOCKED", reason)
    old = {"methodology_id": p.methodology_id, "methodology_version_id": p.methodology_version_id, "methodology_status": "CONFIRMED"}
    p.methodology_id = p.methodology_version_id = None
    p.methodology_status = "UNDER_REVIEW"
    record(db, ctx, "PROJECT_METHODOLOGY_UNLOCKED", ENTITY, p.id, old, {"methodology_status": "UNDER_REVIEW",
                                                                        "project_methodology_id": pm.id}, reason, organization_id=p.organization_id)
    db.commit()
    return pm


def current(db: Session, project_id: uuid.UUID) -> ProjectMethodology | None:
    return db.scalars(select(ProjectMethodology).where(ProjectMethodology.project_id == project_id, ProjectMethodology.status == "LOCKED")).first()


def history(db: Session, project_id: uuid.UUID) -> list[ProjectMethodology]:
    return list(db.scalars(select(ProjectMethodology).where(ProjectMethodology.project_id == project_id)
                           .order_by(ProjectMethodology.locked_at.desc())).all())


def permissions(principal: Principal, p: Project) -> dict[str, bool]:
    return {"can_evaluate": _can_evaluate(principal, p) and p.status in EVALUABLE,
            "can_review": principal.can_in_org(P.METHODOLOGIES_REVIEW_PROJECT, p.organization_id) and p.status == "METHODOLOGY_REVIEW",
            "can_confirm": principal.can_in_org(P.PROJECTS_MANAGE, p.organization_id) and p.status == "METHODOLOGY_REVIEW",
            "can_unlock": principal.can_in_org(P.PROJECTS_MANAGE, p.organization_id) and p.status == "METHODOLOGY_CONFIRMED"}


def lineage_pointer(db: Session, p: Project) -> dict[str, Any]:
    """For later phases: the exact methodology + version + rule revisions the project is locked to."""
    pm = current(db, p.id)
    return {} if pm is None else {"methodology_id": pm.methodology_id, "methodology_version_id": pm.methodology_version_id,
                                  "rules_version": pm.rules_version, "monitoring_rules_version": pm.monitoring_rules_version,
                                  "calculation_rules_version": pm.calculation_rules_version}
