"""Soil organic carbon on an equivalent soil mass (ESM) basis — Wendt & Hauser (2013), as required by VM0042 v2.2 §8.2.1.6.

Reproduces Verra's published worksheet "ESM-sample-spreadsheets-Wendt-and-Hauser-2013.xlsx" (sheet "Cubic spline simple"):

1. Soil mass of each depth layer per hectare (VM0042 Equation 3, bracketed term; worksheet column E):
       M_layer [Mg/ha] = sample_mass [g] / (π · (D/2)² [mm²]) / N × 10 000
   where D is the inside diameter of the probe or auger (mm) and N the number of cores composited into the sample.
2. OC mass of the layer (worksheet column G; Equation 3 with OC in g/kg, expressed in Mg/ha):
       OC_layer [Mg/ha] = M_layer × OC [g/kg] / 1000
3. Cumulative soil mass and cumulative OC mass from the surface, starting at the point (0, 0) (the worksheet's hidden
   zero row), ordered by depth.
4. The cumulative OC mass at each reference cumulative soil mass is interpolated with a natural cubic spline through the
   points (cumulative soil mass, cumulative OC mass) (worksheet column J, macro `cubic_spline`). A reference mass beyond the
   deepest sample is evaluated on the last spline segment's cubic, exactly as the worksheet macro does (no linear tail).
   The depth to each reference mass uses the same spline through (cumulative soil mass, layer bottom depth) (column K).
5. The OC mass of each ESM layer is the difference of consecutive cumulative values (column M).

All arithmetic is Decimal in the framework's fixed context; the worksheet's VBA macro computes in single precision, so the
two agree to about 7 significant digits.

VM0042 requirements per Verra's draft Soil Sampling and Analysis Handbook v1.0 (26 Feb 2026, §6), also supported here:
- **mineral soil mass** basis: the x axis is the cumulative *mineral* fine-earth mass = fine-earth dry mass minus soil organic
  matter, SOM = SOC × 1/0.58 (van Bemmelen factor, as in the handbook / von Haden et al. 2020); the coarse fraction (> 2 mm)
  must already be excluded from the sample mass (the laboratory reports fine-earth mass);
- **linear interpolation** is mandatory when a profile has only 2 depth increments; cubic spline (or linear) with 3 or more.
"""
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal, localcontext
from itertools import pairwise

from app.calculation.framework import DECIMAL_CONTEXT

PI = Decimal("3.141592653589793238462643383279503")
ZERO, ONE, TWO, SIX = Decimal(0), Decimal(1), Decimal(2), Decimal(6)
SOM_PER_SOC = ONE / Decimal("0.58")          # soil organic matter = SOC / 0.58 (handbook §6.2 example)
SPLINE, LINEAR = "CUBIC_SPLINE", "LINEAR"
G_PER_MM2_TO_MG_PER_HA = Decimal(10_000)   # VM0042 Eq. 3 factor (with OC in g/kg the product is kg/ha; here soil mass is Mg/ha)


class EsmError(ValueError):
    """Inputs that cannot form a soil profile (the calling module turns this into a calculation blocker)."""


@dataclass(frozen=True)
class Layer:
    """One sampled depth increment of a soil profile."""
    depth_top_cm: Decimal
    depth_bottom_cm: Decimal
    sample_mass_g: Decimal        # dry fine-fraction soil mass of the (composited) sample
    oc_g_per_kg: Decimal          # organic carbon concentration


@dataclass(frozen=True)
class EsmPoint:
    reference_mass_mg_ha: Decimal      # cumulative reference soil mass
    cumulative_oc_mg_ha: Decimal       # OC mass from the surface down to the reference mass
    layer_oc_mg_ha: Decimal            # OC mass of the ESM layer ending at this reference mass
    depth_cm: Decimal                  # depth at which the reference mass is reached


@dataclass(frozen=True)
class Profile:
    cumulative_soil_mass_mg_ha: tuple[Decimal, ...]   # includes the leading 0
    cumulative_oc_mg_ha: tuple[Decimal, ...]          # includes the leading 0
    depths_cm: tuple[Decimal, ...]                    # includes the leading 0 (surface)


