"""DEMO methodologies (spec section 43: "2 methodology versions"), created through the real services.

These are ILLUSTRATIVE demo entries: the rules are invented for demonstration of the engine and are NOT taken from
any real methodology (VM0042, CCTS or other). Versions are flagged `is_demo_illustrative` and every calculation
rule is NOT_IMPLEMENTED. The DEMO project B is then taken through candidate evaluation → specialist review →
confirmation, which locks its methodology version. Project A stays in data collection.
"""
from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Activity, Methodology, Project, Standard
from app.schemas.methodologies import (
    ApplicabilityRuleIn,
    CalculationRuleIn,
    ConfirmIn,
    MethodologyIn,
    MonitoringRuleIn,
    ReviewIn,
    VersionIn,
)
from app.seed.demo_farms import _actor
from app.services import methodology_service, project_methodology_service

NOTE = "DEMO ILLUSTRATIVE ENTRY — rules invented for demonstration; not from any authoritative methodology."
RULES: list[dict[str, Any]] = [
    {"rule_code": "D1", "title": "Project located in India (DEMO rule)", "category": "COUNTRY", "fact_key": "country", "operator": "IN",
     "expected_value": ["IN"]},
    {"rule_code": "D2", "title": "Participating land is cropland (DEMO rule)", "category": "LAND_USE", "fact_key": "land_use_current",
     "operator": "ALL_IN", "expected_value": ["CROPLAND"]},
    {"rule_code": "D3", "title": "At least 5 years of land-use history (DEMO rule)", "category": "DATA_AVAILABILITY",
     "fact_key": "land_use_history_years_min", "operator": "GTE", "expected_value": 5},
    {"rule_code": "D4", "title": "A management change is proposed (DEMO rule)", "category": "PROPOSED_PRACTICE",
     "fact_key": "proposed_practice_categories", "operator": "ANY_IN", "expected_value": ["TILLAGE", "RESIDUE", "FERTILIZER", "COVER_CROP"]},
    {"rule_code": "D5", "title": "Additionality assessment completed (DEMO rule)", "category": "ADDITIONALITY",
     "fact_key": "additionality_assessment", "operator": "EQUALS", "expected_value": "COMPLETED",
     "evidence_requirement": "Additionality demonstration document (DEMO)"},
]


def _build(db: Session, code: str, name: str, standard_code: str, activity_codes: list[str], labels: list[str]) -> Methodology:
    author, a_ctx = _actor(db, "methodology")
    approver, b_ctx = _actor(db, "methodologyqa")
    std = db.scalars(select(Standard).where(Standard.code == standard_code)).one()
    acts = [db.scalars(select(Activity).where(Activity.code == c)).one().id for c in activity_codes]
    m = methodology_service.create_methodology(db, a_ctx, author, MethodologyIn(code=code, name=name, standard_id=std.id, activity_ids=acts,
                                                                                owner_name="DEMO", description=NOTE, environment="DEMO"))
    previous = None
    for label in labels:
        v = methodology_service.create_version(db, a_ctx, author, m.id, VersionIn(
            version_label=label, effective_from=date(2020, 1, 1), source_name="DEMO illustrative source (not authoritative)", notes=NOTE,
            based_on_version_id=previous.id if previous else None))
        if previous is None:
            for r in RULES:
                methodology_service.add_rule(db, a_ctx, author, v.id, "applicability", ApplicabilityRuleIn(**r))
            methodology_service.add_rule(db, a_ctx, author, v.id, "monitoring", MonitoringRuleIn(
                rule_code="DM1", title="Soil sampling per stratum (DEMO)", parameter="Soil organic carbon", unit="% / t C ha-1",
                measurement_source="LABORATORY",  # DEMO definition: SOC is analysed on the soil samples (decision V2-A)
                frequency="each verification (DEMO)", method="Configured in the MRV plan (Phase 5)"))
            methodology_service.add_rule(db, a_ctx, author, v.id, "calculation", CalculationRuleIn(
                rule_code="DC1", title="Net removals (placeholder; no equation)", step="NET",
                description="DEMO placeholder. No equation is implemented; calculation stays NOT_PRODUCTION_READY."))
        methodology_service.submit_version(db, a_ctx, author, v.id, "DEMO: ready for approval")
        if label.endswith("draft"):
            methodology_service.return_version(db, b_ctx, approver, v.id, "DEMO: kept as a draft to show drafts are never candidates")
        else:
            methodology_service.approve_version(db, b_ctx, approver, v.id, "DEMO: illustrative entry approved for demonstrations", None)
        previous = v
    return m


def seed_demo_methodologies(db: Session) -> dict[str, int]:
    if db.scalars(select(Methodology).where(Methodology.code == "DEMO-ALM-SOC")).first():
        return {"methodologies": 0, "locked_projects": 0}
    _build(db, "DEMO-ALM-SOC", "Agricultural land management – soil carbon (DEMO illustrative)", "DEMO-VCS",
           ["DEMO-ALM-TILLAGE", "DEMO-ALM-RESIDUE", "DEMO-ALM-NUTRIENT"], ["1.0", "2.0", "2.1-draft"])
    _build(db, "DEMO-CCTS-SOIL", "Soil carbon in agriculture under an offset route (DEMO illustrative)", "DEMO-CCTS-OFFSET",
           ["DEMO-ALM-TILLAGE", "DEMO-ALM-RESIDUE"], ["1.0"])
    locked = 0
    project_b = db.scalars(select(Project).where(Project.environment == "DEMO", Project.status == "ACTIVITY_SELECTED",
                                                 Project.name.like("Niphad%"))).first()
    if project_b is not None:
        pm, pm_ctx = _actor(db, "pm")
        spec, spec_ctx = _actor(db, "methodology")
        ev = project_methodology_service.run_evaluation(db, pm_ctx, pm, project_b.id, {"additionality_assessment": "COMPLETED"})
        cand = next((r for r in project_methodology_service.results(db, ev.id) if r.outcome in ("APPLICABLE", "EVIDENCE_REQUIRED")), None)
        if cand is not None:
            project_methodology_service.review_candidate(db, spec_ctx, spec, project_b.id, ReviewIn(
                evaluation_result_id=cand.id, recommendation="RECOMMENDED", evidence_acknowledged=True,
                notes="DEMO: candidate fits the recorded project data; additionality document requested"))
            project_methodology_service.confirm(db, pm_ctx, pm, project_b.id, ConfirmIn(
                evaluation_result_id=cand.id, notes="DEMO: methodology and version confirmed and locked"))
            locked = 1
    return {"methodologies": 2, "locked_projects": locked}
