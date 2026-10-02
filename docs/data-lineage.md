# Data lineage

Target chain (spec section 35), and which links exist after each phase:

```
CREDIT → REGISTRY → VERIFICATION → CALCULATION RUN → METHODOLOGY VERSION → INPUT DATASET → LAB RESULT → SAMPLE
       → SAMPLING POINT → STRATUM → FARM → PROJECT → FARMER
```

| Link | Where it is stored | Phase |
|---|---|---|
| Farmer → farm | `farms.farmer_id` (operator); owner(s) in `farm_ownership` | 2 |
| Farm → boundary version | `farms.current_boundary_id`; every version kept in `farm_boundaries` | 2 |
| Farm → history | versioned `farm_land/crop/practice_history` (`record_id`, `version`, `is_current`) | 2 |
| Project → farm participation | `project_farms` with the **farm boundary version** and area used when the farm joined | 3 |
| Participation → carbon rights | `project_carbon_rights` (agreement / document / reference, review) | 3 |
| Project boundary → farm boundaries | `project_boundaries.farm_boundary_ids` (exact versions in each union) | 3 |
| Project → standard / activity | `project_standards`, `project_activities` (history) | 3 |
| Project → methodology + version | `project_methodologies` (LOCKED) with the evaluation result, specialist review and the three rule-set revisions | 4 |
| Methodology version → candidate decision | `methodology_evaluations` (facts snapshot, engine version) → `methodology_evaluation_results` (per-rule results) → `project_methodology_reviews` | 4 |
| MRV, samples, lab, calculation, verification, registry, credits | — | 5–9 |

Reverse lineage, from a farm up to its projects, works through `project_farms` (`GET /projects/my-participation` for the
farmer's own farms; project farms lists for staff). Every link above is written in the same transaction as its
audit-log entry.
