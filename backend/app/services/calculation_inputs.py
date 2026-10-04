"""Calculation readiness and the frozen calculation input snapshot (decisions A5–A11, A18, A20, A22; C3, C4).

`evaluate()` is deterministic and read-only. It returns every blocker in a fixed order and, when nothing blocks, the snapshot:
canonical JSON of the project, period, approved dataset (+ its re-verified SHA-256), locked methodology, calculation rules,
module declaration and the copied input values with their source IDs and versions. The same data always gives the same
snapshot hash (no timestamps, no user, deterministic ordering).

Eligibility (nothing is ever substituted — no zero, average, previous, estimated or interpolated value):
- MRV: only the reporting period's APPROVED dataset; only records the dataset snapshot lists as authoritative methodology records
- laboratory: only APPROVED results of the same project, the locked methodology version, a LABORATORY rule of that version and the
  dataset plan's measurement, whose root sample belongs to this period and to a field collection version in the dataset snapshot
- numeric variables refuse text results (INPUT_NOT_NUMERIC); units must match the module's exact text (UNIT_MISMATCH)
"""
import json
import uuid
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.calculation import framework as fw
from app.calculation.registry import Resolver
from app.calculation.registry import bind as registry_bind
from app.calculation.registry import resolve as registry_resolve
from app.core.config import get_settings
from app.models import (
    DocumentVersion,
    FieldCollectionRecord,
    LabResult,
    LabSample,
    Methodology,
    MethodologyCalculationRule,
    MethodologyMonitoringRule,
    MethodologyVersion,
    MonitoringPeriod,
    MonitoringRecord,
    MrvDataset,
    MrvPlanMeasurement,
    Project,
    ProjectCreditingPeriod,
    ProjectMethodology,
    ProjectStratum,
    SamplingDesignVersion,
    SamplingPoint,
    StratumCharacteristic,
    StratumFarm,
)

# later monitoring periods are calculated while the project is in (aggregate) verification (Phase 8B, C2)
CALC_PROJECT_STATES = ("MONITORING", "CALCULATION_READY", "CALCULATED", "VERIFICATION", "VERIFIED", "ISSUED")
STEP_LABELS = {fw.IMPLEMENTED: "Implemented", fw.NOT_INCLUDED_DEMO: "Not included — DEMO", "NOT_CONFIGURED": "CONFIGURATION_REQUIRED"}


@dataclass
class Blocker:
    code: str
    message: str
    reason: str | None = None
    details: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {"code": self.code, "message": self.message, "reason": self.reason, "details": self.details}


@dataclass
class Evaluation:
    project: Project
    period: MonitoringPeriod
    pm: ProjectMethodology | None = None
    version: MethodologyVersion | None = None
    methodology: Methodology | None = None
    module: fw.CalculationModule | None = None
    dataset: MrvDataset | None = None
    blockers: list[Blocker] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    steps: list[dict[str, Any]] = field(default_factory=list)
    calc_rules: list[MethodologyCalculationRule] = field(default_factory=list)
    inputs: list[dict[str, Any]] = field(default_factory=list)
    snapshot: dict[str, Any] | None = None
    snapshot_sha256: str | None = None
    previous_period: MonitoringPeriod | None = None
    previous_dataset: MrvDataset | None = None

    @property
    def ready(self) -> bool:
        return not self.blockers and self.snapshot is not None


def locked(db: Session, p: Project) -> ProjectMethodology | None:
    return db.scalars(select(ProjectMethodology).where(ProjectMethodology.project_id == p.id, ProjectMethodology.status == "LOCKED")).first()


def approved_dataset(db: Session, period_id: uuid.UUID) -> MrvDataset | None:
    return db.scalars(select(MrvDataset).where(MrvDataset.monitoring_period_id == period_id, MrvDataset.status == "APPROVED")).first()