def layer_soil_mass_mg_ha(sample_mass_g: Decimal, probe_diameter_mm: Decimal, cores: int) -> Decimal:
    """VM0042 Eq. 3 bracketed term: soil mass of one depth layer per hectare (Mg/ha)."""
    if probe_diameter_mm <= 0 or cores < 1:
        raise EsmError("Probe diameter must be positive and at least one core is needed.")
    if sample_mass_g < 0:
        raise EsmError("Sample mass cannot be negative.")
    with localcontext(DECIMAL_CONTEXT):
        radius = probe_diameter_mm / TWO
        return sample_mass_g / PI / (radius * radius) / Decimal(cores) * G_PER_MM2_TO_MG_PER_HA


def layer_soc_mass_kg_ha(sample_mass_g: Decimal, probe_diameter_mm: Decimal, cores: int, oc_g_per_kg: Decimal) -> Decimal:
    """VM0042 Eq. 3 as printed: M_n,dl,SOC (kg/ha) = (M_sample / (π (D/2)² N) × 10 000) × OC (g/kg)."""
    with localcontext(DECIMAL_CONTEXT):
        return layer_soil_mass_mg_ha(sample_mass_g, probe_diameter_mm, cores) * oc_g_per_kg


def profile(layers: Sequence[Layer], probe_diameter_mm: Decimal, cores: int, mineral: bool = False) -> Profile:
    """Cumulative soil mass / OC mass from the surface (worksheet columns F and H), layers ordered by depth. With
    `mineral=True` the cumulative soil mass is the mineral mass (fine-earth mass minus SOM), as VM0042 requires."""
    if len(layers) < 1:
        raise EsmError("A profile needs at least one sampled depth layer.")
    ordered = sorted(layers, key=lambda x: x.depth_top_cm)
    if ordered[0].depth_top_cm != 0:
        raise EsmError("The first depth layer must start at the soil surface (0 cm).")
    for a, b in pairwise(ordered):
        if b.depth_top_cm != a.depth_bottom_cm:
            raise EsmError(f"Depth layers must be contiguous ({a.depth_bottom_cm} cm is followed by {b.depth_top_cm} cm).")
    with localcontext(DECIMAL_CONTEXT):
        mass, oc, depth = [ZERO], [ZERO], [ZERO]
        for layer in ordered:
            if layer.depth_bottom_cm <= layer.depth_top_cm:
                raise EsmError("Each depth layer must have its bottom below its top.")
            if layer.oc_g_per_kg < 0:
                raise EsmError("Organic carbon content cannot be negative.")
            m = layer_soil_mass_mg_ha(layer.sample_mass_g, probe_diameter_mm, cores)
            if m <= 0:
                raise EsmError("Each depth layer needs a positive soil mass.")
            soc_fraction = layer.oc_g_per_kg / Decimal(1000)
            x = m * (ONE - soc_fraction * SOM_PER_SOC) if mineral else m
            if x <= 0:
                raise EsmError("Organic matter cannot exceed the soil mass (check the organic carbon value).")
            mass.append(mass[-1] + x)
            oc.append(oc[-1] + m * soc_fraction)
            depth.append(layer.depth_bottom_cm)
        return Profile(tuple(mass), tuple(oc), tuple(depth))


def _second_derivatives(x: Sequence[Decimal], y: Sequence[Decimal]) -> list[Decimal]:
    """Natural cubic spline (second derivative 0 at both ends), solved with the Thomas algorithm."""
    n = len(x)
    if n < 3:
        return [ZERO] * n    # two points: the natural spline is the straight line
    h = [x[i + 1] - x[i] for i in range(n - 1)]
    lower, diag, upper, rhs = [ZERO] * n, [ONE] * n, [ZERO] * n, [ZERO] * n
    for i in range(1, n - 1):
        lower[i], diag[i], upper[i] = h[i - 1], TWO * (h[i - 1] + h[i]), h[i]
        rhs[i] = SIX * ((y[i + 1] - y[i]) / h[i] - (y[i] - y[i - 1]) / h[i - 1])
    c, d = [ZERO] * n, [ZERO] * n
    c[0], d[0] = upper[0] / diag[0], rhs[0] / diag[0]
    for i in range(1, n):
        m = diag[i] - lower[i] * c[i - 1]
        c[i] = upper[i] / m if i < n - 1 else ZERO
        d[i] = (rhs[i] - lower[i] * d[i - 1]) / m
    out = [ZERO] * n
    out[-1] = d[-1]
    for i in range(n - 2, -1, -1):
        out[i] = d[i] - c[i] * out[i + 1]
    return out


