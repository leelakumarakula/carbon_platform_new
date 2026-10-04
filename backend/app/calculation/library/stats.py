"""Sampling statistics for measure-and-remeasure methods (VM0042 v2.2 §8.6.2 and §8.6.4; Verra draft VM0042 Soil Sampling and
Analysis Handbook v1.0, Appendix 7.1).

- Sample mean and unbiased sample variance (n − 1) of plot values.
- Welch–Satterthwaite effective degrees of freedom when independent variance components are combined (handbook eq. 23).
- One-sided Student-t critical value at the 66.67 % level (VM0042 Eq. 74 t₀.₆₆₇ ≈ 0.4307 at large sample sizes): the quantile
  for probability 2/3 with the given degrees of freedom.

The t quantile is a statistical constant computed in binary floating point (regularized incomplete beta, bisection) and then
fixed to 12 decimal places, so it is deterministic and reproducible; everything else is Decimal.
"""
import math
from collections.abc import Sequence
from decimal import Decimal, localcontext

from app.calculation.framework import DECIMAL_CONTEXT

T_PROBABILITY = 2.0 / 3.0   # one-sided 66.67 % (probability of exceedance method, VM0042 §8.6.4)


def mean(values: Sequence[Decimal]) -> Decimal:
    if not values:
        raise ValueError("mean of no values")
    with localcontext(DECIMAL_CONTEXT):
        return sum(values, Decimal(0)) / Decimal(len(values))


def sample_variance(values: Sequence[Decimal]) -> Decimal:
    """Unbiased sample variance (divisor n − 1); needs at least two values."""
    if len(values) < 2:
        raise ValueError("a sample variance needs at least two values")
    with localcontext(DECIMAL_CONTEXT):
        m = mean(values)
        return sum(((v - m) * (v - m) for v in values), Decimal(0)) / Decimal(len(values) - 1)


def welch_satterthwaite(components: Sequence[tuple[Decimal, int]]) -> Decimal:
    """Effective degrees of freedom for a sum of independent variance components [(variance_of_mean_component, n)]:
    df = (Σ cᵢ)² / Σ (cᵢ² / (nᵢ − 1))."""
    with localcontext(DECIMAL_CONTEXT):
        total = sum((c for c, _ in components), Decimal(0))
        denom = sum((c * c / Decimal(n - 1) for c, n in components if n > 1), Decimal(0))
        if total == 0 or denom == 0:
            return Decimal(max((n - 1 for _, n in components), default=1))
        return total * total / denom


def _betacf(a: float, b: float, x: float) -> float:
    """Continued fraction for the regularized incomplete beta function (modified Lentz)."""
    tiny, qab, qap, qam = 1e-300, a + b, a + 1.0, a - 1.0
    c, d = 1.0, 1.0 - qab * x / qap
    d = 1.0 / (d if abs(d) > tiny else tiny)
    h = d
    for m in range(1, 400):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        d = 1.0 / (d if abs(d) > tiny else tiny)
        c = 1.0 + aa / c if abs(1.0 + aa / c) > tiny else tiny
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        d = 1.0 / (d if abs(d) > tiny else tiny)
        c = 1.0 + aa / c if abs(1.0 + aa / c) > tiny else tiny
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < 1e-15:
            break
    return h


def _incomplete_beta(a: float, b: float, x: float) -> float:
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    lbeta = math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b) + a * math.log(x) + b * math.log(1.0 - x)
    if x < (a + 1.0) / (a + b + 2.0):
        return math.exp(lbeta) * _betacf(a, b, x) / a
    return 1.0 - math.exp(lbeta) * _betacf(b, a, 1.0 - x) / b


def t_cdf(t: float, df: float) -> float:
    """CDF of Student's t distribution."""
    x = df / (df + t * t)
    tail = 0.5 * _incomplete_beta(df / 2.0, 0.5, x)
    return 1.0 - tail if t >= 0 else tail


def t_quantile(probability: float, df: Decimal) -> Decimal:
    """Student-t quantile for a probability in (0.5, 1) by bisection; fixed to 12 decimal places."""
    d = float(df)
    if d <= 0:
        raise ValueError("degrees of freedom must be positive")
    lo, hi = 0.0, 1.0
    while t_cdf(hi, d) < probability:
        hi *= 2.0
    for _ in range(200):
        mid = (lo + hi) / 2.0
        if t_cdf(mid, d) < probability:
            lo = mid
        else:
            hi = mid
    return Decimal(f"{(lo + hi) / 2.0:.12f}")