def latest_dataset(db: Session, period_id: uuid.UUID) -> MrvDataset | None:
    return db.scalars(select(MrvDataset).where(MrvDataset.monitoring_period_id == period_id).order_by(MrvDataset.version.desc())).first()


def calc_rules(db: Session, version_id: uuid.UUID) -> list[MethodologyCalculationRule]:
    return list(db.scalars(select(MethodologyCalculationRule).where(MethodologyCalculationRule.methodology_version_id == version_id)
                           .order_by(MethodologyCalculationRule.sort_order, MethodologyCalculationRule.rule_code)).all())


def step_statuses(module: fw.CalculationModule | None) -> list[dict[str, Any]]:
    out = []
    for name in fw.STEPS:
        spec = module.step(name) if module else None
        status = spec.status if spec else "NOT_CONFIGURED"
        out.append({"step": name, "status": status, "rule_code": spec.rule_code if spec else None, "label": STEP_LABELS.get(status, status)})
    return out


def evaluate(db: Session, p: Project, period: MonitoringPeriod, crediting: ProjectCreditingPeriod | None = None,
             resolver: Resolver | None = None) -> Evaluation:
    """Readiness + snapshot. Blocker order: lock → project state → module (C3/C4) → readiness → rules → steps → dataset →
    crediting period → inputs → size guard."""
    ev = Evaluation(p, period)
    settings = get_settings()
    pm = locked(db, p)
    if pm is None or p.methodology_status != "CONFIRMED":
        ev.blockers.append(Blocker("METHODOLOGY_NOT_LOCKED", "The project's methodology and version must be locked."))
        return ev
    ev.pm, ev.version, ev.methodology = pm, db.get(MethodologyVersion, pm.methodology_version_id), db.get(Methodology, pm.methodology_id)
    assert ev.version is not None and ev.methodology is not None
    ev.calc_rules = calc_rules(db, ev.version.id)
    if p.status not in CALC_PROJECT_STATES:
        ev.blockers.append(Blocker("PROJECT_NOT_IN_MRV", f"Calculation needs a project in monitoring (it is {p.status})."))
    # ---- module (decision A1 / A2 / A10; C3 / C4)
    selected = ev.version.calculation_module_code
    module = (resolver(ev.methodology.code, ev.version.version_label) if resolver
              else registry_resolve(ev.methodology.code, ev.version.version_label, selected))
    if module is not None and selected and module.code != selected:
        ev.blockers.append(Blocker("CONFIGURATION_REQUIRED", f"The methodology version selected calculation module {selected}, which is not "
                                   "the registered module for it.", "MODULE_SELECTION_MISMATCH", {"selected": selected, "registered": module.code}))
    if module is not None and module.calculation_rules_version == 0:
        if selected == module.code:
            module = registry_bind(module, ev.version.calculation_rules_version, ev.version.calculation_readiness)
        else:
            ev.blockers.append(Blocker("CONFIGURATION_REQUIRED", f"Calculation module {module.code} is available for this methodology version but "
                                       "has not been selected on its Calculation tab and approved.", "MODULE_NOT_SELECTED",
                                       {"module": module.code}))
    ev.module = module
    ev.steps = step_statuses(module)
    if module is None:
        ev.blockers.append(Blocker("CONFIGURATION_REQUIRED", "No calculation module is registered for the locked methodology version "
                                   f"{ev.methodology.code} {ev.version.version_label}. Nothing can be calculated.", "NO_CALCULATION_MODULE",
                                   {"methodology_code": ev.methodology.code, "version_label": ev.version.version_label}))
    else:
        if module.readiness != fw.PRODUCTION_READY:
            if settings.is_production:
                ev.blockers.append(Blocker("NOT_PRODUCTION_READY", f"Module {module.code} {module.version} is NOT_PRODUCTION_READY and is "
                                           "blocked in production."))
            else:
                ev.warnings.append(f"Module {module.code} {module.version} is NOT_PRODUCTION_READY: non-production use only.")
        version_rules = {r.rule_code: r.step for r in ev.calc_rules}
        missing = sorted(set(version_rules) - set(module.rules))
        extra = sorted(set(module.rules) - set(version_rules))
        wrong_step = sorted(c for c in set(version_rules) & set(module.rules) if version_rules[c] != module.rules[c])
        versions_ok = module.calculation_rules_version == pm.calculation_rules_version == ev.version.calculation_rules_version
        if missing or extra or wrong_step or not versions_ok:
            ev.blockers.append(Blocker("CALCULATION_RULE_NOT_CONFIGURED", "The calculation module does not match the locked version's "
                                       "calculation rules exactly.", "RULE_MODULE_MISMATCH",
                                       {"missing_in_module": missing, "not_in_methodology": extra, "step_mismatch": wrong_step,
                                        "module_rules_version": module.calculation_rules_version,
                                        "locked_rules_version": pm.calculation_rules_version}))
        for s in ev.steps:
            spec = module.step(s["step"])
            if spec is None:
                ev.blockers.append(Blocker("CONFIGURATION_REQUIRED", f"Step {s['step']} is not configured by the module.", "STEP_NOT_CONFIGURED",
                                           {"step": s["step"]}))
            elif spec.status == fw.NOT_INCLUDED_DEMO:
                if p.environment != "DEMO" or settings.is_production:
                    ev.blockers.append(Blocker("CONFIGURATION_REQUIRED", f"Step {s['step']} is not included; only a DEMO calculation outside "
                                               "production may leave a step out.", "STEP_NOT_INCLUDED", {"step": s["step"]}))
                else:
                    ev.warnings.append(f"{s['step']}: Not included — DEMO")
            elif spec.status != fw.IMPLEMENTED or module.rules.get(spec.rule_code or "") != s["step"]:
                ev.blockers.append(Blocker("CALCULATION_RULE_NOT_CONFIGURED", f"Step {s['step']} does not cite a {s['step']} rule of the module.",
                                           "STEP_RULE_MISMATCH", {"step": s["step"], "rule_code": spec.rule_code}))
    # ---- dataset (only the APPROVED dataset of the reporting period; its snapshot hash is re-verified)
    ds = approved_dataset(db, period.id)
    ev.dataset = ds
    if ds is None:
        latest = latest_dataset(db, period.id)
        ev.blockers.append(Blocker("DATASET_NOT_APPROVED", "The reporting period has no APPROVED MRV dataset.", None,
                                   {"dataset_status": latest.status if latest else None, "dataset_code": latest.dataset_code if latest else None}))
    elif ds.snapshot is None or fw.sha256(json.loads(ds.snapshot)) != ds.snapshot_sha256:
        ev.blockers.append(Blocker("SNAPSHOT_MISMATCH", "The approved dataset snapshot does not match its checksum."))
    # ---- crediting period (decision A20)
    if crediting is not None and not (crediting.start_date <= period.start_date and period.end_date <= crediting.end_date):
        ev.blockers.append(Blocker("OUTSIDE_CREDITING_PERIOD", "The reporting period is not inside the selected crediting period.", None,
                                   {"crediting_period": f"{crediting.start_date}–{crediting.end_date}",
                                    "reporting_period": f"{period.start_date}–{period.end_date}"}))
    if ev.blockers or module is None or ds is None:
        return ev
    # ---- inputs (A5–A8, A11, A22)
    rows, problems = _resolve_inputs(db, ev, module, ds)
    ev.blockers.extend(problems)
    if len(rows) > settings.CALCULATION_MAX_INPUT_ROWS:
        ev.blockers.append(Blocker("INPUT_TOO_LARGE", f"{len(rows)} input rows exceed the synchronous limit of "
                                   f"{settings.CALCULATION_MAX_INPUT_ROWS} (background execution is not available yet)."))
    if any(r["requirement_source"] == "PROJECT_CONFIGURED" for r in rows):
        ev.warnings.append("Project-configured sampling parameters are used as inputs (not methodology parameters).")
    if ev.blockers:
        return ev
    ev.inputs = rows
    ev.snapshot = _snapshot(ev, module, ds, crediting, rows)
    ev.snapshot_sha256 = fw.sha256(ev.snapshot)
    return ev


