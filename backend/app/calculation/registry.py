"""Application registry of methodology-specific calculation modules (decision A1 / A2).

A module is looked up by the locked methodology's code and version label; it is used only when its declared rule set matches
the locked version exactly. Registered modules:

- `VM0042-V2.2-QA2-QA3` — Verra VM0042 v2.2 (SOC measure & remeasure + default-factor emissions), NOT_PRODUCTION_READY until
  its production-readiness approval is recorded.

A module declared with `calculation_rules_version = 0` is version-bound: a methodology version selects it on its Calculation tab
(which copies the module's rule set and is approved with the version), and `bind()` then pins the module to that version's
calculation-rule revision. A version that did not select the module keeps the unbound module, whose revision 0 never matches —
so the calculation stays blocked until the choice is made and approved. Test fixtures are never registered here.
"""
from collections.abc import Callable

from app.calculation.framework import CalculationModule
from app.calculation.modules.vm0042_v2_2 import Vm0042V22

Resolver = Callable[[str, str], CalculationModule | None]

_MODULES: tuple[CalculationModule, ...] = (Vm0042V22(),)


def modules() -> list[CalculationModule]:
    return list(_MODULES)


def by_code(code: str) -> CalculationModule | None:
    return next((m for m in _MODULES if m.code == code), None)


def resolve(methodology_code: str, version_label: str) -> CalculationModule | None:
    return next((m for m in _MODULES if m.methodology_code == methodology_code and m.version_label == version_label), None)


def bind(module: CalculationModule | None, calculation_rules_version: int, version_readiness: str | None = None) -> CalculationModule | None:
    """Pin a version-bound module (calculation_rules_version 0) to the selecting version's calculation-rule revision. When the
    version's production readiness has been approved (methodology_versions.calculation_readiness), the bound module carries it."""
    if module is None or module.calculation_rules_version != 0:
        return module
    attrs: dict[str, object] = {"calculation_rules_version": calculation_rules_version}
    if version_readiness == "PRODUCTION_READY":
        attrs["readiness"] = "PRODUCTION_READY"
    return type(f"{type(module).__name__}Bound", (type(module),), attrs)()
