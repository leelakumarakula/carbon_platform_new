"""Field-collection rules (decisions S1, S2): GPS tolerance, duplicate-point threshold, field checklist, minimum photos.

These are PLATFORM DEFAULTS unless the locked methodology version configures a value in a SAMPLING rule
(`gps_max_distance_m`, `duplicate_point_distance_m`, `field_checklist`, `min_photos_per_sample`). Platform defaults are
never presented as requirements of VM0042, CCTS or any other methodology.

The resolved rules are frozen (JSON) on each sampling design version when it is created, and copied onto each field
collection record when it is started. Later changes to the defaults therefore apply only to new design versions;
historical records keep the rules they were collected under.
"""
import json
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import FieldCollectionRecord, MethodologyVersion, SamplingDesignVersion
from app.models.base import utcnow
from app.services.mrv_requirements import requirements

PLATFORM_DEFAULT = "PLATFORM_DEFAULT"
METHODOLOGY = "METHODOLOGY"

# Versioned platform checklists. Add a new version instead of editing one that records were collected under.
PLATFORM_CHECKLISTS: dict[str, list[dict[str, str]]] = {
    "PLATFORM-DEFAULT-1": [
        {"key": "location_confirmed", "label": "Location confirmed on site"},
        {"key": "depth_measured", "label": "Sampling depth measured"},
        {"key": "sample_labelled", "label": "Sample bag labelled with the collection code"},
        {"key": "photo_taken", "label": "Field photo taken"},
    ],
    # Phase 6 (decision 18): physical samples carry their own SMP code. Used by new sampling design versions only;
    # records frozen with PLATFORM-DEFAULT-1 keep it.
    "PLATFORM-DEFAULT-2": [
        {"key": "location_confirmed", "label": "Location confirmed on site"},
        {"key": "depth_measured", "label": "Sampling depth measured"},
        {"key": "sample_labelled_with_sample_code", "label": "Sample container labelled with its sample code (SMP-…)"},
        {"key": "photo_taken", "label": "Field photo taken"},
    ],
}
NOTE = ("Values marked PLATFORM_DEFAULT are platform governance defaults, not requirements of any methodology; "
        "values marked METHODOLOGY come from the locked methodology version's SAMPLING rules.")


def _checklist_items(raw: Any) -> list[dict[str, str]]:
    items = raw if isinstance(raw, list) else []
    out = []
    for it in items:
        if isinstance(it, dict) and it.get("key"):
            out.append({"key": str(it["key"]), "label": str(it.get("label") or it["key"])})
        elif isinstance(it, str) and it.strip():
            out.append({"key": it.strip(), "label": it.strip()})
    return out


def resolve(db: Session, version: MethodologyVersion) -> dict[str, Any]:
    """Rules for a NEW design version: methodology-configured values first, otherwise the current platform defaults."""
    s = get_settings()
    req = requirements(db, version)

    def pick(key: str, default: Any) -> tuple[Any, str, str | None]:
        val = req.value(key)
        if val is None:
            return default, PLATFORM_DEFAULT, None
        return val, METHODOLOGY, req.sampling[key]["rule_code"]

    gps, gps_src, gps_rule = pick("gps_max_distance_m", s.GPS_MAX_DISTANCE_M)
    dup, dup_src, dup_rule = pick("duplicate_point_distance_m", s.SAMPLING_DUPLICATE_DISTANCE_M)
    photos, ph_src, ph_rule = pick("min_photos_per_sample", s.FIELD_MIN_PHOTOS_PER_SAMPLE)
    cores, cores_src, cores_rule = pick("core_details_required", False)
    method_items = _checklist_items(req.value("field_checklist"))
    if method_items:
        rule_code = req.sampling["field_checklist"]["rule_code"]
        checklist_version, items, chk_src = f"METHODOLOGY:{version.version_label}:{rule_code}", method_items, METHODOLOGY
    else:
        checklist_version = s.FIELD_CHECKLIST_VERSION
        items, chk_src = PLATFORM_CHECKLISTS[checklist_version], PLATFORM_DEFAULT
    return {
        "gps_tolerance_m": float(gps), "gps_tolerance_source": gps_src, "gps_tolerance_rule": gps_rule,
        "duplicate_distance_m": float(dup), "duplicate_distance_source": dup_src, "duplicate_distance_rule": dup_rule,
        "min_photos": int(photos), "min_photos_source": ph_src, "min_photos_rule": ph_rule,
        "core_details_required": cores is True or str(cores).strip().lower() == "true",
        "core_details_source": cores_src, "core_details_rule": cores_rule,
        "checklist_version": checklist_version, "checklist_items": items, "checklist_source": chk_src,
        "methodology_version_id": str(version.id), "resolved_at": utcnow().isoformat(), "note": NOTE,
    }


def legacy_defaults() -> dict[str, Any]:
    """Rules for records created before rules were frozen (migration 0007 backfill): the values in force then."""
    return {"gps_tolerance_m": 30.0, "gps_tolerance_source": PLATFORM_DEFAULT, "gps_tolerance_rule": None,
            "duplicate_distance_m": 1.0, "duplicate_distance_source": PLATFORM_DEFAULT, "duplicate_distance_rule": None,
            "min_photos": 1, "min_photos_source": PLATFORM_DEFAULT, "min_photos_rule": None,
            "checklist_version": "PLATFORM-DEFAULT-1", "checklist_items": PLATFORM_CHECKLISTS["PLATFORM-DEFAULT-1"],
            "checklist_source": PLATFORM_DEFAULT, "methodology_version_id": None, "resolved_at": None, "note": NOTE}


def of_design(dv: SamplingDesignVersion) -> dict[str, Any]:
    return json.loads(dv.field_rules) if dv.field_rules else legacy_defaults()


def of_collection(fc: FieldCollectionRecord) -> dict[str, Any]:
    return json.loads(fc.field_rules) if fc.field_rules else legacy_defaults()


def checklist_keys(rules: dict[str, Any]) -> list[str]:
    return [i["key"] for i in rules["checklist_items"]]