@dataclass
class _PeriodData:
    """One period's approved dataset as seen by the input builder (CURRENT = the reporting period, PREVIOUS = the most recent
    earlier period of the project with an APPROVED dataset, i.e. the re-measurement baseline of measure-and-remeasure methods)."""
    label: str
    period: MonitoringPeriod
    ds: MrvDataset
    snap: dict[str, Any]
    collections: dict[str, dict]
    points: dict[str, dict]
    strata: dict[str, dict]
    measurements: dict[uuid.UUID, MrvPlanMeasurement]


def _period_data(db: Session, label: str, period: MonitoringPeriod, ds: MrvDataset) -> _PeriodData:
    snap = json.loads(ds.snapshot or "{}")
    measurements = {m.monitoring_rule_id: m for m in db.scalars(select(MrvPlanMeasurement).where(
        MrvPlanMeasurement.mrv_plan_id == ds.mrv_plan_id)).all() if m.monitoring_rule_id}
    return _PeriodData(label, period, ds, snap, {c["id"]: c for c in snap.get("field_collections", [])},
                       {x["id"]: x for x in snap.get("sampling_points", [])}, {x["id"]: x for x in snap.get("strata", [])}, measurements)


def previous_period(db: Session, p: Project, period: MonitoringPeriod) -> tuple[MonitoringPeriod, MrvDataset] | None:
    """The most recent earlier monitoring period of the project (by start date) that has an APPROVED dataset."""
    earlier = db.scalars(select(MonitoringPeriod).where(MonitoringPeriod.project_id == p.id, MonitoringPeriod.start_date < period.start_date)
                         .order_by(MonitoringPeriod.start_date.desc())).all()
    for mp in earlier:
        ds = approved_dataset(db, mp.id)
        if ds is not None:
            return mp, ds
    return None


