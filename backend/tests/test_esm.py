"""Equivalent soil mass (Wendt & Hauser 2013) against Verra's own worksheet (ESM-sample-spreadsheets-Wendt-and-Hauser-2013.xlsx,
sheet "Cubic spline simple": probe 21.5 mm, 4 cores, five profiles MFCF1–5, reference masses 1500/3000/4500/6000 Mg/ha) and the
VM0042 v2.2 Figure 3 / Equation 3 example. The worksheet macro computes in single precision, so values match to ~7 significant
digits; the expected numbers below are the worksheet's cached results."""
from decimal import Decimal

import pytest

from app.calculation.library.esm import EsmError, Layer, cubic_spline, equivalent_soil_mass, layer_soc_mass_kg_ha, layer_soil_mass_mg_ha, profile

D, N = Decimal("21.5"), 4
DEPTHS = [(0, 8), (8, 16), (16, 32), (32, 48)]
REFS = [Decimal(1500), Decimal(3000), Decimal(4500), Decimal(6000)]
# (sample mass g, OC g/kg) per layer, and the worksheet's cumulative OC (column J) and depth to reference mass (column K)
PROFILES = {
    "MFCF1": ([("123.2", "24.287188420042472"), ("139.2", "12.681478533824528"), ("306.1", "8.706741680356373"), ("292.2", "6.9685959018314385")],
              ["29.738546027937353", "43.60408069529065", "55.46116675279182", "65.61606190251439"],
              ["13.54560333893949", "25.09982173684576", "36.552980811902536", "48.59194249189269"]),
    "MFCF2": ([("122.7", "28.76730530717023"), ("144.3", "10.647029879769182"), ("300.8", "7.702035647491051"), ("315.1", "6.6103840588666625")],
              ["32.62708050328494", "43.580115017506934", "55.110121245576686", "64.69518212795994"],
              ["13.381010847445726", "25.009797129360884", "36.42816030929719", "47.42029390081624"]),
    "MFCF3": ([("117.5", "20.679025872460244"), ("143.5", "11.283054618834822"), ("306.5", "8.52984726426919"), ("303.6", "7.094227289986121")],
              ["25.21565354474639", "38.39320625121876", "50.358693042744115", "60.72569305190596"],
              ["13.72855204847876", "25.111449517806594", "36.51576201843954", "48.01166648623429"]),
    "MFCF4": ([("127.4", "20.043011842080425"), ("158.8", "11.251199236039827"), ("317.6", "9.09973010012957"), ("339.8", "7.65073162934959")],
              ["25.486967530670487", "39.37700829440551", "52.64292291412874", "64.08999607756334"],
              ["12.710590912366023", "23.47164176091071", "34.439543581044184", "44.684183566660096"]),
    "MFCF5": ([("125.5", "19.879660587333586"), ("146.9", "10.157388911017502"), ("324.4", "7.504624944694696"), ("297.7", "6.702912243994888")],
              ["24.477793718170467", "36.023896011312054", "46.95521090437861", "56.92334093307248"],
              ["13.175317878597298", "24.046159835711475", "34.92912620919984", "46.721562623098144"]),
}


def _close(actual: Decimal, expected: str, rel: str = "1e-6") -> bool:
    e = Decimal(expected)
    return abs(actual - e) <= abs(e) * Decimal(rel) + Decimal("1e-9")


def _layers(rows: list[tuple[str, str]]) -> list[Layer]:
    return [Layer(Decimal(t), Decimal(b), Decimal(m), Decimal(oc)) for (t, b), (m, oc) in zip(DEPTHS, rows, strict=True)]


