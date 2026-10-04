"""CDM-style A/R tree and shrub biomass (CDM AR-TOOL14 as adopted by the India CCTS tool BM-T-AR-0004 v1.0).

Plot-based estimation of tree carbon stocks by stratified random sampling (Eqs. 12-17), the per-plot root-shoot ratio
(Appendix 1, Eq. 4 note), the change between two independent stock estimates with its uncertainty (Eqs. 1-2), the uncertainty
discount of Appendix 2, and shrubs from crown cover (Eqs. 26-27). Pure Decimal functions; the calling module turns problems into
calculation blockers.
"""
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal, localcontext

from app.calculation.framework import DECIMAL_CONTEXT
from app.calculation.library import stats

ZERO, ONE = Decimal(0), Decimal(1)
C_TO_CO2 = Decimal("3.666666666666666666666666666666667")
TWO_SIDED_90 = 0.95
# Appendix 2: (upper bound of U, discount as a fraction of U)
DISCOUNT_BANDS = ((Decimal("0.10"), ZERO), (Decimal("0.15"), Decimal("0.25")), (Decimal("0.20"), Decimal("0.50")),
                  (Decimal("0.30"), Decimal("0.75")))


def mokany_root_shoot(agb_per_ha: Decimal) -> Decimal:
    """R = e^(−1.085 + 0.9256 ln b) / b, b = above-ground tree biomass per hectare (t d.m./ha) — Appendix 1 note to Eq. 4."""
    if agb_per_ha <= 0:
        return ZERO
    with localcontext(DECIMAL_CONTEXT):
        return (Decimal("-1.085") + Decimal("0.9256") * agb_per_ha.ln()).exp() / agb_per_ha


@dataclass(frozen=True)
class StockEstimate:
    carbon_t_co2e: Decimal          # C_TREE (Eq. 12)
    mean_biomass_t_ha: Decimal      # b_TREE (Eq. 14), total (above + below ground)
    uncertainty: Decimal            # u_C (Eq. 15), fraction of the mean
    plots: int


def stratified_stock(strata: Sequence[tuple[Decimal, Sequence[Decimal]]], carbon_fraction: Decimal) -> StockEstimate:
    """strata = [(area ha, [total tree biomass per ha of each plot, t d.m./ha]), ...] → carbon stock with its 90 % uncertainty
    (Eqs. 12-17; t two-sided 90 % with n − M degrees of freedom)."""
    used = [(a, list(p)) for a, p in strata if a > 0]
    if not used:
        return StockEstimate(ZERO, ZERO, ZERO, 0)
    with localcontext(DECIMAL_CONTEXT):
        area = sum((a for a, _ in used), ZERO)
        mean = ZERO
        var = ZERO
        n_total = 0
        for a, plots in used:
            if len(plots) < 2:
                raise ValueError("Each stratum needs at least two sample plots for a variance.")
            w = a / area
            mean += w * stats.mean(plots)                                                       # Eqs. 14, 16
            var += w * w * stats.sample_variance(plots) / Decimal(len(plots))                    # Eqs. 15, 17
            n_total += len(plots)
        df = Decimal(max(1, n_total - len(used)))
        t = stats.t_quantile(TWO_SIDED_90, df)
        u = t * var.sqrt() / mean if mean > 0 else ZERO
        carbon = C_TO_CO2 * carbon_fraction * area * mean                                       # Eqs. 12, 13
        return StockEstimate(carbon, mean, u, n_total)


def change_uncertainty(c1: Decimal, u1: Decimal, c2: Decimal, u2: Decimal) -> Decimal:
    """Eq. 2: uncertainty of the difference of two independent stock estimates (fraction of |ΔC|)."""
    d = c2 - c1
    with localcontext(DECIMAL_CONTEXT):
        if d == 0:
            return ONE
        return ((u1 * c1) ** 2 + (u2 * c2) ** 2).sqrt() / abs(d)


def discount_fraction(u: Decimal) -> Decimal:
    """Appendix 2: the share of the uncertainty half-width deducted (0, 25, 50, 75 or 100 %)."""
    for limit, df in DISCOUNT_BANDS:
        if u <= limit:
            return df
    return ONE


def conservative(value: Decimal, u: Decimal, increase: bool = False) -> Decimal:
    """Appendix 2: a project estimate is decreased (a baseline estimate increased) by discount × U × |value|."""
    adj = discount_fraction(u) * u * abs(value)
    return value + adj if increase else value - adj


def shrub_carbon(strata: Sequence[tuple[Decimal, Decimal]], b_forest: Decimal, bdr_sf: Decimal = Decimal("0.10"),
                 carbon_fraction: Decimal = Decimal("0.47"), root_shoot: Decimal = Decimal("0.40")) -> Decimal:
    """Eqs. 26-27: strata = [(area ha, shrub crown cover fraction)]; crown cover < 5 % counts as zero (para 67)."""
    with localcontext(DECIMAL_CONTEXT):
        total = ZERO
        for area, cc in strata:
            if cc >= Decimal("0.05"):
                total += area * bdr_sf * b_forest * cc
        return C_TO_CO2 * carbon_fraction * (ONE + root_shoot) * total