def _stratum_context(db: Session, pd: _PeriodData, stratum_id: str | None) -> dict[str, Any]:
    """Role and links of a stratum as frozen in the dataset snapshot (older snapshots: read from the stratum version itself)."""
    if not stratum_id:
        return {}
    meta = pd.strata.get(stratum_id) or {}
    s = db.get(ProjectStratum, uuid.UUID(stratum_id))
    role = meta.get("role") or (s.role if s else "PROJECT")
    links = meta.get("linked_stratum_record_ids")
    if links is None:
        links = json.loads(s.linked_stratum_record_ids or "[]") if s else []
    record = meta.get("record_id") or (str(s.record_id) if s else None)
    farms = sorted(str(f) for f in db.scalars(select(StratumFarm.farm_id).where(StratumFarm.stratum_id == uuid.UUID(stratum_id))).all())
    return {"stratum_role": role, "stratum_record_id": record, "stratum_code": meta.get("code") or (s.code if s else None),
            "linked_stratum_record_ids": list(links), "farm_ids": farms}


def _snapshot(ev: Evaluation, module: fw.CalculationModule, ds: MrvDataset, crediting: ProjectCreditingPeriod | None,
              rows: list[dict[str, Any]]) -> dict[str, Any]:
    p, mp, pm, v, m = ev.project, ev.period, ev.pm, ev.version, ev.methodology
    assert pm is not None and v is not None and m is not None
    return {
        "schema": "calculation-input-v1",
        "engine_version": fw.ENGINE_VERSION,
        "project": {"id": str(p.id), "code": p.project_code, "organization_id": str(p.organization_id), "environment": p.environment},
        "reporting_period": {"id": str(mp.id), "number": mp.period_number, "name": mp.name, "purpose": mp.purpose,
                             "start": mp.start_date.isoformat(), "end": mp.end_date.isoformat()},
        "crediting_period": ({"id": str(crediting.id), "number": crediting.period_number, "start": crediting.start_date.isoformat(),
                              "end": crediting.end_date.isoformat()} if crediting else None),
        "dataset": {"id": str(ds.id), "code": ds.dataset_code, "version": ds.version, "snapshot_sha256": ds.snapshot_sha256,
                    "mrv_plan_id": str(ds.mrv_plan_id)},
        "methodology": {"methodology_id": str(m.id), "code": m.code, "version_id": str(v.id), "version_label": v.version_label,
                        "is_demo_illustrative": v.is_demo_illustrative, "project_methodology_id": str(pm.id),
                        "calculation_readiness": v.calculation_readiness, "calculation_module_code": v.calculation_module_code,
                        "calculation_rules_version": pm.calculation_rules_version, "monitoring_rules_version": pm.monitoring_rules_version,
                        "calculation_rules": [{"id": str(r.id), "rule_code": r.rule_code, "step": r.step, "title": r.title,
                                               "equation_reference": r.equation_reference} for r in ev.calc_rules]},
        "previous_period": ({"id": str(ev.previous_period.id), "number": ev.previous_period.period_number, "name": ev.previous_period.name,
                             "start": ev.previous_period.start_date.isoformat(), "end": ev.previous_period.end_date.isoformat(),
                             "dataset_id": str(ev.previous_dataset.id) if ev.previous_dataset else None,
                             "dataset_snapshot_sha256": ev.previous_dataset.snapshot_sha256 if ev.previous_dataset else None}
                            if ev.previous_period else None),
        "module": module.declaration(),
        "inputs": rows,
    }


