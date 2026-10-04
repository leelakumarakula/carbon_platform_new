"""Methodology-independent calculation framework (spec section 18; decisions A1, A10–A13).

A methodology-specific module is a Python class that declares, explicitly and completely:
- the methodology code, the version label it supports and the `calculation_rules_version` it was written against
- the exact calculation rule codes (rule code → step) of that version — any difference blocks the calculation
- its variables (source, monitoring-rule code, exact expected unit, level), constants (value, unit, source reference)
- one step declaration per calculation step (IMPLEMENTED with its rule code, or NOT_INCLUDED_DEMO)
- its version and readiness (always NOT_PRODUCTION_READY until a production-readiness workflow exists)

The framework never supplies a formula. Step methods raise NotImplementedError unless the module implements them, which
blocks the calculation with CONFIGURATION_REQUIRED. Execution is a pure function of the frozen input snapshot: Decimal
arithmetic in a fixed context, no float, no randomness, no I/O, no clock, no database.
"""
import hashlib
import json
from collections.abc import Iterable
from dataclasses import dataclass, field
from decimal import Context, Decimal, DivisionByZero, InvalidOperation, Overflow, localcontext
from typing import Any, ClassVar

ENGINE_VERSION = "calc-framework-1.0"
STEPS = ("BASELINE", "PROJECT", "EMISSIONS", "REMOVALS", "LEAKAGE", "UNCERTAINTY", "ADJUSTMENT", "NET")
STEP_METHODS = {"BASELINE": "calculate_baseline", "PROJECT": "calculate_project", "EMISSIONS": "calculate_emissions",
                "REMOVALS": "calculate_removals", "LEAKAGE": "calculate_leakage", "UNCERTAINTY": "calculate_uncertainty",
                "ADJUSTMENT": "apply_methodology_adjustments", "NET": "calculate_net_result"}
IMPLEMENTED = "IMPLEMENTED"
NOT_INCLUDED_DEMO = "NOT_INCLUDED_DEMO"          # decision A10: only for DEMO, shown as "Not included — DEMO"
NOT_PRODUCTION_READY = "NOT_PRODUCTION_READY"
PRODUCTION_READY = "PRODUCTION_READY"
VARIABLE_SOURCES = ("LAB_RESULT", "MONITORING_RECORD", "STRATUM_AREA", "SAMPLING_DESIGN_PARAMETER", "STRATUM_CHARACTERISTIC")
# which approved dataset a variable reads: the reporting period's, or the most recent earlier period's (re-measurement methods)
PERIODS = ("CURRENT", "PREVIOUS")
DESIGN_PARAMETERS = ("target_precision_pct", "confidence_level_pct")
LEVELS = ("PROJECT", "STRATUM", "FARM", "SAMPLING_POINT")
# Fixed arithmetic context (decision A12): 34 significant digits, banker's rounding only where Decimal itself must round
# (division); invalid operations, division by zero and overflow raise instead of producing NaN / Infinity.
DECIMAL_CONTEXT = Context(prec=34, rounding="ROUND_HALF_EVEN", traps=[InvalidOperation, DivisionByZero, Overflow])


