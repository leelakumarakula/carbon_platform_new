"""Deterministic calculation QA checks (decision A15; A22 warning; A10 "Not included — DEMO"). No domain threshold is invented:
value bounds exist only where the methodology module declares them (its validate_output), and those already block execution."""
import json
import uuid
from collections import Counter
from typing import Any

from sqlalchemy.orm import Session

from app.calculation import framework as fw
from app.calculation.registry import Resolver
from app.core.config import get_settings
from app.models import CalculationRun, Project


def _c(key: str, label: str, problems: list[str], warn: list[str] | None = None) -> dict[str, Any]:
    if problems:
        return {"key": key, "label": label, "result": "FAIL", "details": problems}
    if warn:
        return {"key": key, "label": label, "result": "WARN", "details": warn}
    return {"key": key, "label": label, "result": "PASS", "details": []}


def checks(db: Session, run: CalculationRun, reviewer_id: uuid.UUID | None, resolver: Resolver) -> list[dict[str, Any]]:
    from app.services import calculation_service as cs
    snapshot = json.loads(run.input_snapshot or "{}")
    out: list[dict[str, Any]] = []
    out.append(_c("input_snapshot", "Frozen input snapshot matches its SHA-256",
                  [] if snapshot and fw.sha256(snapshot) == run.input_sha256 else ["the snapshot hash does not match"]))
    stale = cs.current_problems(db, run, snapshot) if snapshot else ["no snapshot"]
    out.append(_c("inputs_current", "Approved dataset, approved laboratory results and methodology lock are still current", stale))
    rows = snapshot.get("inputs", [])
    decl = snapshot.get("module", {})
    variables = {v["code"]: v for v in decl.get("variables", [])}
    missing = [v for v, d in variables.items() if d["required"] and not any(r["variable"] == v for r in rows)]
    out.append(_c("required_inputs", "Every required variable has frozen inputs (nothing substituted)", missing))
    unit_problems = [f"{r['variable']} {r['source_code']}: '{r['unit']}' ≠ '{variables[r['variable']]['unit']}'" for r in rows
                     if r["variable"] in variables and variables[r["variable"]]["kind"] == "NUMBER"
                     and (r["unit"] or "").strip() != variables[r["variable"]]["unit"].strip()]
    out.append(_c("units", "Input units equal the module's declared units (exact text, no conversion)", unit_problems))
    type_problems = [f"{r['variable']} {r['source_code']}" for r in rows
                     if r["variable"] in variables and variables[r["variable"]]["kind"] == "NUMBER" and r["value_kind"] != "NUMBER"]
    out.append(_c("input_types", "Numeric variables have numeric inputs (text results are never parsed)", type_problems))
    keys = Counter((r["variable"], r["source_type"], r["source_id"]) for r in rows if r["source_id"])
    roots = Counter((r["variable"], r["root_sample_id"]) for r in rows if r["source_type"] == "LAB_RESULT")
    dups = [f"{k[0]} {k[2]}" for k, n in keys.items() if n > 1] + [f"{k[0]} root sample {k[1]}" for k, n in roots.items() if n > 1]
    out.append(_c("no_duplicate_inputs", "No duplicate authoritative inputs (one result per root sample and rule)", dups))
    module = resolver(snapshot.get("methodology", {}).get("code", ""), snapshot.get("methodology", {}).get("version_label", ""))
    mod_problems = []
    if module is None:
        mod_problems.append("no calculation module is registered for this methodology version")
    elif module.code != run.module_code or module.version != run.module_version or module.declaration() != decl:
        mod_problems.append("the registered module differs from the module the inputs were frozen with")
    out.append(_c("module_rules", "The registered module matches the frozen module and the locked calculation rules", mod_problems))
    stored = cs.stored_output_records(db, run.id)
    repro: list[str] = []
    if module is not None and not mod_problems:
        try:
            again = fw.execute(module, snapshot)
            if again.output_sha256 != run.output_sha256:
                repro.append("re-running the module on the frozen snapshot gives a different output hash")
        except fw.CalculationBlocked as e:
            repro.append(f"re-running the module is blocked: {e.code}")
    else:
        repro.append("cannot re-run without the frozen module")
    if fw.output_hash(stored, run.module_code or "", run.module_version or "", run.engine_version) != run.output_sha256:
        repro.append("stored outputs do not match the output hash")
    out.append(_c("reproducible", "Re-running the frozen snapshot reproduces the output hash", repro))
    step_status = {s["step"]: s for s in decl.get("steps", [])}
    produced = {o["step"] for o in stored}
    step_problems = [s for s in fw.STEPS if step_status.get(s, {}).get("status") == fw.IMPLEMENTED and s not in produced]
    step_problems += [s for s in fw.STEPS if s not in step_status]
    finals = [o for o in stored if o["is_final"]]
    if len(finals) != 1 or finals[0]["step"] != "NET":
        step_problems.append("exactly one final NET output is required")
    not_included = [f"{s}: Not included — DEMO" for s in fw.STEPS if step_status.get(s, {}).get("status") == fw.NOT_INCLUDED_DEMO]
    out.append(_c("steps_complete", "Every configured step executed; one final NET output", step_problems, not_included))
    seqs = {r["seq"] for r in rows}
    out_seqs = {o["seq"] for o in stored}
    rule_codes = {r["rule_code"] for r in snapshot.get("methodology", {}).get("calculation_rules", [])}
    lineage = [o["output_code"] for o in stored if o["rule_code"] not in rule_codes or not (o["inputs"] or o["outputs"])
               or any(s not in seqs for s in o["inputs"]) or any(s not in out_seqs for s in o["outputs"])]
    lineage += [f"input {r['seq']}" for r in rows if r["source_type"] != "MODULE_CONSTANT" and not r["source_id"]]
    out.append(_c("lineage_complete", "Every output cites a calculation rule and its inputs; every input has a source", lineage))
    pc = sorted({f"{r['variable']} ({r['source_code']})" for r in rows if r.get("requirement_source") == "PROJECT_CONFIGURED"})
    out.append(_c("project_configured_parameters", "Project-configured sampling parameters used as inputs (not methodology parameters)", [],
                  [f"PROJECT_CONFIGURED: {x}" for x in pc]))
    readiness_problems, readiness_warn = [], []
    if run.module_readiness != fw.PRODUCTION_READY:
        if get_settings().is_production:
            readiness_problems.append("NOT_PRODUCTION_READY module (blocked in production)")
        else:
            readiness_warn.append("NOT_PRODUCTION_READY module: non-production use only")
    out.append(_c("module_readiness", "Module readiness allows this environment", readiness_problems, readiness_warn))
    p = db.get(Project, run.project_id)
    env = [] if p and p.environment == run.environment == snapshot.get("project", {}).get("environment") else ["DEMO and live records are mixed"]
    out.append(_c("environment", "Environment consistent (DEMO never mixed with live)", env))
    sod = cs.sod_reasons(run, reviewer_id) if reviewer_id else []
    out.append(_c("separation_of_duties", "Reviewer is not the run's creator, freezer, executor or submitter", sod))
    return out