def _resolve_inputs(db: Session, ev: Evaluation, module: fw.CalculationModule, ds: MrvDataset) -> tuple[list[dict[str, Any]], list[Blocker]]:
    v = ev.version
    assert v is not None
    rules = {r.rule_code: r for r in db.scalars(select(MethodologyMonitoringRule).where(
        MethodologyMonitoringRule.methodology_version_id == v.id)).all()}
    periods: dict[str, _PeriodData] = {"CURRENT": _period_data(db, "CURRENT", ev.period, ds)}
    rows: list[dict[str, Any]] = []
    problems: list[Blocker] = []
    if any(var.period == "PREVIOUS" for var in module.variables):
        prev = previous_period(db, ev.project, ev.period)
        if prev is None:
            problems.append(Blocker("PREVIOUS_PERIOD_REQUIRED", "This methodology compares two measurement campaigns: an earlier monitoring "
                                    "period with an APPROVED dataset (e.g. the baseline sampling at t0) is required.", "NO_PREVIOUS_APPROVED_PERIOD"))
        else:
            ev.previous_period, ev.previous_dataset = prev
            periods["PREVIOUS"] = _period_data(db, "PREVIOUS", *prev)
    for var in module.variables:
        found: list[dict[str, Any]] = []
        pd = periods.get(var.period)
        if pd is None:
            continue   # PREVIOUS_PERIOD_REQUIRED already reported
        if var.source == "LAB_RESULT":
            found = _lab_inputs(db, ev, var, rules, pd, problems)
        elif var.source == "MONITORING_RECORD":
            found = _record_inputs(db, var, rules, pd, problems)
        elif var.source == "STRATUM_AREA":
            for st in pd.snap.get("strata", []):
                s = db.get(ProjectStratum, uuid.UUID(st["id"]))
                if s is None or s.area_hectares is None:
                    problems.append(Blocker("MISSING_REQUIRED_INPUT", f"Stratum {st['code']} has no computed area.", None,
                                            {"variable": var.code, "stratum": st["code"]}))
                    continue
                found.append(_row(var, "STRATUM_AREA", s.id, s.version, s.code, _num(s.area_hectares), "ha", "STRATUM", stratum_id=s.id,
                                  context={"period": pd.label, **_stratum_context(db, pd, st["id"])}))
        elif var.source == "STRATUM_CHARACTERISTIC":
            for st in pd.snap.get("strata", []):
                ch = db.scalars(select(StratumCharacteristic).where(StratumCharacteristic.stratum_id == uuid.UUID(st["id"]),
                                                                    StratumCharacteristic.characteristic == var.parameter)).first()
                if ch is None:
                    continue
                value: str = ch.value
                if var.kind == "NUMBER":
                    try:
                        value = _num(Decimal(ch.value.strip()))
                    except Exception:  # a characteristic is free text: refuse rather than guess
                        problems.append(Blocker("INPUT_NOT_NUMERIC", f"{var.code}: stratum {st['code']} value '{ch.value}' is not a number.",
                                                None, {"variable": var.code, "stratum": st["code"]}))
                        continue
                found.append(_row(var, "STRATUM_CHARACTERISTIC", ch.id, None, f"{st['code']}:{var.parameter}", value, var.unit, "STRATUM",
                                  kind=var.kind, stratum_id=st["id"], context={"period": pd.label, **_stratum_context(db, pd, st["id"])}))
        elif var.source == "SAMPLING_DESIGN_PARAMETER":
            for dvs in pd.snap.get("sampling_design_versions", []):
                dv = db.get(SamplingDesignVersion, uuid.UUID(dvs["id"]))
                val = getattr(dv, var.parameter or "", None) if dv else None
                if dv is None or val is None:
                    problems.append(Blocker("MISSING_REQUIRED_INPUT", f"Sampling design parameter {var.parameter} is not set.", None,
                                            {"variable": var.code}))
                    continue
                found.append(_row(var, "SAMPLING_DESIGN_PARAMETER", dv.id, dv.version, var.parameter, _num(val), "%", "PROJECT",
                                  requirement_source=dv.requirement_source))
        for r in found:
            if var.kind == "NUMBER" and (r["unit"] or "").strip() != var.unit.strip():
                problems.append(Blocker("UNIT_MISMATCH", f"{var.code}: unit '{r['unit']}' does not match the module's '{var.unit}' "
                                        "(exact text; never converted).", None, {"variable": var.code, "source_code": r["source_code"],
                                                                               "unit": r["unit"], "expected_unit": var.unit}))
        if var.required and not found and not any(b.details.get("variable") == var.code for b in problems):
            problems.append(Blocker("MISSING_REQUIRED_INPUT", f"No eligible input for {var.code}.", None, {"variable": var.code}))
        rows.extend(sorted(found, key=lambda r: (r["source_code"] or "", r["source_id"] or "")))
    for c in module.constants:
        rows.append({"variable": c.code, "source_type": "MODULE_CONSTANT", "source_id": None, "source_version": None, "source_code": c.code,
                     "value": fw.decimal_text(Decimal(c.value)), "value_kind": "NUMBER", "unit": c.unit, "level": "PROJECT",
                     "stratum_id": None, "farm_id": None, "sampling_point_id": None, "field_collection_id": None, "sample_id": None,
                     "root_sample_id": None, "monitoring_rule_id": None, "plan_measurement_id": None, "requirement_source": "MODULE",
                     "source_reference": c.source_reference, "source_sha256": None, "context": {}})
    for i, r in enumerate(rows):
        r["seq"] = i + 1
    return rows, problems


