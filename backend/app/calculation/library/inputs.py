"""Input-shaping helpers shared by the methodology modules (pure, deterministic, no I/O).

- `pair_lab_samples`: pairs the organic-carbon and soil-mass laboratory results of each sample (by root sample) and groups them per
  field collection, refusing duplicates and unpaired results instead of silently keeping one of them;
- `stratum_labels`: readable, collision-free labels for per-stratum output codes (the stratum code when the frozen inputs carry
  it, otherwise a prefix of the stratum record id that is long enough to be unique);
- `previous_period_gap`: whether the earlier approved campaign closes the day before the reporting period starts.
"""
from collections import defaultdict
from collections.abc import Iterable
from datetime import date, timedelta
from typing import Any

from app.calculation.framework import CalculationBlocked, CalculationContext, InputValue

MIN_PREFIX = 8


def pair_lab_samples(ctx: CalculationContext, oc_var: str, mass_var: str) -> dict[str, list[tuple[InputValue, InputValue]]]:
    """Field collection id -> [(organic carbon, soil mass)] per sample. Blocks DUPLICATE_LAB_RESULT when a sample has more than one
    result of a kind (or two samples of one field collection cover the same depth increment) and MASS_RESULT_MISSING /
    MISSING_REQUIRED_INPUT when a result has no partner: nothing is dropped or picked silently."""
    def by_sample(var: str) -> dict[Any, InputValue]:
        seen: dict[Any, list[InputValue]] = defaultdict(list)
        for v in ctx.values(var):
            seen[v.context.get("root_sample_id")].append(v)
        dup = {str(k): [v.seq for v in vs] for k, vs in seen.items() if len(vs) > 1}
        if dup:
            first = sorted(dup)[0]
            raise CalculationBlocked("DUPLICATE_LAB_RESULT", f"Sample {first} has {len(dup[first])} approved {var} results; exactly one "
                                     "is used, so the extra result must be withdrawn (no result is picked silently).",
                                     {"variable": var, "root_sample_ids": sorted(dup), "input_seqs": dup})
        return {k: vs[0] for k, vs in seen.items()}

    oc, mass = by_sample(oc_var), by_sample(mass_var)
    no_oc = sorted(str(k) for k in mass if k not in oc)
    if no_oc:
        raise CalculationBlocked("MISSING_REQUIRED_INPUT", f"Sample {no_oc[0]} has a soil mass but no organic carbon result.",
                                 {"variable": oc_var, "reason": "OC_RESULT_MISSING", "root_sample_ids": no_oc})
    no_mass = sorted(str(k) for k in oc if k not in mass)
    if no_mass:
        raise CalculationBlocked("MASS_RESULT_MISSING", f"Sample {no_mass[0]} has an organic carbon result but no soil mass result; "
                                 "both are needed for the equivalent soil mass.", {"variable": mass_var, "root_sample_ids": no_mass})
    by_fc: dict[str, list[tuple[InputValue, InputValue]]] = defaultdict(list)
    for key, m in mass.items():
        by_fc[m.context["field_collection_id"]].append((oc[key], m))
    for fc, pairs in by_fc.items():
        depths: dict[tuple[Any, Any], list[str]] = defaultdict(list)
        for o, _ in pairs:
            depths[(o.context.get("depth_top_cm"), o.context.get("depth_bottom_cm"))].append(str(o.context.get("root_sample_id")))
        dup_depth = {f"{t}-{b} cm": ids for (t, b), ids in depths.items() if len(ids) > 1}
        if dup_depth:
            rng = sorted(dup_depth)[0]
            raise CalculationBlocked("DUPLICATE_LAB_RESULT", f"Field collection {fc} has {len(dup_depth[rng])} samples for the depth "
                                     f"increment {rng}; one sample per increment is expected.",
                                     {"variable": mass_var, "reason": "DUPLICATE_DEPTH_INCREMENT", "field_collection": fc,
                                      "increments": dup_depth})
    return dict(by_fc)


def stratum_labels(values: Iterable[InputValue], records: Iterable[str]) -> dict[str, str]:
    """Stratum record id -> label for output codes. The stratum code (frozen in the input context) is used when every input names the
    same code for the record and no other record uses it; otherwise the shortest prefix of the record id (at least 8 characters) that
    no other record or label shares, the full id at worst. Labels are always distinct."""
    recs = sorted(set(records))
    codes: dict[str, set[str]] = defaultdict(set)
    for v in values:
        rec, code = v.context.get("stratum_record_id"), v.context.get("stratum_code")
        if rec and code and str(code).strip():
            codes[str(rec)].add(str(code).strip())
    chosen = {r: next(iter(codes[r])) for r in recs if len(codes.get(r, ())) == 1}
    count: dict[str, int] = defaultdict(int)
    for c in chosen.values():
        count[c] += 1
    labels = {r: c for r, c in chosen.items() if count[c] == 1 and c not in recs}
    taken = set(labels.values())
    for r in recs:
        if r in labels:
            continue
        n = min(MIN_PREFIX, len(r))
        while n < len(r) and (any(o != r and o.startswith(r[:n]) for o in recs) or r[:n] in taken):
            n += 1
        label = r[:n] if r[:n] not in taken else r
        labels[r] = label
        taken.add(label)
    return labels


def previous_period_gap(snapshot: dict[str, Any]) -> dict[str, Any] | None:
    """None when the earlier approved campaign's period ends at most one day before the reporting period starts; otherwise the
    details of the gap (or of the missing previous-period dates)."""
    prev, cur = snapshot.get("previous_period") or {}, snapshot.get("reporting_period") or {}
    if not prev.get("end") or not cur.get("start"):
        return {"reason": "PREVIOUS_PERIOD_UNKNOWN", "previous_period": prev or None}
    prev_end, cur_start = date.fromisoformat(prev["end"]), date.fromisoformat(cur["start"])
    if prev_end + timedelta(days=1) >= cur_start:
        return None
    return {"reason": "PREVIOUS_PERIOD_NOT_ADJACENT", "previous_period_end": prev["end"], "reporting_period_start": cur["start"],
            "gap_days": (cur_start - prev_end).days - 1, "previous_period_number": prev.get("number"),
            "reporting_period_number": cur.get("number")}


def is_first_comparison(snapshot: dict[str, Any]) -> bool:
    """True only when the earlier approved period is demonstrably the project's first monitoring period (period number 1): then no
    earlier verification can have credited a stock that the earlier period does not measure."""
    prev = snapshot.get("previous_period") or {}
    return prev.get("number") == 1
