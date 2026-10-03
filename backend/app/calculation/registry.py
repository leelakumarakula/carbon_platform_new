"""Application registry of methodology-specific calculation modules (decision A1 / A2).

A module is looked up by the locked methodology's code and version label; it is used only when its declared rule set matches
the locked version exactly. Phase 7 ships NO module: no real methodology is configured and no illustrative DEMO equations
have been approved (decision A19 / C2), so every project is blocked with CONFIGURATION_REQUIRED (reason NO_CALCULATION_MODULE).
Test fixtures are never registered here.
"""
from collections.abc import Callable

from app.calculation.framework import CalculationModule

Resolver = Callable[[str, str], CalculationModule | None]

_MODULES: tuple[CalculationModule, ...] = ()


def modules() -> list[CalculationModule]:
    return list(_MODULES)


def resolve(methodology_code: str, version_label: str) -> CalculationModule | None:
    return next((m for m in _MODULES if m.methodology_code == methodology_code and m.version_label == version_label), None)