def _lab_inputs(db: Session, ev: Evaluation, var: fw.Variable, rules: dict[str, MethodologyMonitoringRule], pd: _PeriodData,
                problems: list[Blocker]) -> list[dict[str, Any]]:
    measurements, collections, points = pd.measurements, pd.collections, pd.points
    rule = rules.get(var.rule_code or "")
    if rule is None or rule.measurement_source != "LABORATORY":
        problems.append(Blocker("CALCULATION_RULE_NOT_CONFIGURED", f"{var.code}: monitoring rule {var.rule_code} is not a LABORATORY rule of "
                                "the locked version.", "VARIABLE_RULE_MISMATCH", {"variable": var.code}))
        return []
    meas = measurements.get(rule.id)
    if meas is None:
        problems.append(Blocker("MISSING_REQUIRED_INPUT", f"{var.code}: the dataset's MRV plan has no measurement for {rule.rule_code}.", None,
                                {"variable": var.code}))
        return []
    results = db.scalars(select(LabResult).where(
        LabResult.status == "APPROVED", LabResult.project_id == ev.project.id, LabResult.methodology_version_id == rule.methodology_version_id,
        LabResult.methodology_monitoring_rule_id == rule.id, LabResult.mrv_plan_measurement_id == meas.id)).all()
    by_collection: dict[str, list[tuple[LabResult, LabSample]]] = {}
    for res in results:
        root = db.get(LabSample, res.root_sample_id)
        if root is None or root.project_id != ev.project.id or root.monitoring_period_id != pd.period.id:
            continue
        if str(root.field_collection_id) not in collections:
            ev.warnings.append(f"Approved result for sample {root.sample_code} excluded: its field-collection version is not in the dataset.")
            continue
        by_collection.setdefault(str(root.field_collection_id), []).append((res, root))
    out = []
    for fc_id, fc in sorted(collections.items(), key=lambda kv: kv[1]["code"]):
        found = by_collection.get(fc_id, [])
        pt = points.get(fc["point_id"], {})
        if not found:
            problems.append(Blocker("MISSING_APPROVED_LAB_RESULT", f"No approved {rule.rule_code} result for field collection {fc['code']} "
                                    f"(point {pt.get('code')}, {pd.label.lower()} period).", None,
                                    {"variable": var.code, "rule_code": rule.rule_code, "field_collection": fc["code"], "point": pt.get("code"),
                                     "period": pd.label}))
            continue
        for res, root in found:
            if var.kind == "NUMBER" and res.result_type != "NUMERIC":
                problems.append(Blocker("INPUT_NOT_NUMERIC", f"{var.code}: the approved result for {root.sample_code} is text "
                                        f"('{res.value_text}'); text is never parsed or converted.", None,
                                        {"variable": var.code, "sample": root.sample_code}))
                continue
            value = _num(res.value_number) if res.result_type == "NUMERIC" else (res.value_text or "")
            sha = None
            if res.report_document_id:
                dv = db.scalars(select(DocumentVersion).where(DocumentVersion.document_id == res.report_document_id)
                                .order_by(DocumentVersion.version.desc())).first()
                sha = dv.checksum_sha256 if dv else None
            fcr = db.get(FieldCollectionRecord, uuid.UUID(fc_id))
            context = {"period": pd.label, "period_id": str(pd.period.id), "period_end": pd.period.end_date.isoformat(),
                       "depth_top_cm": _num(root.depth_top_cm) if root.depth_top_cm is not None else None,
                       "depth_bottom_cm": _num(root.depth_bottom_cm) if root.depth_bottom_cm is not None else None,
                       "probe_diameter_mm": _num(fcr.probe_diameter_mm) if fcr and fcr.probe_diameter_mm is not None else None,
                       "cores_count": fcr.cores_count if fcr else None, "root_sample_id": str(root.id), "field_collection_id": fc_id,
                       **_stratum_context(db, pd, pt.get("stratum_id"))}
            out.append(_row(var, "LAB_RESULT", res.id, res.version, root.sample_code, value, res.unit, "SAMPLING_POINT",
                            kind="NUMBER" if res.result_type == "NUMERIC" else "TEXT", context=context,
                            stratum_id=pt.get("stratum_id"), farm_id=pt.get("farm_id"), sampling_point_id=fc["point_id"],
                            field_collection_id=fc_id, sample_id=res.sample_id, root_sample_id=root.id, monitoring_rule_id=rule.id,
                            plan_measurement_id=meas.id, requirement_source="METHODOLOGY", source_sha256=sha))
    return out


