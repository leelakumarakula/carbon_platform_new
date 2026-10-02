"""Unit tests for the deterministic methodology applicability engine (no database)."""
import pytest

from app.rules.methodology_engine import Fact, RuleError, RuleSpec, check, evaluate, evaluate_rule


def rule(code: str, key: str, op: str, expected: object = None, **kw: object) -> RuleSpec:
    return RuleSpec(rule_code=code, title=code, category="OTHER", fact_key=key, operator=op, expected=expected, **kw)  # type: ignore[arg-type]


@pytest.mark.parametrize(("op", "actual", "expected", "ok"), [
    ("EQUALS", "in", "IN", True), ("NOT_EQUALS", "IN", "BR", True), ("IN", "IN", ["IN", "BR"], True), ("NOT_IN", "US", ["IN"], True),
    ("ANY_IN", ["TILLAGE", "MANURE"], ["TILLAGE"], True), ("ANY_IN", ["MANURE"], ["TILLAGE"], False),
    ("ALL_IN", ["CROPLAND"], ["CROPLAND", "GRASSLAND"], True), ("ALL_IN", ["CROPLAND", "FOREST"], ["CROPLAND"], False),
    ("ALL_IN", [], ["CROPLAND"], False), ("NONE_IN", ["CROPLAND"], ["FOREST"], True), ("GTE", 5, 5, True), ("GTE", 4, 5, False),
    ("LTE", 3.5, 4, True), ("BETWEEN", 7, [5, 10], True), ("BETWEEN", 11, [5, 10], False),
    ("DATE_ON_OR_AFTER", "2026-06-01", "2020-01-01", True), ("DATE_ON_OR_BEFORE", "2026-06-01", "2020-01-01", False),
    ("IS_TRUE", True, None, True), ("IS_FALSE", True, None, False), ("EXISTS", "x", None, True), ("EXISTS", [], None, False),
])
def test_operators(op: str, actual: object, expected: object, ok: bool) -> None:
    assert check(op, actual, expected) is ok


def test_unknown_operator_is_a_configuration_error() -> None:
    with pytest.raises(RuleError):
        check("SOUNDS_RIGHT", 1, 1)


def test_missing_mandatory_fact_needs_information_and_optional_is_skipped() -> None:
    r = evaluate_rule(rule("R1", "additionality_assessment", "EQUALS", "COMPLETED"), {})
    assert (r.check, r.effect) == ("MISSING", "NEEDS_INFORMATION") and "additionality_assessment" in r.reason
    r = evaluate_rule(rule("R2", "soil_type", "IN", ["VERTISOL"], mandatory=False), {})
    assert (r.check, r.effect) == ("SKIPPED", "APPLICABLE")


def test_declared_fact_with_evidence_requirement_needs_evidence() -> None:
    spec = rule("R1", "additionality_assessment", "EQUALS", "COMPLETED", evidence_requirement="Additionality report")
    declared = evaluate_rule(spec, {"additionality_assessment": Fact("COMPLETED", "DECLARED")})
    derived = evaluate_rule(spec, {"additionality_assessment": Fact("COMPLETED", "PROJECT")})
    assert declared.effect == "EVIDENCE_REQUIRED" and derived.effect == "APPLICABLE"


def test_failure_uses_on_fail_and_precedence() -> None:
    facts = {"country": Fact("IN", "PROJECT"), "land_use_current": Fact(["FOREST"], "FARM_DATA")}
    soft = [rule("C", "country", "IN", ["IN"]), rule("E", "land_use_current", "ALL_IN", ["CROPLAND"], on_fail="EVIDENCE_REQUIRED")]
    assert evaluate(soft, facts).outcome == "EVIDENCE_REQUIRED"
    hard = [*soft, rule("N", "missing_fact", "EXISTS"), rule("X", "country", "IN", ["BR"])]
    out = evaluate(hard, facts)
    assert out.outcome == "NOT_APPLICABLE"  # NOT_APPLICABLE wins over NEEDS_INFORMATION and EVIDENCE_REQUIRED
    assert [r.check for r in out.rules] == ["PASS", "FAIL", "FAIL", "FAIL"]
    assert evaluate([rule("N", "missing_fact", "GTE", 1), *soft], facts).outcome == "NEEDS_INFORMATION"


def test_all_pass_is_applicable_and_is_deterministic() -> None:
    facts = {"country": Fact("IN", "PROJECT"), "years": Fact(6, "FARM_DATA")}
    rules = [rule("C", "country", "IN", ["IN"]), rule("Y", "years", "GTE", 5, evidence_requirement="Land records")]
    a, b = evaluate(rules, facts), evaluate(rules, facts)
    assert a.outcome == "APPLICABLE" and [r.as_dict() for r in a.rules] == [r.as_dict() for r in b.rules]
    assert a.evidence_requirements == ["Land records"]


def test_no_rules_cannot_be_assessed() -> None:
    assert evaluate([], {}).outcome == "NEEDS_INFORMATION"


def test_bad_value_type_needs_information_not_crash() -> None:
    r = evaluate_rule(rule("Y", "years", "GTE", 5), {"years": Fact("many", "DECLARED")})
    assert r.effect == "NEEDS_INFORMATION" and "Could not evaluate" in r.reason
