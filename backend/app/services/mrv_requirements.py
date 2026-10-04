"""MRV requirements of a methodology version (spec section 17, Phase 5 rule 24).

Requirements are read from the locked version's Phase 4 configuration:
- monitoring rules → measurement definitions (parameter, unit, frequency, method, evidence)
- general rules of type SAMPLING → sampling parameters (recognised keys below)
- general rules of type BASELINE / UNCERTAINTY / LEAKAGE → listed for information

Anything a version does not configure is reported as CONFIGURATION_REQUIRED. Nothing is invented: the platform never
fills a methodology requirement with a default value.
"""
import json
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.orm import Session

from app.models import MethodologyVersion
from app.services import methodology_service as msvc

# Keys the platform understands in a SAMPLING rule's parameters (all optional; set by the methodology specialist).
SAMPLING_KEYS = {
    "gps_max_distance_m": "GPS tolerance from the planned point (m) — overrides the platform default",
    "duplicate_point_distance_m": "Duplicate sampling-point threshold (m) — overrides the platform default",
    "field_checklist": "Field checklist items — overrides the platform default checklist",
    "min_photos_per_sample": "Minimum field photos per sample — overrides the platform default",
    "core_details_required": "Probe/auger inside diameter and number of cores must be recorded per sample (e.g. VM0042 Eq. 3)",
    "quantification_approach": "Quantification approach (MEASURE_AND_REMEASURE / MEASURE_AND_MODEL)",
    "depth_top_cm": "Sampling depth (top, cm)",
    "depth_bottom_cm": "Sampling depth (bottom, cm)",
    "min_samples_per_stratum": "Minimum samples per stratum",
    "target_precision_pct": "Target precision (%)",
    "confidence_level_pct": "Confidence level (%)",
    "statistical_design": "Statistical design",
    "stratification_variables": "Stratification variables",
    "repeat_sampling": "Repeat (re-measurement) sampling requirement",
}


@dataclass
class Requirements:
    methodology_version_id: str
    version_label: str
    is_demo_illustrative: bool
    monitoring: list[dict[str, Any]] = field(default_factory=list)
    sampling: dict[str, Any] = field(default_factory=dict)       # key → {"value", "rule_code", "source_reference"}
    other_rules: list[dict[str, Any]] = field(default_factory=list)
    gaps: list[str] = field(default_factory=list)

    @property
    def status(self) -> str:
        return "CONFIGURED" if not self.gaps else "CONFIGURATION_REQUIRED"

    def value(self, key: str) -> Any:
        return self.sampling[key]["value"] if key in self.sampling else None

    def as_dict(self) -> dict[str, Any]:
        return {"methodology_version_id": self.methodology_version_id, "version_label": self.version_label,
                "is_demo_illustrative": self.is_demo_illustrative, "status": self.status, "monitoring": self.monitoring,
                "sampling": self.sampling, "other_rules": self.other_rules, "gaps": self.gaps,
                "sampling_keys": SAMPLING_KEYS}


def requirements(db: Session, v: MethodologyVersion) -> Requirements:
    rs = msvc.rules(db, v.id)
    req = Requirements(str(v.id), v.version_label, v.is_demo_illustrative)
    for r in rs["monitoring"]:
        req.monitoring.append({"rule_id": str(r.id), "rule_code": r.rule_code, "title": r.title, "parameter": r.parameter, "unit": r.unit,
                               "frequency": r.frequency, "method": r.method, "evidence_requirement": r.evidence_requirement,
                               "source_reference": r.source_reference, "measurement_source": r.measurement_source,
                               "data_level": r.data_level})
    for r in rs["general"]:
        params = json.loads(r.parameters) if r.parameters else {}
        if r.rule_type == "SAMPLING":
            for k, val in params.items():
                if k in SAMPLING_KEYS:
                    req.sampling[k] = {"value": val, "rule_code": r.rule_code, "source_reference": r.source_reference}
        elif r.rule_type in ("BASELINE", "UNCERTAINTY", "LEAKAGE", "PERMANENCE", "ADDITIONALITY"):
            req.other_rules.append({"rule_code": r.rule_code, "rule_type": r.rule_type, "title": r.title, "parameters": params})
    if not req.monitoring:
        req.gaps.append("Monitoring parameters (no monitoring rules in the methodology version)")
    for m in req.monitoring:
        if m["measurement_source"] == "UNCLASSIFIED":
            req.gaps.append(f"Measurement source of monitoring rule {m['rule_code']} (FIELD / FIELD_ACTIVITY / LABORATORY not declared)")
    for key in ("quantification_approach", "depth_top_cm", "depth_bottom_cm", "min_samples_per_stratum", "statistical_design"):
        if key not in req.sampling:
            req.gaps.append(SAMPLING_KEYS[key])
    return req