def _record_inputs(db: Session, var: fw.Variable, rules: dict[str, MethodologyMonitoringRule], pd: _PeriodData,
                   problems: list[Blocker]) -> list[dict[str, Any]]:
    measurements, snap = pd.measurements, pd.snap
    rule = rules.get(var.rule_code or "")
    if rule is None or rule.measurement_source not in ("FIELD", "FIELD_ACTIVITY"):
        problems.append(Blocker("CALCULATION_RULE_NOT_CONFIGURED", f"{var.code}: monitoring rule {var.rule_code} is not a FIELD / FIELD_ACTIVITY "
                                "rule of the locked version.", "VARIABLE_RULE_MISMATCH", {"variable": var.code}))
        return []
    meas = measurements.get(rule.id)
    if meas is None:
        problems.append(Blocker("MISSING_REQUIRED_INPUT", f"{var.code}: the dataset's MRV plan has no measurement for {rule.rule_code}.", None,
                                {"variable": var.code}))
        return []
    out = []
    for rec in snap.get("monitoring_records", []):
        if rec.get("measurement_code") != meas.code or not rec.get("authoritative"):
            continue  # decision V2-B: supplementary observations are never inputs
        r = db.get(MonitoringRecord, uuid.UUID(rec["id"]))
        if r is None:
            continue
        if var.kind == "NUMBER" and r.value_number is None:
            problems.append(Blocker("INPUT_NOT_NUMERIC", f"{var.code}: record {rec['record_id']} has no numeric value.", None,
                                    {"variable": var.code}))
            continue
        level = "SAMPLING_POINT" if r.sampling_point_id else "STRATUM" if r.stratum_id else "FARM" if r.farm_id else "PROJECT"
        value = _num(r.value_number) if r.value_number is not None else (r.value_text or "")
        out.append(_row(var, "MONITORING_RECORD", r.id, r.version, meas.code, value, r.unit or meas.unit, level,
                        kind="NUMBER" if r.value_number is not None else "TEXT", stratum_id=r.stratum_id, farm_id=r.farm_id,
                        sampling_point_id=r.sampling_point_id, field_collection_id=r.field_collection_id, monitoring_rule_id=rule.id,
                        plan_measurement_id=meas.id, requirement_source="METHODOLOGY",
                        context={"period": pd.label, "phase": r.measurement_phase,
                                 "observed_on": r.observed_on.isoformat() if r.observed_on else None,
                                 **(_stratum_context(db, pd, _record_stratum(db, r)) if (r.stratum_id or r.sampling_point_id) else {})}))
    return out