class CalculationBlocked(Exception):
    """A deterministic blocker raised during execution (the run becomes BLOCKED with this code)."""

    def __init__(self, code: str, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.code, self.message, self.details = code, message, details or {}


@dataclass(frozen=True)
class Variable:
    code: str
    source: str                      # one of VARIABLE_SOURCES
    unit: str                        # exact expected unit text (trimmed, case-sensitive; never converted)
    level: str
    rule_code: str | None = None     # monitoring rule code (LAB_RESULT / MONITORING_RECORD)
    parameter: str | None = None     # SAMPLING_DESIGN_PARAMETER: target_precision_pct / confidence_level_pct
    kind: str = "NUMBER"             # NUMBER or TEXT
    required: bool = True
    period: str = "CURRENT"          # CURRENT or PREVIOUS (LAB_RESULT / MONITORING_RECORD / STRATUM_AREA)

    def __post_init__(self) -> None:
        if self.source not in VARIABLE_SOURCES or self.level not in LEVELS or self.kind not in ("NUMBER", "TEXT") or self.period not in PERIODS:
            raise ValueError(f"Invalid variable declaration {self.code}")
        if self.source == "STRATUM_CHARACTERISTIC" and not self.parameter:
            raise ValueError(f"Variable {self.code} must name the stratum characteristic")
        if self.source in ("LAB_RESULT", "MONITORING_RECORD") and not self.rule_code:
            raise ValueError(f"Variable {self.code} must name its monitoring rule")
        if self.source == "SAMPLING_DESIGN_PARAMETER" and self.parameter not in DESIGN_PARAMETERS:
            raise ValueError(f"Variable {self.code} must name a sampling design parameter")
        if self.kind == "NUMBER" and not self.unit.strip():
            raise ValueError(f"Variable {self.code} must declare its unit")


@dataclass(frozen=True)
class Constant:
    code: str
    value: str                       # exact decimal string
    unit: str
    source_reference: str            # methodology section / equation (or, for a test fixture, an explicit test label)

    def __post_init__(self) -> None:
        Decimal(self.value)          # must be a valid decimal literal
        if not self.source_reference.strip():
            raise ValueError(f"Constant {self.code} needs a source reference")


@dataclass(frozen=True)
class Step:
    step: str
    status: str                      # IMPLEMENTED or NOT_INCLUDED_DEMO
    rule_code: str | None = None


@dataclass(frozen=True)
class InputValue:
    seq: int
    variable: str
    value: Decimal | str
    unit: str | None
    level: str
    stratum_id: str | None
    farm_id: str | None
    sampling_point_id: str | None
    context: dict[str, Any] = field(default_factory=dict)   # depth layer, probe, period, stratum role / links, record phase, ...


@dataclass
class Output:
    code: str
    step: str
    rule_code: str
    value: Decimal
    unit: str
    level: str = "PROJECT"
    entity_id: str | None = None
    inputs: tuple[int, ...] = ()     # input seq numbers used
    outputs: tuple[str, ...] = ()    # codes of earlier outputs used
    is_final: bool = False


class CalculationContext:
    """Read-only view of the frozen snapshot for a module."""

    def __init__(self, snapshot: dict[str, Any]) -> None:
        self.snapshot = snapshot
        self._inputs: dict[str, list[InputValue]] = {}
        for row in snapshot["inputs"]:
            value: Decimal | str = Decimal(row["value"]) if row["value_kind"] == "NUMBER" else row["value"]
            self._inputs.setdefault(row["variable"], []).append(InputValue(
                row["seq"], row["variable"], value, row.get("unit"), row["level"], row.get("stratum_id"), row.get("farm_id"),
                row.get("sampling_point_id"), dict(row.get("context") or {})))
        self.outputs: dict[str, Output] = {}

    def values(self, variable: str) -> list[InputValue]:
        return list(self._inputs.get(variable, []))

    def constant(self, code: str) -> InputValue:
        found = self._inputs.get(code)
        if not found:
            raise CalculationBlocked("MISSING_REQUIRED_INPUT", f"Constant {code} is not in the frozen inputs.", {"variable": code})
        return found[0]

    def output(self, code: str) -> Output:
        return self.outputs[code]


class CalculationModule:
    """Base class. Subclasses set the declarations and implement the steps they declare IMPLEMENTED."""
    code: str = ""
    version: str = ""
    methodology_code: str = ""
    version_label: str = ""
    calculation_rules_version: int = 0
    readiness: str = NOT_PRODUCTION_READY
    rules: ClassVar[dict[str, str]] = {}       # calculation rule code → step
    variables: tuple[Variable, ...] = ()
    constants: tuple[Constant, ...] = ()
    steps: tuple[Step, ...] = ()
    label: str = ""                            # e.g. "DEMO — not carbon accounting"
    # The rule set a methodology version must carry to use this module. Selecting the module on a DRAFT version's Calculation
    # tab copies these (calculation rules, monitoring rules, SAMPLING parameters); approval of the version approves the choice.
    calculation_rule_definitions: ClassVar[tuple[dict[str, Any], ...]] = ()
    monitoring_rule_definitions: ClassVar[tuple[dict[str, Any], ...]] = ()
    sampling_parameters: ClassVar[dict[str, Any]] = {}
    assumptions: ClassVar[tuple[str, ...]] = ()   # documented interpretations, shown to reviewers

    def step(self, name: str) -> Step | None:
        return next((s for s in self.steps if s.step == name), None)

    def declaration(self) -> dict[str, Any]:
        return {
            "code": self.code, "version": self.version, "methodology_code": self.methodology_code, "version_label": self.version_label,
            "calculation_rules_version": self.calculation_rules_version, "readiness": self.readiness, "label": self.label,
            "rules": dict(sorted(self.rules.items())),
            "steps": [{"step": s.step, "status": s.status, "rule_code": s.rule_code} for s in self.steps],
            "variables": [{"code": v.code, "source": v.source, "unit": v.unit, "level": v.level, "rule_code": v.rule_code,
                           "parameter": v.parameter, "kind": v.kind, "required": v.required, "period": v.period} for v in self.variables],
            "constants": [{"code": c.code, "value": c.value, "unit": c.unit, "source_reference": c.source_reference} for c in self.constants],
            "assumptions": list(self.assumptions),
        }

    # ---- spec section 18 framework methods; no default formula exists
    def validate_inputs(self, ctx: CalculationContext) -> None:
        return None

    def calculate_baseline(self, ctx: CalculationContext) -> list[Output]:
        raise NotImplementedError

    def calculate_project(self, ctx: CalculationContext) -> list[Output]:
        raise NotImplementedError

    def calculate_emissions(self, ctx: CalculationContext) -> list[Output]:
        raise NotImplementedError

    def calculate_removals(self, ctx: CalculationContext) -> list[Output]:
        raise NotImplementedError

    def calculate_leakage(self, ctx: CalculationContext) -> list[Output]:
        raise NotImplementedError

    def calculate_uncertainty(self, ctx: CalculationContext) -> list[Output]:
        raise NotImplementedError

    def apply_methodology_adjustments(self, ctx: CalculationContext) -> list[Output]:
        raise NotImplementedError

    def calculate_net_result(self, ctx: CalculationContext) -> list[Output]:
        raise NotImplementedError

    def validate_output(self, ctx: CalculationContext, outputs: list[Output]) -> None:
        return None


@dataclass
class ExecutionResult:
    outputs: list[dict[str, Any]] = field(default_factory=list)
    net_value: str = ""
    net_unit: str = ""
    output_sha256: str = ""


def canonical_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def sha256(obj: Any) -> str:
    return hashlib.sha256(canonical_json(obj).encode()).hexdigest()


def decimal_text(value: Decimal) -> str:
    """Exact, exponent-free text of a Decimal (no rounding)."""
    return format(value, "f")


def output_hash(records: Iterable[dict[str, Any]], module_code: str, module_version: str, engine_version: str) -> str:
    return sha256({"engine_version": engine_version, "module": module_code, "module_version": module_version, "outputs": list(records)})


def execute(module: CalculationModule, snapshot: dict[str, Any]) -> ExecutionResult:
    """Run the module on the frozen snapshot. Raises CalculationBlocked for every deterministic blocker."""
    with localcontext(DECIMAL_CONTEXT):
        ctx = CalculationContext(snapshot)
        input_seqs = {row["seq"] for row in snapshot["inputs"]}
        ordered: list[Output] = []
        try:
            module.validate_inputs(ctx)
            for step_name in STEPS:
                spec = module.step(step_name)
                if spec is not None and spec.status == NOT_INCLUDED_DEMO:
                    continue
                if spec is None or spec.status != IMPLEMENTED:
                    raise CalculationBlocked("CONFIGURATION_REQUIRED", f"Step {step_name} is not configured by the module.",
                                             {"reason": "STEP_NOT_CONFIGURED", "step": step_name})
                try:
                    produced = getattr(module, STEP_METHODS[step_name])(ctx)
                except NotImplementedError:
                    raise CalculationBlocked("CONFIGURATION_REQUIRED", f"Step {step_name} has no implementation in the module.",
                                             {"reason": "STEP_NOT_IMPLEMENTED", "step": step_name}) from None
                for out in produced:
                    _check_output(module, step_name, out, ctx, input_seqs)
                    ctx.outputs[out.code] = out
                    ordered.append(out)
            module.validate_output(ctx, ordered)
        except (InvalidOperation, DivisionByZero, Overflow) as e:
            raise CalculationBlocked("CALCULATION_ERROR", f"Invalid arithmetic in the module: {type(e).__name__}.") from None
        finals = [o for o in ordered if o.is_final]
        if len(finals) != 1 or finals[0].step != "NET":
            raise CalculationBlocked("CONFIGURATION_REQUIRED", "The module must produce exactly one final NET output.",
                                     {"reason": "NO_FINAL_NET_OUTPUT"})
        seq_of = {o.code: i + 1 for i, o in enumerate(ordered)}
        records = [{"seq": seq_of[o.code], "step": o.step, "output_code": o.code, "rule_code": o.rule_code, "value": decimal_text(o.value),
                    "unit": o.unit, "level": o.level, "entity_id": o.entity_id, "inputs": sorted(o.inputs),
                    "outputs": sorted(seq_of[c] for c in o.outputs), "is_final": o.is_final} for o in ordered]
        final = finals[0]
        return ExecutionResult(records, decimal_text(final.value), final.unit,
                               output_hash(records, module.code, module.version, ENGINE_VERSION))


def _check_output(module: CalculationModule, step: str, out: Output, ctx: CalculationContext, input_seqs: set[int]) -> None:
    if not isinstance(out.value, Decimal) or not out.value.is_finite():
        raise CalculationBlocked("CALCULATION_ERROR", f"Output {out.code} is not a finite Decimal (float is never allowed).")
    if out.step != step or module.rules.get(out.rule_code) != step:
        raise CalculationBlocked("CALCULATION_RULE_NOT_CONFIGURED", f"Output {out.code} does not cite a {step} calculation rule of the module.",
                                 {"output": out.code, "rule_code": out.rule_code})
    if out.code in ctx.outputs:
        raise CalculationBlocked("CALCULATION_ERROR", f"Output code {out.code} is produced twice.")
    if not out.unit.strip() or out.level not in LEVELS:
        raise CalculationBlocked("CALCULATION_ERROR", f"Output {out.code} needs a unit and a valid level.")
    missing_in = [s for s in out.inputs if s not in input_seqs]
    missing_out = [c for c in out.outputs if c not in ctx.outputs]
    if missing_in or missing_out or not (out.inputs or out.outputs):
        raise CalculationBlocked("CALCULATION_ERROR", f"Output {out.code} must reference existing inputs or earlier outputs (lineage).",
                                 {"output": out.code})
