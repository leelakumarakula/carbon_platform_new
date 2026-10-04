"""Application registry of methodology-specific calculation modules (decision A1 / A2).

A module is looked up by the locked methodology's code and version label; it is used only when its declared rule set matches
the locked version exactly. Registered modules:

- `VM0042-V2.2-QA2-QA3` — Verra VM0042 v2.2 (SOC measure & remeasure + default-factor emissions)
- `GS402-ZT-A1`, `GS402-IT-A1`, `GS402-IT-A3`, `GS402-CC-A1`, `GS402-CC-A3` — Gold Standard SOC Framework (402) v1.0 with the
  zero tillage (402.4), improved tillage (402.1) and cover crops (402.6) activity modules, per quantification approach
- `VM0047-V1.1-CENSUS` — Verra VM0047 v1.1 ARR, census-based approach
- `VM0044-V1.2` — Verra VM0044 v1.2 biochar
- `CCTS-FR05.002`, `CCTS-FR05.001` — India CCTS A/R (lands except wetlands; degraded mangroves)
- `GS403-V2.1` — Gold Standard A/R GS 403 v2.1
- `VM0051-V1.1-QA3`, `CCTS-AG04.002` — rice methane (Verra VM0051 v1.1; India CCTS AG04.002)
All are NOT_PRODUCTION_READY until their production-readiness approval is recorded.

Several modules may implement the same methodology version (one per activity module / approach): the version's Calculation-tab
choice (`calculation_module_code`) decides which one `resolve` returns.

A module declared with `calculation_rules_version = 0` is version-bound: a methodology version selects it on its Calculation tab
(which copies the module's rule set and is approved with the version), and `bind()` then pins the module to that version's
calculation-rule revision. A version that did not select the module keeps the unbound module, whose revision 0 never matches —
so the calculation stays blocked until the choice is made and approved. Test fixtures are never registered here.
"""
from collections.abc import Callable

from app.calculation.framework import CalculationModule
from app.calculation.modules import gs_soc_402
from app.calculation.modules.ccts_ar import CctsFr05001, CctsFr05002
from app.calculation.modules.gs_ar_403 import Gs403V21
from app.calculation.modules.rice import CctsAg04002, Vm0051V11
from app.calculation.modules.vm0042_v2_2 import Vm0042V22
from app.calculation.modules.vm0044_v1_2 import Vm0044V12
from app.calculation.modules.vm0047_v1_1 import Vm0047V11Census

Resolver = Callable[[str, str], CalculationModule | None]

_MODULES: tuple[CalculationModule, ...] = (Vm0042V22(), *gs_soc_402.MODULES, Vm0047V11Census(), Vm0044V12(), CctsFr05002(), CctsFr05001(),
                                          Vm0051V11(), CctsAg04002(), Gs403V21())


def modules() -> list[CalculationModule]:
    return list(_MODULES)


def by_code(code: str) -> CalculationModule | None:
    return next((m for m in _MODULES if m.code == code), None)


def resolve(methodology_code: str, version_label: str, selected: str | None = None) -> CalculationModule | None:
    """The module for a methodology version: the selected one when it implements the version, otherwise the first registered."""
    found = [m for m in _MODULES if m.methodology_code == methodology_code and m.version_label == version_label]
    return next((m for m in found if m.code == selected), found[0] if found else None)


def bind(module: CalculationModule | None, calculation_rules_version: int, version_readiness: str | None = None) -> CalculationModule | None:
    """Pin a version-bound module (calculation_rules_version 0) to the selecting version's calculation-rule revision. When the
    version's production readiness has been approved (methodology_versions.calculation_readiness), the bound module carries it."""
    if module is None or module.calculation_rules_version != 0:
        return module
    attrs: dict[str, object] = {"calculation_rules_version": calculation_rules_version}
    if version_readiness == "PRODUCTION_READY":
        attrs["readiness"] = "PRODUCTION_READY"
    return type(f"{type(module).__name__}Bound", (type(module),), attrs)()