def _record_stratum(db: Session, r: MonitoringRecord) -> str | None:
    """The stratum of a record: its own, or that of its sampling point (per-unit records of census methods)."""
    if r.stratum_id:
        return str(r.stratum_id)
    sp = db.get(SamplingPoint, r.sampling_point_id) if r.sampling_point_id else None
    return str(sp.stratum_id) if sp is not None and sp.stratum_id else None


def _num(v: Any) -> str:
    return fw.decimal_text(Decimal(str(v)))


def _s(v: Any) -> str | None:
    return str(v) if v is not None else None


def _row(var: fw.Variable, source: str, source_id: Any, version: int | None, code: str | None, value: str, unit: str | None, level: str,
         kind: str = "NUMBER", **ids: Any) -> dict[str, Any]:
    base: dict[str, Any] = {"variable": var.code, "source_type": source, "source_id": _s(source_id), "source_version": version, "source_code": code,
            "value": value, "value_kind": kind, "unit": unit, "level": level, "stratum_id": None, "farm_id": None, "sampling_point_id": None,
            "field_collection_id": None, "sample_id": None, "root_sample_id": None, "monitoring_rule_id": None, "plan_measurement_id": None,
            "requirement_source": None, "source_reference": None, "source_sha256": None, "context": {}}
    for k, v in ids.items():
        base[k] = _s(v) if k.endswith("_id") else v
    return base