@pytest.mark.parametrize("name", sorted(PROFILES))
def test_matches_verra_esm_worksheet(name: str) -> None:
    rows, cum_oc, depth = PROFILES[name]
    points = equivalent_soil_mass(profile(_layers(rows), D, N), REFS)
    for p, oc, d in zip(points, cum_oc, depth, strict=True):
        assert _close(p.cumulative_oc_mg_ha, oc), (name, p.reference_mass_mg_ha, p.cumulative_oc_mg_ha, oc)
        assert _close(p.depth_cm, d), (name, p.reference_mass_mg_ha, p.depth_cm, d)
    # ESM layer masses are the differences of the cumulative values (worksheet column M)
    assert points[0].layer_oc_mg_ha == points[0].cumulative_oc_mg_ha
    assert abs(points[3].layer_oc_mg_ha - (points[3].cumulative_oc_mg_ha - points[2].cumulative_oc_mg_ha)) < Decimal("1e-24")


def test_layer_masses_match_worksheet_columns_e_and_g() -> None:
    # MFCF1 first layer: E13 = 848.3672899479288 Mg/ha, G13 = 20.604456220366153 Mg/ha
    m = layer_soil_mass_mg_ha(Decimal("123.2"), D, N)
    assert _close(m, "848.3672899479288", "1e-12")
    p = profile(_layers(PROFILES["MFCF1"][0]), D, N)
    assert _close(p.cumulative_oc_mg_ha[1], "20.604456220366153", "1e-12")
    assert _close(p.cumulative_soil_mass_mg_ha[4], "5926.864662809922", "1e-12")


def test_reference_mass_beyond_deepest_sample_uses_the_end_cubic() -> None:
    # MFCF1 reaches 5926.86 Mg/ha at 48 cm; 6000 Mg/ha lies beyond it and the worksheet extends the last cubic segment
    p = profile(_layers(PROFILES["MFCF1"][0]), D, N)
    assert p.cumulative_soil_mass_mg_ha[-1] < REFS[-1]
    (last,) = equivalent_soil_mass(p, [Decimal(6000)])
    assert _close(last.cumulative_oc_mg_ha, "65.61606190251439")


def test_spline_reproduces_the_worksheet_demo() -> None:
    # sheet "Cubic spline description": points (1..5, [0.75, 0, -1, 3, 4.75]) incl. extrapolation at 5.2
    x = [Decimal(i) for i in range(1, 6)]
    y = [Decimal(v) for v in ("0.75", "0", "-1", "3", "4.75")]
    for t, expected in (("1.2", "0.6891428842544556"), ("2.2", "-0.3748571561234345"), ("3.4", "0.3068570882933495"),
                        ("4.6", "4.3740000430430666"), ("5.2", "4.914857120846"), ("3", "-1")):
        assert _close(cubic_spline(x, y, Decimal(t)), expected, "1e-6"), t


def test_vm0042_figure_3_equation_3_example() -> None:
    # VM0042 v2.2 p.40: point VM42point1-1, 0-30 cm, 283.2 g, probe 21.5 mm, 4 cores, OC 24.29 g/kg -> 1950 Mg/ha soil, 47.36 Mg/ha OC
    assert abs(layer_soil_mass_mg_ha(Decimal("283.2"), D, N) - 1950) < 1
    assert abs(layer_soc_mass_kg_ha(Decimal("283.2"), D, N, Decimal("24.29")) / 1000 - Decimal("47.36")) < Decimal("0.05")


def test_invalid_profiles_are_refused() -> None:
    good = Layer(Decimal(0), Decimal(30), Decimal(280), Decimal(20))
    with pytest.raises(EsmError, match="surface"):
        profile([Layer(Decimal(5), Decimal(30), Decimal(280), Decimal(20))], D, N)
    with pytest.raises(EsmError, match="contiguous"):
        profile([good, Layer(Decimal(35), Decimal(50), Decimal(200), Decimal(9))], D, N)
    with pytest.raises(EsmError, match="core"):
        layer_soil_mass_mg_ha(Decimal(100), D, 0)
    with pytest.raises(EsmError, match="increasing"):
        equivalent_soil_mass(profile([good], D, N), [Decimal(3000), Decimal(1500)])
    # a single layer gives a straight line through the origin
    (pt,) = equivalent_soil_mass(profile([good], D, N), [Decimal(1000)])
    assert _close(pt.cumulative_oc_mg_ha, "20", "1e-20")   # 20 g/kg -> 20 Mg OC per 1000 Mg soil
