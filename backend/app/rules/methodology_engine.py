"""Deterministic methodology applicability engine (spec section 9).

Pure functions, no database. Given the rules of one methodology version and a dictionary of project facts, it
returns one result per rule and an aggregated candidate outcome:

    APPLICABLE         every mandatory rule passed on system-derived (or evidenced) facts
    EVIDENCE_REQUIRED  no rule failed hard, but at least one rule needs evidence (failed with on_fail=EVIDENCE_REQUIRED,
                       or passed only on a fact *declared* by a user while the rule names an evidence requirement)
    NEEDS_INFORMATION  a mandatory rule could not be evaluated because its fact is missing
    NOT_APPLICABLE     a rule with on_fail=NOT_APPLICABLE failed

Precedence: NOT_APPLICABLE > NEEDS_INFORMATION > EVIDENCE_REQUIRED > APPLICABLE.

The engine *proposes* candidates. It never selects or confirms a methodology; a methodology specialist reviews and
the project developer confirms (spec section 9, rule 6: no automated decision on methodology).
"""
from dataclasses import asdict, dataclass, field
from datetime import date
from typing import Any

ENGINE_VERSION = "1.0.0"
PRECEDENCE = ["NOT_APPLICABLE", "NEEDS_INFORMATION", "EVIDENCE_REQUIRED", "APPLICABLE"]


@dataclass(frozen=True)
class Fact:
    value: Any
    source: str          # PROJECT | FARM_DATA | DECLARED
    detail: str = ""


@dataclass(frozen=True)
class RuleSpec:
    rule_code: str
    title: str
    category: str
    fact_key: str
    operator: str
    expected: Any
    on_fail: str = "NOT_APPLICABLE"
    evidence_requirement: str | None = None
    mandatory: bool = True
    source_reference: str | None = None


@dataclass
class RuleResult:
    rule_code: str
    title: str
    category: str
    fact_key: str
    operator: str
    expected: Any
    actual: Any
    fact_source: str | None
    check: str            # PASS | FAIL | MISSING | SKIPPED
    effect: str           # contribution to the outcome (one of PRECEDENCE)
    reason: str
    evidence_requirement: str | None
    source_reference: str | None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class CandidateOutcome:
    outcome: str
    rules: list[RuleResult] = field(default_factory=list)
    evidence_requirements: list[str] = field(default_factory=list)


class RuleError(ValueError):
    """A rule is badly configured (unknown operator, malformed expected value)."""


def _as_list(v: Any) -> list[Any]:
    if v is None:
        return []
    return list(v) if isinstance(v, (list, tuple, set, frozenset)) else [v]


def _norm(v: Any) -> Any:
    return v.strip().upper() if isinstance(v, str) else v


def _date(v: Any) -> date:
    return v if isinstance(v, date) else date.fromisoformat(str(v)[:10])


def _number(v: Any) -> float:
    if isinstance(v, bool):
        raise RuleError("expected a number")
    return float(v)


def check(operator: str, actual: Any, expected: Any) -> bool:
    """Evaluate one comparison. Strings compare case-insensitively; lists are sets."""
    op = operator.upper()
    if op == "EXISTS":
        return actual is not None and actual != "" and actual != []
    if op == "IS_TRUE":
        return actual is True
    if op == "IS_FALSE":
        return actual is False
    if op in ("EQUALS", "NOT_EQUALS"):
        same = _norm(actual) == _norm(expected)
        return same if op == "EQUALS" else not same
    if op in ("IN", "NOT_IN"):
        member = _norm(actual) in {_norm(x) for x in _as_list(expected)}
        return member if op == "IN" else not member
    if op in ("ANY_IN", "ALL_IN", "NONE_IN"):
        have = {_norm(x) for x in _as_list(actual)}
        allowed = {_norm(x) for x in _as_list(expected)}
        if op == "ANY_IN":
            return bool(have & allowed)
        if op == "ALL_IN":
            return bool(have) and have <= allowed
        return not (have & allowed)
    if op == "GTE":
        return _number(actual) >= _number(expected)
    if op == "LTE":
        return _number(actual) <= _number(expected)
    if op == "BETWEEN":
        lo, hi = _as_list(expected)
        return _number(lo) <= _number(actual) <= _number(hi)
    if op == "DATE_ON_OR_AFTER":
        return _date(actual) >= _date(expected)
    if op == "DATE_ON_OR_BEFORE":
        return _date(actual) <= _date(expected)
    raise RuleError(f"unknown operator {operator}")


def _missing(fact: Fact | None) -> bool:
    return fact is None or fact.value is None or (isinstance(fact.value, (list, str)) and len(fact.value) == 0 and fact.source == "DECLARED")


def evaluate_rule(rule: RuleSpec, facts: dict[str, Fact]) -> RuleResult:
    fact = facts.get(rule.fact_key)
    base = {"rule_code": rule.rule_code, "title": rule.title, "category": rule.category, "fact_key": rule.fact_key,
            "operator": rule.operator, "expected": rule.expected, "evidence_requirement": rule.evidence_requirement,
            "source_reference": rule.source_reference}
    if rule.operator.upper() != "EXISTS" and _missing(fact):
        if rule.mandatory:
            return RuleResult(**base, actual=None, fact_source=None, check="MISSING", effect="NEEDS_INFORMATION",
                              reason=f"No value for '{rule.fact_key}'. Record the data (or declare it) and evaluate again.")
        return RuleResult(**base, actual=None, fact_source=None, check="SKIPPED", effect="APPLICABLE",
                          reason=f"Optional rule skipped: no value for '{rule.fact_key}'.")
    actual = fact.value if fact else None
    try:
        ok = check(rule.operator, actual, rule.expected)
    except (RuleError, ValueError, TypeError) as e:
        return RuleResult(**base, actual=actual, fact_source=fact.source if fact else None, check="MISSING",
                          effect="NEEDS_INFORMATION", reason=f"Could not evaluate ({e}); check the value of '{rule.fact_key}'.")
    src = fact.source if fact else None
    if ok:
        if src == "DECLARED" and rule.evidence_requirement:
            return RuleResult(**base, actual=actual, fact_source=src, check="PASS", effect="EVIDENCE_REQUIRED",
                              reason="Passes on a declared (unverified) value; the evidence listed is required.")
        return RuleResult(**base, actual=actual, fact_source=src, check="PASS", effect="APPLICABLE",
                          reason=f"{rule.fact_key} = {actual!r} satisfies {rule.operator} {rule.expected!r}.")
    effect = rule.on_fail if rule.mandatory else "APPLICABLE"
    return RuleResult(**base, actual=actual, fact_source=src, check="FAIL", effect=effect,
                      reason=f"{rule.fact_key} = {actual!r} does not satisfy {rule.operator} {rule.expected!r}"
                             + ("" if rule.mandatory else " (optional rule; recorded only)") + ".")


def evaluate(rules: list[RuleSpec], facts: dict[str, Fact]) -> CandidateOutcome:
    results = [evaluate_rule(r, facts) for r in rules]
    outcome = "APPLICABLE"
    for level in PRECEDENCE:
        if any(r.effect == level for r in results):
            outcome = level
            break
    evidence = sorted({r.evidence_requirement for r in results if r.evidence_requirement and r.check in ("PASS", "FAIL")})
    if not rules:
        return CandidateOutcome("NEEDS_INFORMATION", [], [])  # a version without applicability rules cannot be assessed
    return CandidateOutcome(outcome, results, evidence)