def cubic_spline(x: Sequence[Decimal], y: Sequence[Decimal], t: Decimal) -> Decimal:
    """Value at t of the natural cubic spline through (x, y). Outside the data range the nearest end segment's cubic is used
    (the behaviour of the worksheet's `cubic_spline` macro)."""
    if len(x) != len(y) or len(x) < 2:
        raise EsmError("A spline needs at least two points.")
    if any(b <= a for a, b in pairwise(x)):
        raise EsmError("Cumulative soil mass must increase strictly with depth.")
    with localcontext(DECIMAL_CONTEXT):
        m = _second_derivatives(x, y)
        n = len(x)
        if t <= x[0]:
            i = 0
        elif t >= x[-1]:
            i = n - 2
        else:
            i = max(k for k in range(n - 1) if x[k] <= t)
        h = x[i + 1] - x[i]
        a = (x[i + 1] - t) / h
        b = (t - x[i]) / h
        return a * y[i] + b * y[i + 1] + ((a * a * a - a) * m[i] + (b * b * b - b) * m[i + 1]) * h * h / SIX


def linear(x: Sequence[Decimal], y: Sequence[Decimal], t: Decimal) -> Decimal:
    """Piecewise-linear interpolation through (x, y); outside the range the nearest end segment is extended."""
    if len(x) != len(y) or len(x) < 2:
        raise EsmError("Interpolation needs at least two points.")
    if any(b <= a for a, b in pairwise(x)):
        raise EsmError("Cumulative soil mass must increase strictly with depth.")
    with localcontext(DECIMAL_CONTEXT):
        n = len(x)
        i = 0 if t <= x[0] else n - 2 if t >= x[-1] else max(k for k in range(n - 1) if x[k] <= t)
        return y[i] + (y[i + 1] - y[i]) * (t - x[i]) / (x[i + 1] - x[i])


def interpolate(x: Sequence[Decimal], y: Sequence[Decimal], t: Decimal, method: str) -> Decimal:
    return cubic_spline(x, y, t) if method == SPLINE else linear(x, y, t)


def method_for(increments: int) -> str:
    """Handbook §6.2.2: linear when only 2 depth increments; cubic spline when 3 or more."""
    return SPLINE if increments >= 3 else LINEAR


def mass_at_depth(p: Profile, depth_cm: Decimal, method: str) -> Decimal:
    """Cumulative (mineral) soil mass from the surface to a depth, e.g. 30 cm for the reference soil mass."""
    return interpolate(p.depths_cm, p.cumulative_soil_mass_mg_ha, depth_cm, method)


def oc_at_mass(p: Profile, reference_mass_mg_ha: Decimal, method: str) -> Decimal:
    """Cumulative OC mass (Mg/ha) down to a cumulative reference soil mass."""
    return interpolate(p.cumulative_soil_mass_mg_ha, p.cumulative_oc_mg_ha, reference_mass_mg_ha, method)


def equivalent_soil_mass(p: Profile, reference_masses_mg_ha: Sequence[Decimal]) -> list[EsmPoint]:
    """OC mass at each cumulative reference soil mass (ascending), the ESM layer masses between them, and the depth at which
    each reference mass is reached (worksheet columns J, M and K)."""
    refs = list(reference_masses_mg_ha)
    if not refs or any(r <= 0 for r in refs) or any(b <= a for a, b in pairwise(refs)):
        raise EsmError("Reference soil masses must be positive and strictly increasing.")
    out: list[EsmPoint] = []
    previous = ZERO
    with localcontext(DECIMAL_CONTEXT):
        for r in refs:
            cum = cubic_spline(p.cumulative_soil_mass_mg_ha, p.cumulative_oc_mg_ha, r)
            depth = cubic_spline(p.cumulative_soil_mass_mg_ha, p.depths_cm, r)
            out.append(EsmPoint(r, cum, cum - previous, depth))
            previous = cum
    return out
